"""Laporan Pembelian TBS (Daily / Weekly / Monthly) siap saat menu dibuka.

- Hasil prosedur ERP disimpan sebentar di memori (REKAPIN_TBS_SIMPAN_MENIT, bawaan 15). Laporan yang sama dalam waktu itu tidak
  menjalankan prosedur lagi; permintaan yang datang saat prosedur yang sama sedang berjalan menunggu hasilnya, bukan menjalankan ulang.
- Setelah login (routes/auth.py), laporan TBS yang boleh dibuka user dijalankan di latar dengan periode bawaannya, jadi saat menunya
  dibuka hasilnya sudah ada (atau tinggal menunggu sisa waktunya).
Data hanya disimpan per (prosedur, perusahaan, periode); hak lihat tetap diperiksa di halaman (routes.laporan)."""
import logging
import os
import threading
import time
from calendar import monthrange
from datetime import date, timedelta

import pyodbc

from modules.rekapin import erp, laporan_tbs

log = logging.getLogger(__name__)

SIMPAN_DETIK = max(0, int(os.getenv("REKAPIN_TBS_SIMPAN_MENIT", "15") or 0)) * 60
TUNGGU_DETIK = 300   # batas menunggu prosedur yang sedang dijalankan permintaan lain

_kunci = threading.Lock()
_hasil = {}       # (prosedur, param) -> (waktu, result set)
_berjalan = {}    # (prosedur, param) -> threading.Event, selesai saat prosedurnya selesai


def company_bawaan(kode):
    """YBS; kalau user tidak punya akses YBS, perusahaan pertama yang boleh dilihatnya."""
    return "YBS" if "YBS" in kode else (kode[0] if kode else "")


def periode_bawaan(jenis, company, hari_ini=None):
    """(awal, akhir) ISO. Daily: tanggal terakhir yang ada datanya (harga sudah diisi), bukan hari ini yang sering masih kosong."""
    hari_ini = hari_ini or date.today()
    if laporan_tbs.LAPORAN[jenis]["periode"] == "daily":
        tanggal = hari_ini
        if company:
            try:
                tanggal = erp.tanggal_harga_terakhir(company, hari_ini) or hari_ini
            except pyodbc.Error:
                log.exception("Tanggal terakhir laporan TBS harian gagal dibaca")
        return tanggal.isoformat(), tanggal.isoformat()
    if jenis == "weekly":
        return (hari_ini - timedelta(weeks=4)).isoformat(), hari_ini.isoformat()
    return hari_ini.replace(day=1).isoformat(), hari_ini.replace(day=monthrange(hari_ini.year, hari_ini.month)[1]).isoformat()


def param(jenis, company, awal, akhir):
    return (company, awal) if laporan_tbs.LAPORAN[jenis]["periode"] == "daily" else (company, awal, akhir)


def jalankan(prosedur, *param):
    """erp.jalankan_prosedur dengan simpanan singkat. Melempar pyodbc.Error seperti aslinya."""
    k = (prosedur, param)
    with _kunci:
        ada = _hasil.get(k)
        if ada and time.time() - ada[0] < SIMPAN_DETIK:
            return ada[1]
        tanda = _berjalan.get(k)
        milik_saya = tanda is None
        if milik_saya:
            tanda = _berjalan[k] = threading.Event()
    if not milik_saya:
        tanda.wait(TUNGGU_DETIK)
        with _kunci:
            ada = _hasil.get(k)
        if ada:
            return ada[1]
        return jalankan(prosedur, *param)      # yang dijalankan permintaan lain gagal: coba sendiri
    try:
        hasil = erp.jalankan_prosedur(prosedur, *param)
        with _kunci:
            sekarang = time.time()
            for lama in [x for x, (w, _) in _hasil.items() if sekarang - w >= SIMPAN_DETIK]:
                del _hasil[lama]
            if SIMPAN_DETIK:
                _hasil[k] = (sekarang, hasil)
        return hasil
    finally:
        with _kunci:
            _berjalan.pop(k, None)
        tanda.set()


def mulai(jenis_boleh, kode_company):
    """Dipanggil saat login: laporan TBS yang boleh dibuka dijalankan di latar, bersamaan, dengan perusahaan & periode bawaan."""
    company = company_bawaan(kode_company)
    if not company or not jenis_boleh or not SIMPAN_DETIK:
        return

    def satu(jenis):
        try:
            lap = laporan_tbs.LAPORAN[jenis]
            jalankan(lap["prosedur"], *param(jenis, company, *periode_bawaan(jenis, company)))
        except Exception:  # noqa: BLE001 - latar; halaman menampilkan galatnya sendiri saat dibuka
            log.exception("Pramuat laporan TBS %s gagal", jenis)

    for jenis in jenis_boleh:
        threading.Thread(target=satu, args=(jenis,), daemon=True, name=f"pramuat-tbs-{jenis}").start()
