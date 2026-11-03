"""Perusahaan yang dipanggil SP laporan, dari tabel company. Perusahaan baru atau yang dinonaktifkan langsung ikut tanpa mengubah kode."""
from . import konfigurasi
from .db import get_connection_app
from .pengguna import PenyimpanPengguna, PenyimpanTidakTersedia


def daftar_perusahaan(sumber=None, buka=None):
    """Perusahaan aktif dengan CompType `sumber` (bawaan LAPORAN_SUMBER), urut CompID."""
    return _baca(sumber, buka, "company_menurut_jenis")


def lokasi_perusahaan(sumber=None, buka=None):
    """[(nama, server tertaut, database)] untuk perusahaan yang sama dengan daftar_perusahaan."""
    return _baca(sumber, buka, "lokasi_menurut_jenis")


def _baca(sumber, buka, metode):
    sumber = sumber or konfigurasi.SUMBER_LAPORAN
    penyimpan = PenyimpanPengguna(
        buka or get_connection_app, tabel=konfigurasi.TABEL_PENGGUNA, tabel_role=konfigurasi.TABEL_ROLE,
        tabel_company=konfigurasi.TABEL_COMPANY, cache_detik=0,
    )
    try:
        nama = getattr(penyimpan, metode)(sumber)
    except PenyimpanTidakTersedia as e:
        raise RuntimeError(
            f"Daftar perusahaan tidak bisa dibaca dari tabel company '{konfigurasi.TABEL_COMPANY}' (kolom CompID, CompName, CompType, Status): {e}"
        ) from e
    if not nama:
        raise RuntimeError(
            f"Tabel company '{konfigurasi.TABEL_COMPANY}' tidak punya perusahaan aktif bertipe '{sumber}'. "
            "Periksa kolom CompType dan Status di tabel itu, atau LAPORAN_SUMBER di backend/.env."
        )
    return nama
