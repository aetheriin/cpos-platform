"""Laporan PO Spend Analysis: ambil PO dari SP, perbaiki kurs yang janggal atau kosong, lalu hitung nilai rupiah dan kategorinya.

Urutan kurs: kurs di PO; kalau janggal, kurs PO lain dengan mata uang sama pada tanggal terdekat; kalau tidak ada, kurs internet
pada tanggal PO. Kurs internet disimpan di kurs_internet.json supaya tidak diambil ulang dan tetap tersedia tanpa internet.
"""
import json
import logging
import urllib.request
from pathlib import Path

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection

log = logging.getLogger(__name__)
BERKAS_KURS = Path(__file__).with_name("kurs_internet.json")
URL_KURS = "https://api.frankfurter.dev/v1/{tgl}?base={uang}&symbols=IDR"   # kurs acuan ECB
BATAS_JANGGAL = 2   # kurs lebih dari 2x atau kurang dari setengah nilai tengah mata uangnya dianggap janggal

# (batas atas nilai rupiah, nama), sama dengan SP_R_PO_AMT
KATEGORI = [(1_000_000, "<= 1JT"), (5_000_000, "1JT - 5JT"), (10_000_000, "5JT - 10JT"), (50_000_000, "10JT - 50JT"),
            (100_000_000, "50JT - 100JT"), (500_000_000, "100JT - 500JT"), (float("inf"), "> 500JT")]
NAMA_KATEGORI = [n for _, n in KATEGORI]
NAMA_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def ambil_data(kendali=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if kendali:
            kendali.daftarkan(cur)
        cur.execute(f"EXEC {konfigurasi.SP_PO_AMT}")
        while cur.description is None:
            if not cur.nextset():
                raise RuntimeError("SP PO Spend Analysis tidak mengembalikan tabel hasil")
        return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description])
    finally:
        conn.close()


def _baca_simpanan():
    try:
        return json.loads(BERKAS_KURS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _kurs_internet(uang, tanggal, simpanan):
    """Kurs rupiah pada tanggal itu, atau None kalau belum tersimpan dan internet tidak bisa dihubungi."""
    kunci = f"{uang}|{tanggal}"
    if kunci not in simpanan:
        try:
            req = urllib.request.Request(URL_KURS.format(tgl=tanggal, uang=uang), headers={"User-Agent": "cpos-analytics"})
            with urllib.request.urlopen(req, timeout=8) as r:
                simpanan[kunci] = float(json.load(r)["rates"]["IDR"])
        except Exception as e:
            log.warning("Kurs %s tanggal %s tidak bisa diambil: %s", uang, tanggal, e)
            return None
    return simpanan[kunci]


def perbaiki_kurs(d):
    """Mengisi kolom kurs, kurs_asal, dan kurs_po. Mengembalikan d."""
    d["kurs_po"] = d["kurs"]
    d["kurs_asal"] = "PO"
    asing = d["uang"] != "IDR"
    terisi = d["kurs"].where(asing & (d["kurs"] > 1))
    tengah = terisi.groupby(d["uang"]).transform("median")
    janggal = asing & (terisi.isna() | (terisi > tengah * BATAS_JANGGAL) | (terisi < tengah / BATAS_JANGGAL))
    acuan = d[asing & ~janggal]
    simpanan = _baca_simpanan()
    awal = len(simpanan)
    for i, r in d[janggal].iterrows():
        calon = acuan[acuan["uang"] == r["uang"]]
        if len(calon):
            j = (calon["tgl"] - r["tgl"]).abs().idxmin()
            d.at[i, "kurs"], d.at[i, "kurs_asal"] = calon.at[j, "kurs"], f"PO terdekat {calon.at[j, 'po']}"
            continue
        nilai = _kurs_internet(r["uang"], r["tgl"].strftime("%Y-%m-%d"), simpanan)
        d.at[i, "kurs"], d.at[i, "kurs_asal"] = (nilai, "Internet (ECB)") if nilai else (1.0, "Belum ada")
    if len(simpanan) != awal:
        try:
            BERKAS_KURS.write_text(json.dumps(simpanan, indent=0, sort_keys=True), encoding="utf-8")
        except OSError as e:
            log.warning("Kurs internet tidak bisa disimpan: %s", e)
    return d


def _kategori(nilai):
    v = round(nilai)
    return next(n for batas, n in KATEGORI if v <= batas)


def bersihkan(raw):
    d = pd.DataFrame({
        "comp": raw["COMPID"].astype(str).str.strip(),
        "po": raw["PONUMBER"].astype(str).str.strip(),
        "supplier": raw["SUPPLIERNAME"].fillna("").astype(str).str.strip(),
        "nilai_po": pd.to_numeric(raw["NETTOTALPO"]).astype(float),
        "uang": raw["CURRENCYNAME"].astype(str).str.strip(),
        "kurs": pd.to_numeric(raw["EXCRATE"]).astype(float),
        "tgl": pd.to_datetime(raw["CREATEDATE"]),
    })
    perbaiki_kurs(d)
    d["nilai_idr"] = d["nilai_po"] * d["kurs"]
    d["kategori"] = d["nilai_idr"].map(_kategori)
    d["tahun"] = d["tgl"].dt.year.astype(str)
    d["bulan"] = d["tgl"].dt.month.map(lambda m: NAMA_BULAN[m - 1])
    return d


def muat(mulai, akhir, kendali=None):
    """SP selalu mengembalikan semua PO; rentang dipotong setelah kurs diperbaiki, supaya kurs terdekat bisa dari luar rentang."""
    d = bersihkan(ambil_data(kendali))
    if kendali:
        kendali.periksa()
    d = d[(d["tgl"] >= pd.Timestamp(mulai)) & (d["tgl"] <= pd.Timestamp(akhir))].reset_index(drop=True)
    return d, {"baris_sp": len(d)}
