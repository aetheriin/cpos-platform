"""Laporan Tiket Penjualan: ambil tiket timbang produk keluar dari SP TIKET_PENJUALAN dan rapikan.

SP membaca PALM_Tickets tiap perusahaan lewat server tertaut (tabel company). Nama pengangkutan adalah kolom Contractor di tiket (isian
"Nama Pengangkutan" di layar timbangan Ascend). Tiket split sudah diwakili tiket induknya oleh SP; pecahannya tidak ikut."""
import re
from datetime import date, timedelta

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.nama import seragam
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan

SP_NAME = konfigurasi.SP_TIKET_PENJUALAN
SUMBER = konfigurasi.SUMBER_TIKET_PENJUALAN

# Kolom hasil SP -> nama di program (huruf besar-kecil, spasi, titik, dan garis bawah diabaikan).
WAJIB = {
    "Tanggal": "tgl", "Jam Masuk": "jam_masuk", "Jam Keluar": "jam_keluar", "Nama Pembeli": "pembeli", "Nomor DO": "no_do", "Produk": "produk",
    "Nama Pengangkutan": "pengangkut", "No. Tiket": "tiket", "No. Kendaraan": "kendaraan", "Nama Supir": "supir", "Nomor Kontrak": "kontrak",
    "Bruto": "bruto", "Tara": "tara", "Potongan": "potongan", "Netto": "netto", "Netto Sumber": "netto_sumber", "FFA": "ffa",
    "Kadar Air": "air", "Kadar Kotoran": "kotoran", "Dobi": "dobi", "Split": "split",
}
ANGKA = ["bruto", "tara", "potongan", "netto", "netto_sumber", "ffa", "air", "kotoran", "dobi"]
TEKS = ["pembeli", "no_do", "pengangkut", "tiket", "kendaraan", "supir", "kontrak"]
# Nama produk di Ascend yang ditulis rapat; yang lain tampil apa adanya.
NAMA_PRODUK = {"janjangkosong": "Janjang Kosong", "lainlain": "Lain-lain"}


_BADAN_DEPAN = re.compile(r"^(PT|CV|UD|PD)(\s*[.,]\s*|\s+)", re.I)
_BADAN_BELAKANG = re.compile(r"[\s.,]+(PT|CV|UD|PD)\s*\.?$", re.I)


def _kunci(nama):
    return re.sub(r"[^a-z0-9]", "", str(nama).lower())


def badan_di_depan(nama):
    """Bentuk badan usaha ditulis di depan tanpa titik, supaya satu perusahaan tidak tampil dua kali:
    'JASA SAHABAT ABADI .CV', 'CV. JASA SAHABAT ABADI', dan 'CV JASA SAHABAT ABADI' -> 'CV JASA SAHABAT ABADI'."""
    n = str(nama).strip()
    if not n:
        return n
    m = _BADAN_BELAKANG.search(n)
    if m:
        return f"{m.group(1).upper()} {n[:m.start()].strip(' .,')}"
    m = _BADAN_DEPAN.match(n)
    if m:
        return f"{m.group(1).upper()} {n[m.end():].strip(' .,')}"
    return n


def ambil_data(mulai, akhir, perusahaan=None, kendali=None):
    if perusahaan is None:
        perusahaan = daftar_perusahaan(SUMBER)
    return per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?, ?", lambda comp: (comp, mulai, akhir), kendali,
                          boleh_kosong=True, tandai=True)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. TIKET_PENJUALAN_HARI_LALU hari sebelum `mulai` ikut diambil (kolom `lalu`) supaya bulan pertama pun punya
    pembanding di kartu."""
    awal = (date.fromisoformat(mulai) - timedelta(days=konfigurasi.TIKET_PENJUALAN_HARI_LALU)).isoformat()
    raw = ambil_data(awal, akhir, kendali=kendali)
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
    d["comp"] = raw["__comp"].astype(str).str.strip()
    d["tgl"] = pd.to_datetime(d["tgl"], errors="coerce").dt.normalize()
    d = d[d["tgl"].notna()]
    for k in ANGKA:
        d[k] = pd.to_numeric(d[k], errors="coerce").fillna(0.0).astype(float)
    for k in TEKS:
        t = d[k].astype("string").fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
        d[k] = t.astype(str)
    # nama yang hanya beda huruf besar-kecil (KERNEL dan Kernel) atau letak badan usahanya disatukan ke ejaan yang paling sering
    d["pembeli"] = seragam(d["pembeli"].map(badan_di_depan))
    d["pengangkut"] = seragam(d["pengangkut"].map(badan_di_depan))
    produk = seragam(d["produk"].astype("string").fillna("").astype(str))
    d["produk"] = produk.map(lambda p: NAMA_PRODUK.get(_kunci(p), p) or "(tanpa produk)")
    d["split"] = d["split"].astype("string").fillna("").str.strip().eq("Ya").map({True: "Ya", False: ""})
    d["jam"] = d["jam_keluar"].astype("string").fillna("").str[:2]
    d["jam"] = d["jam"].where(d["jam"].str.fullmatch(r"\d\d"), "")
    for k in ("jam_masuk", "jam_keluar"):
        d[k] = d[k].astype("string").fillna("").str[:5].astype(str)
    d["hari"] = d["tgl"].dt.strftime("%Y-%m-%d")
    return d.reset_index(drop=True)
