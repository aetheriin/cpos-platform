"""Laporan Pembelian TBS Mingguan: tonase per minggu per business group dari stored procedure mingguan.

SP dipanggil satu kali per perusahaan (parameter company, tanggal awal, tanggal akhir). Minggu dari SP: Senin sampai Minggu, minggu
pertama dan terakhir dipotong ke periode. Kolom MEAN, STD_DEV, dan ATTENSI dari SP tidak dipakai: SP menghitungnya per baris (grup dan
jenis kebun) tanpa minggu kosong, sedangkan laporan ini menghitung per grup dengan minggu tanpa kiriman = 0 kg (lihat ukuran.py)."""
import re
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan

SP_NAME = konfigurasi.SP_TBS_MINGGUAN
SUMBER = konfigurasi.SUMBER_TBS
FORMAT_TANGGAL = konfigurasi.FORMAT_TANGGAL_TBS

WAJIB = {
    "TANGGAL_AWAL": "awal", "TANGGAL_AKHIR": "akhir", "JENIS_KEBUN": "tipe", "GROUP": "grup", "KATEGORI": "kategori",
    "TONASE_KG": "netto", "TOTAL_LINETOTAL": "nilai",
}
TEKS = ["tipe", "grup", "kategori"]
KOSONG = "(kosong)"


def _kunci(nama):
    return re.sub(r"[^a-z0-9]", "", str(nama).lower())


def muat(mulai, akhir, kendali=None):
    perusahaan = daftar_perusahaan(SUMBER)
    ubah = lambda t: date.fromisoformat(t).strftime(FORMAT_TANGGAL)
    raw = per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?, ?", lambda comp: (comp, ubah(mulai), ubah(akhir)), kendali,
                         boleh_kosong=True, tandai=True)
    if kendali:
        kendali.periksa()
    d = bersihkan(raw)
    return d, {"baris_sp": int(len(d))}


def bersihkan(raw):
    ada = {_kunci(c): c for c in raw.columns}
    hilang = [k for k in WAJIB if _kunci(k) not in ada]
    if hilang:
        raise RuntimeError(f"Hasil SP {SP_NAME} tidak memuat kolom yang dibutuhkan: {', '.join(hilang)}. Kolom yang ada: {', '.join(map(str, raw.columns))}")
    d = pd.DataFrame({baru: raw[ada[_kunci(lama)]] for lama, baru in WAJIB.items()})
    d["comp"] = raw["__comp"].astype(str).str.upper()
    for k in ("awal", "akhir"):
        d[k] = pd.to_datetime(d[k], errors="coerce")
    d = d[d["awal"].notna() & d["akhir"].notna()]
    for k in ("netto", "nilai"):
        d[k] = pd.to_numeric(d[k], errors="coerce").fillna(0.0).astype(float)
    for k in TEKS:
        t = d[k].astype("string").str.strip()
        d[k] = t.where(t.notna() & (t != ""), KOSONG).astype(str)
    d["minggu"] = d["awal"].dt.strftime("%Y-%m-%d")
    return d.reset_index(drop=True)
