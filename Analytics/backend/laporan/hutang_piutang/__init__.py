"""Laporan Outstanding: hutang dan piutang yang belum lunas, semua perusahaan dan semua sumber (tabel saja, tanpa grafik)."""
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="outstanding",
    nama="Outstanding",
    grup="Reports",
    deskripsi="Hutang supplier dan piutang customer yang belum lunas.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={"perusahaan": "Perusahaan", "sumber": "Sumber"},
    mulai_bawaan="2025-01-01",   # hutang lama yang belum lunas tetap ikut
)
