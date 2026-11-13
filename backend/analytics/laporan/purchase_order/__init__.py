"""Laporan Purchase Orders: PO yang belum, sebagian, dan sudah dibuatkan PI (tabel saja, model laporan Purchase Invoice)."""
from inti.laporan import Laporan

from ..status_dokumen import AMBANG_LAMA, LaporanStatus, Tab, dokumen, lama
from .sumber import BELUM, DITUTUP, SEBAGIAN, SUDAH, URUTAN_STATUS, muat

_PO = [("comp", "Perusahaan", "teks"), ("status", "Status", "teks"), ("po_number", "No. PO", "teks"), ("cd", "Tanggal PO Dibuat", "tanggal"),
       ("supplier_code", "Kode Supplier", "teks"), ("supplier_name", "Nama Supplier", "teks")]
_BARANG = [("category", "Kategori", "teks"), ("itemcode", "Kode Barang", "teks"), ("itemname", "Nama Barang", "teks"), ("uom", "Satuan", "teks"),
           ("qtyordered", "Qty PO", "angka"), ("qtydelivered", "Qty Diterima", "angka"), ("qtyout", "Qty belum diterima", "angka"),
           ("harga_po", "Harga", "angka"), ("total_po", "Line Total", "angka"), ("mata_uang_po", "Mata Uang", "teks"),
           ("creator", "PO Dibuat Oleh", "teks")]
_PI = [("pi_number", "No. PI", "teks"), ("pi_date", "Tanggal PI", "tanggal"), ("lama_pi", "PO ke PI (hari)", "angka")]
_UMUR = [("umur", "Aging PO (hari)", "angka")]


def _kpi(d):
    belum, sebagian, sudah = d[d["status"] == BELUM], d[d["status"] == SEBAGIAN], d[d["status"].isin([SEBAGIAN, SUDAH])]
    nilai = lambda t: float(t.loc[t["rupiah"], "total_po"].sum())
    umur = belum.groupby(["comp", "po_number"])["umur"].max()
    return {
        "belum": dokumen(belum, "po_number"), "nilai_belum": nilai(belum),
        "belum_lama": int((umur > AMBANG_LAMA).sum()), "umur_maks": int(umur.max()) if len(umur) else None,
        "sebagian": dokumen(sebagian, "po_number"), "nilai_sebagian": nilai(sebagian),
        "sudah": dokumen(d[d["status"] == SUDAH], "po_number"), "nilai_sudah": nilai(d[d["status"] == SUDAH]),
        "lama": lama(sudah, "lama_pi"),
        "valas": dokumen(d[~d["rupiah"]], "po_number"),
    }


_L = LaporanStatus(
    nama="Purchase Orders", kol_tanggal="cd", urutan_status=URUTAN_STATUS, kpi=_kpi, pembanding="po_number",
    dim={"kategori": ("category", "Kategori"), "supplier": ("supplier_name", "Supplier"), "pembuat": ("creator", "Dibuat oleh")},
    kolom_cari=["comp", "po_number", "supplier_code", "supplier_name", "itemcode", "itemname", "category", "creator", "pi_number"],
    tab={
        "belum": Tab("Belum PI", (BELUM,), "cd", "asc", _PO + _UMUR + _BARANG),
        "sebagian": Tab("PI sebagian", (SEBAGIAN,), "cd", "asc", _PO + _UMUR + _BARANG + _PI),
        "sudah": Tab("Sudah PI", (SUDAH,), "pi_date", "desc", _PO + _BARANG + _PI),
        "ditutup": Tab("Ditutup tanpa PI", (DITUTUP,), "cd", "desc", _PO + _BARANG),
    })

LAPORAN = Laporan(
    id="purchase_order",
    nama="Purchase Orders",
    grup="Reports",
    deskripsi="PO yang belum, sebagian, dan sudah dibuatkan PI.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: _L.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: _L.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=_L.filter_didukung,
    label_filter=_L.label_filter,
    awal_tahun=True,
)
