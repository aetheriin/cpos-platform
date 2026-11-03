"""Laporan Penerimaan TBS: ambil detail pembelian TBS dari stored procedure dan bersihkan."""
import re
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.banding import jendela_sebelumnya
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan

SP_NAME = konfigurasi.SP_TBS
SUMBER = konfigurasi.SUMBER_TBS
FORMAT_TANGGAL = konfigurasi.FORMAT_TANGGAL_TBS

# Kolom hasil SP -> nama di program (huruf besar-kecil, spasi, dan garis bawah diabaikan).
WAJIB = {
    "PURCHASEID": "purchase_id", "DETAILID": "detail_id", "PURCHASEDATE": "tgl", "LINETOTAL": "nilai", "NETTO": "netto",
    "PRICEPERKG": "harga", "SupplierName": "supplier", "BUSINESSGROUPNAME": "grup", "SUPPLIERTYPECODE": "tipe", "Company": "comp",
    "Category": "kategori",
}
ANGKA = ["nilai", "netto", "harga"]
TEKS = ["supplier", "grup", "tipe", "comp", "kategori"]
KOSONG = "(kosong)"
NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _kunci(nama):
    return re.sub(r"[^a-z0-9]", "", str(nama).lower())


def ambil_data(tgl_mulai, tgl_akhir, perusahaan=None, kendali=None):
    if perusahaan is None:
        perusahaan = daftar_perusahaan(SUMBER)
    return per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?, ?", lambda comp: (comp, tgl_mulai, tgl_akhir), kendali,
                          boleh_kosong=True)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Periode sebelumnya ikut diambil (kolom `lalu`) untuk pembanding KPI dan riwayat forecast."""
    mulai_lalu, _ = jendela_sebelumnya(mulai, akhir)
    raw = ambil_data(mulai_lalu.strftime(FORMAT_TANGGAL), date.fromisoformat(akhir).strftime(FORMAT_TANGGAL), kendali=kendali)
    if kendali:
        kendali.periksa()
    d = bersihkan(raw)
    d["lalu"] = d["tgl"] < pd.Timestamp(mulai)
    return d, {"baris_sp": int((~d["lalu"]).sum())}


def bersihkan(raw):
    ada = {_kunci(c): c for c in raw.columns}
    hilang = [k for k in WAJIB if _kunci(k) not in ada]
    if hilang:
        raise RuntimeError(f"Hasil SP {SP_NAME} tidak memuat kolom yang dibutuhkan: {', '.join(hilang)}. Kolom yang ada: {', '.join(map(str, raw.columns))}")
    d = pd.DataFrame({baru: raw[ada[_kunci(lama)]] for lama, baru in WAJIB.items()})
    d["tgl"] = pd.to_datetime(d["tgl"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True), format="%Y%m%d", errors="coerce")
    d = d[d["tgl"].notna()]
    for k in ANGKA:
        d[k] = pd.to_numeric(d[k], errors="coerce").astype(float)
    for k in TEKS:
        t = d[k].astype("string").str.strip()
        d[k] = t.where(t.notna() & (t != ""), KOSONG).astype(str)
    d["purchase_id"] = d["purchase_id"].astype(str)
    d["hari"] = d["tgl"].dt.strftime("%Y-%m-%d")
    d["nama_hari"] = d["tgl"].dt.weekday.map(dict(enumerate(NAMA_HARI)))
    return d.reset_index(drop=True)
