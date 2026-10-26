"""Nilai yang bisa berubah antar lingkungan dibaca dari .env di satu tempat (inti/konfigurasi.py), dengan bawaan dan pesan salah isi yang jelas."""
import ahli  # noqa: F401
import os
import subprocess
import sys
from pathlib import Path

from inti import konfigurasi as k

BACKEND = Path(__file__).resolve().parent.parent


class Env:
    def __init__(self, **isi):
        self.isi = isi

    def __enter__(self):
        self.asli = {n: os.environ.get(n) for n in self.isi}
        for n, v in self.isi.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v

    def __exit__(self, *a):
        for n, v in self.asli.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v


def salah(fn):
    try:
        fn()
    except k.KonfigurasiSalah as e:
        return str(e)
    raise AssertionError("seharusnya melempar KonfigurasiSalah")


def impor_di_proses_baru(**env):
    """Impor konfigurasi di proses Python baru dengan variabel lingkungan tertentu (nilai dibaca saat impor)."""
    kode = ("import sys; sys.path.insert(0, 'tests'); import stub; stub.pasang(); sys.path.insert(0, '.'); "
            "from inti import konfigurasi as k; print(k.MAKS_HARI, k.SP_PR_PO, k.SP_PO_PI, k.SUMBER_LAPORAN, k.ROLE_ADMIN, k.ROLE_BAWAAN, k.LOGIN_BERSAMAAN, k.TANGGAL_MULAI_BAWAAN)")
    lingkungan = {n: v for n, v in os.environ.items() if n not in ("MAKS_HARI_PERIODE", "SP_PR_PO", "SP_PO_PI", "LAPORAN_SUMBER", "ROLE_ADMIN",
                                                                    "ROLE_BAWAAN", "LOGIN_BERSAMAAN", "LAPORAN_MULAI_BAWAAN", "MAKS_DATASET")}
    lingkungan.update(env)
    return subprocess.run([sys.executable, "-c", kode], cwd=BACKEND, capture_output=True, text=True, env=lingkungan)


def test_pembaca_nilai_kosong_memakai_bawaan_dan_angka_divalidasi():
    with Env(UJI_TEKS=None, UJI_ANGKA=None):
        assert k.teks("UJI_TEKS", "bawaan") == "bawaan" and k.angka("UJI_ANGKA", 7) == 7
    with Env(UJI_TEKS="  isi  ", UJI_ANGKA="12"):
        assert k.teks("UJI_TEKS", "bawaan") == "isi" and k.angka("UJI_ANGKA", 7) == 12
    with Env(UJI_TEKS="   ", UJI_ANGKA=""):                          # spasi atau kosong sama dengan tidak diisi
        assert k.teks("UJI_TEKS", "bawaan") == "bawaan" and k.angka("UJI_ANGKA", 7) == 7
    with Env(UJI_ANGKA="abc"):
        assert "UJI_ANGKA harus berupa angka" in salah(lambda: k.angka("UJI_ANGKA", 7)) and "'abc'" in salah(lambda: k.angka("UJI_ANGKA", 7))
    with Env(UJI_ANGKA="0"):
        assert "UJI_ANGKA minimal 1" in salah(lambda: k.angka("UJI_ANGKA", 7))
    with Env(UJI_TGL="2026-13-45"):
        assert "YYYY-MM-DD" in salah(lambda: k.tanggal("UJI_TGL", "2025-10-01"))
    with Env(UJI_TGL="2026-01-31", UJI_PILIH="Ganti"):
        assert k.tanggal("UJI_TGL", "2025-10-01") == "2026-01-31" and k.pilihan("UJI_PILIH", "ganti", ("ganti", "izinkan")) == "ganti"
    with Env(UJI_PILIH="tolak"):
        assert "salah satu dari ganti, izinkan" in salah(lambda: k.pilihan("UJI_PILIH", "ganti", ("ganti", "izinkan")))


def test_bawaan_sama_dengan_perilaku_sebelumnya_dan_env_mengubahnya():
    hasil = impor_di_proses_baru()
    assert hasil.returncode == 0, hasil.stderr
    nilai = hasil.stdout.strip()
    assert nilai == "1100 R_PR_OUT_YBS_2 R_PO_OUT_YBS cloud System Administrator Operator ganti 2025-10-01"
    ubah = impor_di_proses_baru(MAKS_HARI_PERIODE="500", SP_PR_PO="SP_BARU_PR", SP_PO_PI="SP_BARU_PO", LAPORAN_SUMBER="lokal", ROLE_ADMIN="Super Admin",
                                ROLE_BAWAAN="PPIC", LOGIN_BERSAMAAN="izinkan", LAPORAN_MULAI_BAWAAN="2026-01-01")
    assert ubah.returncode == 0, ubah.stderr
    assert ubah.stdout.strip() == "500 SP_BARU_PR SP_BARU_PO lokal Super Admin PPIC izinkan 2026-01-01"


def test_isian_salah_menghentikan_server_dengan_pesan_yang_menyebut_variabelnya():
    for env, kata in ((dict(MAKS_HARI_PERIODE="tiga tahun"), "MAKS_HARI_PERIODE harus berupa angka"),
                      (dict(LOGIN_BERSAMAAN="tolak"), "LOGIN_BERSAMAAN harus salah satu dari ganti, izinkan"),
                      (dict(LAPORAN_MULAI_BAWAAN="kemarin"), "LAPORAN_MULAI_BAWAAN harus berformat YYYY-MM-DD"),
                      (dict(MAKS_DATASET="0"), "MAKS_DATASET minimal 1")):
        hasil = impor_di_proses_baru(**env)
        assert hasil.returncode != 0 and kata in hasil.stderr and "backend/.env" in hasil.stderr, (env, hasil.stderr[-300:])


def test_modul_yang_memakai_konfigurasi_mengambil_nilainya_dari_sana():
    from inti import ekspor, gudang, laporan
    import api
    assert gudang.MAKS_DATASET == k.MAKS_DATASET and gudang.SIMPAN_PEKERJAAN_DETIK == k.SIMPAN_PEKERJAAN_DETIK
    assert ekspor.MAKS_BARIS == k.MAKS_BARIS_EKSPOR and laporan.TANGGAL_MULAI_BAWAAN == k.TANGGAL_MULAI_BAWAAN and api.MAKS_HARI == k.MAKS_HARI
