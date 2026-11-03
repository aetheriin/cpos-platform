"""Koneksi ke database ERP untuk laporan Pembelian TBS (prosedur dbo.tbsdetail*).

Di .env: REKAPIN_ERP_SERVER / _DB / _USER / _PASSWORD (sama dengan DB_* di Analytics\backend\.env bila prosedurnya di
database yang sama), atau satu REKAPIN_ERP_CONNECTION_STRING lengkap. Semua kosong = prosedur dicari di database CPOS sendiri."""
import os
import re

import pyodbc

from utils.db_utils import get_connection

NAMA_PROSEDUR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _connection_string():
    teks = os.getenv("REKAPIN_ERP_CONNECTION_STRING", "").strip()
    server = os.getenv("REKAPIN_ERP_SERVER", "").strip()
    if teks or not server:
        return teks
    user = os.getenv("REKAPIN_ERP_USER", "").strip()
    sandi = os.getenv("REKAPIN_ERP_PASSWORD", "")
    login = f"UID={user};PWD={{{sandi.replace('}', '}}')}}};" if user else "Trusted_Connection=yes;"
    driver = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
    # Encrypt=no sama dengan RekapIn lama: ODBC Driver 18 memakai enkripsi bawaan dan gagal ke SQL Server lama tanpa TLS
    enkripsi = os.getenv("REKAPIN_ERP_ENCRYPT", "no").strip() or "no"
    return (f"DRIVER={driver};SERVER={server};DATABASE={os.getenv('REKAPIN_ERP_DB', '').strip()};{login}"
            f"Encrypt={enkripsi};TrustServerCertificate=yes;APP=CPOS-RekapIn;")


def _koneksi():
    teks = _connection_string()
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


def tanggal_harga_terakhir(company, sampai):
    """Tanggal terakhir (paling lambat `sampai`) yang punya harga di dbo.HARGA untuk perusahaan itu, atau None.
    Prosedur laporan TBS harian hanya mengembalikan baris pada tanggal yang punya harga, jadi ini tanggal terakhir yang ada datanya."""
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(tanggal) FROM dbo.HARGA WHERE UPPER(LTRIM(RTRIM(company))) = ? AND tanggal <= ?",
                       company.strip().upper(), sampai)
        hasil = cursor.fetchone()[0]
        return hasil.date() if hasattr(hasil, "date") and callable(hasil.date) else hasil
    finally:
        conn.close()


def terhubung():
    """Koneksi ERP diisi di .env (bila tidak, data diambil dari database CPOS sendiri)."""
    return bool(_connection_string())
