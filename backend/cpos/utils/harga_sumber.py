"""Sumber harga harian (CPO, kernel, OER, biaya olah, qty RSI) per perusahaan per tanggal.

Bawaan: tabel dbo.DailyPrice di database CPOS. Bila HARGA_TABEL diisi (mis. Main.dbo.HARGA yang sudah berisi data RekapIn),
harga dibaca & ditulis ke tabel itu, dipakai halaman RekapIn › Harga CPO & Kernel dan Dashboard CPOS. Koneksinya memakai DB_*;
tabel di server lain: SQLSERVER_PRICE_SERVER / _DATABASE / _UID / _PWD (nama lama RekapIn) atau SQLSERVER_PRICE_CONNECTION_STRING.
SQLSERVER_PRICE_TABLE (nama lama) masih dibaca bila HARGA_TABEL kosong.
Kolom tabel HARGA: id, company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi. Bila satu perusahaan +
tanggal tercatat lebih dari sekali (data lama), yang dipakai baris dengan id terbesar."""
import os
import re

import pyodbc

from utils.koneksi_lain import connection_string

NAMA_TABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")


def _nama_tabel():
    return (os.getenv("HARGA_TABEL") or os.getenv("SQLSERVER_PRICE_TABLE") or "").strip()


def aktif():
    """True = harga di tabel luar (HARGA_TABEL); False = dbo.DailyPrice CPOS."""
    return bool(_nama_tabel())


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
    """Baris harga terbaru per perusahaan per tanggal: {id_company, tanggal (date), harga_cpo, harga_kernel, oer_cpo,
    biaya_olah, qty_rsi, oleh, diubah}. companies: kode yang boleh dilihat (None = semua)."""
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


def ada(id_company, tanggal):
    return bool(_query(f"SELECT TOP 1 1 AS x FROM {_tabel()} WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?",
                       id_company, tanggal))


def simpan(id_company, tanggal, nilai, qty_rsi):
    """nilai = [harga_cpo, harga_kernel, oer_cpo, biaya_olah]. Perusahaan + tanggal yang sudah ada diperbarui."""
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""UPDATE {_tabel()} SET harga_cpo = ?, harga_kernel = ?, oer_cpo = ?, biaya_olah = ?, qty_rsi = ?
                           WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?""", *nilai, qty_rsi, id_company, tanggal)
        if cursor.rowcount == 0:
            cursor.execute(f"""INSERT INTO {_tabel()} (company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""", id_company, tanggal, *nilai, qty_rsi)
        conn.commit()
    finally:
        conn.close()


def simpan_banyak(items):
    """Simpan beberapa baris harga dalam satu transaksi."""
    conn = _koneksi()
    try:
        cursor = conn.cursor()
        for id_company, tanggal, nilai, qty_rsi in items:
            cursor.execute(f"""UPDATE {_tabel()} SET harga_cpo = ?, harga_kernel = ?, oer_cpo = ?, biaya_olah = ?, qty_rsi = ?
                               WHERE {_kode()} = ? AND CAST(tanggal AS DATE) = ?""",
                           *nilai, qty_rsi, id_company, tanggal)
            if cursor.rowcount == 0:
                cursor.execute(f"""INSERT INTO {_tabel()} (company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                               id_company, tanggal, *nilai, qty_rsi)
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
    """Route harga: koneksi / query ke tabel harga luar gagal -> 503 dengan pesan jelas (bukan galat 500 umum)."""
    from functools import wraps
    from flask import jsonify

    @wraps(fn)
    def bungkus(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except pyodbc.Error as e:
            if not aktif():
                raise
            return jsonify({"error": f"Gagal membuka tabel harga {os.getenv('SQLSERVER_PRICE_TABLE', 'Main.dbo.HARGA')} "
                                     f"di {os.getenv('SQLSERVER_PRICE_SERVER', '') or 'server harga'}: {e.args[-1] if e.args else e}"}), 503
    return bungkus


def nama_sumber():
    """Teks sumber harga untuk ditampilkan (mis. 'Main.dbo.HARGA @ 172.20.111.4' atau 'CPOS dbo.DailyPrice')."""
    if not aktif():
        return "CPOS dbo.DailyPrice"
    server = (os.getenv("SQLSERVER_PRICE_SERVER") or os.getenv("DB_SERVER") or "").strip()
    return _nama_tabel() + (f" @ {server}" if server else "")
