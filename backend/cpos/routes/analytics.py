"""Laporan Analytics (backend\\analytics + frontend\\analytics) di dalam CPOS.

Menu yang Url-nya /an/<id> membuka laporan Analytics <id> dalam bingkai halaman CPOS (sidebar & header CPOS).
Analytics tidak punya login sendiri: backend-nya menanyakan /api/analytics/saya ke CPOS dengan cookie sesi browser,
jadi hak lihat tiap laporan = hak Lihat menunya di Admin › Hak Akses."""
import os

from flask import Blueprint, render_template, jsonify, session, abort
from flask_login import login_required, current_user

from utils.area import company_menu_banyak, company_user
from utils.db_organisasi import daftar_company
from utils.hak_akses import boleh_lihat, halaman as lihat_halaman, remah_menu, semua_menu

analytics_bp = Blueprint("analytics", __name__)

# Alamat frontend Analytics. Satu situs IIS: /analytics (bawaan). Saat pengembangan bisa alamat lengkap, mis. http://localhost:5173/analytics
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "/analytics").rstrip("/")


def _menu_laporan():
    """{id laporan: menu} untuk semua menu aktif yang Url-nya /an/<id>."""
    return {m["url"][4:]: m for m in semua_menu() if (m["url"] or "").startswith("/an/")}


@analytics_bp.route("/an/<laporan>")
@login_required
@lihat_halaman(lambda r: (_menu_laporan().get(r.view_args["laporan"]) or {}).get("kode"))
def halaman(laporan):
    menu = _menu_laporan().get(laporan)
    if menu is None:
        abort(404)
    kode_aktif = menu["induk"] if menu["level"] == 3 else menu["kode"]
    return render_template("analytics/sematan.html", halaman="analytics", kode_aktif=kode_aktif, remah=remah_menu(menu["kode"]),
                           menu=menu, src=f"{ANALYTICS_URL}/laporan/{laporan.replace('_', '-')}?embed=1")


@analytics_bp.route("/api/analytics/saya")
@login_required
def saya():
    """Dipanggil backend Analytics (bukan browser): siapa pemilik sesi ini dan laporan apa saja yang boleh dibukanya."""
    pt = company_user(current_user.id)
    laporan = {i: m for i, m in _menu_laporan().items() if boleh_lihat(m["kode"])}
    nama = {c["id_company"]: c["nama"] for c in daftar_company()}
    # PT yang datanya boleh dilihat per laporan (Admin › Hak Akses › Cakupan data): kode & nama PT, None = semua PT
    cakupan = company_menu_banyak(current_user.id, [m["kode"] for m in laporan.values()])
    per_laporan = {}
    for i, m in laporan.items():
        boleh = cakupan[m["kode"]]
        per_laporan[i] = None if boleh is None else sorted({*boleh, *(nama[k] for k in boleh if k in nama)})
    return jsonify({"id": current_user.id, "username": current_user.username, "nama": current_user.nama_lengkap,
                    "role": current_user.nama_level, "company": sorted(pt) if pt is not None else None,
                    "laporan": sorted(laporan), "company_laporan": per_laporan,
                    "sid": session.get("_sid")})
