"""Laporan PI & GT, sama dengan Excel PI GT db: GT dari SP gt_out (termasuk GT tanpa PI, mis. pindahan antar site),
ditambah barang yang sudah PI tapi belum di-GT dari SP CheckStatItem. Barang PI yang langsung dipakai (usage) tanpa GT
dianggap selesai pada tanggal usage-nya; usage dilacak ke PI asalnya lewat PurchaseDetailID di IC_UsageDetails."""
import logging
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan, lokasi_perusahaan
from inti.sp import per_perusahaan

SP_NAME = konfigurasi.SP_PI_GT
SP_GT = konfigurasi.SP_GT_OUT
SUMBER = konfigurasi.SUMBER_LAPORAN
log = logging.getLogger(__name__)

# Status (slicer Aging di Excel: Completed / InCompleted, ditambah PI yang belum di-GT). GT void dibuang.
BELUM_GT, BELUM_DITERIMA, DITERIMA, USAGE = "Belum GT", "GT belum diterima", "Diterima", "Langsung usage"
URUTAN_STATUS = [BELUM_GT, USAGE, BELUM_DITERIMA, DITERIMA]

# Usage pertama tiap baris PI HO (PurchaseDetailID), hanya baca. {db} dari tabel company, sama dengan yang dipakai SP gt_out.
_USAGE = """
SELECT pis.PurchaseNumber, it.ItemCode, MIN(u.UsageDate) AS UsageDate, MIN(u.UsageNumber) AS UsageNumber,
       MIN(w.WarehouseCode) AS UsageWarehouse, SUM(ud.Quantity) AS QtyUsage
FROM {db}.IC_UsageDetails ud
JOIN {db}.IC_Usages u ON u.UsageID = ud.UsageID
JOIN {db}.ap_purchasedetails pid ON pid.PurchaseDetailID = COALESCE(ud.PurchaseDetailID, ud.SourcePurchaseDetailID)
JOIN {db}.ap_purchases pis ON pis.PurchaseID = pid.PurchaseID
LEFT JOIN {db}.IC_ITEMS it ON it.ItemID = pid.ItemID
LEFT JOIN {db}.IC_Warehouses w ON w.WarehouseID = ud.WarehouseID
WHERE pis.PurchaseNumber LIKE '%/PI/HO/%' AND pis.PurchaseDate >= ?
  AND ISNULL(u.Void, 0) = 0 AND ISNULL(ud.DetailVoid, 0) = 0 AND ISNULL(pis.Void, 0) = 0
GROUP BY pis.PurchaseNumber, it.ItemCode
"""

_GT_TEKS = {
    "comp": "COMPID", "gt_number": "MutationNumber", "dari_gudang": "FromWarehouse", "ke_gudang": "ToWarehouse", "gt_by": "CreatedBy",
    "pr_number": "PRNumber", "po_number": "PONumber", "pi_number": "PurchaseNumber", "importance": "PRImportance",
    "itemcode": "ItemCode", "itemname": "ItemName", "diterima_oleh": "ReceivedBy", "aging": "Aging", "peminta": "RequestedBy",
}
_GT_TANGGAL = {"gt_date": "MutationDate", "terima_date": "ReceivedDateTime", "pi_date": "PIDate", "gt_dibuat": "CreateDate"}
_PI_TEKS = {
    "comp": "CompanyName", "pr_number": "PRNumber", "po_number": "PONumber", "pi_number": "PurchaseNumber", "gt_number": "MutationNumber",
    "importance": "Importance", "itemcode": "ItemCode", "itemname": "ItemName", "pi_by": "PICreateBy", "peminta": "ReqFrom",
}
GUDANG_HO = {g.casefold() for g in konfigurasi.PIGT_GUDANG_HO}
_OPSIONAL = {"uom": "UOM"}     # kolom UOM yang direncanakan di CheckStatItem; kosong selama SP belum mengirimnya


def ambil_gt(mulai, akhir, kendali=None):
    """mulai, akhir: 'YYYYMMDD' tanggal GT. Satu panggilan untuk semua perusahaan, sama seperti query di Excel."""
    comp = ",".join(c.lower() for c in daftar_perusahaan(SUMBER))
    return per_perusahaan([comp], get_connection, f"EXEC {SP_GT} ?, ?, ?, ?, ?", lambda c: (c, SUMBER, mulai, akhir, "4"), kendali, boleh_kosong=True)


def ambil_pi(mulai, perusahaan=None, kendali=None):
    """mulai: 'YYYYMMDD', tanggal PR awal. SP selalu sampai data terbaru."""
    if perusahaan is None:
        perusahaan = daftar_perusahaan(SUMBER)
    return per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?", lambda comp: (comp, mulai), kendali, boleh_kosong=True)


def ambil_usage(mulai, kendali=None):
    """Usage barang PI HO sejak `mulai` ('YYYYMMDD') per perusahaan. Gagal dibaca: laporan tetap jalan tanpa usage (dicatat di log)."""
    bagian = []
    for comp, server, db in lokasi_perusahaan(SUMBER):
        if not server or not db:
            continue
        if not all(n.replace("_", "").isalnum() for n in (server, db)):
            log.warning("Usage %s dilewati: nama server/database tidak valid (%s.%s)", comp, server, db)
            continue
        if kendali:
            kendali.periksa()
        conn = get_connection()
        try:
            cur = conn.cursor()
            if kendali:
                kendali.daftarkan(cur)
            cur.execute(_USAGE.format(db=f"[{server}].[{db}].dbo"), f"{mulai[:4]}-{mulai[4:6]}-{mulai[6:8]}")
            kolom = [c[0] for c in cur.description]
            bagian.append(pd.DataFrame.from_records(cur.fetchall(), columns=kolom).assign(comp=comp))
        except Exception as e:
            log.warning("Usage %s tidak terbaca, barang yang langsung di-usage tetap dihitung belum GT: %s", comp, e)
        finally:
            conn.close()
    return pd.concat(bagian, ignore_index=True) if bagian else pd.DataFrame()


def tandai_usage(pi, usage):
    """Barang belum GT yang sudah di-usage: status Langsung usage, selesai pada tanggal usage (cocok per perusahaan, nomor PI, kode barang)."""
    for k in ("usage_number", "gudang_usage"):
        pi[k] = ""
    pi["usage_date"] = pd.NaT
    if pi.empty or usage.empty:
        return pi
    u = pd.DataFrame({"comp": _teks(usage["comp"]).str.upper(), "pi_number": _teks(usage["PurchaseNumber"]),
                      "itemcode": _teks(usage["ItemCode"]), "_tgl": _tanggal(usage["UsageDate"]),
                      "_no": _teks(usage["UsageNumber"]), "_gudang": _teks(usage["UsageWarehouse"])})
    u = u.sort_values("_tgl").drop_duplicates(["comp", "pi_number", "itemcode"])
    kunci = pi[["comp", "pi_number", "itemcode"]].assign(comp=pi["comp"].str.upper())
    cocok = kunci.merge(u, on=["comp", "pi_number", "itemcode"], how="left")
    ada = cocok["_tgl"].notna().to_numpy()
    pi.loc[ada, "status"] = USAGE
    pi.loc[ada, "usage_date"] = cocok.loc[ada, "_tgl"].to_numpy()
    pi.loc[ada, "usage_number"] = cocok.loc[ada, "_no"].to_numpy()
    pi.loc[ada, "gudang_usage"] = cocok.loc[ada, "_gudang"].to_numpy()
    return pi


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang."""
    m, a = mulai.replace("-", ""), akhir.replace("-", "")
    raw_gt = ambil_gt(m, a, kendali)
    raw_pi = ambil_pi(m, kendali=kendali)
    usage = ambil_usage(m, kendali)
    if kendali:
        kendali.periksa()
    d = gabung(bersihkan_gt(raw_gt), tandai_usage(bersihkan_pi(raw_pi), usage))
    d = d[d["tanggal"] <= pd.Timestamp(akhir)].reset_index(drop=True)
    return d, {"baris_gt": int(d["status"].isin([BELUM_DITERIMA, DITERIMA]).sum()), "baris_pi_belum_gt": int((d["status"] == BELUM_GT).sum()),
               "baris_langsung_usage": int((d["status"] == USAGE).sum())}


def _tanggal(seri):
    if pd.api.types.is_datetime64_any_dtype(seri):
        return seri
    if seri.dropna().map(lambda v: hasattr(v, "year")).all():
        return pd.to_datetime(seri, errors="coerce")
    # CheckStatItem: 'YYYYMMDD'; gt_out: 'YYYY-MM-DD HH:MM:SS'
    teks = seri.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    angka = pd.to_datetime(teks.where(teks.str.fullmatch(r"\d{8}")), format="%Y%m%d", errors="coerce")
    return angka.fillna(pd.to_datetime(teks.where(~teks.str.fullmatch(r"\d{8}", na=False)), errors="coerce", format="ISO8601"))


def _teks(seri):
    t = seri.astype("string").str.strip()
    return t.where(t.notna() & (t != "") & (t.str.upper() != "NULL"), "").astype(str)


def _nama(seri):
    """Nama orang ditulis beda-beda ("rizky ramadan", "Rizky Ramadan"): disamakan supaya satu orang satu baris."""
    return seri.str.split().str.join(" ").str.title()


def _periksa(raw, kolom, sp):
    hilang = [k for k in kolom if k not in raw.columns]
    if hilang:
        raise RuntimeError(f"Hasil SP {sp} tidak memuat kolom: {', '.join(hilang)}. Kolom yang ada: {', '.join(map(str, raw.columns))}")


def perlu_gt(d):
    """Barang PI yang perlu di-GT: di-PI di HO (lokasi di nomor PI, mis. YBS/PI/HO/2610/001) untuk gudang peminta selain HO.
    PI di gudang peminta sendiri, atau PI HO untuk HO, tidak perlu GT."""
    lokasi = d["pi_number"].str.split("/").str[2].fillna("").str.casefold()
    return lokasi.isin(GUDANG_HO) & ~d["peminta"].str.casefold().isin(GUDANG_HO | {""})


def bersihkan_gt(raw, hari_ini=None):
    """Satu baris per barang di GT. Lead time dihitung seperti kolom tambahan di Power Query Excel PI GT db."""
    if raw.empty:
        return pd.DataFrame()
    _periksa(raw, [*_GT_TEKS.values(), *_GT_TANGGAL.values(), "Quantity"], SP_GT)
    d = pd.DataFrame({
        **{k: _teks(raw[v]) for k, v in _GT_TEKS.items()},
        **{k: _tanggal(raw[v]) for k, v in _GT_TANGGAL.items()},
        "qty_gt": pd.to_numeric(raw["Quantity"], errors="coerce"),
    }).reset_index(drop=True)
    d = d[(d["gt_number"] != "") & (d["aging"].str.casefold() != "void") & d["gt_date"].notna()].reset_index(drop=True)
    d["status"] = DITERIMA
    d.loc[d["aging"].str.casefold() != "completed", "status"] = BELUM_DITERIMA
    d["gt_by"] = _nama(d["gt_by"]).replace("", "(kosong)")
    for k in ("dari_gudang", "ke_gudang", "importance"):
        d[k] = d[k].replace("", "(kosong)")

    hari_ini = pd.Timestamp(hari_ini or date.today())
    # Logistics Lead Time: tanggal GT sampai diterima; GT yang belum diterima dihitung sampai hari ini (seperti Excel)
    selesai = d["terima_date"].where(d["status"] == DITERIMA, hari_ini)
    d["lead_logistik"] = (selesai - d["gt_date"]).dt.days
    # Procurement Lead Time: tanggal PI sampai GT dibuat; kosong untuk GT tanpa PI
    d["lead_pengadaan"] = (d["gt_dibuat"] - d["pi_date"]).dt.days
    d["tanggal"] = d["gt_date"]
    d["perlu_gt"] = perlu_gt(d)   # hanya baris ini yang ikut alur outstanding (New PI, outstanding); GT-nya tetap dihitung semua
    return d.drop(columns=["aging", "gt_dibuat"])


def bersihkan_pi(raw, hari_ini=None):
    """Barang yang sudah PI tapi belum di-GT. Baris yang kembar persis (hasil join di SP) dihitung sekali."""
    if raw.empty:
        return pd.DataFrame()
    _periksa(raw, [*_PI_TEKS.values(), "PIDate", "QtyPI"], SP_NAME)
    raw = raw.drop_duplicates()
    d = pd.DataFrame({
        **{k: _teks(raw[v]) for k, v in _PI_TEKS.items()},
        **{k: _teks(raw[v]) if v in raw.columns else "" for k, v in _OPSIONAL.items()},
        "pi_date": _tanggal(raw["PIDate"]),
        "qty_pi": pd.to_numeric(raw["QtyPI"], errors="coerce"),
    }).reset_index(drop=True)
    d = d[(d["pi_number"] != "") & d["pi_date"].notna() & (d["gt_number"] == "")]
    d = d[perlu_gt(d)].reset_index(drop=True)
    d["importance"] = d["importance"].replace("", "(kosong)")
    d["pi_by"] = _nama(d["pi_by"])
    d["status"] = BELUM_GT
    d["perlu_gt"] = True
    d["umur_pi"] = (pd.Timestamp(hari_ini or date.today()) - d["pi_date"]).dt.days
    d["tanggal"] = d["pi_date"]
    return d.drop(columns=["gt_number"])


_SEMUA = ["comp", "status", "tanggal", "pr_number", "po_number", "pi_number", "pi_date", "pi_by", "peminta", "gt_number", "gt_date", "gt_by",
          "dari_gudang", "ke_gudang", "terima_date", "diterima_oleh", "lead_pengadaan", "lead_logistik", "umur_pi",
          "itemcode", "itemname", "uom", "qty_pi", "qty_gt", "importance", "perlu_gt", "usage_number", "usage_date", "gudang_usage"]
_TANGGAL_SEMUA = ("tanggal", "pi_date", "gt_date", "terima_date", "usage_date")
_ANGKA_SEMUA = ("lead_pengadaan", "lead_logistik", "umur_pi", "qty_pi", "qty_gt")


def gabung(gt, pi):
    """Satu tabel: baris GT (tanggal = tanggal GT) dan baris PI belum GT (tanggal = tanggal PI). Kolom yang tidak dimiliki diisi kosong."""
    bagian = [b.reindex(columns=_SEMUA) for b in (gt, pi) if not b.empty]
    d = pd.concat(bagian, ignore_index=True) if bagian else pd.DataFrame(columns=_SEMUA)
    for k in _SEMUA:
        if k in _TANGGAL_SEMUA:
            d[k] = pd.to_datetime(d[k])
        elif k in _ANGKA_SEMUA:
            d[k] = pd.to_numeric(d[k], errors="coerce")
        elif k == "perlu_gt":
            d[k] = d[k].fillna(False).astype(bool)
        else:
            d[k] = d[k].fillna("").astype(str)
    return d
