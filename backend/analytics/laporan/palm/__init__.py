"""Laporan Deteksi Kecurangan Timbangan (weighbridge sawit)."""
from inti import konfigurasi
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="palm_weighbridge",
    nama="Weighbridge Fraud Detector",
    deskripsi="Transaksi timbang sawit dan indikator risiko kecurangannya.",
    pemuat=muat,
    mulai_bawaan=konfigurasi.PALM_MULAI,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(kunci for kunci, *_ in dashboard.FILTER),
    label_filter={kunci: nama for kunci, nama, *_ in dashboard.FILTER},
)
