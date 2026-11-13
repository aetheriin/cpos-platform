"""Laporan Purchase Request: PR yang belum, sebagian, dan sudah dibuatkan PO (tabel saja, model laporan Purchase Invoice)."""
from inti.laporan import Laporan

from ..status_dokumen import AMBANG_LAMA, LaporanStatus, Tab, dokumen, lama
from .sumber import BELUM, DITUTUP, SEBAGIAN, SUDAH, URUTAN_STATUS, muat

_PR = [("comp", "Perusahaan", "teks"), ("status", "Status", "teks"), ("prnumber", "No. PR", "teks"), ("pr_date", "Tanggal PR", "tanggal")]
_BARANG = [("category", "Kategori", "teks"), ("itemcode", "Kode Barang", "teks"), ("itemname", "Nama Barang", "teks"), ("uom", "Satuan", "teks"),
           ("qtyreq", "Qty PR", "angka"), ("qtyorder", "Qty PO", "angka"), ("qtyout", "Qty belum PO", "angka"),
           ("approve_by", "Disetujui Oleh", "teks"), ("approve_date", "Tanggal Disetujui", "tanggal")]
_PO = [("po_number", "No. PO", "teks"), ("po_date", "Tanggal PO", "tanggal"), ("buyer", "Buyer", "teks"),
       ("supplier_name", "Nama Supplier", "teks"), ("lama_po", "PR ke PO (hari)", "angka")]
_UMUR = [("umur", "Aging PR (hari)", "angka")]


def _kpi(d):
    belum, sebagian, sudah = d[d["status"] == BELUM], d[d["status"] == SEBAGIAN], d[d["status"].isin([SEBAGIAN, SUDAH])]
    umur = belum.groupby(["comp", "prnumber"])["umur"].max()
    return {
        "belum": dokumen(belum, "prnumber"), "baris_belum": len(belum),
        "belum_lama": int((umur > AMBANG_LAMA).sum()), "umur_maks": int(umur.max()) if len(umur) else None,
        "sebagian": dokumen(sebagian, "prnumber"), "baris_sebagian": len(sebagian),
        "sudah": dokumen(d[d["status"] == SUDAH], "prnumber"), "baris_sudah": int((d["status"] == SUDAH).sum()),
        "lama": lama(sudah, "lama_po"),
    }


_L = LaporanStatus(
    nama="Purchase Request", kol_tanggal="pr_date", urutan_status=URUTAN_STATUS, kpi=_kpi, pembanding="prnumber",
    dim={"kategori": ("category", "Kategori"), "buyer": ("buyer", "Buyer")}, banyak=("buyer",),
    kolom_cari=["comp", "prnumber", "itemcode", "itemname", "category", "approve_by", "po_number", "buyer", "supplier_name"],
    tab={
        "belum": Tab("Belum PO", (BELUM,), "pr_date", "asc", _PR + _UMUR + _BARANG),
        "sebagian": Tab("PO sebagian", (SEBAGIAN,), "pr_date", "asc", _PR + _UMUR + _BARANG + _PO),
        "sudah": Tab("Sudah PO", (SUDAH,), "po_date", "desc", _PR + _BARANG + _PO),
        "ditutup": Tab("Ditutup tanpa PO", (DITUTUP,), "pr_date", "desc", _PR + _BARANG),
    })

LAPORAN = Laporan(
    id="purchase_request",
    nama="Purchase Request",
    grup="Reports",
    deskripsi="PR yang belum, sebagian, dan sudah dibuatkan PO.",
    pemuat=muat,
    bangun=lambda ds, n, mg, f: _L.bangun(ds.df, ds, f),
    detail=lambda ds, jenis, n, mg, f, cari, urut, arah, hal, uk: _L.detail(ds.df, jenis, ds, f, cari, urut, arah, hal, uk),
    filter_didukung=_L.filter_didukung,
    label_filter=_L.label_filter,
    awal_tahun=True,
)
