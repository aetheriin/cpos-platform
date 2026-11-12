"""Laporan Purchase Invoice: PI yang belum dan sudah dibuatkan PVR (tabel saja, tanpa grafik)."""
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="pi_pvr",
    nama="Purchase Invoice",
    grup="Reports",
    deskripsi="PI yang belum dan sudah dibuatkan PVR.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={"perusahaan": "Perusahaan", "status": "Status"},
    awal_tahun=True,   # periode bawaan: 1 Januari tahun ini sampai hari ini
)
