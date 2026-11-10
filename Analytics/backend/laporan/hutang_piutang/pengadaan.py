"""PR dan PO yang masih outstanding untuk laporan Outstanding, dari SP yang sama dengan laporan PR & PO dan PO & PI (SP_PR_PO, SP_PO_PI).

Aturan sama dengan kartu Outstanding Akhir di Analytics: status Open (bukan Completed, Void, atau Closed; PO juga belum di-close di
header) dan sisa qty (QTYOUT) > 0. Satu baris per item.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from ..po_pi import sumber as po_pi
from ..pr_po import sumber as pr_po


def _teks(seri):
    return seri.fillna("").astype(str).str.strip()


def _angka(seri):
    return pd.to_numeric(seri, errors="coerce")


def _tanggal(seri):
    return pd.to_datetime(seri.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str[:8], format="%Y%m%d", errors="coerce")


def _bendera(raw, kolom):
    return raw[kolom].fillna(False).astype(bool) if kolom in raw.columns else pd.Series(False, index=raw.index)


def _gabung_koma(seri):
    """'A,B,A' -> 'A, B' (nomor PO/PI yang dipisah koma oleh SP)."""
    return seri.fillna("").astype(str).map(lambda t: ", ".join(dict.fromkeys(x.strip() for x in t.split(",") if x.strip())))


def _terbuka(raw, header_close=False):
    buka = _bendera(raw, "ISOPEN") & ~_bendera(raw, "ISCOMPLETE") & ~_bendera(raw, "ISVOID") & ~_bendera(raw, "ISCLOSE")
    if header_close:
        buka &= ~_bendera(raw, "POISCLOSE")
    return raw[buka & (_angka(raw["QTYOUT"]).fillna(0) > 0)]


def bersihkan_pr(raw):
    r = _terbuka(raw)
    tgl = _tanggal(r["CREATEDDATE"])
    return pd.DataFrame({
        "jenis": "pr", "comp": _teks(r["COMPID"]), "no_dok": _teks(r["PRNUMBER"]), "tgl": tgl,
        "kode_barang": _teks(r["ITEMCODE"]), "nama_barang": _teks(r["ITEMNAME"]), "satuan": _teks(r["UOMNAME"]),
        "qty_minta": _angka(r["QTYREQ"]), "qty_proses": _angka(r["QTYORDER"]), "qty_sisa": _angka(r["QTYOUT"]),
        "no_lanjut": _gabung_koma(r["PONUMBER"]), "mitra": _gabung_koma(r["SUPPLIERNAME"]), "kategori": _teks(r["CATEGORY"]),
        "dibuat_oleh": _teks(r["CREATEDBY"]), "approve_oleh": _teks(r["APPROVEBY"]),
    })


def bersihkan_po(raw):
    r = _terbuka(raw, header_close=True)
    tgl = _tanggal(r["CREATEDDATE"])
    return pd.DataFrame({
        "jenis": "po", "comp": _teks(r["COMPID"]), "no_dok": _teks(r["PONUMBER"]), "tgl": tgl,
        "kode_barang": _teks(r["ITEMCODE"]), "nama_barang": _teks(r["ITEMNAME"]), "satuan": _teks(r["UOMNAME"]),
        "qty_minta": _angka(r["QTYORDERED"]), "qty_proses": _angka(r["QTYDELIVERED"]), "qty_sisa": _angka(r["QTYOUT"]),
        "no_lanjut": _gabung_koma(r["PURCHASENUMBER"]), "mitra": _teks(r["SUPPLIERNAME"]), "kategori": _teks(r["CATEGORY"]),
        "dibuat_oleh": _teks(r["CREATEDBY"]), "approve_oleh": "",
    })


def muat(mulai, akhir, kendali=None):
    """(PR, PO) outstanding yang dibuat dalam mulai..akhir (ISO). Dipanggil bersamaan dengan data hutang/piutang."""
    a, b = mulai.replace("-", ""), akhir.replace("-", "")
    with ThreadPoolExecutor(max_workers=2) as pool:   # kedua SP jalan bersamaan
        t_pr = pool.submit(pr_po.ambil_data, a, b, None, kendali)
        t_po = pool.submit(po_pi.ambil_data, a, b, None, kendali)
        pr, po = bersihkan_pr(t_pr.result()), bersihkan_po(t_po.result())
    hasil = pd.concat([pr, po], ignore_index=True)
    hasil["umur"] = (pd.Timestamp(date.today()) - hasil["tgl"]).dt.days
    return hasil
