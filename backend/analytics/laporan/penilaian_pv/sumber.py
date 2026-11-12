"""Laporan PV KPI: skor kasir pembuat PV menurut kategori (Check Number) dan bobotnya, sama dengan Excel Penilaian PV.

Aturan hitung dan pembersihan sama dengan PVR KPI (laporan.penilaian_pvr.sumber); yang beda hanya sumber datanya (PV hutang, FI_ARAP
IsAR = 0) dan tabel bobot (Bobot_PV). Satu baris per item PV, ditambah item lain-lain dan potongan PPh.

Data mentah dari SP PENILAIAN_PV_SP (Main.dbo.PENILAIAN_PV, SQL-nya di backend/database/penilaian_pv_sp.sql), dipanggil per perusahaan
bersamaan. Di sini: nomor dokumen (ItemRef), label dan tanda potongan PPh, nama supplier, Check Number kosong diisi dari histori supplier,
kategori, bobot, dan item pertama per PV.
"""
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

from ..penilaian_pvr.sumber import SUMBER, _kosong_jadi_na, _REF_DOKUMEN, ambil_bobot, bersihkan

_URUT_BAGIAN = {"ITEM": 0, "LAIN": 1, "PPH": 2}   # item pertama per PV: item dokumen, lalu lain-lain, lalu potongan PPh


def ambil_data(mulai, akhir, lokasi=None, kendali=None):
    """mulai dan akhir: date, akhir ikut dihitung."""
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    d = per_perusahaan([l[0] for l in lokasi], get_connection, f"EXEC {konfigurasi.PENILAIAN_PV_SP} ?, ?, ?",
                       lambda comp: (comp, mulai.isoformat(), akhir.isoformat()), kendali, boleh_kosong=True, tandai=True)
    return d.drop(columns=["CompID"], errors="ignore")


def rakit(raw):
    """Data mentah SP jadi bentuk yang dibaca isi_dari_histori() dan bersihkan()."""
    if raw.empty:
        return pd.DataFrame(columns=["__comp", "VoucherDate", "VoucherNo", "ItemRef", "CheckNumber", "ItemAmountPaid", "CreatedBy",
                                     "SupplierName", "Source", "Urut"])
    bagian = raw["Bagian"].fillna("").astype(str).str.strip()
    jenis = raw["ItemType"].fillna("").astype(str).str.strip()
    ket = _kosong_jadi_na(raw["Keterangan"])
    jumlah = pd.to_numeric(raw["Jumlah"], errors="coerce")
    # Item dokumen: nomor dokumen asal menurut jenisnya, lalu Remarks. Lain-lain: keterangannya. PPh: "Pot. PPh <jenis>", nilainya negatif.
    dok = pd.Series(pd.NA, index=raw.index, dtype="string")
    for kolom, jenis_ini in _REF_DOKUMEN.items():
        dok = dok.mask(jenis.isin(jenis_ini), raw[kolom].astype("string"))
    pph = bagian == "PPH"
    ref = dok.fillna(ket).mask(pph, "Pot. PPh " + raw["Keterangan"].astype("string").fillna(""))
    sumber = jenis.mask(bagian == "LAIN", "Others").mask(pph, "PPh")
    urut = bagian.map(_URUT_BAGIAN).fillna(9) * 1e10 + pd.to_numeric(raw["Urut"], errors="coerce").fillna(0)
    return pd.DataFrame({
        "__comp": raw["__comp"],
        "VoucherDate": pd.to_datetime(raw["VoucherDate"], errors="coerce").dt.normalize(),
        "VoucherNo": raw["VoucherNo"],
        "ItemRef": ref,
        "CheckNumber": _kosong_jadi_na(raw["CheckNo"]),
        "ItemAmountPaid": jumlah.mask(pph, -jumlah.abs()),
        "CreatedBy": raw["CreatedBy"],
        "SupplierName": raw["SupplierName"].astype("string").fillna(_kosong_jadi_na(raw["AssociateName"])).fillna(_kosong_jadi_na(raw["AnonymName"])),
        "Source": sumber,
        "Urut": urut,
    })


def isi_dari_histori(raw):
    """PV tanpa Check Number diberi Check Number yang paling sering dipakai supplier yang sama di perusahaan itu, seperti sheet
    MasterSupplier di Excel (dan histori supplier di query PVR). Hanya PV pada periode yang dimuat yang dipakai sebagai acuan."""
    raw = raw.copy()
    cek = raw["CheckNumber"].fillna("").astype(str).str.strip()
    ada = raw.assign(cek=cek, supplier=raw["SupplierName"].fillna("").astype(str).str.strip())
    ada = ada[(ada["cek"] != "") & (ada["supplier"] != "")].drop_duplicates(["__comp", "VoucherNo"])
    paling = ada.groupby(["__comp", "supplier"])["cek"].agg(lambda s: s.value_counts().index[0])
    kunci = list(zip(raw["__comp"], raw["SupplierName"].fillna("").astype(str).str.strip()))
    dari_histori = [paling.get(k, "") for k in kunci]
    kosong = cek == ""
    raw["CheckNoSource"] = "Asli"
    raw.loc[kosong, "CheckNumber"] = [v for v, k in zip(dari_histori, kosong) if k]
    raw.loc[kosong, "CheckNoSource"] = ["Histori Supplier" if v else "Kosong" for v, k in zip(dari_histori, kosong) if k]
    return raw


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang."""
    raw = rakit(ambil_data(date.fromisoformat(mulai), date.fromisoformat(akhir), kendali=kendali))
    bobot = ambil_bobot(konfigurasi.PV_TABEL_BOBOT)
    if kendali:
        kendali.periksa()
    d = bersihkan(isi_dari_histori(raw) if not raw.empty else raw, bobot)
    return d, {"baris_dinilai": len(d)}
