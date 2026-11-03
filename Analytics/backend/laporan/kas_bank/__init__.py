"""Laporan Cash Flow: saldo berjalan, mutasi harian, lawan transaksi, dan jasa giro per rekening bank."""
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="cash_flow",
    nama="Cash Flow",
    deskripsi="Running balance, debit, credit, credit to date, dan jasa giro per rekening bank.",
    pemuat=muat,
    awal_tahun=True,   # dimuat dari 1 Januari supaya kredit to date lengkap; tampilan bawaannya KAS_HARI_BAWAAN hari terakhir
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(kunci for kunci, *_ in dashboard.FILTER),
    label_filter={kunci: nama for kunci, nama, *_ in dashboard.FILTER},
)
