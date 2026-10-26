"""Laporan PV KPI: skor kasir pembuat PV per bulan menurut kategori dan bobotnya, mengikuti Excel Penilaian PV.
Grafik dan tabelnya sama dengan PVR KPI, jadi memakai laporan.penilaian_pvr.dashboard."""
from inti import konfigurasi
from inti.laporan import Laporan

from ..penilaian_pvr import dashboard
from .sumber import muat

_DINILAI = konfigurasi.PV_PENILAIAN_PEMBUAT

LAPORAN = Laporan(
    id="penilaian_pv",
    nama="PV KPI",
    deskripsi="Skor kasir pembuat PV per bulan menurut kategori dan bobotnya.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f, _DINILAI),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk, _DINILAI, "PV"),
    filter_didukung=tuple(dashboard.DIM),
    label_filter=dashboard.label_filter("PV"),
    awal_tahun=True,
)
