"""Bantuan uji: menyiapkan data contoh (dari file Excel) sebagai pengganti hasil stored procedure.

Letakkan pr_po_db.xlsx dan po_pi_db.xlsx di backend/tests/data/ (atau atur variabel DATA_UJI ke foldernya).
Uji yang membutuhkan Excel dilewati kalau filenya tidak ada."""
import functools
import json
import os
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))
import stub  # noqa: E402

stub.pasang()

import pandas as pd  # noqa: E402

DATA = Path(os.environ.get("DATA_UJI", TESTS / "data"))

# Pemetaan kategori contoh (salinan isi dbo.MappingCategory) menggantikan pembacaan tabel, supaya uji tidak butuh SQL Server
PETA_KATEGORI = json.loads((TESTS / "kategori_contoh.json").read_text(encoding="utf-8"))
from inti import kategori as _kategori  # noqa: E402

BACA_PETA_ASLI = _kategori.baca_peta   # untuk uji pembacaan tabel itu sendiri
_kategori.baca_peta = lambda *a, **k: PETA_KATEGORI


class Lewati(Exception):
    pass


def lewati(pesan):
    try:
        import pytest
        pytest.skip(pesan)
    except ImportError:
        raise Lewati(pesan)


def butuh(nama):
    p = DATA / nama
    if not p.exists():
        lewati(f"{nama} tidak ada di {DATA}")
    return p


def butuh_data():
    """Lewati uji ini kalau data contoh (kedua berkas Excel) tidak ada."""
    butuh("pr_po_db.xlsx")
    butuh("po_pi_db.xlsx")


def lima_minggu(jangkar, jumlah=5):
    """(dari, sampai) untuk rentang tampilan yang sama dengan cara lama "jumlah minggu Jumat-Kamis sampai minggu yang memuat jangkar".
    Uji laporan mingguan ditulis dengan patokan itu; dashboard sekarang menerima rentang tanggal (filter tanggal)."""
    from inti.laporan import awal_minggu

    s = awal_minggu(jangkar)
    return s - pd.Timedelta(days=7 * (jumlah - 1)), s + pd.Timedelta(days=6)


BUKAN_FILTER = {"laporan_id", "data_id", "jenis", "jumlah_minggu", "minggu", "dari", "sampai", "cari", "urut", "arah", "halaman", "ukuran", "user"}


def dengan_permintaan(argumen):
    """Argumen endpoint untuk uji: filter (perusahaan=[...], dst.) dipindah ke Request, seperti yang dikirim browser lewat URL."""
    from urllib.parse import urlencode

    from starlette.requests import Request

    a = {k: v for k, v in argumen.items() if k in BUKAN_FILTER}
    pasangan = [(k, x) for k, v in argumen.items() if k not in BUKAN_FILTER and v for x in ([v] if isinstance(v, str) else v)]
    a["request"] = Request({"type": "http", "query_string": urlencode(pasangan).encode(), "headers": []})
    return a


def kode(e):
    """Kode HTTP dari HTTPException asli atau pengganti."""
    return getattr(e, "status_code", None)


def balik_kategori(comp, kat):
    peta = {c: {v: k for k, v in t.items()} for c, t in PETA_KATEGORI.items()}
    return [peta.get(c, {}).get(k, k) if pd.notna(k) else k for c, k in zip(comp, kat)]


@functools.lru_cache(maxsize=None)
def raw_pr_po():
    """Bentuk mentah keluaran SP PR/PO: satu baris per PR line, kategori kembali ke bentuk sebelum dipetakan."""
    raw = pd.read_excel(butuh("pr_po_db.xlsx"), sheet_name="DATA").drop_duplicates("COMPPRDETAILID").copy()
    raw["CATEGORY"] = balik_kategori(raw["COMPID"], raw["CATEGORY"])
    return raw


@functools.lru_cache(maxsize=None)
def raw_po_pi():
    """Bentuk mentah keluaran SP PO PI: satu baris per PO line, daftar PI digabung dengan koma."""
    y = pd.read_excel(butuh("po_pi_db.xlsx"), sheet_name="DATA")

    def gabung(s):
        v = [str(a).strip() for a in s if pd.notna(a)]
        return ",".join(v) if v else None

    def f(v):
        return v if pd.isna(v) else (str(int(v)) if float(v).is_integer() else str(v))

    g = y.groupby("COMPPODETAILID", sort=False)
    raw = g.first().reset_index()
    raw["PURCHASEID"] = g["PURCHASEID"].agg(lambda s: gabung([f(a) for a in s])).values
    raw["PURCHASENUMBER"] = g["PURCHASENUMBER"].agg(gabung).values
    raw["PURCHASEDATE"] = g["PURCHASEDATE"].agg(lambda s: gabung([f(a) for a in s])).values
    raw["CATEGORY"] = balik_kategori(raw["COMPID"], raw["CATEGORY"])
    return raw


@functools.lru_cache(maxsize=None)
def df_pr_po():
    """Hasil bersihkan() PR/PO dari data contoh."""
    from laporan.pr_po import sumber
    return sumber.bersihkan(raw_pr_po())


@functools.lru_cache(maxsize=None)
def df_po_pi():
    """Hasil bersihkan() PO/PI dari data contoh."""
    from laporan.po_pi import sumber
    return sumber.bersihkan(raw_po_pi())
