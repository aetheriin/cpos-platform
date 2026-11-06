"""Laporan PO Spend Analysis: nilai PO per kategori, tren bulanan, dan supplier terbesar, mengikuti Excel PO AMT db."""
import pandas as pd

from inti.laporan import Laporan, rentang_tampil

from . import dashboard
from .sumber import muat


def _rentang(ds, f):
    """Tampilan awal tahun terakhir pada periode. Rentang tanggal yang dipilih atau filter Tahun membuka tahun lain."""
    dari, sampai = rentang_tampil(ds)
    if getattr(ds, "dari", None) is None and not (f or {}).get("tahun"):
        dari = min(max(dari, pd.Timestamp(sampai.year, 1, 1)), sampai)
    return dari, sampai


LAPORAN = Laporan(
    id="po_amt",
    nama="PO Spend Analysis",
    deskripsi="Jumlah dan nilai PO per kategori, tren bulanan, dan supplier terbesar.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, *_rentang(ds, f), f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, *_rentang(ds, f), f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={k: judul for k, judul, _ in dashboard.FILTER},
    mulai_bawaan="2022-01-01",   # semua tahun dimuat; tampilan awalnya tahun berjalan (_rentang)
    maks_hari=3660,
)
