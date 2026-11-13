"""Laporan Purchase Request: tiap baris PR beserta PO yang dibuat darinya. Data dari SP yang sama dengan laporan PR & PO
(pr_po/sumber.py: ambil_data, bersihkan) ditambah harga PO (harga_po.py), tanpa periode pembanding. Di sini dijadikan satu baris per
baris PR dan diberi status tindak lanjut."""
from concurrent.futures import ThreadPoolExecutor

from inti.nama import orang, seragam

from .. import harga_po
from ..pr_po import sumber as pr_po
from ..status_dokumen import gabung, hari_sejak

BELUM, SEBAGIAN, SUDAH, DITUTUP = "Belum PO", "PO sebagian", "Sudah PO", "Ditutup tanpa PO"
URUTAN_STATUS = [BELUM, SEBAGIAN, SUDAH, DITUTUP]


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. mulai, akhir: 'YYYY-MM-DD', tanggal PR dibuat."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        t_harga = pool.submit(harga_po.ambil, harga_po.mulai_po(mulai), kendali)
        raw = pr_po.ambil_data(mulai.replace("-", ""), akhir.replace("-", ""), kendali=kendali)
        harga = t_harga.result()
    if kendali:
        kendali.periksa()
    bersih = pr_po.bersihkan(raw)
    catatan = dict(bersih.attrs.get("catatan", {}))
    d = susun(harga_po.tempel_pr(bersih, harga))
    return d, dict(catatan, baris_sp=len(d))


def susun(df):
    """Satu baris per baris PR (PR yang dipecah ke beberapa PO digabung: nomor dipisah koma, tanggal PO paling awal). PR Void dibuang."""
    df = df[df["status"] != "Void"]
    d = (df.sort_values("po_date", na_position="last", kind="stable")
         .groupby("line", sort=False, as_index=False)
         .agg(comp=("comp", "first"), status_pr=("status", "first"), prnumber=("prnumber", "first"), pr_date=("pr_date", "first"),
              category=("category", "first"), itemcode=("itemcode", "first"), itemname=("itemname", "first"), uom=("uom", "first"),
              qtyreq=("qtyreq", "first"), qtyorder=("qtyorder", "first"), qtyout=("qtyout", "first"),
              approve_by=("approve_by", "first"), approve_date=("approve_date", "first"),
              po_number=("po_number", gabung), po_date=("po_date", "min"), buyer=("buyer", gabung),
              supplier_name=("supplier_name", gabung)))
    d["buyer"] = orang(d["buyer"])   # beberapa buyer tetap dipisah koma; filter Buyer memecahnya
    d["category"] = seragam(d["category"])
    ada_po = d["po_number"] != ""
    selesai = d["status_pr"].isin(["Closed", "Completed"])
    d["status"] = BELUM
    d.loc[~ada_po & selesai, "status"] = DITUTUP
    d.loc[ada_po, "status"] = SUDAH
    d.loc[ada_po & ~selesai & (d["qtyout"] > 0), "status"] = SEBAGIAN
    d["umur"] = hari_sejak(d["pr_date"])
    d["lama_po"] = (d["po_date"] - d["pr_date"]).dt.days
    return d.reset_index(drop=True)
