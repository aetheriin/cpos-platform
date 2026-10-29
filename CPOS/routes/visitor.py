"""Forms › Visitor & Staff Logs: satu halaman untuk semua scan wajah (tab Scan Wajah · Logs · Data Orang).

Scan wajah dicocokkan ke wajah terdaftar semua orang (Users). Hasilnya mengikuti jenis orangnya:
- karyawan (termasuk security & BHL): absensi langsung dicatat MASUK / KELUAR dengan status waktu jadwal kerja area;
- driver / tamu: form kunjungan (keperluan, orang yang dituju, plat) lalu dicatat MASUK; yang masih di dalam dicatat KELUAR;
- tidak dikenali: dicatat sebagai bukti, lalu bisa didaftarkan di tempat (hak Tambah di Data Orang).
Semua tercatat di FaceActivity, foto saat scan di FaceRecog (utils/db_aktivitas.py)."""
import os
import re
import shutil
import uuid
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from extensions import UPLOAD_FOLDER
from utils import db_aktivitas as db, kolom_wajib, pengaturan
from utils.absensi_rules import hari_iso, hitung_status_waktu, is_duplikat, tentukan_jenis
from utils.area import area_data
from utils.audit_utils import catat_security_audit
from utils.db_absensi import get_jadwal_hari, get_jadwal_kerja
from utils.db_personel import daftar_jenis_sim, daftar_kategori, get_personel
from utils.face_cache import cari_terdekat_konsisten, slot_proses_wajah
from utils.face_utils import TANPA_TANTANGAN, TANTANGAN_VALID, cek_liveness, embedding_frontal, embedding_to_binary
from utils.hak_akses import boleh, halaman as lihat_halaman, izin, tab_lihat
from utils.personel_utils import format_nama_personel
from utils.plat_utils import normalisasi_plat
from utils.upload_utils import simpan_frames

visitor_bp = Blueprint("visitor", __name__)

TAB = [("scan", "Scan Wajah", "VSL_SCAN"), ("logs", "Logs", "VSL_LOGS"), ("orang", "Data Orang", "PERSONEL")]
FOLDER_SCAN = "scan"


@visitor_bp.route("/visitor-logs")
@login_required
@lihat_halaman("KUNJUNGAN")
def halaman():
    from utils.db_organisasi import daftar_area, daftar_department
    from utils.hak_akses import daftar_jabatan
    return render_template("visitor/visitor.html", halaman="visitor", kode_aktif="KUNJUNGAN", tabs=tab_lihat(TAB),
                           boleh_scan=boleh("VSL_SCAN", "tambah"), boleh_keluar=boleh("VSL_SCAN", "ubah"),
                           boleh_ubah=boleh("PERSONEL"), boleh_tambah_orang=boleh("PERSONEL", "tambah"),
                           boleh_kode=boleh("PERSONEL", "ubah"), kategori_list=list(daftar_kategori().values()),
                           jenis_sim_list=daftar_jenis_sim(),
                           area_list=[a for a in daftar_area() if a["is_active"]],
                           department_list=[d for d in daftar_department() if d["is_active"]],
                           jabatan_list=[j for j in daftar_jabatan() if j["is_active"] and not j["is_admin"]])


def _area():
    return db.area_akun(current_user.id)


def _info(p, jarak=None):
    return {"id_personel": p["id_personel"], "kode_personel": p["kode_personel"], "nama_personel": p["nama_personel"],
            "nik": p["nik"], "kategori": p["kategori"], "is_blacklisted": p["is_blacklisted"], "foto_path": p["foto_path"],
            "asal_perusahaan": p.get("asal_perusahaan"), "keperluan": p.get("keperluan"), "peran": p.get("peran"),
            "no_sim": p.get("no_sim"), "sim_berlaku_sampai": p.get("sim_berlaku_sampai"),
            "nama_tampil": format_nama_personel(p["kode_personel"], p["id_personel"], p["nama_personel"]),
            "jarak_wajah": round(jarak, 3) if jarak is not None else None}


def _simpan_foto(path_frame, sekarang):
    folder = os.path.join(UPLOAD_FOLDER, FOLDER_SCAN)
    os.makedirs(folder, exist_ok=True)
    nama = f"{sekarang:%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
    shutil.copyfile(path_frame, os.path.join(folder, nama))
    return f"uploads/{FOLDER_SCAN}/{nama}"


def _foto_dari_form():
    """Foto scan yang dikirim balik oleh form kunjungan: hanya file di uploads/scan."""
    teks = (request.form.get("foto_scan") or "").strip()
    return teks if re.fullmatch(rf"uploads/{FOLDER_SCAN}/[\w-]+\.jpg", teks) else None


@visitor_bp.route("/api/visitor/scan", methods=["POST"])
@login_required
@izin("VSL_SCAN", "tambah")
def scan():
    area = _area()
    wajib = pengaturan.nilai("TANTANGAN_ABSENSI", area)
    tantangan = request.form.get("tantangan", "KEDIP") if wajib else TANPA_TANTANGAN
    if wajib and tantangan not in TANTANGAN_VALID:
        return jsonify({"error": "Tantangan uji wajah hidup tidak valid"}), 400
    try:
        paths = simpan_frames(request.files.getlist("frames"), maks=20)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        with slot_proses_wajah():
            if not cek_liveness(paths, tantangan, wajib):        # gagal liveness tidak dicatat (bisa diulang)
                return jsonify({"error": "Uji wajah hidup gagal. Ikuti instruksi di layar, lalu ulangi scan."}), 400
            embeddings, jumlah, tengah = embedding_frontal(paths)
        if jumlah > 1:
            return jsonify({"error": f"Terdeteksi {jumlah} wajah. Pastikan hanya 1 orang di depan kamera"}), 400
        if not embeddings:
            return jsonify({"error": "Wajah tidak terdeteksi. Ulangi scan sambil menghadap kamera"}), 400
        sekarang = datetime.now()
        foto = _simpan_foto(tengah, sekarang)
    finally:
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass

    perangkat, ip = request.form.get("perangkat", "Web")[:50], request.remote_addr
    emb = embedding_to_binary(embeddings[0])
    id_personel, _, jarak = cari_terdekat_konsisten(embeddings, pengaturan.nilai("AMBANG_WAJAH", area))
    p = get_personel(id_personel) if id_personel else None
    if not p:
        db.catat(None, None, db.TIDAK_DIKENALI, area, current_user.id, embedding=emb, foto_path=foto, jarak=jarak,
                 perangkat=perangkat, ip=ip, waktu=sekarang)
        return jsonify({"status": "TIDAK_DIKENALI", "foto_scan": foto})

    nama = format_nama_personel(p["kode_personel"], id_personel, p["nama_personel"])
    if p["is_blacklisted"]:
        db.catat(id_personel, None, db.DITOLAK, area, current_user.id, nama_wajah=p["nama_personel"], embedding=emb, foto_path=foto,
                 id_blacklist=p.get("id_blacklist"), jarak=jarak, perangkat=perangkat, ip=ip, waktu=sekarang)
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=ip,
                             details={"keterangan": f"Scan Visitor & Staff Logs {nama} ditolak (blacklist)", "id_personel": id_personel,
                                      "sumber": "VISITOR", "tindakan": "DITOLAK", "jarak": jarak})
        return jsonify({"status": "DITOLAK", **_info(p, jarak), "foto_scan": foto})

    akhir = db.terakhir(id_personel)
    di_dalam = bool(akhir and akhir["jenis"] == "MASUK")
    if p["kategori"] != "KARYAWAN":                    # driver / tamu: lanjut ke form kunjungan (masuk) atau keluar
        return jsonify({"status": "KUNJUNGAN", **_info(p, jarak), "di_dalam": di_dalam, "foto_scan": foto,
                        "masuk_sejak": akhir["waktu"].strftime("%H:%M") if di_dalam else None})

    terakhir_scan, sudah_masuk = db.sudah_masuk_hari_ini(id_personel, sekarang.date())
    if is_duplikat(terakhir_scan, sekarang):
        return jsonify({"status": "DUPLIKAT", **_info(p, jarak),
                        "error": f"{nama} sudah tercatat pukul {terakhir_scan:%H:%M}."}), 409
    jenis = tentukan_jenis(sudah_masuk)
    jadwal = get_jadwal_hari(hari_iso(sekarang), area)
    status_waktu, selisih = hitung_status_waktu(jenis, sekarang, jadwal)
    db.catat(id_personel, jenis, db.BERHASIL, area, current_user.id, nama_wajah=p["nama_personel"], embedding=emb, foto_path=foto,
             status_waktu=status_waktu, selisih=selisih, jarak=jarak, perangkat=perangkat, ip=ip, waktu=sekarang)
    return jsonify({"status": "ABSENSI", **_info(p, jarak), "jenis": jenis, "status_waktu": status_waktu, "selisih_menit": selisih,
                    "waktu": sekarang.strftime("%H:%M"), "foto_scan": foto,
                    "jadwal": None if not jadwal or jadwal["is_libur"] else
                    {"jam_masuk": _jam(jadwal["jam_masuk"]), "jam_pulang": _jam(jadwal["jam_pulang"])}})


def _jam(t):
    return t.strftime("%H:%M") if t else None


def _orang_form():
    teks = (request.form.get("id_personel") or "").strip()
    p = get_personel(int(teks)) if teks.isdigit() else None
    if not p or not p["is_active"]:
        raise ValueError("Scan wajah orangnya terlebih dahulu")
    return p


@visitor_bp.route("/api/visitor/masuk", methods=["POST"])
@login_required
@izin("VSL_SCAN", "tambah")
def masuk():
    """Kunjungan driver / tamu masuk: keperluan wajib, orang yang dituju & plat opsional (Kolom Wajib: form TAMU)."""
    f = request.form
    try:
        p = _orang_form()
        if p["kategori"] == "KARYAWAN":
            raise ValueError(f"{p['nama_personel']} karyawan: absensinya tercatat otomatis saat scan")
        akhir = db.terakhir(p["id_personel"])
        if akhir and akhir["jenis"] == "MASUK":
            raise ValueError(f"{p['nama_personel']} masih tercatat di dalam. Catat keluar terlebih dahulu.")
        kolom_wajib.cek("TAMU", f)
        keperluan = (f.get("keperluan") or "").strip()[:120]
        if not keperluan:
            raise ValueError("Isi keperluan kunjungan")
        keterangan = (f.get("keterangan") or "").strip()[:120]
        id_dituju = None
        if (f.get("id_dituju") or "").strip():
            pilihan = {d["id_personel"] for d in db.daftar_dituju()}
            id_dituju = int(f["id_dituju"]) if f["id_dituju"].isdigit() and int(f["id_dituju"]) in pilihan else None
            if id_dituju is None:
                raise ValueError("Pilih orang yang dituju dari daftar")
        no_plat = None
        if (f.get("no_plat") or "").strip():
            no_plat, error = normalisasi_plat(f.get("no_plat"))
            if error:
                raise ValueError(error)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.catat(p["id_personel"], "MASUK", db.BERHASIL, _area(), current_user.id, nama_wajah=p["nama_personel"],
             foto_path=_foto_dari_form(), keterangan=" · ".join(x for x in (keperluan, keterangan) if x),
             id_dituju=id_dituju, no_plat=no_plat, perangkat=f.get("perangkat"), ip=request.remote_addr)
    return jsonify({"message": f"{p['nama_personel']} dicatat masuk"})


@visitor_bp.route("/api/visitor/keluar", methods=["POST"])
@login_required
@izin("VSL_SCAN", "ubah")
def keluar():
    """Catat keluar orang yang masih di dalam (tombol Keluar di daftar, atau setelah scan driver / tamu)."""
    try:
        p = _orang_form()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    akhir = db.terakhir(p["id_personel"])
    if not akhir or akhir["jenis"] != "MASUK":
        return jsonify({"error": f"{p['nama_personel']} tidak tercatat di dalam"}), 400
    sekarang = datetime.now()
    status_waktu = selisih = None
    if p["kategori"] == "KARYAWAN":
        status_waktu, selisih = hitung_status_waktu("KELUAR", sekarang, get_jadwal_hari(hari_iso(sekarang), _area()))
    db.catat(p["id_personel"], "KELUAR", db.BERHASIL, _area(), current_user.id, nama_wajah=p["nama_personel"],
             foto_path=_foto_dari_form(), status_waktu=status_waktu, selisih=selisih, ip=request.remote_addr, waktu=sekarang)
    return jsonify({"message": f"{p['nama_personel']} dicatat keluar"})


def _tanggal():
    return date.fromisoformat(request.args.get("tanggal") or date.today().isoformat())


@visitor_bp.route("/api/visitor/logs")
@login_required
@izin("VSL_LOGS", "lihat")
def logs():
    try:
        tanggal = _tanggal()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    return jsonify(db.logs(tanggal, area_data(current_user.id), (request.args.get("jenis") or "").upper() or None,
                           (request.args.get("status") or "").upper() or None, (request.args.get("cari") or "").strip()[:60] or None))


@visitor_bp.route("/api/visitor/di-dalam")
@login_required
@izin(("VSL_SCAN", "VSL_LOGS"), "lihat")
def di_dalam():
    return jsonify(db.di_dalam(area_data(current_user.id)))


@visitor_bp.route("/api/visitor/ringkasan")
@login_required
@izin(("VSL_SCAN", "VSL_LOGS"), "lihat")
def ringkasan():
    return jsonify(db.ringkasan(date.today(), area_data(current_user.id)))


@visitor_bp.route("/api/visitor/dituju")
@login_required
@izin("VSL_SCAN", "lihat")
def dituju():
    return jsonify({"dituju": db.daftar_dituju(), "keperluan": db.saran_keperluan()})


@visitor_bp.route("/api/visitor/absensi")
@login_required
@izin("VSL_LOGS", "lihat")
def absensi_harian():
    try:
        tanggal = _tanggal()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    return jsonify(db.rekap_harian(tanggal, area_data(current_user.id)))


@visitor_bp.route("/api/visitor/absensi/bulanan")
@login_required
@izin("VSL_LOGS", "lihat")
def absensi_bulanan():
    try:
        tahun, bulan = map(int, (request.args.get("bulan") or date.today().strftime("%Y-%m")).split("-"))
        date(tahun, bulan, 1)
    except ValueError:
        return jsonify({"error": "Bulan tidak valid (YYYY-MM)"}), 400
    return jsonify(db.rekap_bulanan(tahun, bulan, area_data(current_user.id)))


@visitor_bp.route("/api/jadwal-kerja")
@login_required
def jadwal_kerja():
    return jsonify([{**j, "jam_masuk": _jam(j["jam_masuk"]), "jam_pulang": _jam(j["jam_pulang"])}
                    for j in get_jadwal_kerja(_area())])
