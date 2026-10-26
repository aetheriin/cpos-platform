"""Laporan PR & PO Procurement."""
from inti.laporan import MINGGU_BAWAAN, Laporan, rentang_tampil

from . import dashboard
from .sumber import muat


def _f(filt, nama):
    return filt.get(nama) or None


# n (jumlah_minggu) tidak dipakai lagi: minggu grafik mengikuti rentang tampilan (rentang_tampil; bawaan 5 minggu terakhir)
LAPORAN = Laporan(
    id="pr_po",
    nama="PR & PO Outstanding",
    deskripsi="PR yang masih outstanding dan pembeliannya (PO).",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: dashboard.bangun(
        ds.df, *rentang_tampil(ds, minggu=MINGGU_BAWAAN), mg, _f(f, "perusahaan"), _f(f, "kategori"), _f(f, "buyer"), umur=_f(f, "umur"), mulai_data=ds.mulai),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: dashboard.detail(
        ds.df, jenis, *rentang_tampil(ds, minggu=MINGGU_BAWAAN), mg, _f(f, "perusahaan"), _f(f, "kategori"), _f(f, "buyer"),
        cari, urut, arah, hal, uk, umur=_f(f, "umur")),
    filter_didukung=("perusahaan", "kategori", "buyer", "umur"),
)
