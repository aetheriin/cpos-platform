"""Koneksi dan helper hasil untuk operasi tiket Ascend."""
import pyodbc

from utils.koneksi_lain import connection_string


def koneksi_tiket():
    """Koneksi ke database tiket Ascend."""
    koneksi = pyodbc.connect(
        connection_string("ASCEND", "CPOS", db_bawaan="AS_WB_YBS"),
        timeout=10,
    )
    koneksi.timeout = 30
    return koneksi


def baris_hasil(cursor):
    """Lewati result set tanpa kolom dan baca result set pertama sebagai daftar dict."""
    while cursor.description is None:
        if not cursor.nextset():
            return []

    nama_kolom = [kolom[0] for kolom in cursor.description]
    return [dict(zip(nama_kolom, baris)) for baris in cursor.fetchall()]