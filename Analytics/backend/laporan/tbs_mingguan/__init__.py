"""Laporan Pembelian TBS Mingguan: tonase per business group per minggu dan atensi naik/turun di minggu lengkap terakhir."""
from inti import konfigurasi
from inti.laporan import Laporan

from . import dashboard
from .sumber import muat

LAPORAN = Laporan(
    id="tbs_mingguan",
    nama="Pembelian TBS Mingguan",
    deskripsi="Tonase TBS per business group per minggu, dengan atensi grup yang naik atau turun di luar kebiasaan.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=tuple(kunci for kunci, *_ in dashboard.FILTER),
    mulai_bawaan=konfigurasi.TBS_MINGGUAN_MULAI,
    label_filter={kunci: nama for kunci, nama, *_ in dashboard.FILTER},
)
