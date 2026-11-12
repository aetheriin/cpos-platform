"""Perusahaan yang dipanggil SP laporan, dari tabel company. Perusahaan baru atau yang dinonaktifkan langsung ikut tanpa mengubah kode."""
from . import konfigurasi
from .db import get_connection_app

# Isi kolom Status yang berarti nonaktif (kosong dianggap aktif)
_NONAKTIF = {"0", "false", "n", "no", "off", "inactive", "nonaktif", "non-aktif", "tidak aktif", "disabled"}


def _teks(v):
    return "" if v is None else str(v).strip()


def _aktif(status):
    return status is None or str(status).strip().casefold() not in _NONAKTIF


def _urut(kode):
    return (0, int(kode), "") if kode.isdigit() else (1, 0, kode)


def _tabel():
    """dbo.company -> [dbo].[company]"""
    return ".".join(f"[{b}]" for b in konfigurasi.TABEL_COMPANY.split("."))


def _lokasi(jenis, buka):
    """[(CompID, server tertaut, database)] company aktif dengan CompType = jenis, urut CompID. Baris tanpa server atau database
    (mis. HO) bukan perusahaan ERP, jadi dilewati. CompName berisi nama panjang, jadi kode perusahaan selalu CompID."""
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT [CompID], [CompType], [Status], [CompAddr], [CompDataBase] FROM {_tabel()}")
        baris = cur.fetchall()
    finally:
        conn.close()
    kunci = _teks(jenis).casefold()
    hasil = {}
    for kode, tipe, status, server, database in baris:
        kode, server, database = _teks(kode), _teks(server), _teks(database)
        if kode and server and database and _teks(tipe).casefold() == kunci and _aktif(status) and kode not in hasil:
            hasil[kode] = (kode, server, database)
    return [hasil[k] for k in sorted(hasil, key=_urut)]


def daftar_perusahaan(sumber=None, buka=None):
    """Perusahaan aktif dengan CompType `sumber` (bawaan LAPORAN_SUMBER), urut CompID."""
    return [l[0] for l in lokasi_perusahaan(sumber, buka)]


def lokasi_perusahaan(sumber=None, buka=None):
    """[(CompID, server tertaut, database)] untuk perusahaan yang sama dengan daftar_perusahaan."""
    sumber = sumber or konfigurasi.SUMBER_LAPORAN
    try:
        hasil = _lokasi(sumber, buka or get_connection_app)
    except Exception as e:
        raise RuntimeError(
            f"Daftar perusahaan tidak bisa dibaca dari tabel company '{konfigurasi.TABEL_COMPANY}' "
            f"(kolom CompID, CompType, Status, CompAddr, CompDataBase): {e}"
        ) from e
    if not hasil:
        raise RuntimeError(
            f"Tabel company '{konfigurasi.TABEL_COMPANY}' tidak punya perusahaan aktif bertipe '{sumber}'. "
            "Periksa kolom CompType dan Status di tabel itu, atau LAPORAN_SUMBER di backend/.env."
        )
    return hasil
