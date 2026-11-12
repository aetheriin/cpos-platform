import os
import shutil
import uuid

from datetime import date, datetime
from flask import Blueprint, abort, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from extensions import FOLDER_FOTO_PLAT, UPLOAD_FOLDER
from utils import db_aktivitas as db, pengaturan
from utils.area import area_data
from utils.audit_utils import catat_security_audit
from utils.db_personel import daftar_jenis_sim, daftar_kategori, get_personel
from utils.face_cache import cari_terdekat_konsisten, slot_proses_wajah
from utils.face_utils import TANPA_TANTANGAN, TANTANGAN_VALID, cek_liveness, embedding_frontal, embedding_to_binary
from utils.hak_akses import boleh, halaman as lihat_halaman, izin
from utils.personel_utils import format_nama_personel
from utils.plat_utils import normalisasi_plat
from utils.upload_utils import simpan_frames

visitor_bp = Blueprint("visitor", __name__)
FOLDER_SCAN = "scan"

@visitor_bp.route("/visitor-logs")
@login_required
@lihat_halaman("KUNJUNGAN")
def halaman():
    from utils.db_organisasi import daftar_area, daftar_department
    from utils.hak_akses import daftar_jabatan
    return render_template("visitor/visitor.html", halaman="visitor", kode_aktif="KUNJUNGAN",
                           boleh_scan=boleh("KUNJUNGAN", "tambah"), boleh_keluar=boleh("KUNJUNGAN", "ubah"),
                           boleh_ubah=boleh("PERSONEL"), boleh_tambah_orang=boleh("PERSONEL", "tambah"),
                           kategori_list=list(daftar_kategori().values()),
                           jenis_sim_list=daftar_jenis_sim(),
                           area_list=[a for a in daftar_area() if a["is_active"]],
                           department_list=[d for d in daftar_department() if d["is_active"]],
                           jabatan_list=[j for j in daftar_jabatan() if j["is_active"] and not j["is_admin"]])

@visitor_bp.route("/absensi-karyawan")
@login_required
@lihat_halaman("ABSENSI_KARYAWAN")
def halaman_absensi():
    return render_template("visitor/absensi.html", halaman="absensi", kode_aktif="ABSENSI_KARYAWAN")

@visitor_bp.route("/data-orang")
@login_required
@lihat_halaman("PERSONEL")
def halaman_data_orang():
    from utils.db_organisasi import daftar_area, daftar_department
    from utils.hak_akses import daftar_jabatan
    return render_template("visitor/data_orang.html", halaman="data_orang", kode_aktif="PERSONEL", tab_personel="orang",
                           boleh_ubah=boleh("PERSONEL"), boleh_tambah_orang=boleh("PERSONEL", "tambah"),
                           kategori_list=list(daftar_kategori().values()),
                           jenis_sim_list=daftar_jenis_sim(),
                           area_list=[a for a in daftar_area() if a["is_active"]],
                           department_list=[d for d in daftar_department() if d["is_active"]],
                           jabatan_list=[j for j in daftar_jabatan() if j["is_active"] and not j["is_admin"]])

def _area():
    return db.area_akun(current_user.id)

def _info(p, jarak=None):
    return {"id_personel": p["id_personel"], "nama_personel": p["nama_personel"],
            "nik": p["nik"], "kategori": p["kategori"], "is_blacklisted": p["is_blacklisted"], "foto_path": p["foto_path"],
            "asal_perusahaan": p.get("asal_perusahaan"), "keperluan": p.get("keperluan"), "peran": p.get("peran"),
            "no_sim": p.get("no_sim"), "sim_berlaku_sampai": p.get("sim_berlaku_sampai"),
            "nama_tampil": format_nama_personel(p["id_personel"], p["nama_personel"]),
            "jarak_wajah": round(jarak, 3) if jarak is not None else None}

def _simpan_foto(path_frame, sekarang):
    folder = os.path.join(UPLOAD_FOLDER, FOLDER_SCAN)
    os.makedirs(folder, exist_ok=True)
    nama = f"{sekarang:%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
    shutil.copyfile(path_frame, os.path.join(folder, nama))
    return f"uploads/{FOLDER_SCAN}/{nama}"

@visitor_bp.route("/api/visitor/scan", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "tambah")
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

    nama = format_nama_personel(id_personel, p["nama_personel"])
    if p["is_blacklisted"]:
        db.catat(id_personel, None, db.DITOLAK, area, current_user.id, nama_wajah=p["nama_personel"], embedding=emb, foto_path=foto,
                 id_blacklist=p.get("id_blacklist"), jarak=jarak, perangkat=perangkat, ip=ip, waktu=sekarang)
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=ip,
                             details={"keterangan": f"Scan Visitor & Staff Logs {nama} ditolak (blacklist)", "id_personel": id_personel,
                                      "sumber": "VISITOR", "tindakan": "DITOLAK", "jarak": jarak})
        return jsonify({"status": "DITOLAK", **_info(p, jarak), "foto_scan": foto})

    visit_group = (
        "EMPLOYEE"
        if p["kategori"] == "KARYAWAN"
        else "VISITOR"
    )

    kunjungan = db.kunjungan_aktif(id_personel)
    face_id = None

    if not kunjungan:
        face_id = db.simpan_bukti_wajah(
            p["nama_personel"],
            emb,
            foto,
        )
    return jsonify({
        "status": "KUNJUNGAN",
        **_info(p, jarak),
        "visit_group": visit_group,
        "di_dalam": bool(kunjungan),
        "face_id": face_id,
        "masuk_sejak": (
            kunjungan["waktu"].strftime("%H:%M")
            if kunjungan and kunjungan.get("waktu")
            else None
        ),
        "activity_id": (
            kunjungan["id_aktivitas"]
            if kunjungan
            else None
        ),
        "foto_scan": foto,
    })

def _orang_form():
    teks = (request.form.get("id_personel") or "").strip()
    p = get_personel(int(teks)) if teks.isdigit() else None
    if not p or not p["is_active"]:
        raise ValueError("Scan wajah orangnya terlebih dahulu")
    return p

@visitor_bp.route(
    "/api/visitor/kunjungan/<int:activity_id>/lengkapi",
    methods=["POST"],
)
@login_required
@izin("KUNJUNGAN", "tambah")
def lengkapi_kunjungan(activity_id):
    f = request.form

    try:
        p = _orang_form()

        if p["is_blacklisted"]:
            raise ValueError("Orang ini masuk daftar blacklist.")

        teks_face_id = (f.get("face_id") or "").strip()
        if not teks_face_id.isdigit():
            raise ValueError("Scan wajah terlebih dahulu.")

        face_id = int(teks_face_id)
        if not db.bukti_wajah_milik(face_id, p["nama_personel"]):
            raise ValueError("Bukti scan wajah tidak cocok dengan data orang.")

        keperluan = (f.get("keperluan") or "").strip()[:120]
        if not keperluan:
            raise ValueError("Isi tujuan kunjungan.")

        teks_host = (f.get("id_dituju") or "").strip()
        if not teks_host.isdigit():
            raise ValueError("Pilih host atau orang yang dituju.")

        id_host = int(teks_host)
        host_valid = {
            int(x["id_personel"])
            for x in db.daftar_dituju()
        }
        if id_host not in host_valid:
            raise ValueError("Host yang dipilih tidak tersedia.")

        no_plat = None
        teks_plat = (f.get("no_plat") or "").strip()
        if teks_plat:
            no_plat, error = normalisasi_plat(teks_plat)
            if error:
                raise ValueError(error)

        jumlah = (f.get("jumlah_penumpang") or "0").strip()
        if not jumlah.isdigit() or int(jumlah) > 50:
            raise ValueError("Jumlah penumpang harus berupa angka 0 sampai 50.")

        data_kunjungan = {
            "asal_perusahaan": (f.get("asal_perusahaan") or "").strip()[:150],
            "jenis_kendaraan": (f.get("jenis_kendaraan") or "").strip()[:50],
            "jumlah_penumpang": int(jumlah),
            "penumpang": [
                nama.strip()[:100]
                for nama in f.getlist("penumpang")
                if nama.strip()
            ][:50],
        }

        visit_group = (
            "EMPLOYEE"
            if p["kategori"] == "KARYAWAN"
            else "VISITOR"
        )

        db.lengkapi_kunjungan(
            activity_id,
            p["id_personel"],
            face_id,
            visit_group,
            data_kunjungan,
            id_dituju=id_host,
            tujuan=keperluan,
            no_plat=no_plat,
            id_area=_area(),
            user_id=current_user.id,
            perangkat=f.get("perangkat", "Web"),
            ip=request.remote_addr,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Data kunjungan berhasil disimpan.",
        "activity_id": activity_id,
        "visit_group": visit_group,
    })

@visitor_bp.route("/api/visitor/kunjungan/manual", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "tambah")
def kunjungan_manual():
    """Buat catatan kunjungan menunggu tanpa kamera (plat tidak terbaca). Plat boleh kosong."""
    id_area = _area()
    if not id_area:
        return jsonify({"error": "Akun belum memiliki area."}), 400
    no_plat = None
    teks_plat = (request.form.get("no_plat") or "").strip()
    if teks_plat:
        no_plat, error = normalisasi_plat(teks_plat)
        if error:
            return jsonify({"error": error}), 400
    try:
        activity_id = db.buat_kunjungan_menunggu(no_plat, id_area, perangkat="Web", ip=request.remote_addr)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"activity_id": activity_id})

@visitor_bp.route("/api/visitor/kunjungan/<int:activity_id>")
@login_required
@izin("KUNJUNGAN", "lihat")
def detail_kunjungan(activity_id):
    r = db.detail_kunjungan(activity_id, area_data(current_user.id))
    if not r:
        return jsonify({"error": "Kunjungan tidak ditemukan"}), 404
    return jsonify(r)

@visitor_bp.route("/api/visitor/kunjungan/<int:activity_id>/keluar", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "ubah")
def kunjungan_keluar(activity_id):
    try:
        db.tutup_kunjungan(activity_id, id_area=_area())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Kunjungan dicatat keluar."})

@visitor_bp.route("/api/visitor/sinkron", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "lihat")
def sinkron_kunjungan():
    """Tarik kejadian gerbang terbaru dari kamera deteksi plat: MASUK jadi catatan menunggu, KELUAR menutup kunjungan."""
    id_area = _area()
    if not id_area:
        return jsonify({"masuk": 0, "keluar": 0})
    try:
        masuk, keluar = db.sinkron_kejadian_plat(id_area)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"masuk": masuk, "keluar": keluar})

@visitor_bp.route("/api/visitor/<int:activity_id>/foto/<arah>/<sisi>")
@login_required
@izin("KUNJUNGAN", "lihat")
def foto_kendaraan(activity_id, arah, sisi):
    arah, sisi = arah.upper(), sisi.upper()
    if arah not in ("MASUK", "KELUAR") or sisi not in ("DEPAN", "BELAKANG"):
        abort(404)
    rel = db.path_foto_kunjungan(activity_id, arah, sisi, area_data(current_user.id))
    folder = FOLDER_FOTO_PLAT
    if not rel or not folder:
        abort(404)
    dasar = os.path.realpath(folder)
    path = os.path.realpath(os.path.join(dasar, rel))
    try:
        aman = os.path.commonpath([dasar, path]) == dasar        # cegah path keluar dari folder foto
    except ValueError:
        aman = False
    if not aman or not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=3600)

def _tanggal():
    return date.fromisoformat(request.args.get("tanggal") or date.today().isoformat())

@login_required
@izin("KUNJUNGAN", "lihat")
def logs():
    try:
        tanggal = _tanggal()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    return jsonify(db.logs(tanggal, area_data(current_user.id), (request.args.get("jenis") or "").upper() or None,
                           (request.args.get("status") or "").upper() or None, (request.args.get("cari") or "").strip()[:60] or None))

@visitor_bp.route("/api/visitor/kunjungan")
@login_required
@izin("KUNJUNGAN", "lihat")
def daftar_kunjungan():
    kelompok = (request.args.get("kelompok") or "").upper()
    if kelompok not in ("VISITOR", "EMPLOYEE"):
        return jsonify({"error": "Kelompok tidak valid"}), 400
    try:
        tanggal = _tanggal()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    return jsonify(db.daftar_kunjungan(tanggal, area_data(current_user.id), kelompok,
                                       (request.args.get("cari") or "").strip()[:60] or None))

@visitor_bp.route("/api/visitor/dituju")
@login_required
@izin("KUNJUNGAN", "lihat")
def dituju():
    return jsonify({"dituju": db.daftar_dituju(), "keperluan": db.saran_keperluan()})

@visitor_bp.route("/api/visitor/absensi")
@login_required
@izin(("ABSENSI_KARYAWAN", "KUNJUNGAN"), "lihat")
def absensi_harian():
    try:
        tanggal = _tanggal()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    return jsonify(db.rekap_harian(tanggal, area_data(current_user.id)))

@visitor_bp.route("/api/visitor/absensi/bulanan")
@login_required
@izin(("ABSENSI_KARYAWAN", "KUNJUNGAN"), "lihat")
def absensi_bulanan():
    try:
        tahun, bulan = map(int, (request.args.get("bulan") or date.today().strftime("%Y-%m")).split("-"))
        date(tahun, bulan, 1)
    except ValueError:
        return jsonify({"error": "Bulan tidak valid (YYYY-MM)"}), 400
    return jsonify(db.rekap_bulanan(tahun, bulan, area_data(current_user.id)))
