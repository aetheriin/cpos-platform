"""Uji PenyimpanSql dan alat admin. Memakai SQLite sebagai pengganti SQL Server: query aplikasi memakai SQL standar saja.
Skema SQL Server yang sebenarnya (database/skema_pengguna.sql) tidak bisa diuji di sini."""
import ahli  # noqa: F401
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import api
from inti import admin
from inti import sandi as ks
from inti.pengguna import PenyimpanBerkas, PenyimpanSql, PenyimpanTidakTersedia, laporan_diizinkan
from inti.sesi import PembatasLogin, Sesi

try:
    from fastapi import HTTPException
except ImportError:
    HTTPException = Exception

DUMMY = Path(api.__file__).parent / "inti" / "data" / "pengguna_dummy.json"
SKEMA = """
CREATE TABLE peran (id INTEGER PRIMARY KEY AUTOINCREMENT, kode TEXT NOT NULL UNIQUE, nama TEXT NOT NULL);
CREATE TABLE peran_laporan (peran_id INTEGER NOT NULL REFERENCES peran(id) ON DELETE CASCADE, laporan_id TEXT NOT NULL,
                            PRIMARY KEY (peran_id, laporan_id));
CREATE TABLE pengguna (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, nama TEXT NOT NULL,
                       peran_id INTEGER NOT NULL REFERENCES peran(id), sandi TEXT NOT NULL, aktif INTEGER NOT NULL DEFAULT 1,
                       dibuat_pada TEXT, terakhir_masuk TEXT);
"""


def basis():
    """Database SQLite sementara dengan skema yang setara, dan pabrik koneksinya."""
    path = os.path.join(tempfile.mkdtemp(), "app.db")
    c = sqlite3.connect(path)
    c.executescript(SKEMA)
    c.commit()
    c.close()

    def buka():
        k = sqlite3.connect(path)
        k.execute("PRAGMA foreign_keys = ON")
        return k
    return path, buka


def toko(cache=0, jam=time.time):
    path, buka = basis()
    return PenyimpanSql(buka, cache_detik=cache, jam=jam), buka, path


def terisi(cache=0):
    t, buka, path = toko(cache)
    t.impor_dari_berkas(DUMMY)
    return t, buka, path


def kode(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return getattr(e, "status_code", None)
    return None


class Respons:
    def __init__(self):
        self.cookies = {}

    def set_cookie(self, key, value, **k):
        self.cookies[key] = (value, k)

    def delete_cookie(self, key, **k):
        pass


def segar_api(penyimpan):
    api.penyimpan_pengguna = penyimpan
    api.sesi_login, api.pembatas_login = Sesi(), PembatasLogin()


# ---------- data dan pencarian ----------
def test_peran_pengguna_dan_antarmuka_sama_dengan_berkas():
    t, _, _ = toko()
    t.simpan_peran("semua", "Semua laporan", ["*"])
    t.simpan_peran("pr_po", "PR & PO saja", ["pr_po"])
    t.tambah_pengguna("Budi", "Budi Santoso", "pr_po", ks.hash_sandi("rahasia123"))
    p = t.cari("BUDI")                                                         # username tidak peka huruf besar-kecil
    assert p.username == "Budi" and p.nama == "Budi Santoso" and p.role == "pr_po" and p.aktif is True
    assert ks.cocok("rahasia123", p.sandi) and "rahasia123" not in p.sandi
    assert t.info_role("pr_po") == {"nama": "PR & PO saja", "laporan": ["pr_po"]}
    assert t.info_role("tidak-ada") is None and t.cari("orang-asing") is None
    ids = ["pr_po", "po_pi"]
    assert laporan_diizinkan(t.info_role("semua"), ids) == ids and laporan_diizinkan(t.info_role("pr_po"), ids) == ["pr_po"]
    # bentuk hasil sama dengan penyimpan berkas (yang dipakai api.py)
    b = PenyimpanBerkas(DUMMY)
    assert set(vars(b.cari("manajer"))) == set(vars(t.cari("Budi"))) and set(b.info_role("semua")) == set(t.info_role("semua"))


def test_masukan_salah_ditolak_dengan_pesan_jelas():
    t, _, _ = toko()
    t.simpan_peran("pr_po", "PR & PO", ["pr_po"])
    t.tambah_pengguna("budi", "Budi", "pr_po", "x")
    for fn, kata in [(lambda: t.tambah_pengguna("BUDI", "B", "pr_po", "x"), "sudah dipakai"),
                     (lambda: t.tambah_pengguna("sari", "S", "tidak-ada", "x"), "tidak ada"),
                     (lambda: t.tambah_pengguna(" ", "S", "pr_po", "x"), "wajib"),
                     (lambda: t.ubah_sandi("hantu", "x"), "tidak ditemukan"),
                     (lambda: t.atur_aktif("hantu", False), "tidak ditemukan"),
                     (lambda: t.simpan_peran("", "x", []), "wajib")]:
        try:
            fn()
            raise AssertionError("seharusnya ditolak")
        except ValueError as e:
            assert kata in str(e)


def test_ubah_peran_mengganti_daftar_laporan():
    t, _, _ = toko()
    t.simpan_peran("r", "Satu", ["pr_po", "po_pi"])
    t.simpan_peran("r", "Dua", ["po_pi"])
    assert t.info_role("r") == {"nama": "Dua", "laporan": ["po_pi"]} and len(t.daftar_peran()) == 1


def test_validasi_menolak_laporan_yang_tidak_ada():
    t, _, _ = toko()
    t.simpan_peran("ok", "OK", ["pr_po", "*"])
    t.validasi(["pr_po", "po_pi"])
    t.simpan_peran("salah", "Salah", ["laporan_hantu"])
    try:
        t.validasi(["pr_po", "po_pi"])
        raise AssertionError("seharusnya ditolak")
    except ValueError as e:
        assert "laporan_hantu" in str(e) and "salah" in str(e)


def test_impor_dummy():
    t, _, _ = toko()
    assert t.impor_dari_berkas(DUMMY) == (3, 4, 0)
    assert t.impor_dari_berkas(DUMMY) == (3, 0, 4)                              # ulangan tidak menggandakan
    assert {p["username"] for p in t.daftar_pengguna()} == {"admin", "manajer", "staff_prpo", "staff_popi"}
    assert t.info_role("semua")["laporan"] == ["*"] and ks.cocok("popi123", t.cari("staff_popi").sandi)
    t.ubah_sandi("manajer", ks.hash_sandi("baru-12345"))
    t.impor_dari_berkas(DUMMY)
    assert ks.cocok("baru-12345", t.cari("manajer").sandi)                       # tanpa --timpa, sandi yang sudah diganti aman
    t.impor_dari_berkas(DUMMY, timpa=True)
    assert ks.cocok("manajer123", t.cari("manajer").sandi)


# ---------- cache ----------
def test_cache_perubahan_berlaku_setelah_tenggang_dan_pengguna_baru_langsung_terlihat():
    jam = [1000.0]
    path, buka = basis()
    web = PenyimpanSql(buka, cache_detik=60, jam=lambda: jam[0])               # seperti server web
    admin_ = PenyimpanSql(buka, cache_detik=0)                                  # seperti alat admin (proses lain)
    admin_.simpan_peran("pr_po", "PR & PO", ["pr_po"])
    admin_.tambah_pengguna("budi", "Budi", "pr_po", "x")
    assert web.cari("budi").aktif is True
    admin_.atur_aktif("budi", False)
    jam[0] += 59
    assert web.cari("budi").aktif is True                                       # masih memakai data lama
    jam[0] += 2
    assert web.cari("budi").aktif is False                                      # setelah 60 detik terbaca ulang
    assert web.cari("sari") is None
    admin_.tambah_pengguna("sari", "Sari", "pr_po", "x")
    assert web.cari("sari").nama == "Sari"                                      # hasil "tidak ada" tidak disimpan
    web.bersihkan_cache()
    admin_.atur_aktif("budi", True)
    assert web.cari("budi").aktif is True


def test_catat_masuk_dan_database_tidak_terjangkau():
    t, buka, path = terisi()
    t.catat_masuk("MANAJER")
    c = sqlite3.connect(path)
    assert c.execute("SELECT terakhir_masuk FROM pengguna WHERE username = 'manajer'").fetchone()[0]
    c.close()

    def putus():
        raise ConnectionError("server mati")
    rusak = PenyimpanSql(putus)
    for fn in (lambda: rusak.cari("x"), lambda: rusak.info_role("semua"), lambda: rusak.validasi(["pr_po"]), lambda: rusak.catat_masuk("x")):
        try:
            fn()
            raise AssertionError("seharusnya gagal")
        except PenyimpanTidakTersedia as e:
            assert "ConnectionError" in str(e)


def test_daftar_laporan_peran_dibersihkan():
    t, _, _ = toko()
    t.simpan_peran("r2", "R2", ["pr_po", "pr_po", None, "", "  po_pi  "])
    assert t.info_role("r2")["laporan"] == ["po_pi", "pr_po"]                    # duplikat, kosong, dan None dibuang


def test_tulisan_gagal_di_tengah_dibatalkan_seluruhnya():
    """Kalau satu langkah gagal di tengah, tidak boleh ada yang setengah tersimpan."""
    t, buka, path = toko()
    t.simpan_peran("r", "Lama", ["pr_po"])
    c = sqlite3.connect(path)                                                    # pemicu yang menggagalkan penyisipan laporan tertentu
    c.execute("CREATE TRIGGER racun BEFORE INSERT ON peran_laporan WHEN NEW.laporan_id = 'racun' BEGIN SELECT RAISE(ABORT, 'racun'); END")
    c.commit()
    c.close()
    for fn in (lambda: t.simpan_peran("baru", "Baru", ["pr_po", "racun"]), lambda: t.simpan_peran("r", "Diubah", ["po_pi", "racun"])):
        try:
            fn()
            raise AssertionError("seharusnya gagal")
        except PenyimpanTidakTersedia:
            pass
    assert t.info_role("baru") is None                                           # role baru tidak tersisa
    assert t.info_role("r") == {"nama": "Lama", "laporan": ["pr_po"]}            # role lama utuh (nama dan laporan tidak berubah)


# ---------- dipakai oleh aplikasi ----------
def test_login_dan_role_lewat_database():
    asli = api.penyimpan_pengguna
    try:
        t, _, path = terisi()
        segar_api(t)
        r = Respons()
        info = api.masuk(api.PermintaanLogin(username="Staff_PRPO", sandi="prpo123"), r)
        assert info["role"] == "pr_po" and info["laporan"] == ["pr_po"] and info["nama_role"] == "PR & PO saja"
        assert api.pengguna_saat_ini(sesi_id=r.cookies["sesi"][0]) == info
        assert [l["id"] for l in api.daftar_laporan(user=info)] == ["pr_po"]
        assert kode(api.masuk, api.PermintaanLogin(username="staff_prpo", sandi="salah"), Respons()) == 401
        c = sqlite3.connect(path)
        assert c.execute("SELECT terakhir_masuk FROM pengguna WHERE username = 'staff_prpo'").fetchone()[0]   # waktu masuk tercatat
        c.close()
        semua = api.masuk(api.PermintaanLogin(username="manajer", sandi="manajer123"), Respons())
        assert semua["laporan"] == ["pr_po", "po_pi"]
    finally:
        api.penyimpan_pengguna = asli


def test_penonaktifan_dan_penggantian_role_di_database_berlaku_di_aplikasi():
    asli = api.penyimpan_pengguna
    try:
        t, buka, path = terisi()
        segar_api(t)
        r = Respons()
        api.masuk(api.PermintaanLogin(username="staff_popi", sandi="popi123"), r)
        sid = r.cookies["sesi"][0]
        t.atur_aktif("staff_popi", False)
        assert kode(api.pengguna_saat_ini, sesi_id=sid) == 401                   # sesi lama langsung tak berlaku
        assert kode(api.masuk, api.PermintaanLogin(username="staff_popi", sandi="popi123"), Respons()) == 401
        t.atur_aktif("staff_popi", True)
        t.simpan_peran("po_pi", "PO & PI saja", ["pr_po"])                        # role diubah: sekarang hanya PR/PO
        assert api.pengguna_saat_ini(sesi_id=sid)["laporan"] == ["pr_po"]
    finally:
        api.penyimpan_pengguna = asli


def test_database_pengguna_mati_membuat_503_bukan_401_atau_error_server():
    asli = api.penyimpan_pengguna
    try:
        path, buka = basis()
        hidup = [True]

        def sambung():
            if not hidup[0]:
                raise ConnectionError("server mati")
            return buka()
        t = PenyimpanSql(sambung, cache_detik=0)
        t.impor_dari_berkas(DUMMY)
        segar_api(t)
        r = Respons()
        api.masuk(api.PermintaanLogin(username="manajer", sandi="manajer123"), r)
        hidup[0] = False
        assert kode(api.pengguna_saat_ini, sesi_id=r.cookies["sesi"][0]) == 503     # tidak dikira "belum masuk"
        assert kode(api.masuk, api.PermintaanLogin(username="manajer", sandi="manajer123"), Respons()) == 503
        hidup[0] = True
        assert api.pengguna_saat_ini(sesi_id=r.cookies["sesi"][0])["username"] == "manajer"   # pulih tanpa harus masuk lagi
    finally:
        api.penyimpan_pengguna = asli


def test_login_tetap_berhasil_walau_pencatatan_waktu_masuk_gagal():
    asli = api.penyimpan_pengguna
    try:
        t, _, _ = terisi()
        t.catat_masuk = lambda u: (_ for _ in ()).throw(PenyimpanTidakTersedia("gagal tulis"))
        segar_api(t)
        assert api.masuk(api.PermintaanLogin(username="manajer", sandi="manajer123"), Respons())["username"] == "manajer"
    finally:
        api.penyimpan_pengguna = asli


def test_pilihan_sumber_pengguna_menurut_env():
    lama = os.environ.get("PENGGUNA_SUMBER")
    try:
        os.environ["PENGGUNA_SUMBER"] = "berkas"
        assert isinstance(api._buat_penyimpan(), PenyimpanBerkas)
        os.environ["PENGGUNA_SUMBER"] = " SQL "
        assert isinstance(api._buat_penyimpan(), PenyimpanSql)
        os.environ["PENGGUNA_SUMBER"] = "ngawur"
        try:
            api._buat_penyimpan()
            raise AssertionError("seharusnya ditolak")
        except RuntimeError as e:
            assert "berkas" in str(e) and "sql" in str(e)
    finally:
        if lama is None:
            os.environ.pop("PENGGUNA_SUMBER", None)
        else:
            os.environ["PENGGUNA_SUMBER"] = lama


# ---------- alat admin ----------
def jalan(argv, t, sandi=None):
    keluar = []
    urutan = iter(sandi or [])
    kode_ = admin.main(argv, penyimpan=t, baca_sandi=lambda p: next(urutan), keluar=keluar.append)
    return kode_, "\n".join(keluar)


def test_alat_admin_alur_lengkap():
    t, _, _ = toko()
    assert jalan(["peran", "semua", "Semua laporan", "*"], t)[0] == 0
    assert jalan(["peran", "pr_po", "PR & PO saja", "pr_po"], t)[0] == 0
    assert jalan(["peran", "gabung", "Dua laporan", "pr_po,po_pi"], t)[0] == 0 and t.info_role("gabung")["laporan"] == ["po_pi", "pr_po"]
    k, o = jalan(["tambah", "budi", "Budi Santoso", "pr_po"], t, ["rahasia123", "rahasia123"])
    assert k == 0 and ks.cocok("rahasia123", t.cari("budi").sandi)
    k, o = jalan(["daftar"], t)
    assert k == 0 and "budi" in o and "Budi Santoso" in o and "aktif" in o and "rahasia123" not in o   # sandi tidak pernah dicetak
    assert "pr_po" in jalan(["peran-daftar"], t)[1]
    assert jalan(["sandi", "budi"], t, ["sandibaru-99", "sandibaru-99"])[0] == 0 and ks.cocok("sandibaru-99", t.cari("budi").sandi)
    assert jalan(["nonaktif", "budi"], t)[0] == 0 and t.cari("budi").aktif is False and "NONAKTIF" in jalan(["daftar"], t)[1]
    assert jalan(["aktif", "budi"], t)[0] == 0 and t.cari("budi").aktif is True
    k, o = jalan(["impor-dummy"], t)
    assert k == 0 and "DUMMY" in o and t.cari("manajer") is not None


def test_alat_admin_menolak_masukan_buruk_dan_database_mati():
    t, _, _ = toko()
    jalan(["peran", "pr_po", "PR & PO", "pr_po"], t)
    assert jalan(["tambah", "budi", "Budi", "pr_po"], t, ["pendek", "pendek"])[0] == 1                 # sandi < 8 karakter
    assert jalan(["tambah", "budi", "Budi", "pr_po"], t, ["rahasia123", "berbeda123"])[0] == 1         # konfirmasi berbeda
    assert t.cari("budi") is None                                                                        # tidak ada yang tersimpan
    assert jalan(["tambah", "budi", "Budi", "tidak-ada"], t, ["rahasia123", "rahasia123"])[0] == 1     # role tak dikenal
    assert jalan(["nonaktif", "hantu"], t)[0] == 1
    k, o = jalan(["tambah", "budi", "Budi", "pr_po"], t, ["rahasia123", "rahasia123"])
    assert k == 0 and jalan(["tambah", "BUDI", "Lain", "pr_po"], t, ["rahasia123", "rahasia123"])[0] == 1   # username ganda

    def putus():
        raise ConnectionError("server mati")
    k, o = jalan(["daftar"], PenyimpanSql(putus))
    assert k == 2 and "Tidak bisa menghubungi" in o
