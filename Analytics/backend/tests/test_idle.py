import ahli  # noqa: F401
import tempfile
from pathlib import Path

from inti.pengaturan import DataTidakValid, Pengaturan, periksa_idle
from inti.sesi import Sesi


def salah(f):
    try:
        f()
    except DataTidakValid as e:
        return str(e)
    raise AssertionError("seharusnya ditolak")


def test_sesi_berakhir_kalau_idle_melebihi_batas_dan_diberi_alasan():
    jam, dibuang = [1000.0], []
    s = Sesi(umur_detik=8 * 3600, jam=lambda: jam[0], saat_berakhir=lambda k, u: dibuang.append(u), idle_detik=600)
    a = s.buat("budi")
    jam[0] += 599
    assert s.ambil(a) == "budi"                                               # masih aktif: waktu aktivitas terakhir diperbarui
    jam[0] += 599
    assert s.ambil(a) == "budi"                                               # 599 detik sejak permintaan terakhir: belum habis
    jam[0] += 600
    assert s.ambil(a) is None and dibuang == ["budi"]                         # 600 detik tanpa aktivitas: keluar, datanya dibuang
    assert "tidak ada aktivitas selama 10 menit" in s.alasan(a)


def test_penyapu_membuang_sesi_idle_walau_tidak_diakses_dan_batas_bisa_diubah():
    jam = [1000.0]
    s = Sesi(umur_detik=8 * 3600, jam=lambda: jam[0], idle_detik=0)
    a = s.buat("budi")
    jam[0] += 3600
    assert s.bersihkan() == 0 and s.ambil(a) == "budi"                        # tanpa batas idle: hanya umur sesi yang berlaku
    s.idle = 300                                                              # diubah administrator saat server berjalan
    jam[0] += 300
    assert s.bersihkan() == 1 and s.ambil(a) is None and "5 menit" in s.alasan(a)


def test_batas_idle_divalidasi():
    assert periksa_idle(0) == 0 and periksa_idle(30) == 30 and periksa_idle(30.0) == 30 and periksa_idle(1440) == 1440
    for nilai in (-1, 1441, 2.5, True, "30", None):
        assert "0 sampai 1440" in salah(lambda: periksa_idle(nilai)), nilai


def test_pengaturan_tersimpan_ke_berkas_dan_bawaan_dipakai_kalau_belum_ada():
    with tempfile.TemporaryDirectory() as d:
        berkas = Path(d) / "sub" / "pengaturan.json"
        p = Pengaturan(berkas, {"idle_menit": 30})
        assert p.baca() == {"idle_menit": 30} and not berkas.exists()
        p.simpan(idle_menit=15)
        assert Pengaturan(berkas, {"idle_menit": 30}).baca() == {"idle_menit": 15}   # tetap setelah server dimulai ulang
        berkas.write_text("rusak", encoding="utf-8")
        assert p.baca() == {"idle_menit": 30}                                        # berkas rusak: kembali ke bawaan
