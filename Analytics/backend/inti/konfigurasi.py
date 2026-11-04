"""Semua pengaturan dari backend/.env, di satu tempat. Tiap nilai punya bawaan; isi yang salah menghentikan server dengan nama variabelnya.

Tidak ada kata sandi, alamat server, nama SP, atau daftar data (perusahaan, role, hak akses) yang tertanam di kode.
"""
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class KonfigurasiSalah(RuntimeError):
    pass


def teks(nama, bawaan):
    """Kosong atau tidak ada = bawaan."""
    nilai = os.environ.get(nama)
    return nilai.strip() if nilai and nilai.strip() else bawaan


def angka(nama, bawaan, minimum=1):
    nilai = teks(nama, None)
    if nilai is None:
        return bawaan
    try:
        hasil = float(nilai)
    except ValueError:
        raise KonfigurasiSalah(f"{nama} harus berupa angka, tetapi isinya {nilai!r}. Perbaiki di backend/.env.") from None
    if hasil < minimum:
        raise KonfigurasiSalah(f"{nama} minimal {minimum}, tetapi isinya {nilai!r}. Perbaiki di backend/.env.")
    return int(hasil) if hasil == int(hasil) else hasil


def _nama_sql(nama, bawaan, jenis):
    """Nama objek SQL (boleh berawalan skema atau database). Hanya nama, karena disisipkan langsung ke perintah SQL."""
    nilai = teks(nama, bawaan)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}", nilai):
        raise KonfigurasiSalah(f"{nama} harus berupa nama {jenis} saja (huruf, angka, garis bawah, dan titik), tetapi isinya {nilai!r}. Perbaiki di backend/.env.")
    return nilai


def nama_sp(nama, bawaan):
    return _nama_sql(nama, bawaan, "stored procedure")


def nama_tabel(nama, bawaan):
    return _nama_sql(nama, bawaan, "tabel")


def format_tanggal(nama, bawaan):
    """Format strftime tanggal untuk SP, mis. %Y%m%d."""
    nilai = teks(nama, bawaan)
    if not re.search(r"%[Yymd]", nilai):
        raise KonfigurasiSalah(f"{nama} harus format tanggal seperti %Y%m%d atau %Y-%m-%d, tetapi isinya {nilai!r}. Perbaiki di backend/.env.")
    return nilai


def tanggal(nama, bawaan):
    nilai = teks(nama, bawaan)
    try:
        date.fromisoformat(nilai)
    except ValueError:
        raise KonfigurasiSalah(f"{nama} harus berformat YYYY-MM-DD, tetapi isinya {nilai!r}. Perbaiki di backend/.env.") from None
    return nilai


def pilihan(nama, bawaan, sah):
    nilai = teks(nama, bawaan).lower()
    if nilai not in sah:
        raise KonfigurasiSalah(f"{nama} harus salah satu dari {', '.join(sah)}, tetapi isinya {nilai!r}. Perbaiki di backend/.env.")
    return nilai


# ---------- Tabel di database aplikasi (tempat akun login) ----------
TABEL_PENGGUNA = teks("DB_APP_TABEL", "users")
TABEL_ROLE = teks("DB_APP_TABEL_ROLE", "role")
TABEL_COMPANY = teks("DB_APP_TABEL_COMPANY", "company")
TABEL_DIVISI = teks("DB_APP_TABEL_DIVISI", "DIVISION")
TABEL_IZIN =teks("DB_APP_TABEL_IZIN", "PERMISSIONS")      # boleh di database lain: "Main.dbo.PERMISSIONS"

# ---------- Stored procedure laporan ----------
SUMBER_LAPORAN = teks("LAPORAN_SUMBER", "cloud")     # parameter sumber SP, sekaligus CompType perusahaan yang dipanggil
SP_PR_PO = nama_sp("SP_PR_PO", "R_PR_OUT_YBS_2")
SP_PO_PI = nama_sp("SP_PO_PI", "R_PO_OUT_YBS")
TABEL_KATEGORI = nama_tabel("TABEL_KATEGORI", "dbo.MappingCategory")
SP_STATUS = teks("SP_STATUS", "4")                   # 4 = semua status

NAMA_APLIKASI = teks("NAMA_APLIKASI", "Dashboard Analytics")

# ---------- Gabungan dengan CPOS ----------
CPOS_URL = os.getenv("CPOS_URL", "").strip()          # kosong = Analytics berdiri sendiri dengan login sendiri
CPOS_COOKIE = teks("CPOS_COOKIE", "wb_sesi")

# ---------- Weighbridge ----------
SP_PALM = nama_sp("SP_PALM_WEIGHBRIDGE", "dbo.palm_tickets")      # @PT, @StartDate; selalu sampai hari ini
SUMBER_PALM = teks("PALM_SUMBER", SUMBER_LAPORAN)
PALM_MULAI = tanggal("PALM_MULAI", "2026-01-01")                  # tanggal tarikan bawaan
FORMAT_TANGGAL_PALM = format_tanggal("PALM_FORMAT_TANGGAL", "%Y%m%d")
PALM_AMBANG_TARA_KG = angka("PALM_AMBANG_TARA_KG", 150)           # naik atau turun
PALM_AMBANG_DURASI_MENIT = angka("PALM_AMBANG_DURASI_MENIT", 180)
PALM_TOP_KENDARAAN = angka("PALM_TOP_KENDARAAN", 12)
PALM_TOP_SUPPLIER = angka("PALM_TOP_SUPPLIER", 15)
PALM_MAKS_TITIK = angka("PALM_MAKS_TITIK", 1500)                  # lebih dari ini disampel; yang ekstrem selalu ikut
PALM_TITIK_EKSTREM = angka("PALM_TITIK_EKSTREM", 100)
PALM_HARI_TREN = angka("PALM_HARI_TREN", 30)                      # rentang tampilan bawaan
PALM_TOP_PELANGGAR = angka("PALM_TOP_PELANGGAR", 10)
PALM_MIN_TRANSAKSI_PERSEN = angka("PALM_MIN_TRANSAKSI_PERSEN", 10)  # di bawah ini supplier tidak diurutkan menurut persen
PALM_TOP_OPERATOR = angka("PALM_TOP_OPERATOR", 12)

# ---------- Kas & Bank ----------
# Daftar rekening, perusahaan, dan akun giro. Mutasi dan giro dibaca dengan query langsung ke database ERP tiap perusahaan (kas_bank/ledger.py).
TABEL_KAS_BANK = nama_sp("TABEL_KAS_BANK", "Main.dbo.Bank")
TABEL_KAS_PERUSAHAAN = nama_sp("TABEL_KAS_PERUSAHAAN", "Main.dbo.Company")
TABEL_KAS_GIRO = nama_sp("TABEL_KAS_GIRO", "Main.dbo.GiroAccount")
TABEL_KAS_KURS = nama_sp("TABEL_KAS_KURS", "Main.dbo.exc_rate")   # kurs ke rupiah per perusahaan, CURRENCYID, dan tahun
# kurs yang diinput user di CPOS (Data Master › Kurs Mata Uang): riwayat per tanggal berlaku, dipakai lebih dulu dari TABEL_KAS_KURS
TABEL_KAS_KURS_INPUT = nama_sp("TABEL_KAS_KURS_INPUT", "CPOS.dbo.ExchangeRate")
TABEL_KAS_MATA_UANG = nama_sp("TABEL_KAS_MATA_UANG", "CPOS.dbo.Currency")
# kurs harian dari internet untuk mata uang yang tidak ada di TABEL_KAS_KURS; {dari} {sampai} {kode} diisi.
KAS_KURS_INTERNET = teks("KAS_KURS_INTERNET", "https://api.frankfurter.dev/v1/{dari}..{sampai}?base={kode}&symbols=IDR")
KAS_HARI_GRAFIK = angka("KAS_HARI_GRAFIK", 31)  # rentang tampilan lebih panjang dari ini: grafik deret waktu per bulan
KAS_PARALEL = angka("KAS_PARALEL", 6)                   # perusahaan yang diambil bersamaan
# Saldo awal rekening per 1 Januari (membaca seluruh riwayat ERP, lambat) disimpan di folder ini; dihitung ulang di latar belakang kalau
# simpanannya lebih tua dari KAS_SALDO_AWAL_JAM jam, untuk menangkap transaksi mundur tanggal sebelum 1 Januari.
KAS_CACHE_FOLDER = teks("KAS_CACHE_FOLDER", str(Path(__file__).resolve().parent.parent / "cache_kas"))
KAS_SALDO_AWAL_JAM = angka("KAS_SALDO_AWAL_JAM", 24)
KAS_TOP_MITRA = angka("KAS_TOP_MITRA", 10)

# ---------- Penerimaan TBS ----------
SP_PI_GT = nama_sp("SP_PI_GT", "dbo.CheckStatItem")              # PI yang belum di-GT
SP_GT_OUT = nama_sp("SP_GT_OUT", "dbo.gt_out")                    # semua GT, sama dengan query di Excel PI GT db
PVR_TABEL_BOBOT = nama_sp("PVR_TABEL_BOBOT", "dbo.Bobot_PVR")     # kolom Kategori, Bobot
# Pembuat PVR yang dinilai: tampilan awal laporan Penilaian PVR (lihat DashboardPenilaianPvr.jsx); nama lain lewat filter
PVR_PENILAIAN_PEMBUAT = [n.strip() for n in teks("PVR_PENILAIAN_PEMBUAT", "Dinda,Dwi,Ferdinan,Intan").split(",") if n.strip()]
PV_TABEL_BOBOT = nama_sp("PV_TABEL_BOBOT", "dbo.Bobot_PV")
# Kasir yang dinilai di laporan PV KPI (sama dengan Excel Penilaian PV; lihat DashboardPenilaianPv.jsx)
PV_PENILAIAN_PEMBUAT = [n.strip() for n in teks("PV_PENILAIAN_PEMBUAT", "Agnes,Ana,Anisa,Mega,Nuri,Syely,Yusni").split(",") if n.strip()]
# PI di gudang ini untuk peminta di luar gudang ini yang perlu di-GT. HRD = departemen di HO, barangnya tetap di HO.
PIGT_GUDANG_HO = [n.strip() for n in teks("PIGT_GUDANG_HO", "HO,HRD").split(",") if n.strip()]
PIGT_AMBANG_HARI = angka("PIGT_AMBANG_HARI", 7)                   # lebih dari ini sejak PI dan belum di-GT: tertahan
# Pembuat GT orang Logistik: selalu ada di pilihan filter Pembuat GT; tampilan awal dashboard memilih mereka (lihat DashboardPiGt.jsx)
PIGT_LOGISTIK = [n.strip() for n in teks("PIGT_LOGISTIK", "Ilias,Rizky Ramadan,Robby,Rudianto").split(",") if n.strip()]

SP_TBS = nama_sp("SP_TBS", "dbo.tbsdetailybs")
SUMBER_TBS = teks("TBS_SUMBER", SUMBER_LAPORAN)
FORMAT_TANGGAL_TBS = format_tanggal("TBS_FORMAT_TANGGAL", "%Y%m%d")
TBS_HARI_FORECAST = angka("TBS_HARI_FORECAST", 7)
TBS_HARI_TREN = angka("TBS_HARI_TREN", 30)                         # rentang tampilan bawaan
TBS_HARI_SKALA = angka("TBS_HARI_SKALA", 14)                       # skala forecast: netto sekian hari terakhir
TBS_INTERVAL = float(teks("TBS_INTERVAL", "0.8"))                 # interval kepercayaan forecast
TBS_UJI_MINGGU = angka("TBS_UJI_MINGGU", 12)
TBS_UJI_MIN = angka("TBS_UJI_MIN", 4)                              # kurang dari ini, interval tidak ditampilkan
# Sudah tidak dipakai; tetap divalidasi supaya .env lama tetap sah
TBS_SIMULASI = teks("TBS_SIMULASI", "Turun 5%:0.95,Normal:1,Naik 10%:1.1")
TBS_TOP_SUPPLIER = angka("TBS_TOP_SUPPLIER", 10)
TBS_TOP_TIPE = angka("TBS_TOP_TIPE", 10)
TBS_TOP_TIPE_HARGA = angka("TBS_TOP_TIPE_HARGA", 10)

# Pembelian TBS Mingguan: atensi per business group pada minggu lengkap terakhir
SP_TBS_MINGGUAN = nama_sp("SP_TBS_MINGGUAN", "dbo.tbsdetailybsweekly")   # parameter: company, tanggal awal, tanggal akhir
TBS_MINGGUAN_MULAI = tanggal("TBS_MINGGUAN_MULAI", "2026-01-01")           # tanggal tarikan bawaan
TBS_MINGGUAN_MINGGU_TAMPIL = angka("TBS_MINGGUAN_MINGGU_TAMPIL", 13)      # rentang tampilan bawaan: 13 minggu terakhir (12 minggu lengkap)
TBS_MINGGUAN_TARGET_TON = angka("TBS_MINGGUAN_TARGET_TON", 4000)           # target per minggu, sementara tetap
TBS_MINGGUAN_BATAS_SD = float(teks("TBS_MINGGUAN_BATAS_SD", "1.5"))       # di luar rata-rata ± sekian SD: atensi
TBS_MINGGUAN_MIN_MINGGU = angka("TBS_MINGGUAN_MIN_MINGGU", 3)              # kurang dari ini minggu lengkap: tanpa atensi


def _simulasi(teks_env):
    hasil = []
    for bagian in teks_env.split(","):
        nama, _, nilai = bagian.rpartition(":")
        try:
            hasil.append((nama.strip(), float(nilai)))
        except ValueError:
            raise KonfigurasiSalah(f"TBS_SIMULASI harus seperti 'Turun 5%:0.95,Normal:1', tetapi ada {bagian!r}. Perbaiki di backend/.env.") from None
    if not hasil or any(not n or v <= 0 for n, v in hasil):
        raise KonfigurasiSalah(f"TBS_SIMULASI tidak sah: {teks_env!r}. Perbaiki di backend/.env.")
    return hasil


TBS_SIMULASI_DAFTAR = _simulasi(TBS_SIMULASI)

# ---------- Akun dan role ----------
ROLE_ADMIN = teks("ROLE_ADMIN", "System Administrator")   # selalu akses penuh dan mengelola pengguna
ROLE_BAWAAN = teks("ROLE_BAWAAN", "Operator")             # terpilih lebih dulu di formulir akun baru
LOGIN_BERSAMAAN = pilihan("LOGIN_BERSAMAAN", "ganti", ("ganti", "izinkan"))   # ganti: login baru mengakhiri sesi lama

# ---------- Batas laporan ----------
TANGGAL_MULAI_BAWAAN = tanggal("LAPORAN_MULAI_BAWAAN", "2025-10-01")
MAKS_HARI = angka("MAKS_HARI_PERIODE", 1100)           # sekitar 3 tahun
PRAMUAT = teks("PRAMUAT", "1") != "0"                          # 1: setelah login, semua laporan yang boleh dibuka langsung dimuat
MAKS_DATASET = angka("MAKS_DATASET", 1000)               # data laporan di memori sekaligus, semua pengguna (satu per laporan dan periode)
SIMPAN_PEKERJAAN_DETIK = angka("SIMPAN_PEKERJAAN_DETIK", 3600)
# Data yang dimuat kurang dari sekian menit lalu dipakai bersama semua sesi (login berikutnya langsung siap, SQL tidak diulang).
# Lebih lama dari itu, sesi lain memuat ulang dari SQL. 0 = tiap sesi selalu memuat sendiri.
DATA_SEGAR_MENIT = angka("DATA_SEGAR_MENIT", 15, minimum=0)
MAKS_BARIS_EKSPOR = angka("MAKS_BARIS_EKSPOR", 100_000)   # batas berkas Excel sendiri 1.048.576 baris

AKTIVITAS_FOLDER = teks("AKTIVITAS_FOLDER", str(Path(__file__).resolve().parent.parent / "log_aktivitas"))
AKTIVITAS_SIMPAN_HARI = angka("AKTIVITAS_SIMPAN_HARI", 180)
