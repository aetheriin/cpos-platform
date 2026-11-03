"""Laporan Purchase Invoice: PI beserta PVR yang menyebut nomor PI itu di kolom details, dan PV yang membayar PI itu (item PV bertipe
PI/PO), langsung lewat OPENQUERY ke database tiap perusahaan. PI bisa dibayar PV tanpa lewat PVR; status membedakannya.

Server tertaut dan nama database diambil dari tabel company (CompAddr, CompDataBase), jadi perusahaan baru langsung ikut.
"""
import re
from datetime import date, timedelta

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

SUMBER = konfigurasi.SUMBER_LAPORAN
_NAMA_SQL = re.compile(r"^[A-Za-z0-9_]+$")   # nama server dan database disisipkan ke teks SQL, jadi hanya huruf, angka, dan _

# {db}, {mulai}, dan {akhir} diisi per perusahaan.
_QUERY = """
    SELECT
        pi.PONumbers AS PONumber,
        s.SupplierCode AS SupplierCode,
        s.SupplierName AS SupplierName,
        pid.PurchaseDetailID AS DetailID,
        pi.PurchaseNumber,
        pi.PurchaseDate AS PIDate,
        pid.Quantity AS QtyPI,
        it.ItemCode,
        it.ItemName,
        (pid.LineTotal * ISNULL(pi.ExchangeRate, 1)) AS LineTotal,
        pvr.VoucherNo AS PVRNumber,
        pvr.VoucherDate AS PVRDate,
        pi.CreateDate AS PICreateDate,
        pi.CreatedBy AS PICreateBy,
        pvr.CreateDate AS PVRCreateDate,
        pvr.CreatedBy AS PVRCreateBy,
        pv.VoucherNo AS PVNumber,
        pv.VoucherDate AS PVDate,
        pv.CreatedBy AS PVCreateBy
    FROM {db}.dbo.ap_purchases pi
    INNER JOIN {db}.dbo.ap_purchasedetails pid
        ON pid.PurchaseID = pi.PurchaseID
    LEFT JOIN {db}.dbo.ic_items it
        ON it.ItemID = pid.ItemID
    LEFT JOIN {db}.dbo.ap_suppliers s
        ON s.SupplierID = pi.SupplierID
    LEFT JOIN {db}.dbo.fi_aprequest pvr
        ON CHARINDEX(RTRIM(LTRIM(pi.PurchaseNumber)), pvr.Details) > 0
        AND TRIM(ISNULL(pvr.PVRSource, '''')) = ''''
    LEFT JOIN (
        SELECT i.ItemID, v.VoucherNo, v.VoucherDate, v.CreatedBy
        FROM {db}.dbo.FI_ARAPItems i
        JOIN {db}.dbo.FI_ARAP v
            ON v.VoucherID = i.VoucherID
        WHERE i.ItemType IN (''PI'', ''PO'')
          AND v.IsAR = 0
          AND ISNULL(v.Void, 0) = 0
    ) pv
        ON pv.ItemID = pi.PurchaseID
    WHERE pi.PurchaseDate >= ''{mulai}'' AND pi.PurchaseDate < ''{akhir}''
      AND ISNULL(pi.Void, 0) = 0
      AND pi.PurchaseNumber LIKE ''%/PI/%''
"""


def _nama(teks, apa, comp):
    if not _NAMA_SQL.match(teks or ""):
        raise RuntimeError(f"{apa} perusahaan {comp} di tabel company tidak valid: '{teks}'. Hanya huruf, angka, dan _.")
    return teks


def perintah(lokasi, mulai, akhir):
    """lokasi: (nama, server, database). mulai dan akhir: date, akhir ikut dihitung."""
    comp, server, db = lokasi
    isi = _QUERY.format(db=_nama(db, "CompDataBase", comp), mulai=mulai.isoformat(), akhir=(akhir + timedelta(days=1)).isoformat())
    return f"SELECT * FROM OPENQUERY([{_nama(server, 'CompAddr', comp)}], '{isi}')"


def ambil_data(mulai, akhir, lokasi=None, kendali=None):
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    peta = {l[0]: l for l in lokasi}
    return per_perusahaan(list(peta), get_connection, lambda comp: perintah(peta[comp], mulai, akhir), lambda comp: (), kendali,
                          boleh_kosong=True, tandai=True)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang."""
    raw = ambil_data(date.fromisoformat(mulai), date.fromisoformat(akhir), kendali=kendali)
    if kendali:
        kendali.periksa()
    d = bersihkan(raw)
    return d, {"baris_sp": len(d)}


def _teks(seri):
    return seri.fillna("").astype(str).str.strip()


def _gabung(nilai):
    return ", ".join(dict.fromkeys(v for v in nilai if v))


# Status tiap baris PI, urut dari yang paling perlu ditindaklanjuti
BELUM, PV_TANPA_PVR, PVR_BELUM_PV, LENGKAP = "Belum PVR & PV", "PV tanpa PVR", "PVR, belum PV", "PVR & PV"
URUTAN_STATUS = [BELUM, PV_TANPA_PVR, PVR_BELUM_PV, LENGKAP]


def bersihkan(raw):
    """Satu baris per baris PI. PI yang disebut beberapa PVR atau dibayar beberapa PV digabung: nomor dipisah koma, tanggal yang paling awal."""
    for k in ("PVNumber", "PVDate", "PVCreateBy"):   # data lama tanpa kolom PV
        if k not in raw.columns:
            raw = raw.assign(**{k: None})
    d = pd.DataFrame({
        "comp": _teks(raw["__comp"]),
        "detail_id": _teks(raw["DetailID"].astype(str).str.replace(r"\.0$", "", regex=True)),
        "po_number": _teks(raw["PONumber"]),
        "supplier_code": _teks(raw["SupplierCode"]),
        "supplier_name": _teks(raw["SupplierName"]),
        "pi_number": _teks(raw["PurchaseNumber"]),
        "pi_date": pd.to_datetime(raw["PICreateDate"], errors="coerce").dt.normalize(),
        "qty": pd.to_numeric(raw["QtyPI"], errors="coerce"),
        "itemcode": _teks(raw["ItemCode"]),
        "itemname": _teks(raw["ItemName"]),
        "line_total": pd.to_numeric(raw["LineTotal"], errors="coerce"),
        "pi_by": _teks(raw["PICreateBy"]),
        "pvr_number": _teks(raw["PVRNumber"]),
        "pvr_date": pd.to_datetime(raw["PVRDate"], errors="coerce").dt.normalize(),
        "pvr_by": _teks(raw["PVRCreateBy"]),
        # Tanggal PVR dibuat di sistem: dipakai untuk lama PI ke PVR, karena VoucherDate kadang salah ketik (mis. tahun 1968)
        "pvr_dibuat": pd.to_datetime(raw["PVRCreateDate"] if "PVRCreateDate" in raw.columns else raw["PVRDate"], errors="coerce").dt.normalize(),
        "pv_number": _teks(raw["PVNumber"]),
        "pv_date": pd.to_datetime(raw["PVDate"], errors="coerce").dt.normalize(),
        "pv_by": _teks(raw["PVCreateBy"]),
    })
    d = (
        d.sort_values("pvr_date", na_position="last", kind="stable")
        .groupby(["comp", "detail_id"], sort=False, as_index=False)
        .agg(po_number=("po_number", "first"), supplier_code=("supplier_code", "first"), supplier_name=("supplier_name", "first"),
             pi_number=("pi_number", "first"), pi_date=("pi_date", "first"), qty=("qty", "first"), itemcode=("itemcode", "first"),
             itemname=("itemname", "first"), line_total=("line_total", "first"), pi_by=("pi_by", "first"), pvr_number=("pvr_number", _gabung),
             pvr_date=("pvr_date", "min"), pvr_by=("pvr_by", _gabung), pvr_dibuat=("pvr_dibuat", "min"),
             pv_number=("pv_number", _gabung), pv_date=("pv_date", "min"), pv_by=("pv_by", _gabung))
    )
    d["sudah_pvr"] = d["pvr_number"] != ""
    d["sudah_pv"] = d["pv_number"] != ""
    d["status"] = BELUM
    d.loc[~d["sudah_pvr"] & d["sudah_pv"], "status"] = PV_TANPA_PVR
    d.loc[d["sudah_pvr"] & ~d["sudah_pv"], "status"] = PVR_BELUM_PV
    d.loc[d["sudah_pvr"] & d["sudah_pv"], "status"] = LENGKAP
    hari_ini = pd.Timestamp(date.today())
    d["umur"] = (hari_ini - d["pi_date"]).dt.days
    d["lama_pvr"] = (d["pvr_dibuat"] - d["pi_date"]).dt.days   # kedua tanggal dicatat sistem saat dokumen dibuat
    d["lama_pv"] = (d["pv_date"] - d["pi_date"]).dt.days
    return d.reset_index(drop=True)
