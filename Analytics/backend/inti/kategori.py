"""Pemetaan kategori item dari stored procedure ke kategori baru, dibaca dari tabel TABEL_KATEGORI (bawaan dbo.MappingCategory:
id, CompID, Company, OldCategory, Category) di database data.

Hanya perusahaan yang punya baris di tabel itu yang dipetakan; perusahaan lain memakai kategori apa adanya. Tabel dibaca setiap kali data
laporan dimuat, jadi perubahan di tabel berlaku pada pemuatan berikutnya tanpa mengubah kode. Nama yang persis sama (abaikan spasi dan huruf
besar-kecil) dicocokkan dulu, lalu yang mirip dengan ambang kemiripan teks 0,8. Yang tidak ketemu pasangannya menjadi kosong. Hasil yang mirip
dan yang tidak cocok dilaporkan di catatan pemuatan supaya bisa dicek dan ditambahkan ke tabel.
"""
import difflib
import logging
import re

from . import konfigurasi
from .db import get_connection

log = logging.getLogger(__name__)
AMBANG_MIRIP = 0.8


def _norm(teks):
    return re.sub(r"\s+", "", str(teks)).lower()


def baca_peta(buka=get_connection):
    """{perusahaan: {kategori lama: kategori baru}}. Tabel tidak terbaca atau kosong: peta kosong, jadi kategori ERP dipakai apa adanya
    (laporan tetap tampil) dan peringatannya dicatat di log."""
    tabel = ".".join(f"[{b}]" for b in konfigurasi.TABEL_KATEGORI.split("."))
    try:
        conn = buka()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT [Company], [OldCategory], [Category] FROM {tabel}")
            baris = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        log.warning("Tabel pemetaan kategori '%s' tidak bisa dibaca (kolom Company, OldCategory, Category), kategori ERP dipakai apa adanya. "
                    "Periksa TABEL_KATEGORI di backend/.env. Detail: %s", konfigurasi.TABEL_KATEGORI, e)
        return {}
    peta = {}
    for comp, lama, baru in baris:
        comp, lama, baru = (str(v).strip() if v is not None else "" for v in (comp, lama, baru))
        if comp and lama and baru:
            peta.setdefault(comp, {})[lama] = baru
    if not peta:
        log.warning("Tabel pemetaan kategori '%s' kosong, kategori ERP dipakai apa adanya.", konfigurasi.TABEL_KATEGORI)
    return peta


def _indeks(peta):
    return {c: {_norm(k): v for k, v in tabel.items()} for c, tabel in peta.items()}


def petakan_satu(comp, mentah, indeks):
    """Kembalikan (kategori_baru, jenis). jenis: tanpa_peta, tepat, mirip, tidak_cocok, kosong. indeks: hasil _indeks(peta)."""
    kosong = mentah is None or mentah != mentah or str(mentah).strip() == ""   # None, NaN, atau teks kosong
    if comp not in indeks:
        return (None if kosong else mentah), "tanpa_peta"
    if kosong:
        return None, "kosong"
    kunci = _norm(mentah)
    tabel = indeks[comp]
    if kunci in tabel:
        return tabel[kunci], "tepat"
    terbaik, skor = None, 0.0
    for k in tabel:
        s = difflib.SequenceMatcher(None, kunci, k).ratio()
        if s > skor:
            terbaik, skor = k, s
    if terbaik is not None and skor >= AMBANG_MIRIP:
        return tabel[terbaik], "mirip"
    return None, "tidak_cocok"


def petakan_seri(comp, mentah, peta=None):
    """Petakan dua Series (perusahaan, kategori mentah). peta: hasil baca_peta() (None = baca dari tabel). Mengembalikan (Series hasil, catatan)."""
    import pandas as pd

    indeks = _indeks(baca_peta() if peta is None else peta)
    pasangan = pd.DataFrame({"c": comp.astype(str), "k": mentah.where(mentah.notna(), None)}).drop_duplicates()
    hasil, jenis = {}, {}
    for c, k in zip(pasangan["c"], pasangan["k"]):
        hasil[(c, k)], jenis[(c, k)] = petakan_satu(c, k, indeks)
    baru = pd.Series([hasil[(c, k)] for c, k in zip(comp.astype(str), mentah.where(mentah.notna(), None))], index=mentah.index)
    mirip = sorted({(c, k, hasil[(c, k)]) for (c, k), j in jenis.items() if j == "mirip"})
    tidak = sorted({f"{c}: {k}" for (c, k), j in jenis.items() if j == "tidak_cocok"})
    catatan = {"kategori_mirip": [f"{c}: {k} -> {b}" for c, k, b in mirip][:15], "kategori_tidak_cocok": tidak[:15]}
    return baru, catatan
