"""Mills Operation › Monitoring CCTV (tahap 1: live per area) + Admin › Perangkat › Gateway Video & Kamera.

Siapa boleh melihat: hak Lihat menu MON_CCTV di Admin › Hak Akses; kamera yang terlihat = kamera di area dalam
cakupan data aturan itu (area sendiri / PT sendiri / semua PT / PT tertentu). Gambar & video diambil server CPOS
dari gateway video (utils/cctv_gateway.py), jadi browser tidak pernah menghubungi kamera langsung."""
import re
import time

from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import current_user, login_required

from utils import cctv_gateway as gw, db_cctv as db, log_aktivitas
from utils.area import area_data
from utils.galat_isian import GalatIsian, isi_galat
from utils.area_filter import area_cocok
from utils.hak_akses import admin_required, halaman as lihat_halaman, izin

cctv_bp = Blueprint("cctv", __name__)
MENU = "MON_CCTV"
POLA_KODE = re.compile(r"^[A-Z0-9_-]{2,20}$")
POLA_STREAM = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_terlihat = {}              # id kamera -> waktu terakhir LastSeen ditulis (supaya tidak menulis database tiap frame)


@cctv_bp.route("/cctv")
@login_required
@lihat_halaman(MENU)
def halaman():
    return render_template("cctv/cctv.html", halaman="cctv", kode_aktif=MENU, titik=db.TITIK)


def _kamera_boleh(id_kamera):
    k = db.get_kamera(id_kamera)
    if not k or not k["is_active"] or not k["gateway_aktif"] or not area_cocok(area_data(current_user.id, MENU), k["id_comp_area"]):
        return None
    return k


def _catat_terlihat(k):
    if time.monotonic() - _terlihat.get(k["id_kamera"], 0) > 60:
        _terlihat[k["id_kamera"]] = time.monotonic()
        db.tandai_terlihat(k["id_kamera"], k["id_gateway"])


@cctv_bp.route("/api/cctv/kamera")
@login_required
@izin(MENU, "lihat")
def kamera():
    return jsonify([{**{x: k[x] for x in ("id_kamera", "kode", "nama", "area", "id_comp_area", "titik", "jembatan", "peran", "merk", "ai")},
                     "nama_titik": db.TITIK.get(k["titik"], k["titik"]),
                     "online": bool(k["terakhir"] and (time.time() - k["terakhir"].timestamp()) < 180)}
                    for k in db.kamera_area(area_data(current_user.id, MENU))])


@cctv_bp.route("/api/cctv/<int:id_kamera>/frame")
@login_required
@izin(MENU, "lihat")
def frame(id_kamera):
    """Satu gambar JPEG (grid); ringan = sub-stream."""
    k = _kamera_boleh(id_kamera)
    if not k:
        return jsonify({"error": "Kamera tidak ditemukan atau di luar cakupan Anda"}), 404
    try:
        gambar = gw.frame(k["url_gateway"], k["stream_ringan"] or k["stream_utama"])
    except gw.GatewayGagal as e:
        return jsonify({"error": str(e)}), 502
    _catat_terlihat(k)
    return Response(gambar, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@cctv_bp.route("/api/cctv/<int:id_kamera>/live")
@login_required
@izin(MENU, "lihat")
def live(id_kamera):
    """Video MJPEG kualitas penuh (layar penuh). Siapa membuka kamera tercatat di log."""
    k = _kamera_boleh(id_kamera)
    if not k:
        return jsonify({"error": "Kamera tidak ditemukan atau di luar cakupan Anda"}), 404
    try:
        gw.ambil_slot_live()
    except gw.GatewayGagal as e:
        return jsonify({"error": str(e)}), 503
    try:
        jenis, isi = gw.mjpeg(k["url_gateway"], k["stream_utama"])
    except gw.GatewayGagal as e:
        gw.lepas_slot_live()
        return jsonify({"error": str(e)}), 502
    log_aktivitas.catat("CCTV", "LIHAT_LIVE", tabel="Camera", id_baris=k["id_kamera"], baru={"kamera": k["kode"]},
                        user_id=current_user.id, ip=request.remote_addr)

    def alir():
        try:
            yield from isi
        finally:
            gw.lepas_slot_live()
    return Response(alir(), mimetype=jenis.split(";")[0], content_type=jenis, headers={"Cache-Control": "no-store"},
                    direct_passthrough=True)


# ===== ADMIN › PERANGKAT: gateway video & kamera =====
@cctv_bp.route("/api/admin/cctv")
@login_required
@admin_required
def admin_daftar():
    def rapi(r):
        return {**r, "terakhir": r["terakhir"].strftime("%Y-%m-%d %H:%M") if r.get("terakhir") else None}
    from utils.db_jembatan import daftar_jembatan
    return jsonify({"gateway": [rapi(g) for g in db.daftar_gateway()], "kamera": [rapi(k) for k in db.kamera()],
                    "jembatan": [{"id": j["id_jembatan"], "nama": j["nama"], "id_comp_area": j["id_comp_area"]} for j in daftar_jembatan()],
                    "titik": db.TITIK, "peran": db.PERAN, "ai": db.AI})


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
    except (ValueError, gw.GatewayGagal) as e:
        return jsonify(isi_galat(e)), 400


@cctv_bp.route("/api/admin/cctv/gateway", methods=["POST"])
@login_required
@admin_required
def admin_gateway():
    def aksi():
        url = _teks("url", 255)
        if not re.match(r"^https?://[\w.\-]+(:\d+)?/?$", url):
            raise GalatIsian("Alamat gateway contoh: http://192.168.10.5:1984", "url")
        db.simpan_gateway(_angka("id_gateway", False), _teks("nama", 100), url.rstrip("/"), _angka("id_comp_area"),
                          request.form.get("is_active", "1") == "1")
        return jsonify({"message": "Gateway video disimpan"})
    return _jalankan(aksi)


@cctv_bp.route("/api/admin/cctv/gateway/tes", methods=["POST"])
@login_required
@admin_required
def admin_gateway_tes():
    def aksi():
        stream = gw.cek(_teks("url", 255))
        return jsonify({"message": f"Gateway terhubung · {len(stream)} stream" + (f": {', '.join(stream[:8])}" if stream else ""),
                        "stream": stream})
    return _jalankan(aksi)


@cctv_bp.route("/api/admin/cctv/kamera", methods=["POST"])
@login_required
@admin_required
def admin_kamera():
    def aksi():
        f = request.form
        d = {"kode": _teks("kode", 20).upper(), "nama": _teks("nama", 100), "id_comp_area": _angka("id_comp_area"),
             "id_gateway": _angka("id_gateway"), "titik": f.get("titik"), "id_jembatan": _angka("id_jembatan", False),
             "peran": f.get("peran") or "UMUM", "merk": _teks("merk", 100, False), "stream_utama": _teks("stream_utama", 100),
             "stream_ringan": _teks("stream_ringan", 100, False), "ai": f.get("ai") or "NONE",
             "urutan": _angka("urutan", False) or 0, "is_active": f.get("is_active", "1") == "1"}
        if not POLA_KODE.match(d["kode"]):
            raise GalatIsian("Kode kamera: huruf besar, angka, - atau _ (mis. CAM-01)", "kode")
        if d["titik"] not in db.TITIK or d["peran"] not in db.PERAN or d["ai"] not in db.AI:
            raise ValueError("Pilih titik, peran, dan AI dari daftar")
        if not all(POLA_STREAM.match(s) for s in (d["stream_utama"], d["stream_ringan"] or "x")):
            raise ValueError("Nama stream: huruf, angka, titik, - atau _ (sama dengan nama di konfigurasi gateway)")
        g = next((x for x in db.daftar_gateway() if x["id_gateway"] == d["id_gateway"]), None)
        if not g or g["id_comp_area"] != d["id_comp_area"]:
            raise GalatIsian("Gateway harus berada di area yang sama dengan kamera", "id_gateway")
        db.simpan_kamera(_angka("id_kamera", False), d)
        return jsonify({"message": f"Kamera {d['kode']} disimpan"})
    return _jalankan(aksi)


@cctv_bp.route("/api/admin/cctv/kamera/<int:id_kamera>/tes")
@login_required
@admin_required
def admin_kamera_tes(id_kamera):
    """Tes koneksi: gambar dari stream utama (admin tidak terikat hak menu)."""
    k = db.get_kamera(id_kamera)
    if not k:
        return jsonify({"error": "Kamera tidak ditemukan"}), 404
    try:
        gambar = gw.frame(k["url_gateway"], k["stream_ringan"] or k["stream_utama"])
    except gw.GatewayGagal as e:
        return jsonify({"error": str(e)}), 502
    db.tandai_terlihat(k["id_kamera"], k["id_gateway"])
    return Response(gambar, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
