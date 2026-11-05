"""Laporan PO Spend Analysis: nilai PO per kategori, tren bulanan, dan supplier terbesar, mengikuti Excel PO AMT db."""
from inti.laporan import Laporan, rentang_tampil

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="po_amt",
    nama="PO Spend Analysis",
    deskripsi="Jumlah dan nilai PO per kategori, tren bulanan, dan supplier terbesar.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, *rentang_tampil(ds), f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, *rentang_tampil(ds), f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={k: judul for k, judul, _ in dashboard.FILTER},
    mulai_bawaan="2022-01-01",   # Excel memakai seluruh data sejak PO pertama
    maks_hari=3660,
)
