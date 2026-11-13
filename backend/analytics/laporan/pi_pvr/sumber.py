"""Laporan Purchase Invoice: PI beserta PVR dan PV yang memuat PI itu (item bertipe PI/PO, dicocokkan lewat ID). PI bisa dibayar PV tanpa
lewat PVR; status membedakannya.

Data mentah dari SP PI_PVR_SP (Main.dbo.PI_PVR, SQL-nya di backend/database/pi_pvr_sp.sql), dipanggil per perusahaan bersamaan. Di sini:
kurs ke rupiah (LineTotal x ExchangeRate), PVR yang void atau bersumber lain (PVRSource terisi) tidak dihitung, penggabungan nomor PVR/PV,
status, dan umur.
"""
import re
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.nama import orang, seragam
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

SUMBER = konfigurasi.SUMBER_LAPORAN
_NAMA_SQL = re.compile(r"^[A-Za-z0-9_]+$")   # nama server dan database disisipkan ke teks SQL, jadi hanya huruf, angka, dan _


def _nama(teks, apa, comp):
    if not _NAMA_SQL.match(teks or ""):
        raise RuntimeError(f"{apa} perusahaan {comp} di tabel company tidak valid: '{teks}'. Hanya huruf, angka, dan _.")
    return teks


def ambil_data(mulai, akhir, lokasi=None, kendali=None):
    """mulai dan akhir: date, akhir ikut dihitung."""
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    return per_perusahaan([l[0] for l in lokasi], get_connection, f"EXEC {konfigurasi.PI_PVR_SP} ?, ?, ?",
                          lambda comp: (comp, mulai.isoformat(), akhir.isoformat()), kendali, boleh_kosong=True, tandai=True)


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
    if raw.empty:
        raw = pd.DataFrame(columns=["__comp", "DetailID", "PONumber", "SupplierCode", "SupplierName", "PurchaseNumber", "PICreateDate", "QtyPI",
                                    "ItemCode", "ItemName", "LineTotal", "ExchangeRate", "PICreateBy", "PVRNumber", "PVRDate", "PVRCreateBy",
                                    "PVRCreateDate", "PVRVoid", "PVRSource", "PVNumber", "PVDate", "PVCreateBy"])
    # PVR yang void atau bersumber lain (PVRSource terisi) tidak dihitung: kolom PVR-nya dikosongkan, baris PI tetap ada
    abaikan = raw["PVRVoid"].fillna(False).astype(bool) | (_teks(raw["PVRSource"]) != "")
    raw = raw.copy()
    raw.loc[abaikan, ["PVRNumber", "PVRDate", "PVRCreateDate", "PVRCreateBy"]] = None
    kurs = pd.to_numeric(raw["ExchangeRate"], errors="coerce").fillna(1)
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
        "line_total": pd.to_numeric(raw["LineTotal"], errors="coerce") * kurs,
        "pi_by": _teks(raw["PICreateBy"]),
        "pvr_number": _teks(raw["PVRNumber"]),
        "pvr_date": pd.to_datetime(raw["PVRDate"], errors="coerce").dt.normalize(),
        "pvr_by": _teks(raw["PVRCreateBy"]),
        # Tanggal PVR dibuat di sistem: dipakai untuk lama PI ke PVR, karena VoucherDate kadang salah ketik (mis. tahun 1968)
        "pvr_dibuat": pd.to_datetime(raw["PVRCreateDate"], errors="coerce").dt.normalize(),
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
    for kolom in ("pi_by", "pvr_by", "pv_by"):
        d[kolom] = orang(d[kolom])
    d["supplier_name"] = seragam(d["supplier_name"])
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
