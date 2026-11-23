"""Halaman & API Item Category Dashboard. Hak: menu AN_ITEM_CATEGORY (Lihat) di Admin › Hak Akses."""
import logging
import math
import threading
import time
from datetime import date, datetime
from decimal import Decimal

import pyodbc
from flask import jsonify, render_template, request
from flask_login import login_required

from modules.item_dashboard import item_dashboard_bp
from modules.item_request.mesin import get_connection
from utils.hak_akses import halaman as lihat_halaman, izin, remah_menu

log = logging.getLogger(__name__)
KODE = "AN_ITEM_CATEGORY"
# (judul, keterangan angka, angkanya mengikuti periode?) sesuai urutan hasil dbo.top_item_category_analysis
HASIL = (
    ("Item dengan stok tertinggi", "Stok saat ini, dalam satuan terbesar tiap item. Satuan antar item bisa berbeda.", False),
    ("Item paling sering diorder", "Jumlah PO", True),
    ("Item paling sering digunakan", "Jumlah dokumen pemakaian", True),
    ("Kategori paling sering diorder", "Jumlah PO", True),
    ("Kategori dengan cost tertinggi", "Total nilai PO dalam Rupiah", True),
    ("Item dengan cost tertinggi", "Total nilai PO dalam Rupiah", True),
)
TOP_N = 10
# Batas rentang dan lama data dianggap segar sama dengan Analytics (MAKS_HARI_PERIODE, DATA_SEGAR_MENIT)
MAKS_HARI = 1100
SEGAR_DETIK = 15 * 60
MAKS_PERIODE = 8
MAKS_BERJALAN = 3  # SP yang boleh berjalan bersamaan untuk periode berbeda, supaya database Main tidak terbebani
# Tidak ada halaman yang menanyakan status selama ini (ditutup atau Batalkan): SP dihentikan. Di atas 60 detik karena
# browser memperlambat timer tab yang tersembunyi sampai sekali per menit.
DITINGGAL_DETIK = 90
PESAN_GAGAL = "Data analisis item gagal dimuat."
PESAN_BATAL = "Pemuatan dibatalkan."


class _Pemuatan:
    """Satu kali menjalankan SP untuk satu periode. Hasilnya dipakai bersama semua pengguna selama masih segar."""

    def __init__(self, mulai, akhir):
        self.mulai, self.akhir = mulai, akhir
        self.sejak = self.ditanya = time.monotonic()
        self.selesai = None
        self.data = None
        self.pesan = None
        self.cursor = None
        self.dihentikan = False

    def segar(self):
        return self.data is not None and time.monotonic() - self.selesai < SEGAR_DETIK


_kunci = threading.Lock()
_pemuatan = {}  # (mulai, akhir) -> _Pemuatan


def _nilai_json(nilai):
    if isinstance(nilai, (datetime, date)):
        return nilai.isoformat()
    if isinstance(nilai, Decimal):
        hasil = float(nilai)
        return hasil if math.isfinite(hasil) else None
    if isinstance(nilai, float) and not math.isfinite(nilai):
        return None
    if isinstance(nilai, bytes):
        return nilai.hex()
    if nilai is None or isinstance(nilai, (str, int, float, bool)):
        return nilai
    return str(nilai)


def _muat_data(p):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        with _kunci:
            if p.dihentikan:
                raise RuntimeError(PESAN_BATAL)
            p.cursor = cursor
        cursor.execute(
            "EXEC dbo.top_item_category_analysis @Company = 'ALL', @DateFrom = ?, @DateTo = ?, @TopN = ?, @Gabung = 0",
            p.mulai, p.akhir, TOP_N,
        )
        hasil = []
        while True:
            if cursor.description is not None:
                kolom = [str(deskripsi[0]) for deskripsi in cursor.description]
                baris = [
                    {nama: _nilai_json(nilai) for nama, nilai in zip(kolom, row)}
                    for row in cursor.fetchall()
                ]
                urutan = len(hasil)
                judul, keterangan, ikut_periode = HASIL[urutan] if urutan < len(HASIL) else (f"Hasil {urutan + 1}", "", True)
                hasil.append({
                    "judul": judul,
                    "keterangan": keterangan,
                    "ikut_periode": ikut_periode,
                    "kolom": kolom,
                    "baris": baris,
                })
            if not cursor.nextset():
                break

        if not hasil:
            raise RuntimeError("Stored procedure tidak menghasilkan result set.")
        return {"hasil": hasil, "periode": {"mulai": p.mulai.isoformat(), "akhir": p.akhir.isoformat()}, "top_n": TOP_N,
                "dimuat": datetime.now().isoformat(timespec="minutes")}
    finally:
        conn.close()


def _jalankan(p):
    try:
        data = _muat_data(p)
        with _kunci:
            p.data = data
    except Exception:  # di thread sendiri: galat apa pun harus sampai ke halaman, bukan membuat status "memuat" selamanya
        if p.dihentikan:
            p.pesan = PESAN_BATAL
        else:
            log.exception("Gagal memuat dbo.top_item_category_analysis dari database Main (%s sampai %s)", p.mulai, p.akhir)
            p.pesan = PESAN_GAGAL
    finally:
        with _kunci:
            p.cursor = None
            p.selesai = time.monotonic()


def _jaga(p):
    while p.selesai is None:
        time.sleep(5)
        if p.selesai is None and time.monotonic() - p.ditanya > DITINGGAL_DETIK:
            with _kunci:
                p.dihentikan = True
                cursor = p.cursor
            if cursor is not None:
                try:
                    cursor.cancel()
                except pyodbc.Error:
                    log.warning("SP item category tidak bisa dihentikan", exc_info=True)
            return


def _buang_basi():
    sekarang = time.monotonic()
    for kunci, p in list(_pemuatan.items()):
        if p.selesai is not None and sekarang - p.selesai >= SEGAR_DETIK:
            del _pemuatan[kunci]
    selesai = sorted((p.selesai, k) for k, p in _pemuatan.items() if p.selesai is not None)
    for _, kunci in selesai[:max(0, len(_pemuatan) - MAKS_PERIODE)]:
        del _pemuatan[kunci]


def _periode(args):
    hari_ini = date.today()
    try:
        mulai = date.fromisoformat(args.get("mulai") or date(hari_ini.year, 1, 1).isoformat())
        akhir = date.fromisoformat(args.get("akhir") or hari_ini.isoformat())
    except ValueError:
        raise ValueError("Tanggal tidak dikenali.") from None
    if mulai > akhir:
        raise ValueError("Tanggal mulai tidak boleh setelah tanggal akhir.")
    if (akhir - mulai).days > MAKS_HARI:
        raise ValueError(f"Rentang terlalu panjang (maksimal {MAKS_HARI} hari).")
    return mulai, akhir


@item_dashboard_bp.route("")
@login_required
@lihat_halaman(KODE)
def halaman_item():
    return render_template(
        "item_dashboard/index.html",
        halaman="analytics",
        kode_aktif="AN_DASHBOARD",
        remah=remah_menu(KODE),
    )


@item_dashboard_bp.route("/api")
@login_required
@izin(KODE, "lihat")
def api_item():
    """SP berjalan di thread sendiri; halaman bertanya ulang tiap detik dengan cek=1 sampai siap.
    Tanpa cek: pakai hasil yang masih segar atau pemuatan yang sedang berjalan, kalau tidak ada mulai baru. ulang=1: selalu ambil ulang."""
    try:
        mulai, akhir = _periode(request.args)
    except ValueError as galat:
        return jsonify({"status": "gagal", "error": str(galat)}), 400
    cek = request.args.get("cek") == "1"
    ulang = request.args.get("ulang") == "1"
    with _kunci:
        _buang_basi()
        p = _pemuatan.get((mulai, akhir))
        jalan = p is not None and p.selesai is None
        if p is None or (not jalan and not cek and (ulang or not p.segar())):
            if sum(1 for q in _pemuatan.values() if q.selesai is None) >= MAKS_BERJALAN:
                return jsonify({"status": "gagal", "error": "Sedang ada beberapa periode lain yang dimuat. Coba lagi sebentar lagi."}), 503
            p = _pemuatan[(mulai, akhir)] = _Pemuatan(mulai, akhir)
            threading.Thread(target=_jalankan, args=(p,), daemon=True, name="item-dashboard-sp").start()
            threading.Thread(target=_jaga, args=(p,), daemon=True, name="item-dashboard-jaga").start()
        p.ditanya = time.monotonic()
        if p.selesai is None:
            return jsonify({"status": "memuat", "detik": int(time.monotonic() - p.sejak)})
        if p.data is not None:
            return jsonify({"status": "siap", **p.data})
        return jsonify({"status": "gagal", "error": p.pesan}), 503
