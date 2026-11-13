"""Pencarian global di header (Ctrl+K). Admin hanya area Admin -> endpoint terpisah /api/admin/cari."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from utils import db_cari
from utils.area import area_data, company_user
from utils.hak_akses import MENU_KENDARAAN, MENU_KONTRAK, MENU_OPERASI, MENU_ORANG, admin_required, boleh_lihat

cari_bp = Blueprint("cari", __name__)
MIN_HURUF = 2


def _kata():
    return (request.args.get("q") or "").strip()[:50]


BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def _waktu(r):
    w = r.get("created_at")
    return {**r, "created_at": f"{w.day} {BULAN[w.month - 1]} {w.year}, {w:%H:%M}" if w else None}


def _angka(v):
    return float(v) if v is not None else None


def _boleh(menu):
    return any(boleh_lihat(k) for k in menu)


def samarkan_nik(nik):
    """NIK hanya tampil 4 angka depan dan 4 angka belakang, mis. 3201********0012."""
    nik = (nik or "").strip()
    return nik if len(nik) <= 8 else nik[:4] + "*" * (len(nik) - 8) + nik[-4:]


@cari_bp.route("/api/cari")
@login_required
def cari():
    """Tiap kelompok hasil hanya untuk pengguna yang boleh melihat menunya (Admin › Hak Akses); tiket dan DO dibatasi
    site / PT pengguna. NIK disamarkan dan hanya dicari bila yang diketik minimal 6 angka."""
    kata = _kata()
    hasil = {"tiket": [], "do": [], "personel": [], "kendaraan": []}
    if len(kata) < MIN_HURUF:
        return jsonify(hasil)
    if _boleh(MENU_OPERASI):
        hasil["tiket"] = [_waktu({**r, "netto": float(r["netto"]) if r["netto"] is not None else None})
                          for r in db_cari.cari_tiket(kata, area_data(current_user.id))]
    if _boleh(MENU_KONTRAK):
        hasil["do"] = [{**r, "qty_kg": _angka(r["qty_kg"]), "realisasi_kg": _angka(r["realisasi_kg"]),
                        "berlaku_sampai": str(r["berlaku_sampai"])[:10] if r["berlaku_sampai"] else None}
                       for r in db_cari.cari_do(kata, company_user(current_user.id))]
    if _boleh(MENU_ORANG):
        hasil["personel"] = [{**r, "nik": samarkan_nik(r["nik"])} for r in db_cari.cari_personel(kata)]
    if _boleh(MENU_KENDARAAN):
        hasil["kendaraan"] = db_cari.cari_kendaraan(kata)
    return jsonify(hasil)


@cari_bp.route("/api/admin/cari")
@login_required
@admin_required
def cari_admin():
    kata = _kata()
    return jsonify({"akun": db_cari.cari_akun(kata) if len(kata) >= MIN_HURUF else []})
