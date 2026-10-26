"""Koneksi ke database ERP untuk laporan Pembelian TBS (prosedur dbo.tbsdetail*).

REKAPIN_ERP_CONNECTION_STRING di .env = connection string ODBC ke database tempat prosedur itu berada. Kosong = prosedur
dicari di database CPOS sendiri (mis. saat uji, atau bila prosedurnya dipindah ke CPOS)."""
import os
import re

import pyodbc

from utils.db_utils import get_connection

NAMA_PROSEDUR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _koneksi():
    teks = os.getenv("REKAPIN_ERP_CONNECTION_STRING", "").strip()
    return pyodbc.connect(teks, timeout=10) if teks else get_connection()


def jalankan_prosedur(nama, *params):
    """EXEC prosedur, kembalikan semua result set: [[{kolom: nilai}]]."""
    if not NAMA_PROSEDUR.fullmatch(nama):
        raise ValueError("Nama prosedur tidak valid")
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SET NOCOUNT ON; EXEC {nama} {', '.join('?' * len(params))}".rstrip(), *params)
        hasil = []
        while True:
            if cursor.description is not None:
                kolom = [c[0] for c in cursor.description]
                hasil.append([dict(zip(kolom, r)) for r in cursor.fetchall()])
            if not cursor.nextset():
                break
        return hasil
    finally:
        conn.close()
