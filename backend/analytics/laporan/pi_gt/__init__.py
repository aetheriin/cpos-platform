"""Laporan PI & GT: PI dari HO untuk gudang lain yang belum di-GT (outstanding) dan GT-nya per bulan, dengan pola PO & PI,
mengikuti definisi lead time di Excel PI GT db."""
from inti.laporan import Laporan, rentang_tampil

from . import dashboard
from .sumber import muat

# Periode bawaan: 1 Januari sampai hari ini (awal_tahun), dibagi per bulan. Parameter `minggu` API dipakai sebagai indeks bulan.
LAPORAN = Laporan(
    id="pi_gt",
    nama="PI & GT",
    deskripsi="PI dari HO untuk gudang lain yang belum di-GT, GT per bulan, dan lead time-nya.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, *rentang_tampil(ds), mg, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, *rentang_tampil(ds), mg, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(dashboard.DIM),
    label_filter={k: judul for k, judul, _ in dashboard.FILTER},
    awal_tahun=True,
)
