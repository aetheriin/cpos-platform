from flask import Blueprint, request, jsonify, current_app
from utils.hak_akses import lihat, MENU_KENDARAAN, MENU_OPERASI, MENU_ORANG
from utils.area import area_data, company_user
from utils.db_admin import supplier_boleh
from flask_login import login_required, current_user
from utils.face_utils import (embedding_frontal, extract_embedding, extract_embedding_tunggal, embedding_to_binary,
                              cek_liveness, TANPA_TANTANGAN)
from utils.plat_utils import normalisasi_plat
from utils import pengaturan, verifikasi_state as verif, db_ascend, db_ascend_split
from utils.db_kontrak import get_do
from utils.db_blacklist import supplier_diblacklist
from utils.db_organisasi import daftar_lokasi
from utils.keamanan import id_pos
from utils.upload_utils import simpan_upload, simpan_frames, hapus_file
from utils.db_utils import (
    cari_transaksi_aktif, buat_transaksi_full, get_history_driver,
    get_driver_by_id, cari_driver_by_nik, cek_nik_ada, cari_wajah_mirip_driver,
    insert_driver, update_driver_dengan_audit, get_kendaraan_by_plat, get_semua_supplier, get_semua_produk,
    cari_riwayat_driver_by_plat, get_supir_kendaraan
)
from utils.serializers import serialisasi_driver
from utils.audit_utils import catat_security_audit
from utils.personel_utils import format_nama_personel, nik_valid
from utils.face_cache import slot_proses_wajah, cari_terdekat_konsisten
from utils.hak_akses import izin
from utils.db_personel import sim_dipakai
from utils import alur
from utils.db_master import stnk_dipakai
from utils.db_aktivitas import area_akun

security_bp = Blueprint('security', __name__)

@security_bp.route("/api/security/list-tiket-aktif")
@login_required
@lihat(*MENU_OPERASI)
def list_tiket_aktif():
    area = area_data(current_user.id)

    try:
        ticket_ids = db_ascend_split.daftar_ticket_id_di_area(area)
        hasil = db_ascend.daftar_tiket_ascend_aktif(ticket_ids)
    except Exception:
        current_app.logger.exception(
            "Gagal memuat daftar tiket Ascend untuk area %s",
            area,
        )
        return jsonify({
            "error": "Daftar tiket Ascend belum dapat dimuat. Coba lagi."
        }), 503

    for tiket in hasil:
        dibuat = tiket.get("created_at")
        tiket["created_at"] = (
            dibuat.strftime("%Y-%m-%d %H:%M")
            if hasattr(dibuat, "strftime")
            else str(dibuat or "")
        )
        tiket["alur_tahap"] = []

    hasil.sort(key=lambda t: t["created_at"], reverse=True)
    return jsonify(hasil)

@security_bp.route("/api/security/history-driver")
@login_required
@lihat(*MENU_OPERASI)
def history_driver():
    return jsonify(get_history_driver())

@security_bp.route("/api/security/ascend/do")
@login_required
@izin("FORM_SECURITY", "tambah")
def ascend_daftar_do():
    ticket_type = (request.args.get("ticket_type") or "").strip()
    try:
        return jsonify(db_ascend.daftar_do(ticket_type))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@security_bp.route("/api/security/ascend/associate")
@login_required
@izin("FORM_SECURITY", "tambah")
def ascend_daftar_associate():
    ticket_type = (request.args.get("ticket_type") or "").strip()
    try:
        return jsonify(db_ascend.daftar_associate(ticket_type))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@security_bp.route("/api/security/ascend/shipper-kendaraan")
@login_required
@izin("FORM_SECURITY", "tambah")
def ascend_shipper_kendaraan():
    ticket_type = (request.args.get("ticket_type") or "").strip()
    teks_id_do = (request.args.get("id_do") or "").strip()
    teks_associate = (request.args.get("associate_id") or "").strip()

    try:
        id_do = int(teks_id_do) if teks_id_do else None
        associate_id = int(teks_associate) if teks_associate else None

        return jsonify(db_ascend.daftar_shipper_kendaraan(
            ticket_type,
            id_do=id_do,
            associate_id=associate_id,
        ))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@security_bp.route("/api/security/supir-terakhir")
@login_required
@lihat(*MENU_OPERASI)
def security_supir_terakhir():
    no_plat, error = normalisasi_plat(request.args.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400

    # Supir utama yang terdaftar untuk kendaraan didahulukan.
    kendaraan = get_kendaraan_by_plat(no_plat)
    if kendaraan:
        daftar_supir = get_supir_kendaraan(kendaraan.id_kendaraan)
        driver_utama = next(
            (d for d in daftar_supir if d.get("is_utama")),
            daftar_supir[0] if daftar_supir else None,
        )

        if driver_utama:
            return jsonify({
                "driver": {
                    "id_driver": driver_utama["id_driver"],
                    "nama": driver_utama["nama_driver"],
                    "nik": driver_utama.get("nik"),
                    "no_sim": driver_utama.get("no_sim"),
                    "foto_path": driver_utama.get("foto_path"),
                    "is_updated": bool(driver_utama.get("is_updated")),
                    "is_blacklisted": bool(driver_utama.get("is_blacklisted")),
                }
            })

    # Jika belum ada supir yang terdaftar pada kendaraan, pakai riwayat tiket timbang.
    row = cari_riwayat_driver_by_plat(no_plat)
    return jsonify({
        "driver": serialisasi_driver(row) if row else None
    })

PRODUK_MANUAL_ASCEND = {
    "Produk": {
        "Cangkang", "CPKO", "CPO", "JanjangKosong", "Kernel", "PAO",
        "PFAD", "PKE", "POME", "R.POME", "RBD Palm Stearin",
        "Spent Bleaching Earth (SBE)", "TBS",
    },
    "TBSLuar": {
        "CPO", "Kernel", "Nut", "PAO", "PFAD", "POME", "R.POME",
        "Technical Oil/HAPOR/POME OIL", "TBS", "UCO",
    },
}

def mill_manual_ascend(ticket_type, produk):
    produk_key = " ".join((produk or "").strip().lower().split())

    refinery = {
        "Produk": {
            "cpo",
            "janjangkosong",
            "pfad",
            "r.pome",
            "rbd palm stearin",
            "spent bleaching earth (sbe)",
        },
        "TBSLuar": {
            "pfad",
            "r.pome",
            "tbs",
            "uco",
        },
    }

    if produk_key == "kernel":
        return 1035

    refinery_key = {
        jenis: {nama.lower() for nama in daftar}
        for jenis, daftar in refinery.items()
    }

    if produk_key in refinery_key.get(ticket_type, set()):
        return 1034

    return 250

@security_bp.route("/api/security/ascend/buat-tiket", methods=["POST"])
@login_required
@izin("FORM_SECURITY", "tambah")
def ascend_buat_tiket():
    f = request.form

    ticket_type = (f.get("ticket_type") or "").strip()
    produk = (f.get("produk") or "").strip()
    teks_associate = (f.get("associate_id") or "").strip()
    vehicle_no = (f.get("vehicle_no") or "").strip().upper()
    tanggal_teks = (f.get("tanggal") or "").strip()
    no_do = (f.get("no_do") or "").strip().upper()
    teks_mill = (f.get("mill_id") or "").strip()

    if ticket_type not in ("Produk", "TBSLuar"):
        return jsonify({"error": "Pilih jenis tiket."}), 400
    if not all((produk, teks_associate, vehicle_no, tanggal_teks, no_do, teks_mill)):
        return jsonify({"error": "Semua field wajib diisi."}), 400
    if len(vehicle_no) > 50:
        return jsonify({"error": "Nomor kendaraan maksimal 50 karakter."}), 400
    if len(no_do) > 50:
        return jsonify({"error": "Nomor DO maksimal 50 karakter."}), 400
    if not teks_associate.isdigit() or not teks_mill.isdigit():
        return jsonify({"error": "Pilih Associate dan Mill dari daftar."}), 400

    from datetime import datetime

    try:
        tanggal = datetime.strptime(tanggal_teks, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid."}), 400

    associate_id = int(teks_associate)
    mill_id = int(teks_mill)

    # Tiket kosong dan tiket yang belum selesai di Ascend juga memblokir tiket baru.
    try:
        tiket_aktif = db_ascend.cari_tiket_ascend_berdasarkan_plat(vehicle_no)
    except Exception:
        current_app.logger.exception(
            "Gagal memeriksa tiket Ascend untuk plat %s",
            vehicle_no,
        )
        return jsonify({
            "error": "Status tiket Ascend belum dapat diperiksa. Coba lagi."
        }), 503

    if tiket_aktif:
        return jsonify({
            "error": (
                f"Truk {vehicle_no} masih memiliki tiket Ascend "
                f"{tiket_aktif['no_tiket']} yang belum selesai."
            )
        }), 409

    daftar_ascend = db_ascend.daftar_do(ticket_type)

    do_dipilih = next(
        (r for r in daftar_ascend if r["no_do"].upper() == no_do),
        None,
    )

    produk_manual_valid = produk.casefold() in {
        nama.casefold()
        for nama in PRODUK_MANUAL_ASCEND.get(ticket_type, set())
    }

    produk_valid = (
        any(r["produk"].casefold() == produk.casefold() for r in daftar_ascend)
        or produk_manual_valid
    )

    if not produk_valid:
        return jsonify({"error": "Pilih Produk yang tersedia di Ascend."}), 400

    if do_dipilih:
        if (
            int(do_dipilih["associate_id"]) != associate_id
            or do_dipilih["produk"] != produk
            or do_dipilih["mill_id"] is None
            or int(do_dipilih["mill_id"]) != mill_id
        ):
            return jsonify({
                "error": "Associate, Produk, dan Mill harus sesuai dengan DO yang dipilih."
            }), 400
    else:
        associate_valid = any(
            int(a["associate_id"]) == associate_id
            for a in db_ascend.daftar_associate(ticket_type)
        )
        mill_valid = any(
            int(m["mill_id"]) == mill_id
            for m in db_ascend.daftar_mill()
        )

        if not associate_valid:
            return jsonify({"error": "Pilih Associate dari daftar Ascend."}), 400
        if not mill_valid:
            return jsonify({"error": "Pilih Mill dari daftar Ascend."}), 400
    
    try:
        tiket = db_ascend.buat_tiket_kosong(
            ticket_type, produk, associate_id, vehicle_no,
            tanggal, no_do, mill_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        db_ascend_split.simpan_pasangan_do2(
            tiket["ticket_id"],
            tiket["ticket_no"],
            "",
            int(current_user.id),
        )
    except Exception:
        current_app.logger.exception(
            "Tiket Ascend %s berhasil dibuat, tetapi rencana DO2 gagal disimpan.",
            tiket["ticket_no"],
        )
        return jsonify({
            "error": (
                f"Tiket Ascend {tiket['ticket_no']} sudah dibuat, "
                "tetapi status pasangan DO2 gagal disimpan. "
                "Jangan buat ulang tiket ini; statusnya perlu diperiksa."
            )
        }), 503

    return jsonify({
        "message": "Tiket kosong berhasil dibuat di Ascend.",
        "no_tiket": tiket["ticket_no"],
        "ticket_id": tiket["ticket_id"],
    })

# ===== DRIVER =====
@security_bp.route("/api/driver/cari-by-nik", methods=["POST"])
@login_required
@lihat(*MENU_ORANG, *MENU_KENDARAAN)
def driver_cari_nik():
    row = cari_driver_by_nik(request.form.get("nik", "").strip())
    if not row:
        return jsonify({"status": "TIDAK_DITEMUKAN"}), 200
    return jsonify({"status": "DITEMUKAN", **serialisasi_driver(row)}), 200

def _simpan_foto(file):
    """Foto supir: divalidasi & disimpan privat. Kembalikan (path_disk, path_relatif 'uploads/personel/...')."""
    return simpan_upload(file, "personel")

def _data_verif(d, is_updated=None):
    """Baris driver -> argumen verif.simpan_hasil_*."""
    return {"id_driver": d.id_driver, "nama": d.nama_driver, "nik": d.nik, "no_sim": d.no_sim,
            "is_updated": bool(d.is_updated) if is_updated is None else is_updated, "foto_path": d.foto_path,
            "kategori": d.kategori, "is_blacklisted": bool(d.is_blacklisted)}


@security_bp.route("/api/driver/tambah", methods=["POST"])
@login_required
@izin(('FORM_SECURITY', 'POS_SECURITY'), 'tambah')
def driver_tambah():
    nik = request.form.get("nik", "").strip()
    nama = request.form.get("nama", "").strip()
    no_sim = request.form.get("no_sim", "").strip().upper()
    file = request.files.get("foto")

    if not all([nik, nama, no_sim, file]):
        return jsonify({"error": "Semua kolom wajib diisi, termasuk foto wajah"}), 400
    if not nik_valid(nik):
        return jsonify({"error": "NIK harus 16 digit angka"}), 400
    if cek_nik_ada(nik):
        return jsonify({"error": f"NIK '{nik}' sudah terdaftar"}), 400
    if sim_dipakai(no_sim):
        return jsonify({"error": f"No. SIM {no_sim} sudah dipakai personel lain"}), 400

    try:
        filepath, foto_path = _simpan_foto(file)
    except ValueError as e:
        return jsonify({"error": f"Foto: {e}"}), 400
    with slot_proses_wajah():
        embedding, jumlah_wajah = extract_embedding_tunggal(filepath)
    if embedding is None:
        hapus_file(filepath)
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah_wajah == 0
                        else f"Terdeteksi {jumlah_wajah} wajah, foto harus berisi 1 orang"}), 400
    mirip = cari_wajah_mirip_driver(embedding)
    if mirip:
        hapus_file(filepath)
        lama = get_driver_by_id(mirip[0])
        nama_lama = format_nama_personel(lama.id_driver, lama.nama_driver)
        if lama.is_blacklisted:
            catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                                 details={"keterangan": f"Tambah supir: wajah cocok dengan {nama_lama} (blacklist)",
                                          "id_personel": lama.id_driver, "sumber": "TAMBAH_SUPIR", "tindakan": "DITOLAK"})
            return jsonify({"error": f"Wajah sudah terdaftar sebagai {nama_lama} (BLACKLIST). "
                                     "Gunakan data supir tersebut lewat Ubah Supir."}), 400
        return jsonify({"error": f"Wajah sudah terdaftar sebagai {nama_lama}"}), 400

    driver_id = insert_driver(nik, nama, no_sim, embedding_to_binary(embedding), foto_path, current_user.id)
    verif.simpan_hasil_user(id_pos(), current_user.id, id_driver=driver_id, nama=nama, nik=nik, no_sim=no_sim,
                            is_updated=False, foto_path=foto_path, kategori="DRIVER",
                            is_blacklisted=False)
    return jsonify({"message": f"Supir {nama} berhasil ditambahkan",
                    "id_driver": driver_id, "foto_path": foto_path}), 200

@security_bp.route("/api/driver/update-identitas", methods=["POST"])
@login_required
@izin(('FORM_SECURITY', 'POS_SECURITY'), 'ubah')
def driver_update_identitas():
    f = request.form
    id_driver, nik, nama, no_sim = f.get("id_driver", "").strip(), f.get("nik", "").strip(), \
        f.get("nama", "").strip(), f.get("no_sim", "").strip().upper()
    file = request.files.get("foto")

    if not all([id_driver, nik, nama, no_sim]) or not id_driver.isdigit():
        return jsonify({"error": "Semua kolom wajib diisi"}), 400
    if not nik_valid(nik):
        return jsonify({"error": "NIK harus 16 digit angka"}), 400
    if cek_nik_ada(nik, exclude_id=int(id_driver)):
        return jsonify({"error": f"NIK '{nik}' sudah dipakai supir lain"}), 400
    if sim_dipakai(no_sim, int(id_driver)):
        return jsonify({"error": f"No. SIM {no_sim} sudah dipakai personel lain"}), 400

    embedding_binary, foto_path = None, None
    if file and file.filename:
        try:
            filepath, foto_path = _simpan_foto(file)
        except ValueError as e:
            return jsonify({"error": f"Foto: {e}"}), 400
        with slot_proses_wajah():
            embedding = extract_embedding(filepath)
        if embedding is None:
            hapus_file(filepath)
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400
        embedding_binary = embedding_to_binary(embedding)

    update_driver_dengan_audit(int(id_driver), nik, nama, no_sim, current_user.id, embedding_binary, foto_path)
    d = get_driver_by_id(int(id_driver))
    v = verif.ambil(id_pos(), current_user.id)
    if v and str(v["id_driver"]) == str(id_driver):
        verif.simpan_hasil_user(id_pos(), current_user.id, **_data_verif(d, is_updated=True))
    return jsonify({
        "message": f"Data {nama} berhasil diperbarui dan tercatat di Log Audit",
        "driver": serialisasi_driver(d)
    }), 200

# ===== SCAN WAJAH SUPIR (webcam browser di PC Security) =====
# Hasil hanya berlaku untuk user yang men-scan & kedaluwarsa 5 menit (utils/verifikasi_state.py).
MAKS_FRAME = 20

@security_bp.route("/api/security/scan-wajah", methods=["POST"])
@login_required
@izin(('FORM_SECURITY', 'POS_SECURITY'), 'tambah')
def scan_wajah_supir():
    area = area_akun(current_user.id)
    wajib = pengaturan.nilai("TANTANGAN_SECURITY", area)
    tantangan = request.form.get("tantangan", "") if wajib else TANPA_TANTANGAN
    try:
        filepaths = simpan_frames(request.files.getlist("frames"), maks=MAKS_FRAME)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        with slot_proses_wajah():
            if not cek_liveness(filepaths, tantangan, wajib):
                return jsonify({"error": "Uji wajah hidup gagal. Ikuti instruksi di layar, lalu ulangi scan."}), 400
            embeddings, _, _ = embedding_frontal(filepaths)       # frame paling menghadap kamera
        if not embeddings:
            return jsonify({"error": "Wajah tidak terdeteksi. Silakan ulangi scan sambil menghadap kamera"}), 400

        id_cocok, _, jarak = cari_terdekat_konsisten(embeddings, pengaturan.nilai("AMBANG_WAJAH", area))
        if id_cocok is None:
            return jsonify({"error": "Supir tidak dikenali. Silakan tambahkan sebagai data baru"}), 404

        d = get_driver_by_id(id_cocok)
        nama = format_nama_personel(d.id_driver, d.nama_driver)
        if d.kategori != 'DRIVER':
            return jsonify({"error": f"{nama} terdaftar sebagai {d.kategori}, bukan supir", "id_driver": d.id_driver}), 400
        # Blacklist = peringatan: tetap terverifikasi, tercatat di Log Audit
        data = _data_verif(d)
        verif.simpan_hasil_user(id_pos(), current_user.id, **data)
        if d.is_blacklisted:
            catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                                 details={"keterangan": f"Scan wajah: {nama} blacklist", "id_personel": d.id_driver,
                                          "sumber": "SCAN_WAJAH", "tindakan": "PERINGATAN", "jarak": jarak})
        return jsonify({"terverifikasi": True, "message": f"Verifikasi berhasil: {nama}", **data})
    finally:
        for path in filepaths:
            hapus_file(path)
