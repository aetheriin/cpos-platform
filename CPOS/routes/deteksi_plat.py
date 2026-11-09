"""Mills Operation › Deteksi Plat (uji coba). Hak lihat: menu MON_PLAT di Admin › Hak Akses; yang tampil = area dalam cakupan data aturan itu.
Backend deteksi jalan terpisah dan menulis ke dbo.RiwayatDeteksi; CPOS hanya menampilkan.
Foto dibaca dari folder FOLDER_FOTO_PLAT (.env); video kamera diteruskan dari backend deteksi (URL_DETEKTOR di .env)."""
import os
import re
from datetime import date, datetime

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from utils import db_kamera_plat as dbk, db_plat as db, detektor_video as dv
from utils.area import area_data
from utils.area_filter import area_cocok
from utils.galat_isian import GalatIsian, isi_galat
from utils.hak_akses import admin_required, izin, halaman as lihat_halaman

deteksi_plat_bp = Blueprint("deteksi_plat", __name__)

POLA_NAMA = re.compile(r"^[A-Z0-9_-]{2,30}$")

def _teks(nama, maks, wajib=True):
    v = (request.form.get(nama) or "").strip()[:maks]
    if wajib and not v:
        raise GalatIsian(f"Isi {nama.replace('_', ' ')}", nama)
    return v or None


def _angka(nama, wajib=True):
    v = (request.form.get(nama) or "").strip()
    if not v.isdigit():
        if wajib:
            raise GalatIsian(f"Pilih {nama.replace('id_', '').replace('_', ' ')}", nama)
        return None
    return int(v)


def _jalankan(fn):
    try:
        return fn()
    except ValueError as e:
        return jsonify(isi_galat(e)), 400


def _tanggal(nama):
    try:
        return datetime.strptime(request.args.get(nama, ""), "%Y-%m-%d")
    except ValueError:
        return datetime.combine(date.today(), datetime.min.time())


def _area_user():
    """Cakupan area user untuk menu ini: None = semua area, int = satu, tuple = beberapa."""
    return area_data(current_user.id, db.MENU)


def _area_pilih(id_area):
    """Area yang dipilih di halaman (kosong = semua). Di luar cakupan user = -1 (tidak ada baris yang cocok)."""
    v = (request.args.get("area") or "").strip()
    if not v.isdigit():
        return None
    pilih = int(v)
    return pilih if area_cocok(id_area, pilih) else -1


def _saringan():
    ia = _area_user()
    f = {"id_area": ia, "area_pilih": _area_pilih(ia),
         "nama_kamera": (request.args.get("kamera") or "").strip() or None,
         "plat": (request.args.get("plat") or "").strip().upper() or None}
    return f, _tanggal("dari"), _tanggal("sampai")


def _kamera_boleh(nama):
    """Kamera deteksi dalam cakupan area user (akun semua-area boleh semua nama)."""
    ia = _area_user()
    if ia is None:
        return True
    return any(k["nama"] == nama and k["is_active"] and area_cocok(ia, k["id_comp_area"]) for k in dbk.daftar())


@deteksi_plat_bp.route("/deteksi-plat")
@login_required
@lihat_halaman(db.MENU)
def halaman():
    return render_template("deteksi_plat/deteksi_plat.html", halaman="deteksi_plat", kode_aktif=db.MENU)


# ===== RIWAYAT PLAT =====
@deteksi_plat_bp.route("/api/deteksi-plat")
@login_required
@izin(db.MENU, "lihat")
def daftar():
    f, dari, sampai = _saringan()
    idt = db.id_terakhir(dari, sampai, **f)          # dibaca dulu: baris yang masuk sesudahnya terdeteksi pada pengecekan berikut
    return jsonify({"data": db.daftar(dari, sampai, **f), "kamera": db.kamera(f["id_area"], f["area_pilih"]), "id_terakhir": idt})


@deteksi_plat_bp.route("/api/deteksi-plat/terbaru")
@login_required
@izin(db.MENU, "lihat")
def terbaru():
    f, dari, sampai = _saringan()
    return jsonify({"id": db.id_terakhir(dari, sampai, **f)})


@deteksi_plat_bp.route("/api/deteksi-plat/<int:id_deteksi>/foto")
@login_required
@izin(db.MENU, "lihat")
def foto(id_deteksi):
    rel = db.path_foto(id_deteksi, request.args.get("plat") == "1", _area_user())
    folder = os.getenv("FOLDER_FOTO_PLAT", "").strip()
    if not rel or not folder:
        abort(404)
    dasar = os.path.realpath(folder)
    path = os.path.realpath(os.path.join(dasar, rel))
    try:
        di_dalam = os.path.commonpath([dasar, path]) == dasar          # cegah path keluar dari folder foto
    except ValueError:
        di_dalam = False
    if not di_dalam or not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=3600)


# ===== VIDEO KAMERA DETEKSI: diteruskan dari backend deteksi (URL_DETEKTOR di .env) =====
@deteksi_plat_bp.route("/api/deteksi-plat/kamera")
@login_required
@izin(db.MENU, "lihat")
def video_daftar():
    """Kamera deteksi dalam cakupan user: dari Admin (per area) digabung dengan status dari backend deteksi."""
    ia = _area_user()
    peringatan, jalan, ai_ms = None, {}, 0
    try:
        s = dv.status()
        jalan = {k["nama"]: k for k in s.get("kamera", [])}
        ai_ms = s.get("ai_ms", 0)
    except dv.DetektorGagal as e:
        peringatan = str(e)
    hasil, terdaftar = [], set()
    for k in dbk.daftar():
        if not k["is_active"] or not area_cocok(ia, k["id_comp_area"]):
            continue
        terdaftar.add(k["nama"])
        j = jalan.get(k["nama"])
        hasil.append({"nama": k["nama"], "id_comp_area": k["id_comp_area"], "area": k["area"], "gate": k["gate"], "facing": k["facing"],
                      "status": j["status"] if j else ("backend tidak terjangkau" if peringatan else "belum berjalan di backend (restart deteksi)"),
                      "fps": j["fps"] if j else 0})
    if ia is None:       # kamera dari .env / daftar_kamera.json (tanpa area) hanya untuk akun yang boleh semua area
        hasil += [{"nama": n, "id_comp_area": None, "area": "-", "gate": None, "facing": None, "status": j["status"], "fps": j["fps"]}
                  for n, j in jalan.items() if n not in terdaftar]
    return jsonify({"kamera": hasil, "ai_ms": ai_ms, "peringatan": peringatan})


@deteksi_plat_bp.route("/api/deteksi-plat/video/<nama>/frame")
@login_required
@izin(db.MENU, "lihat")
def video_frame(nama):
    """Satu gambar JPEG (grid)."""
    if not _kamera_boleh(nama):
        return jsonify({"error": "Kamera tidak ditemukan atau di luar cakupan Anda"}), 404
    try:
        return Response(dv.snapshot(nama), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
    except dv.DetektorGagal as e:
        return jsonify({"error": str(e)}), 502


@deteksi_plat_bp.route("/api/deteksi-plat/video/<nama>/live")
@login_required
@izin(db.MENU, "lihat")
def video_live(nama):
    """Video MJPEG layar penuh. Jumlah yang terbuka bersamaan dibatasi (DETEKTOR_MAKS_LIVE, bawaan 3)."""
    if not _kamera_boleh(nama):
        return jsonify({"error": "Kamera tidak ditemukan atau di luar cakupan Anda"}), 404
    try:
        dv.ambil_slot()
    except dv.DetektorGagal as e:
        return jsonify({"error": str(e)}), 503
    try:
        jenis, isi = dv.mjpeg(nama)
    except dv.DetektorGagal as e:
        dv.lepas_slot()
        return jsonify({"error": str(e)}), 502

    def alir():
        try:
            yield from isi
        finally:
            dv.lepas_slot()
    return Response(alir(), mimetype=jenis.split(";")[0], content_type=jenis, headers={"Cache-Control": "no-store"},
                    direct_passthrough=True)


# ===== ADMIN › PERANGKAT › Kamera Deteksi Plat =====
@deteksi_plat_bp.route("/api/admin/deteksi-plat/kamera", methods=["GET", "POST"])
@login_required
@admin_required
def admin_kamera():
    if request.method == "GET":
        return jsonify({
            "kamera": dbk.daftar(),
            "facing": dbk.FACING,
            "view_position": dbk.VIEW_POSITION,
        })

    def aksi():
        f = request.form
        d = {"nama": _teks("nama", 30).upper(), "id_comp_area": _angka("id_comp_area"),
             "gate": (_teks("gate", 30, False) or "").upper() or None,
             "facing": f.get("facing") or "MASUK",
             "view_position": (f.get("view_position") or "").strip().upper() or None,
             "rtsp": _teks("rtsp", 500, False), "catatan": _teks("catatan", 100, False),
             "urutan": _angka("urutan", False) or 0, "is_active": f.get("is_active", "1") == "1"}
        if not POLA_NAMA.match(d["nama"]):
            raise GalatIsian("Nama kamera: huruf besar, angka, - atau _ (mis. GERBANG1-DEPAN)", "nama")
        if d["facing"] not in dbk.FACING:
            raise ValueError("Pilih arah hadap dari daftar")
        if d["view_position"] and d["view_position"] not in dbk.VIEW_POSITION:
            raise ValueError("Pilih posisi kamera dari daftar.")
        if d["rtsp"] and not re.match(r"^rtsp://\S+$", d["rtsp"]):
            raise GalatIsian("Alamat RTSP contoh: rtsp://user:password@192.168.10.31:554/Streaming/Channels/101", "rtsp")
        dbk.simpan(_angka("id_kamera", False), d)
        return jsonify({"message": f"Kamera {d['nama']} disimpan. Restart deteksi agar kamera baru aktif"})
    return _jalankan(aksi)