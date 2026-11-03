import os
import re
from datetime import date, datetime

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file
from flask_login import login_required

from routes.cctv import _angka, _jalankan, _teks
from utils import db_kamera_plat as dbk, db_plat as db, detektor_video as dv
from utils.galat_isian import GalatIsian
from utils.hak_akses import admin_required, izin, halaman as lihat_halaman

deteksi_plat_bp = Blueprint("deteksi_plat", __name__)
POLA_NAMA = re.compile(r"^[A-Z0-9_-]{2,30}$")


def _tanggal(nama):
    try:
        return datetime.strptime(request.args.get(nama, ""), "%Y-%m-%d")
    except ValueError:
        return datetime.combine(date.today(), datetime.min.time())


@deteksi_plat_bp.route("/deteksi-plat")
@login_required
@lihat_halaman(db.MENU)
def halaman():
    return render_template("deteksi_plat/deteksi_plat.html", halaman="deteksi_plat", kode_aktif=db.MENU)


@deteksi_plat_bp.route("/api/deteksi-plat")
@login_required
@izin(db.MENU, "lihat")
def daftar():
    return jsonify({"kamera": db.kamera(),
                    "data": db.daftar(_tanggal("dari"), _tanggal("sampai"), (request.args.get("kamera") or "").strip() or None,
                                      (request.args.get("plat") or "").strip().upper() or None)})


@deteksi_plat_bp.route("/api/deteksi-plat/<int:id_deteksi>/foto")
@login_required
@izin(db.MENU, "lihat")
def foto(id_deteksi):
    rel = db.path_foto(id_deteksi, request.args.get("plat") == "1")
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

# ===== ADMIN › PERANGKAT › Kamera Deteksi Plat =====
@deteksi_plat_bp.route("/api/admin/deteksi-plat/kamera", methods=["GET", "POST"])
@login_required
@admin_required
def admin_kamera():
    if request.method == "GET":
        return jsonify({"kamera": dbk.daftar(), "facing": dbk.FACING})

    def aksi():
        f = request.form
        d = {"nama": _teks("nama", 30).upper(), "id_comp_area": _angka("id_comp_area"),
             "gate": (_teks("gate", 30, False) or "").upper() or None, "facing": f.get("facing") or "MASUK",
             "rtsp": _teks("rtsp", 500, False), "catatan": _teks("catatan", 100, False),
             "urutan": _angka("urutan", False) or 0, "is_active": f.get("is_active", "1") == "1"}
        if not POLA_NAMA.match(d["nama"]):
            raise GalatIsian("Nama kamera: huruf besar, angka, - atau _ (mis. GERBANG1-DEPAN)", "nama")
        if d["facing"] not in dbk.FACING:
            raise ValueError("Pilih arah hadap dari daftar")
        if d["rtsp"] and not re.match(r"^rtsp://\S+$", d["rtsp"]):
            raise GalatIsian("Alamat RTSP contoh: rtsp://user:password@192.168.10.31:554/Streaming/Channels/101", "rtsp")
        dbk.simpan(_angka("id_kamera", False), d)
        return jsonify({"message": f"Kamera {d['nama']} disimpan. Restart deteksi agar kamera baru aktif"})
    return _jalankan(aksi)

# ===== VIDEO KAMERA DETEKSI: diteruskan dari backend deteksi (URL_DETEKTOR di .env) =====
@deteksi_plat_bp.route("/api/deteksi-plat/kamera")
@login_required
@izin(db.MENU, "lihat")
def video_daftar():
    try:
        s = dv.status()
    except dv.DetektorGagal as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"kamera": s.get("kamera", []), "ai_ms": s.get("ai_ms", 0)})


@deteksi_plat_bp.route("/api/deteksi-plat/video/<nama>/frame")
@login_required
@izin(db.MENU, "lihat")
def video_frame(nama):
    """Satu gambar JPEG (grid)."""
    try:
        return Response(dv.snapshot(nama), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
    except dv.DetektorGagal as e:
        return jsonify({"error": str(e)}), 502


@deteksi_plat_bp.route("/api/deteksi-plat/video/<nama>/live")
@login_required
@izin(db.MENU, "lihat")
def video_live(nama):
    """Video MJPEG layar penuh. Jumlah yang terbuka bersamaan dibatasi (DETEKTOR_MAKS_LIVE, bawaan 3)."""
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