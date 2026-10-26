"""Laporan Penilaian PVR: skor pembuat PVR per bulan menurut kategori dan bobotnya, mengikuti Excel Penilaian PVR."""
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="penilaian_pvr",
    nama="PVR KPI",
    deskripsi="Skor pembuat PVR per bulan menurut kategori dan bobotnya.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={k: judul for k, judul, _ in dashboard.FILTER},
    awal_tahun=True,
)
