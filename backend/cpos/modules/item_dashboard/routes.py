"""Halaman & API Item Category Dashboard. Hak: menu AN_ITEM_CATEGORY (Lihat) di Admin › Hak Akses."""
import logging
import math
from datetime import date, datetime
from decimal import Decimal

import pyodbc
from flask import jsonify, render_template
from flask_login import login_required

from modules.item_dashboard import item_dashboard_bp
from modules.item_request.mesin import get_connection
from utils.hak_akses import halaman as lihat_halaman, izin, remah_menu

log = logging.getLogger(__name__)
KODE = "AN_ITEM_CATEGORY"
JUDUL_HASIL = (
    "Item dengan stok tertinggi",
    "Item paling sering diorder",
    "Item paling sering digunakan",
    "Kategori paling sering diorder",
    "Kategori dengan cost tertinggi",
    "Item dengan cost tertinggi",
)


def _nilai_json(nilai):
    if isinstance(nilai, (datetime, date)):
        return nilai.isoformat()
    if isinstance(nilai, Decimal):
        hasil = float(nilai)
        return hasil if math.isfinite(hasil) else None
    if isinstance(nilai, float) and not math.isfinite(nilai):
        return None
    if isinstance(nilai, bytes):
        return nilai.hex()
    if nilai is None or isinstance(nilai, (str, int, float, bool)):
        return nilai
    return str(nilai)


def _muat_data():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("EXEC dbo.top_item_category_analysis")
        hasil = []
        while True:
            if cursor.description is not None:
                kolom = [str(deskripsi[0]) for deskripsi in cursor.description]
                baris = [
                    {nama: _nilai_json(nilai) for nama, nilai in zip(kolom, row)}
                    for row in cursor.fetchall()
                ]
                urutan = len(hasil)
                hasil.append({
                    "judul": JUDUL_HASIL[urutan] if urutan < len(JUDUL_HASIL) else f"Result set {urutan + 1}",
                    "kolom": kolom,
                    "baris": baris,
                })
            if not cursor.nextset():
                break

        if not hasil:
            raise RuntimeError("Stored procedure tidak menghasilkan result set.")
        return {"hasil": hasil, "kolom": hasil[0]["kolom"], "baris": hasil[0]["baris"]}
    finally:
        conn.close()


@item_dashboard_bp.route("")
@login_required
@lihat_halaman(KODE)
def halaman_item():
    return render_template(
        "item_dashboard/index.html",
        halaman="analytics",
        kode_aktif="AN_DASHBOARD",
        remah=remah_menu(KODE),
    )


@item_dashboard_bp.route("/api")
@login_required
@izin(KODE, "lihat")
def api_item():
    try:
        return jsonify(_muat_data())
    except (pyodbc.Error, RuntimeError):
        log.exception("Gagal memuat dbo.top_item_category_analysis dari database Main")
        return jsonify({"error": "Data analisis item gagal dimuat dari database Main."}), 503