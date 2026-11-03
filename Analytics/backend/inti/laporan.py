"""Objek Laporan (satu per folder laporan) dan dua rentang tanggalnya: periode yang dimuat dari SQL (ds.mulai..ds.akhir), dan rentang
tampilan di dalamnya (filter dari..sampai) yang dipakai semua kartu, grafik, dan tabel.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from . import konfigurasi

TANGGAL_MULAI_BAWAAN = konfigurasi.TANGGAL_MULAI_BAWAAN
MINGGU_BAWAAN = 5   # rentang tampilan bawaan laporan mingguan
MAKS_MINGGU = konfigurasi.MAKS_HARI // 7 + 1   # parameter lama jumlah_minggu, dipertahankan supaya tautan lama tidak gagal


@dataclass
class Laporan:
    id: str
    nama: str
    deskripsi: str
    pemuat: Callable            # (mulai, akhir, kendali) -> (DataFrame, catatan)
    bangun: Callable            # (dataset, jumlah_minggu, minggu, filter) -> dict
    detail: Callable            # (dataset, jenis, jumlah_minggu, minggu, filter, cari, urut, arah, halaman, ukuran) -> dict
    filter_didukung: tuple
    mulai_bawaan: str = TANGGAL_MULAI_BAWAAN
    grup: str = "Analytical Dashboard"   # judul grup di menu samping
    hari_bawaan: int | None = None   # kalau diisi, periode bawaan = sekian hari terakhir sampai hari ini, menggantikan mulai_bawaan
    awal_tahun: bool = False         # periode bawaan = 1 Januari tahun ini sampai hari ini, menggantikan mulai_bawaan
    label_filter: dict = field(default_factory=dict)   # judul filter di Export Excel, kalau beda dari api._LABEL_FILTER


class TampilanRentang:
    """Dataset yang sama (tanpa salinan) dengan rentang tampilan dari..sampai."""

    def __init__(self, ds, dari, sampai):
        self._ds, self.dari, self.sampai = ds, dari, sampai

    def __getattr__(self, nama):
        return getattr(self._ds, nama)


def rentang_tampil(ds, minggu=None, hari=None):
    """(dari, sampai). Tanpa filter tanggal: `minggu` minggu atau `hari` hari terakhir sampai akhir data (paling lambat hari ini),
    atau seluruh periode yang dimuat kalau keduanya kosong."""
    import pandas as pd

    dari = getattr(ds, "dari", None)
    sampai = getattr(ds, "sampai", None)
    if dari is not None and sampai is not None:
        return pd.Timestamp(dari), pd.Timestamp(sampai)
    awal = pd.Timestamp(ds.mulai)
    akhir = max(min(pd.Timestamp(ds.akhir), pd.Timestamp(date.today())), awal)
    if minggu:
        return max(awal, awal_minggu(akhir) - pd.Timedelta(days=7 * (minggu - 1))), akhir
    if hari:
        return max(awal, akhir - pd.Timedelta(days=hari - 1)), akhir
    return awal, akhir


def jangkar(ds):
    """Patokan minggu terakhir."""
    return rentang_tampil(ds)[1]


def awal_minggu(t):
    """Jumat pada atau sebelum t. Minggu laporan: Jumat sampai Kamis."""
    import pandas as pd

    t = pd.Timestamp(t).normalize()
    return t - pd.Timedelta(days=(t.weekday() - 4) % 7)


def minggu_rentang(dari, sampai):
    """[(mulai, akhir)] minggu yang menyentuh rentang, dipotong ke rentang itu, dari yang paling lama."""
    import pandas as pd

    dari, sampai = pd.Timestamp(dari).normalize(), pd.Timestamp(sampai).normalize()
    hasil, s = [], awal_minggu(dari)
    while s <= sampai:
        hasil.append((max(s, dari), min(s + pd.Timedelta(days=6), sampai)))
        s += pd.Timedelta(days=7)
    return hasil
