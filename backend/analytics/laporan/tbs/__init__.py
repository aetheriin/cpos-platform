"""Laporan Penerimaan TBS (pembelian tandan buah segar)."""
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="penerimaan_tbs",
    nama="Forecast Penerimaan TBS",
    deskripsi="Pembelian TBS harian per supplier, harga, dan forecast netto.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(kunci for kunci, *_ in dashboard.FILTER),
    label_filter={kunci: nama for kunci, nama, *_ in dashboard.FILTER},
)
