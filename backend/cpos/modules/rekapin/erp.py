"""Koneksi ke database ERP untuk laporan Pembelian TBS (prosedur dbo.tbsdetail*).

Di .env: REKAPIN_ERP_SERVER / _DB / _USER / _PASSWORD hanya bila prosedurnya di database lain; yang kosong memakai DB_*
(utils/koneksi_lain.py)."""
import os
import re
import pyodbc
import logging
import time

from utils.koneksi_lain import connection_string

log = logging.getLogger(__name__)
NAMA_PROSEDUR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _koneksi():
    return pyodbc.connect(connection_string("REKAPIN_ERP", "CPOS-RekapIn"), timeout=10)


def jalankan_prosedur(nama, *params):
    """EXEC prosedur dan catat durasi query ERP yang lambat."""
    if not NAMA_PROSEDUR.fullmatch(nama):
        raise ValueError("Nama prosedur tidak valid")

    mulai_buka = time.perf_counter()
    conn = _koneksi()
    buka_ms = (time.perf_counter() - mulai_buka) * 1000

    try:
        mulai_query = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute(
            f"SET NOCOUNT ON; EXEC {nama} {', '.join('?' * len(params))}".rstrip(),
            *params,
        )

        hasil = []
        while True:
            if cursor.description is not None:
                kolom = [c[0] for c in cursor.description]
                hasil.append([dict(zip(kolom, r)) for r in cursor.fetchall()])
            if not cursor.nextset():
                break

        query_ms = (time.perf_counter() - mulai_query) * 1000
        if query_ms >= 1000:
            company = str(params[0]) if params else "-"
            log.warning(
                "ERP_TBS_LAMBAT prosedur=%s company=%s koneksi_ms=%.0f query_ms=%.0f",
                nama, company, buka_ms, query_ms,
            )

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
