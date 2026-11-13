"""Harga harian (CPO, kernel, OER, biaya olah, qty RSI) per perusahaan per tanggal. Satu-satunya tempat baca / tulis harga:
dipakai Dashboard (Isi Harga, widget harga & riwayat) dan RekapIn › Harga CPO & Kernel.

Tabelnya HARGA_TABEL (bawaan Main.dbo.HARGA, tabel RekapIn), koneksi memakai DB_*. Tabel di server lain:
SQLSERVER_PRICE_SERVER / _DATABASE / _UID / _PWD atau SQLSERVER_PRICE_CONNECTION_STRING. SQLSERVER_PRICE_TABLE (nama lama)
masih dibaca bila HARGA_TABEL kosong.
Kolom tabel: id, company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi. Bila satu perusahaan + tanggal
tercatat lebih dari sekali (data lama), yang dipakai baris dengan id terbesar."""
import os
import re
from datetime import date, timedelta
from functools import wraps

import pyodbc

from utils.koneksi_lain import connection_string

KOLOM = ("harga_cpo", "harga_kernel", "oer_cpo", "biaya_olah")
# Batas wajar isian (sama untuk Dashboard dan RekapIn) dan namanya di pesan galat
BATAS = {"harga_cpo": (0, 1_000_000), "harga_kernel": (0, 1_000_000), "oer_cpo": (0, 100), "biaya_olah": (0, 1_000_000),
         "qty_rsi": (0, 1_000_000_000)}
LABEL = {"harga_cpo": "Harga CPO", "harga_kernel": "Harga kernel", "oer_cpo": "OER CPO", "biaya_olah": "Biaya olah",
         "qty_rsi": "Qty RSI"}
NAMA_TABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")


# ===== Isian =====
def angka(nilai, kunci, wajib=True):
    """Isian form -> float dalam BATAS[kunci]. Kosong -> None bila tidak wajib. ValueError berisi pesan untuk pengguna."""
    teks = "" if nilai is None or isinstance(nilai, bool) else str(nilai).strip().replace(",", ".")
    if not teks:
        if wajib:
            raise ValueError(f"{LABEL[kunci]} wajib diisi")
        return None
    try:
        v = float(teks)
    except ValueError:
        raise ValueError(f"{LABEL[kunci]} harus berupa angka") from None
    bawah, atas = BATAS[kunci]
    if not bawah <= v <= atas:
        raise ValueError(f"{LABEL[kunci]} harus antara {bawah:,.0f} dan {atas:,.0f}".replace(",", "."))
    return v


def tanggal(teks):
    """Tanggal harga (YYYY-MM-DD), tidak boleh setelah hari ini."""
    try:
        t = date.fromisoformat(str(teks or "").strip())
    except ValueError:
        raise ValueError("Tanggal tidak valid") from None
    if t > date.today():
        raise ValueError("Tanggal tidak boleh setelah hari ini")
    return t


# ===== Tabel =====
def _nama_tabel():
    return (os.getenv("HARGA_TABEL") or os.getenv("SQLSERVER_PRICE_TABLE") or "Main.dbo.HARGA").strip()


def _tabel():
    nama = _nama_tabel()
    if not NAMA_TABEL.fullmatch(nama):
        raise ValueError("HARGA_TABEL tidak valid (contoh: Main.dbo.HARGA)")
    return ".".join(f"[{b}]" for b in nama.split("."))


def _koneksi():
    teks = connection_string("SQLSERVER_PRICE", "CPOS-Harga", {"DB": "DATABASE", "USER": "UID", "PASSWORD": "PWD"}, db_bawaan="Main")
    return pyodbc.connect(teks, timeout=10)


def _query(sql, *params):
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        kolom = [c[0] for c in cursor.description]
        return [dict(zip(kolom, r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def _kode(kolom="company"):
    return f"UPPER(LTRIM(RTRIM({kolom})))"


def daftar(companies, id_company="", tanggal="", dari=None, batas=500):
    """Baris harga terbaru per perusahaan per tanggal, tanggal terbaru dulu: {id_company, tanggal (date), harga_cpo,
    harga_kernel, oer_cpo, biaya_olah, qty_rsi, oleh, diubah}. companies: kode yang boleh dilihat (None = semua)."""
    syarat, args = [], []
    if companies is not None:
        if not companies:
            return []
        syarat.append(f"{_kode()} IN ({', '.join('?' * len(companies))})")
        args += sorted(companies)
    if id_company:
        syarat.append(f"{_kode()} = ?")
        args.append(id_company)
    if tanggal:
        syarat.append("CAST(tanggal AS DATE) = ?")
        args.append(tanggal)
    if dari:
        syarat.append("CAST(tanggal AS DATE) >= ?")
        args.append(dari)
    rows = _query(f"""SELECT TOP {int(batas)} id_company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi
                      FROM (SELECT {_kode()} AS id_company, CAST(tanggal AS DATE) AS tanggal, harga_cpo, harga_kernel, oer_cpo,
                                   biaya_olah, qty_rsi,
                                   ROW_NUMBER() OVER (PARTITION BY {_kode()}, CAST(tanggal AS DATE) ORDER BY id DESC) AS urut
                            FROM {_tabel()} {('WHERE ' + ' AND '.join(syarat)) if syarat else ''}) h
                      WHERE urut = 1 ORDER BY tanggal DESC, id_company""", *args)
    for r in rows:
        r.update(oleh=None, diubah=None)
    return rows


def tren(companies, hari=7):
    """Harga CPO & kernel per perusahaan beberapa hari terakhir: {id_company: {tanggal: (cpo, kernel)}}"""
    hasil = {}
    for r in daftar(companies, dari=date.today() - timedelta(days=hari - 1), batas=1000):
        hasil.setdefault(r["id_company"], {})[r["tanggal"]] = (float(r["harga_cpo"]), float(r["harga_kernel"]))
    return hasil


def ada(id_company, tanggal):
    return bool(_query(f"SELECT TOP 1 1 AS x FROM {_tabel()} WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?",
                       id_company, tanggal))


def simpan(items):
    """items: [(id_company, tanggal, [harga_cpo, harga_kernel, oer_cpo, biaya_olah], qty_rsi)], satu transaksi.
    Perusahaan + tanggal yang sudah ada diperbarui."""
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        for id_company, tgl, nilai, qty_rsi in items:
            cursor.execute(f"""UPDATE {_tabel()} SET harga_cpo = ?, harga_kernel = ?, oer_cpo = ?, biaya_olah = ?, qty_rsi = ?
                               WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?""", *nilai, qty_rsi, id_company, tgl)
            if cursor.rowcount == 0:
                cursor.execute(f"""INSERT INTO {_tabel()} (company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""", id_company, tgl, *nilai, qty_rsi)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hapus(id_company, tanggal):
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {_tabel()} WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?", id_company, tanggal)
        if cursor.rowcount == 0:
            raise ValueError("Data harga tidak ditemukan")
        conn.commit()
    finally:
        conn.close()


def tangani_galat(fn):
    """Route harga: koneksi / query ke tabel harga gagal -> 503 dengan pesan singkat (rinciannya di log)."""
    from flask import current_app, jsonify

    @wraps(fn)
    def bungkus(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except pyodbc.Error:
            current_app.logger.exception("Tabel harga %s gagal dibuka", _nama_tabel())
            return jsonify({"error": "Data harga belum bisa dibuka. Coba lagi, atau hubungi tim IT bila masih gagal."}), 503
    return bungkus
