"""Harga PO per baris PO dari ERP (AP_PurchaseOrderDetails), untuk tabel detail laporan PR & PO dan PO & PI.

SP laporan (R_PR_OUT_YBS_2, R_PO_OUT_YBS) tidak membawa harga, jadi diambil terpisah lewat SP HARGA_PO_SP (data mentah saja),
dipanggil per perusahaan bersamaan (SQL-nya di backend/database/harga_po_sp.sql). Baris PO menyimpan baris PR asalnya di SourceID
(= PRDETAILID di SP PR), jadi harga bisa
ditempel tepat per baris PR dan per baris PO. Harga dalam mata uang PO; kolom mata uang ikut supaya PO valas tidak terbaca rupiah.
"""
from datetime import date, timedelta

import logging

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

log = logging.getLogger(__name__)

KOLOM = ["comp", "po_detail_id", "pr_detail_id", "po_number", "harga_po", "total_po", "mata_uang_po"]

def ambil(mulai, kendali=None, sumber=None):
    """DataFrame KOLOM untuk PO bertanggal mulai (date) ke atas, semua perusahaan. Kosong kalau gagal (tabel detail tetap tampil)."""
    perusahaan = [k for k, _, _ in lokasi_perusahaan(sumber or konfigurasi.SUMBER_LAPORAN)]
    try:
        raw = per_perusahaan(perusahaan, get_connection, f"EXEC {konfigurasi.HARGA_PO_SP} ?, ?", lambda c: (c, mulai.isoformat()),
                             kendali, boleh_kosong=True, tandai=True)
    except Exception as e:      # SP belum ada, belum diberi izin EXECUTE, atau gagal: kolom harga kosong, tabel detail tetap tampil
        log.warning("Harga PO dari SP %s gagal: %s", konfigurasi.HARGA_PO_SP, e)
        return pd.DataFrame(columns=KOLOM)
    angka_id = lambda s: pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)
    return pd.DataFrame({
        "comp": raw["__comp"].astype(str),
        "po_detail_id": angka_id(raw["PODetailID"]),
        "pr_detail_id": angka_id(raw["SourceID"]),
        "po_number": raw["PONumber"].fillna("").astype(str).str.strip(),
        "harga_po": pd.to_numeric(raw["UnitCost"], errors="coerce"),
        "total_po": pd.to_numeric(raw["LineTotal"], errors="coerce"),
        "mata_uang_po": raw["Currency"].fillna("").astype(str).str.strip(),
    })


def mulai_po(mulai_iso):
    """Batas bawah tanggal PO: sebulan sebelum awal data, supaya PO yang dibuat sedikit sebelum tanggal PR/PO di data tetap ikut."""
    return date.fromisoformat(str(mulai_iso)[:10]) - timedelta(days=31)


def tempel_pr(df, harga):
    """Harga PO untuk baris PR & PO (satu baris per PR x PO): dicocokkan lewat baris PR asal (SourceID) dan nomor PO.
    Satu baris PR yang muncul di beberapa baris PO bernomor sama dijumlahkan totalnya."""
    if harga.empty:
        return df.assign(harga_po=float("nan"), total_po=float("nan"), mata_uang_po="")
    h = (harga.groupby(["comp", "pr_detail_id", "po_number"], as_index=False)
         .agg(harga_po=("harga_po", "first"), total_po=("total_po", "sum"), mata_uang_po=("mata_uang_po", "first")))
    kunci = df.assign(pr_detail_id=[l[len(c):] for c, l in zip(df["comp"], df["line"])])
    hasil = kunci.merge(h, how="left", on=["comp", "pr_detail_id", "po_number"]).drop(columns="pr_detail_id")
    hasil.index = df.index
    hasil["mata_uang_po"] = hasil["mata_uang_po"].fillna("")
    return hasil


def tempel_po(df, harga):
    """Harga untuk baris PO & PI: dicocokkan lewat baris PO (PODETAILID)."""
    if harga.empty:
        return df.assign(harga_po=float("nan"), total_po=float("nan"), mata_uang_po="")
    h = harga.drop_duplicates(["comp", "po_detail_id"])[["comp", "po_detail_id", "harga_po", "total_po", "mata_uang_po"]]
    kunci = df.assign(po_detail_id=[l[len(c):] for c, l in zip(df["comp"], df["line"])])
    hasil = kunci.merge(h, how="left", on=["comp", "po_detail_id"]).drop(columns="po_detail_id")
    hasil.index = df.index
    hasil["mata_uang_po"] = hasil["mata_uang_po"].fillna("")
    return hasil
