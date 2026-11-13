"""Laporan Purchase Orders: tiap baris PO beserta PI yang dibuat darinya. Data dari SP yang sama dengan laporan PO & PI
(po_pi/sumber.py: ambil_data, bersihkan) ditambah harga PO (harga_po.py), tanpa periode pembanding. Di sini dijadikan satu baris per
baris PO dan diberi status tindak lanjut."""
from concurrent.futures import ThreadPoolExecutor

from inti.nama import orang, seragam

from .. import harga_po
from ..po_pi import sumber as po_pi
from ..status_dokumen import gabung, hari_sejak

BELUM, SEBAGIAN, SUDAH, DITUTUP = "Belum PI", "PI sebagian", "Sudah PI", "Ditutup tanpa PI"
URUTAN_STATUS = [BELUM, SEBAGIAN, SUDAH, DITUTUP]
RUPIAH = {"", "IDR", "RP"}   # mata uang PO yang dijumlahkan di kartu; PO valas tidak, karena kursnya tidak ikut di data PO


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. mulai, akhir: 'YYYY-MM-DD', tanggal PO dibuat."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        t_harga = pool.submit(harga_po.ambil, harga_po.mulai_po(mulai), kendali)
        raw = po_pi.ambil_data(mulai.replace("-", ""), akhir.replace("-", ""), kendali=kendali)
        harga = t_harga.result()
    if kendali:
        kendali.periksa()
    bersih = po_pi.bersihkan(raw)
    catatan = dict(bersih.attrs.get("catatan", {}))
    d = susun(harga_po.tempel_po(bersih, harga))
    return d, dict(catatan, baris_sp=len(d))


def susun(df):
    """Satu baris per baris PO (PO yang ditagih beberapa PI digabung: nomor dipisah koma, tanggal PI paling awal). PO Void dibuang."""
    df = df[df["status"] != "Void"]
    d = (df.sort_values("pi_date", na_position="last", kind="stable")
         .groupby("line", sort=False, as_index=False)
         .agg(comp=("comp", "first"), status_po=("status", "first"), po_number=("po_number", "first"), po_date=("po_date", "first"),
              cd=("cd", "first"), creator=("creator", "first"), category=("category", "first"), itemcode=("itemcode", "first"),
              itemname=("itemname", "first"), uom=("uom", "first"), qtyordered=("qtyordered", "first"), qtydelivered=("qtydelivered", "first"),
              qtyout=("qtyout", "first"), supplier_code=("supplier_code", "first"), supplier_name=("supplier_name", "first"),
              harga_po=("harga_po", "first"), total_po=("total_po", "first"), mata_uang_po=("mata_uang_po", "first"),
              pi_number=("pi_number", gabung), pi_date=("pi_date", "min")))
    d["creator"] = orang(d["creator"])
    d["category"] = seragam(d["category"])
    d["supplier_name"] = seragam(d["supplier_name"])
    ada_pi = d["pi_number"] != ""
    selesai = d["status_po"].isin(["Closed", "Completed"])
    d["status"] = BELUM
    d.loc[~ada_pi & selesai, "status"] = DITUTUP
    d.loc[ada_pi, "status"] = SUDAH
    d.loc[ada_pi & ~selesai & (d["qtyout"] > 0), "status"] = SEBAGIAN
    d["rupiah"] = d["mata_uang_po"].str.upper().isin(RUPIAH)
    d["umur"] = hari_sejak(d["cd"])
    d["lama_pi"] = (d["pi_date"] - d["cd"]).dt.days
    return d.reset_index(drop=True)
