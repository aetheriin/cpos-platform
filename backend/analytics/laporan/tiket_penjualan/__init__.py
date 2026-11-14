"""Laporan Tiket Penjualan: tiket timbang produk keluar per hari, minggu, atau bulan, dengan peringkat produk dan nama pengangkutan."""
from inti import konfigurasi
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="tiket_penjualan",
    nama="Tiket Penjualan",
    deskripsi="Tiket timbang produk keluar dengan nama pengangkutan, per hari, minggu, atau bulan.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(kunci for kunci, *_ in dashboard.FILTER),
    hari_bawaan=konfigurasi.TIKET_PENJUALAN_HARI,
    label_filter={kunci: nama for kunci, nama, *_ in dashboard.FILTER},
)
