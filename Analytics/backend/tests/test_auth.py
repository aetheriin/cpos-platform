import ahli  # noqa: F401
import asyncio
import base64
import hashlib
import inspect
import json
import logging
import time
from types import SimpleNamespace

import api
from inti import sandi as ks
from inti.gudang import Gudang
from inti.pengguna import ROLE_ADMIN, PenyimpanPengguna, PenyimpanTidakTersedia, TidakPunyaIzin
from inti.sesi import PembatasLogin, Sesi
import pandas as pd
from test_pengguna import LAPORAN_UJI, ROLE_OPERATOR, ROLE_PPIC, ROLE_SOFTWARE, baru as akun_baru, basis, isi
from test_sandi import RFC_PBKDF2, RFC_SCRYPT, argon2_palsu, pustaka_palsu

try:
    from fastapi import HTTPException
except ImportError:
    HTTPException = Exception

ADMIN = ("admin1", "adminrahasia")
OPERATOR = ("operator1", "operatorrahasia")


class Respons:
    """Pengganti Response: mencatat cookie yang dipasang atau dihapus."""

    def __init__(self):
        self.cookies, self.dihapus = {}, []

    def set_cookie(self, key, value, **k):
        self.cookies[key] = (value, k)

    def delete_cookie(self, key, **k):
        self.dihapus.append(key)


def kode(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return getattr(e, "status_code", None), getattr(e, "detail", "")
    return None, ""


def segar(cache=0):
    """Tabel users sementara berisi satu System Administrator dan satu Operator, sesi dan pembatas bersih."""
    path, buka = basis()
    t = PenyimpanPengguna(buka, cache_detik=cache)
    isi(t, akun_baru(ADMIN[0], ADMIN[1], "Admin Satu", ROLE_ADMIN, "IT", "YBS"), akun_baru(OPERATOR[0], OPERATOR[1], "Operator Satu", ROLE_OPERATOR, "Purchasing", "SUN"))
    api.penyimpan_pengguna, api.gudang, api.pembatas_login, api._algoritma = t, Gudang(), PembatasLogin(), None
    api.sesi_login = api.buat_sesi()                       # sama seperti server: sesi yang berakhir membuang data laporannya
    return t, buka


def masuk(username, sandi):
    r = Respons()
    return api.masuk(api.PermintaanLogin(username=username, sandi=sandi), r), r


def pengguna(akun):
    info, r = masuk(*akun)
    return api.pengguna_saat_ini(sesi_id=r.cookies["sesi"][0])


def tambah_perm(**ubah):
    d = dict(username="budi", sandi="rahasia123", nama="Budi Santoso", role=ROLE_OPERATOR, divisi="Purchasing", company="YBS")
    d.update(ubah)
    return api.PermintaanPengguna(**d)


# ---------- sesi dan pembatas ----------
def test_sesi_buat_ambil_hapus_cabut_dan_kedaluwarsa():
    t = [1000.0]
    s = Sesi(umur_detik=60, jam=lambda: t[0])
    a, b, c = s.buat("Budi"), s.buat("budi"), s.buat("sari")
    assert len({a, b, c}) == 3 and len(a) >= 40 and s.ambil(a) == "Budi" and s.ambil(None) is None and s.ambil("palsu") is None
    s.hapus(a)
    assert s.ambil(a) is None and s.ambil(b) == "budi"
    s.cabut("BUDI")                                                            # semua sesi milik username itu, tanpa peduli huruf
    assert s.ambil(b) is None and s.ambil(c) == "sari"
    t[0] += 61
    assert s.ambil(c) is None
    s.hapus(None)


def test_pembatas_login_mengunci_lalu_membuka_dan_per_pengguna():
    t = [0.0]
    p = PembatasLogin(maks=3, jendela=100, jam=lambda: t[0])
    for _ in range(3):
        p.gagal("a")
    assert 0 < p.sisa_tunggu("a") <= 100 and p.sisa_tunggu("b") == 0
    t[0] += 101
    assert p.sisa_tunggu("a") == 0
    p.gagal("c"); p.gagal("c"); p.berhasil("c"); p.gagal("c")
    assert p.sisa_tunggu("c") == 0


# ---------- masuk dan keluar ----------
def test_masuk_berhasil_memasang_cookie_aman_dan_mengembalikan_data_akun():
    segar()
    info, r = masuk("ADMIN1", ADMIN[1])                                        # username tidak peka huruf besar-kecil
    assert info["username"] == "admin1" and info["nama"] == "Admin Satu" and info["role"] == ROLE_ADMIN and info["admin"] is True
    assert (info["divisi"], info["company"], info["laporan"]) == ("IT", "YBS", LAPORAN_UJI) and info["id"] > 0
    assert "sandi" not in json.dumps(info) and "scrypt" not in json.dumps(info)
    nilai, opsi = r.cookies["sesi"]
    assert len(nilai) >= 40 and opsi["httponly"] is True and opsi["samesite"] == "strict" and opsi["path"] == "/"
    assert opsi["secure"] == api.COOKIE_SECURE and opsi["max_age"] == int(api.SESI_JAM * 3600)
    di_server = api.pengguna_saat_ini(sesi_id=nilai)
    assert di_server.pop("_sid") == nilai and di_server == info                  # _sid hanya ada di sisi server
    dari_saya = api.saya(user={**info, "_sid": nilai})
    assert "_sid" not in dari_saya                                                   # tidak pernah dikirim ke browser
    assert dari_saya.pop("batas_idle_detik") == api.sesi_login.idle and dari_saya == info


def test_pengguna_mengganti_password_sendiri():
    t, _ = segar()
    op = pengguna(OPERATOR)
    ganti = lambda lama, baru: api.ganti_sandi(api.PermintaanGantiSandi(sandi_lama=lama, sandi_baru=baru), user=op)
    assert kode(ganti, "salah123", "barurahasia")[0] == 400                      # password lama harus benar
    assert kode(ganti, OPERATOR[1], "pendek")[0] == 422
    assert kode(ganti, OPERATOR[1], OPERATOR[1])[0] == 422                         # harus berbeda
    assert ganti(OPERATOR[1], "barurahasia") == {"ok": True}
    assert kode(masuk, *OPERATOR)[0] == 401 and masuk(OPERATOR[0], "barurahasia")[0]["username"] == OPERATOR[0]
    a = t.cari(OPERATOR[0])
    assert (a.nama, a.role, a.divisi, a.company) == ("Operator Satu", ROLE_OPERATOR, "Purchasing", "SUN")   # data lain tidak berubah
    for _ in range(5):
        kode(ganti, "tebakan123", "apaajadeh1")
    assert kode(ganti, "barurahasia", "lainlagi99")[0] == 429                     # tebakan berulang dibatasi


def test_operator_bukan_admin_tetapi_melihat_semua_laporan():
    segar()
    info, _ = masuk(*OPERATOR)
    assert info["role"] == ROLE_OPERATOR and info["admin"] is False and info["laporan"] == LAPORAN_UJI
    assert [l["id"] for l in api.daftar_laporan(user=info)] == LAPORAN_UJI


def test_role_tidak_dikenal_bisa_masuk_tetapi_tanpa_akses_laporan():
    t, buka = segar()
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES (?, ?, 'Tamu', 'Manager', 'X', 'Y')", ("tamu1234", ks.hash_sandi("tamurahasia")))
    c.commit()
    c.close()
    info, _ = masuk("tamu1234", "tamurahasia")
    assert info["role"] == "Manager" and info["admin"] is False and info["laporan"] == []
    assert api.daftar_laporan(user=info) == [] and kode(api.dashboard, "pr_po", data_id="x", user=info, jumlah_minggu=5, minggu=None)[0] == 403


def test_masuk_gagal_pesan_sama_dan_hash_tetap_dihitung():
    segar()
    hitung, asli = [], ks.cocok
    api.kata_sandi.cocok = lambda s, h: (hitung.append(h), asli(s, h))[1]
    try:
        salah = kode(api.masuk, api.PermintaanLogin(username=ADMIN[0], sandi="salah"), Respons())
        tak_ada = kode(api.masuk, api.PermintaanLogin(username="orang-asing", sandi="apa-saja"), Respons())
    finally:
        api.kata_sandi.cocok = asli
    assert salah[0] == tak_ada[0] == 401 and salah[1] == tak_ada[1]            # username tak dikenal tidak bisa dibedakan dari sandi salah
    assert len(hitung) == 2 and hitung[1] == ks.HASH_PALSU
    assert kode(api.masuk, api.PermintaanLogin(username="x" * 101, sandi="a"), Respons())[0] == 422


def test_masuk_dikunci_setelah_banyak_gagal_dan_tidak_mengunci_pengguna_lain():
    segar()
    for _ in range(5):
        assert kode(api.masuk, api.PermintaanLogin(username=ADMIN[0], sandi="salah"), Respons())[0] == 401
    k, pesan = kode(api.masuk, api.PermintaanLogin(username=ADMIN[0], sandi=ADMIN[1]), Respons())
    assert k == 429 and "detik" in pesan
    assert masuk(*OPERATOR)[0]["role"] == ROLE_OPERATOR


def test_hash_dari_aplikasi_lain_di_tabel_bisa_dipakai_masuk():
    """Akun yang sudah ada di tabel (dibuat aplikasi lain) tetap bisa masuk, apa pun format hash-nya."""
    t, buka = segar()
    django = "pbkdf2_sha256$1$salt$" + base64.b64encode(hashlib.pbkdf2_hmac("sha256", b"djangorahasia", b"salt", 1, 32)).decode()
    lama = {"w_pbkdf2": (f"pbkdf2:sha256:1$salt${RFC_PBKDF2}", "passwd"), "w_scrypt": (f"scrypt:1024:8:16$NaCl${RFC_SCRYPT}", "password"),
            "dj_pbkdf2": (django, "djangorahasia")}
    c = buka()
    for u, (h, _) in lama.items():
        c.execute("INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES (?, ?, ?, 'Operator', 'X', 'Y')", (u, h, u))
    c.commit()
    c.close()
    for u, (_, sandi) in lama.items():
        assert masuk(u, sandi)[0]["username"] == u, u
        assert kode(api.masuk, api.PermintaanLogin(username=u, sandi=sandi + "x"), Respons())[0] == 401, u


def test_hash_argon2_dengan_dan_tanpa_pustaka():
    t, buka = segar()
    with pustaka_palsu(**argon2_palsu()):
        h = ks.hash_sandi("argonrahasia", "argon2")
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES ('argon1', ?, 'Argon', 'Operator', 'X', 'Y')", (h,))
    c.commit()
    c.close()
    with pustaka_palsu(**argon2_palsu()):
        assert masuk("argon1", "argonrahasia")[0]["username"] == "argon1"
        assert kode(api.masuk, api.PermintaanLogin(username="argon1", sandi="salah"), Respons())[0] == 401
    with pustaka_palsu(argon2=None):                                           # pustaka belum terpasang: 503 dengan pesan umum, bukan "salah sandi"
        k, pesan = kode(api.masuk, api.PermintaanLogin(username="argon1", sandi="argonrahasia"), Respons())
        assert k == 503 and "pustaka" in pesan and "argon" not in pesan.lower()
        assert masuk(*ADMIN)[0]["username"] == "admin1"                          # akun berformat lain tidak terpengaruh


def test_keluar_mencabut_sesi_dan_aman_tanpa_sesi():
    segar()
    _, r = masuk(*ADMIN)
    sid, out = r.cookies["sesi"][0], Respons()
    assert api.keluar(out, sesi_id=sid) == {"ok": True} and out.dihapus == ["sesi"]
    assert kode(api.pengguna_saat_ini, sesi_id=sid)[0] == 401
    assert api.keluar(Respons(), sesi_id=None) == {"ok": True}


def test_tanpa_sesi_sesi_palsu_kedaluwarsa_dan_akun_dihapus_ditolak():
    t, buka = segar()
    assert kode(api.pengguna_saat_ini, sesi_id=None)[0] == 401 and kode(api.pengguna_saat_ini, sesi_id="kode-palsu")[0] == 401
    jam = [0.0]
    api.sesi_login = Sesi(umur_detik=10, jam=lambda: jam[0])
    _, r = masuk(*ADMIN)
    jam[0] += 11
    assert kode(api.pengguna_saat_ini, sesi_id=r.cookies["sesi"][0])[0] == 401
    api.sesi_login = Sesi()
    _, r = masuk(*OPERATOR)
    c = buka()
    c.execute("DELETE FROM users WHERE username = ?", (OPERATOR[0],))              # akun dihapus langsung di database
    c.commit()
    c.close()
    assert kode(api.pengguna_saat_ini, sesi_id=r.cookies["sesi"][0])[0] == 401
    assert kode(api.masuk, api.PermintaanLogin(username=OPERATOR[0], sandi=OPERATOR[1]), Respons())[0] == 401


def test_database_pengguna_mati_membuat_503_bukan_401_dan_pulih_sendiri():
    path, buka = basis()
    hidup = [True]

    def sambung():
        if not hidup[0]:
            raise ConnectionError("server mati")
        return buka()
    t = PenyimpanPengguna(sambung, cache_detik=0)
    isi(t, akun_baru(*ADMIN[:1], ADMIN[1], "Admin", ROLE_ADMIN, "IT", "YBS"))
    api.penyimpan_pengguna, api.sesi_login, api.pembatas_login = t, Sesi(), PembatasLogin()
    _, r = masuk(*ADMIN)
    hidup[0] = False
    assert kode(api.pengguna_saat_ini, sesi_id=r.cookies["sesi"][0])[0] == 503
    assert kode(api.masuk, api.PermintaanLogin(username=ADMIN[0], sandi=ADMIN[1]), Respons())[0] == 503
    hidup[0] = True
    assert api.pengguna_saat_ini(sesi_id=r.cookies["sesi"][0])["username"] == "admin1"      # pulih tanpa harus masuk lagi


# ---------- penjagaan endpoint ----------
def test_endpoint_terlindungi_dan_endpoint_admin_hanya_untuk_admin():
    def dep(fn):
        d = inspect.signature(fn).parameters["user"].default
        return getattr(d, "dependency", d)
    for fn in [api.saya, api.daftar_laporan, api.muat_laporan, api.status_pekerjaan, api.batalkan_pekerjaan, api.dashboard, api.detail]:
        assert dep(fn) is api.pengguna_saat_ini, fn.__name__
    for fn in [api.daftar_pengguna, api.opsi_pengguna, api.tambah_pengguna, api.hapus_pengguna]:
        assert dep(fn) is api.wajib_admin, fn.__name__
    for fn in [api.status, api.masuk, api.keluar]:
        assert "user" not in inspect.signature(fn).parameters, fn.__name__
    segar()
    assert kode(api.wajib_admin, user=pengguna(OPERATOR))[0] == 403            # Operator ditolak
    assert api.wajib_admin(user=pengguna(ADMIN))["admin"] is True
    assert api.status()["ok"] is True


# ---------- kelola pengguna ----------
def test_admin_melihat_daftar_akun_tanpa_hash_dan_pilihan_formulir():
    segar()
    daftar = api.daftar_pengguna(user=pengguna(ADMIN))
    assert [p["username"] for p in daftar] == ["admin1", "operator1"]
    assert set(daftar[0]) == {"id", "username", "nama", "role", "divisi", "company", "dibuat", "admin"} and "scrypt" not in json.dumps(daftar)
    assert api.opsi_pengguna(user=pengguna(ADMIN)) == {"role": ["Operator", "PPIC", "SoftwareEngineer", "System Administrator"], "role_bawaan": "Operator",      # dari tabel role, urut abjad
                                                       "divisi": ["IT", "Purchasing"], "company": ["ORI", "RCM", "SJN", "SUN", "YBS"]}      # dari tabel company


def test_admin_membuat_akun_dan_akun_itu_bisa_masuk():
    t, _ = segar()
    admin = pengguna(ADMIN)
    baru = api.tambah_pengguna(tambah_perm(username=" budi ", role="operator"), user=admin)
    assert (baru["username"], baru["nama"], baru["role"], baru["divisi"], baru["company"]) == ("budi", "Budi Santoso", ROLE_OPERATOR, "Purchasing", "YBS")
    assert "sandi" not in json.dumps(baru) and baru["id"] > 0 and baru["dibuat"][:2] == "20"
    assert ks.cocok("rahasia123", t.cari("budi").sandi) and "rahasia123" not in t.cari("budi").sandi        # tersimpan sebagai hash
    info, _ = masuk("budi", "rahasia123")
    assert info["role"] == ROLE_OPERATOR and info["admin"] is False
    admin_baru = api.tambah_pengguna(tambah_perm(username="sari", role=ROLE_ADMIN, nama="Sari", divisi="IT", company="SUN"), user=admin)
    assert masuk("sari", "rahasia123")[0]["admin"] is True and admin_baru["role"] == ROLE_ADMIN


def test_pembuatan_akun_menolak_masukan_salah_dan_username_ganda():
    t, _ = segar()
    admin = pengguna(ADMIN)
    for ubah, kata in [(dict(username="ab"), "Username"), (dict(sandi="pendek"), "Password"), (dict(nama=" "), "Nama lengkap"),
                       (dict(role="Manager"), "Role harus"), (dict(divisi=""), "Divisi"), (dict(company=""), "Company")]:
        k, pesan = kode(api.tambah_pengguna, tambah_perm(**ubah), user=admin)
        assert k == 422 and kata in pesan, ubah
    k, pesan = kode(api.tambah_pengguna, tambah_perm(username="OPERATOR1"), user=admin)
    assert k == 409 and "sudah dipakai" in pesan                                  # tanpa peduli huruf besar-kecil
    assert [p.username for p in t.daftar()] == ["admin1", "operator1"]            # tidak ada yang tersimpan


def test_akun_baru_memakai_hash_yang_sama_dengan_yang_sudah_ada_di_tabel():
    t, buka = segar()
    c = buka()
    c.execute("DELETE FROM users")
    c.execute("INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES ('lama1', 'pbkdf2_sha256$1$salt$AA==', 'Lama', 'System Administrator', 'X', 'Y')")
    c.commit()
    c.close()
    t.bersihkan_cache()
    info = {"id": t.cari("lama1").id, "username": "lama1", "admin": True}
    api.tambah_pengguna(tambah_perm(), user=info)
    assert ks.jenis_hash(t.cari("budi").sandi) == "django-pbkdf2"                  # mengikuti hash yang sudah ada, bukan memaksakan format sendiri
    segar()
    api.tambah_pengguna(tambah_perm(), user=pengguna(ADMIN))
    assert ks.jenis_hash(api.penyimpan_pengguna.cari("budi").sandi) == "scrypt"     # tabel berisi hash buatan aplikasi ini: tetap scrypt


def test_pembuatan_akun_gagal_dengan_pesan_jelas_kalau_pustaka_atau_izin_kurang():
    t, buka = segar()
    c = buka()
    c.execute("UPDATE users SET password_hash = '$argon2id$v=19$m=1,t=1,p=1$g$h'")        # semua akun berformat argon2
    c.commit()
    c.close()
    t.bersihkan_cache()
    admin = {"id": 1, "username": "admin1", "admin": True}
    with pustaka_palsu(argon2=None):
        k, pesan = kode(api.tambah_pengguna, tambah_perm(), user=admin)
        assert k == 503 and "pip install argon2-cffi" in pesan and t.cari("budi") is None
    segar()

    def ditolak(*a, **k):
        raise TidakPunyaIzin("The INSERT permission was denied on the object 'users'")
    api.penyimpan_pengguna.tambah = ditolak
    k, pesan = kode(api.tambah_pengguna, tambah_perm(), user={"id": 1, "username": "admin1", "admin": True})
    assert k == 503 and "INSERT" in pesan and "permission was denied" not in pesan        # pesan teknis dari database tidak bocor ke layar


def test_admin_menghapus_akun_dan_sesinya_langsung_dicabut():
    t, _ = segar(cache=60)                                                         # cache 60 detik: tanpa pencabutan, sesi lama masih hidup
    admin = pengguna(ADMIN)
    _, r = masuk(*OPERATOR)
    sid = r.cookies["sesi"][0]
    assert api.pengguna_saat_ini(sesi_id=sid)["username"] == "operator1"
    id_op = t.cari(OPERATOR[0]).id
    assert api.hapus_pengguna(str(id_op), user=admin) == {"ok": True}
    assert t.cari(OPERATOR[0]) is None and kode(api.pengguna_saat_ini, sesi_id=sid)[0] == 401
    assert kode(api.masuk, api.PermintaanLogin(username=OPERATOR[0], sandi=OPERATOR[1]), Respons())[0] == 401


def test_penghapusan_akun_dijaga():
    t, _ = segar()
    admin = pengguna(ADMIN)
    id_admin, id_op = t.cari(ADMIN[0]).id, t.cari(OPERATOR[0]).id
    k, pesan = kode(api.hapus_pengguna, str(id_admin), user=admin)
    assert k == 400 and "sedang Anda pakai" in pesan and t.cari(ADMIN[0]) is not None        # tidak bisa menghapus akun sendiri
    api.tambah_pengguna(tambah_perm(username="admin2", role=ROLE_ADMIN), user=admin)
    asli = t.jumlah_admin
    t.jumlah_admin = lambda: 1                                                       # kalau hanya tersisa satu administrator
    k, pesan = kode(api.hapus_pengguna, str(t.cari("admin2").id), user=admin)
    assert k == 400 and "terakhir" in pesan and t.cari("admin2") is not None
    t.jumlah_admin = asli
    assert api.hapus_pengguna(str(t.cari("admin2").id), user=admin) == {"ok": True}  # dua administrator: boleh menghapus yang lain
    assert kode(api.hapus_pengguna, "99999", user=admin)[0] == 404 and kode(api.hapus_pengguna, "bukan-angka", user=admin)[0] == 404
    assert t.cari(OPERATOR[0]).id == id_op                                           # akun lain tidak tersentuh
    assert api._id_pengguna("5") == 5 and api._id_pengguna("abc-123") == "abc-123"


# ---------- pemeriksaan saat server dinyalakan ----------
def test_pemeriksaan_awal_melaporkan_masalah_dengan_jelas():
    t, buka = segar()
    pesan = []

    class Tangkap(logging.Handler):
        def emit(self, rec):
            pesan.append(rec.getMessage())
    h = Tangkap()
    api.log.addHandler(h)
    try:
        api.periksa_pengguna_awal()                                                  # tabel lengkap, ada administrator: tanpa peringatan
        assert not [m for m in pesan if "tidak" in m and "akan bisa masuk" in m] and not [m for m in pesan if "Belum ada akun" in m]
        c = buka()
        c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('x', 'teks-biasa', 'X', 'Operator')")
        c.execute("DELETE FROM users WHERE username = 'admin1'")
        c.commit()
        c.close()
        pesan.clear()
        api.periksa_pengguna_awal()
        assert any("format hash yang tidak dikenal" in m for m in pesan) and any("Belum ada akun System Administrator" in m for m in pesan)
    finally:
        api.log.removeHandler(h)
    api.penyimpan_pengguna = PenyimpanPengguna(basis("CREATE TABLE users (id INTEGER, username TEXT)")[1])
    try:
        api.periksa_pengguna_awal()
        raise AssertionError("seharusnya gagal")
    except RuntimeError as e:
        assert "Tidak bisa membaca tabel pengguna 'users'" in str(e) and "DB_APP_TABEL" in str(e) and "division" in str(e)


# ---------- role dari tabel role (PPIC, SoftwareEngineer, dan RoleId) ----------
def test_role_ppic_dan_softwareengineer_melihat_laporan_tetapi_bukan_admin():
    t, buka = segar()
    for u, r in (("ppic1234", ROLE_PPIC), ("swe12345", ROLE_SOFTWARE)):
        t.tambah(akun_baru(u, "rahasia123", u, r, "IT", "YBS"), ks.hash_sandi("rahasia123"))
        info, _ = masuk(u, "rahasia123")
        assert info["role"] == r and info["admin"] is False and info["laporan"] == LAPORAN_UJI, r
        assert [l["id"] for l in api.daftar_laporan(user=info)] == LAPORAN_UJI
        assert kode(api.wajib_admin, user=info)[0] == 403                          # tidak bisa mengelola pengguna


def test_akun_baru_memilih_role_dari_tabel_role():
    t, buka = segar()
    admin = pengguna(ADMIN)
    assert api.tambah_pengguna(tambah_perm(username="ppic1234", role="ppic"), user=admin)["role"] == "PPIC"
    assert api.tambah_pengguna(tambah_perm(username="swe12345", role="Software Engineer"), user=admin)["role"] == "SoftwareEngineer"
    assert masuk("ppic1234", "rahasia123")[0]["laporan"] == LAPORAN_UJI
    k, pesan = kode(api.tambah_pengguna, tambah_perm(username="mgr12345", role="Manager"), user=admin)
    assert k == 422 and "System Administrator, Operator, PPIC, SoftwareEngineer" in pesan
    c = buka()
    c.execute("UPDATE role SET Status = '0' WHERE RoleName = 'PPIC'")             # PPIC dinonaktifkan di tabel role
    c.commit()
    c.close()
    k, pesan = kode(api.tambah_pengguna, tambah_perm(username="ppic5678", role="PPIC"), user=admin)
    assert k == 422 and "PPIC" not in pesan.split(":")[1] and "PPIC" not in api.opsi_pengguna(user=admin)["role"]


def test_akun_baru_disimpan_sebagai_roleid_kalau_tabel_pengguna_memakai_id():
    t, buka = segar()
    c = buka()
    c.execute("UPDATE users SET role = CASE role WHEN 'System Administrator' THEN '1' WHEN 'Operator' THEN '2' END")
    c.commit()
    c.close()
    t.bersihkan_cache()
    admin = pengguna(ADMIN)
    assert admin["role"] == ROLE_ADMIN and admin["admin"] is True                      # RoleId 1 dikenali sebagai System Administrator
    baru = api.tambah_pengguna(tambah_perm(username="ppic1234", role="PPIC"), user=admin)
    c = buka()
    assert str(c.execute("SELECT role FROM users WHERE username = 'ppic1234'").fetchone()[0]) == "3"
    c.close()
    assert baru["role"] == "PPIC" and masuk("ppic1234", "rahasia123")[0]["role"] == "PPIC"
    daftar = {p["username"]: p["role"] for p in api.daftar_pengguna(user=admin)}
    assert daftar == {"admin1": ROLE_ADMIN, "operator1": ROLE_OPERATOR, "ppic1234": "PPIC"}      # tampilan memakai nama, bukan angka


def test_tabel_role_tidak_terbaca_membuat_akun_503_dan_login_tetap_memakai_tabel_izin():
    t, buka = segar()
    c = buka()
    c.execute("DROP TABLE role")
    c.commit()
    c.close()
    t.bersihkan_cache()
    assert masuk(*ADMIN)[0]["admin"] is True                                        # admin selalu penuh, tidak bergantung pada tabel role
    assert masuk(*OPERATOR)[0]["laporan"] == LAPORAN_UJI                             # tabel izin memakai nama role, jadi hak tetap terbaca tanpa tabel role
    assert kode(api.tambah_pengguna, tambah_perm(), user=pengguna(ADMIN))[0] == 503
    assert kode(api.opsi_pengguna, user=pengguna(ADMIN))[0] == 503


def test_pemeriksaan_awal_memperingatkan_tabel_role_dan_role_tanpa_aturan():
    t, buka = segar()
    pesan = []

    class Tangkap(logging.Handler):
        def emit(self, rec):
            pesan.append(rec.getMessage())
    h = Tangkap()
    api.log.addHandler(h)
    try:
        c = buka()
        c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('mgr12345', ?, 'Mgr', 'Manager')", (ks.hash_sandi("rahasia123"),))
        c.commit()
        api.periksa_pengguna_awal()
        assert any("belum punya akses ke halaman apa pun" in m and "Manager" in m for m in pesan) and not any("Tabel role" in m for m in pesan)
        assert not any("Operator" in m for m in pesan)                              # role yang sudah punya hak tidak diperingatkan
        c.execute("DROP TABLE role")
        c.commit()
        c.close()
        pesan.clear()
        api.periksa_pengguna_awal()                                                # tidak gagal: akun yang ada tetap bisa masuk
        assert any("Tabel role 'role' tidak bisa dibaca" in m for m in pesan)
    finally:
        api.log.removeHandler(h)


def test_tabel_berisi_hash_werkzeug_akun_baru_juga_werkzeug_dan_bisa_dibaca_aplikasi_lain():
    """Tabel Anda berisi hash Werkzeug scrypt. Akun baru dari dashboard harus bisa dibaca aplikasi lain yang memakai tabel yang sama."""
    t, buka = segar()
    c = buka()
    for u in (ADMIN[0], OPERATOR[0]):
        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (ks.hash_sandi(dict([ADMIN, OPERATOR])[u], "werkzeug-scrypt"), u))
    c.commit()
    c.close()
    t.bersihkan_cache()
    admin = pengguna(ADMIN)                                                      # login dengan hash Werkzeug berfungsi
    api.tambah_pengguna(tambah_perm(username="budi1234"), user=admin)
    h = t.cari("budi1234").sandi
    assert ks.jenis_hash(h) == "werkzeug-scrypt" and h.startswith("scrypt:32768:8:1$")
    assert masuk("budi1234", "rahasia123")[0]["username"] == "budi1234"
    try:
        from werkzeug.security import check_password_hash
    except ImportError:
        return
    assert check_password_hash(h, "rahasia123") and not check_password_hash(h, "salah")      # dibaca Werkzeug asli


# ---------- laporan tidak tersisa setelah keluar atau sesi berakhir ----------
LAP = SimpleNamespace(id="pr_po")
PERIODE = ("pr_po", "2026-01-01", "2026-01-31")


def muat_contoh(user, panggil):
    """Memuat data contoh atas nama sesi ini (seperti endpoint muat), tanpa SQL sungguhan."""
    def pemuat(m, a, k):
        panggil.append(1)
        return pd.DataFrame({"x": [1, 2, 3]}), {}
    p = api.gudang.mulai_muat(*PERIODE, pemuat, api._pemilik(user))
    for _ in range(300):
        if p.status != "berjalan":
            break
        time.sleep(0.01)
    return p


def test_keluar_membuang_laporan_dan_harus_diulang_setelah_masuk_lagi():
    segar()
    panggil = []
    info, r = masuk(*ADMIN)
    sid = r.cookies["sesi"][0]
    user = api.pengguna_saat_ini(sesi_id=sid)
    p = muat_contoh(user, panggil)
    assert api._dataset(LAP, p.data_id, user).df is not None and len(panggil) == 1
    api.keluar(Respons(), sesi_id=sid)
    assert api.gudang.ambil(p.data_id) is None and not api.gudang.dataset and not api.gudang.pekerjaan    # laporan tidak tersimpan lagi
    assert kode(api._dataset, LAP, p.data_id, user)[0] == 404                                              # id lama tidak berlaku
    assert kode(api.pengguna_saat_ini, sesi_id=sid)[0] == 401
    user2 = pengguna(ADMIN)                                                                                # masuk lagi dengan akun yang sama
    p2 = muat_contoh(user2, panggil)
    assert len(panggil) == 2 and p2.data_id != p.data_id                                                   # harus memuat ulang dari SQL


def test_sesi_kedaluwarsa_membuang_laporan_walau_tidak_diakses_lagi():
    segar()
    jam = [1000.0]
    api.sesi_login = Sesi(umur_detik=60, jam=lambda: jam[0], saat_berakhir=api._sesi_berakhir)
    panggil = []
    user = pengguna(ADMIN)
    p = muat_contoh(user, panggil)
    jam[0] += 30
    assert api.sesi_login.bersihkan() == 0 and api.gudang.ambil(p.data_id) is not None                      # belum habis
    jam[0] += 31
    assert api.sesi_login.bersihkan() == 1                                                                  # disapu tanpa ada yang mengaksesnya
    assert api.gudang.ambil(p.data_id) is None and not api.gudang.dataset


def test_penyapu_berkala_di_latar_belakang_membuang_sesi_kedaluwarsa():
    segar()
    jam = [1000.0]
    api.sesi_login = Sesi(umur_detik=60, jam=lambda: jam[0], saat_berakhir=api._sesi_berakhir)
    user = pengguna(ADMIN)
    p = muat_contoh(user, [])
    asli = api.SAPU_SESI_DETIK
    api.SAPU_SESI_DETIK = 0.01

    async def jalan():
        tugas = asyncio.create_task(api._sapu_sesi())
        jam[0] += 61
        for _ in range(200):
            await asyncio.sleep(0.02)
            if api.gudang.ambil(p.data_id) is None:
                break
        tugas.cancel()
        try:
            await tugas
        except asyncio.CancelledError:
            pass
    try:
        asyncio.run(jalan())
    finally:
        api.SAPU_SESI_DETIK = asli
    assert api.gudang.ambil(p.data_id) is None


def test_laporan_satu_sesi_tidak_bisa_dibaca_sesi_lain_dan_data_bersama_bertahan():
    segar()
    panggil = []
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    pa = muat_contoh(admin, panggil)
    assert kode(api._dataset, LAP, pa.data_id, operator)[0] == 404                       # operator belum meminta data ini
    assert kode(api.status_pekerjaan, pa.id, user=operator)[0] == 404 and kode(api.batalkan_pekerjaan, pa.id, user=operator)[0] == 404
    po = muat_contoh(operator, panggil)                                                   # periode sama dari sesi lain: tetap dari SQL
    assert len(panggil) == 2 and po.data_id != pa.data_id and api._dataset(LAP, po.data_id, operator) is not None
    assert api._dataset(LAP, pa.data_id, admin).id == po.data_id                          # admin ikut memakai data terbaru
    api.keluar(Respons(), sesi_id=admin["_sid"])
    assert kode(api._dataset, LAP, po.data_id, admin)[0] == 404                           # admin sudah keluar
    assert api._dataset(LAP, po.data_id, operator) is not None                            # operator masih memakainya
    api.keluar(Respons(), sesi_id=operator["_sid"])
    assert api.gudang.ambil(po.data_id) is None and not api.gudang.dataset                # tidak ada pemilik lagi: hilang


def test_akun_dihapus_membuang_laporan_sesinya():
    t, _ = segar()
    panggil = []
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    p = muat_contoh(operator, panggil)
    assert api.hapus_pengguna(str(t.cari(OPERATOR[0]).id), user=admin) == {"ok": True}
    assert api.gudang.ambil(p.data_id) is None and kode(api.pengguna_saat_ini, sesi_id=operator["_sid"])[0] == 401


def test_kesalahan_saat_membersihkan_tidak_menggagalkan_keluar():
    def rusak(kode_, username):
        raise RuntimeError("gagal membersihkan")
    s = Sesi(umur_detik=60, saat_berakhir=rusak)
    a = s.buat("budi")
    s.hapus(a)                                                                            # tidak melempar
    assert s.ambil(a) is None
    b = s.buat("sari")
    s.cabut("sari")
    assert s.ambil(b) is None


def test_akun_baru_company_harus_dari_tabel_company():
    t, buka = segar()
    admin = pengguna(ADMIN)
    assert api.tambah_pengguna(tambah_perm(username="rcm12345", company="rcm"), user=admin)["company"] == "RCM"
    k, pesan = kode(api.tambah_pengguna, tambah_perm(username="acme1234", company="ACME"), user=admin)
    assert k == 422 and "ORI, RCM, SJN, SUN, YBS" in pesan
    c = buka()
    c.execute("UPDATE company SET Status = 0 WHERE CompName LIKE 'SJN%'")        # semua baris SJN dinonaktifkan
    c.commit()
    c.close()
    assert "SJN" not in api.opsi_pengguna(user=admin)["company"] and kode(api.tambah_pengguna, tambah_perm(username="sjn12345", company="SJN"), user=admin)[0] == 422
    c = buka()
    c.execute("DROP TABLE company")
    c.commit()
    c.close()
    assert kode(api.opsi_pengguna, user=admin)[0] == 503 and kode(api.tambah_pengguna, tambah_perm(), user=admin)[0] == 503
    assert masuk(*OPERATOR)[0]["role"] == ROLE_OPERATOR                           # login tidak terpengaruh


def test_pemeriksaan_awal_memperingatkan_tabel_company():
    t, buka = segar()
    pesan = []

    class Tangkap(logging.Handler):
        def emit(self, rec):
            pesan.append(rec.getMessage())
    h = Tangkap()
    api.log.addHandler(h)
    try:
        api.periksa_pengguna_awal()
        assert not any("Tabel company" in m for m in pesan)
        c = buka()
        c.execute("DROP TABLE company")
        c.commit()
        c.close()
        api.periksa_pengguna_awal()                                                 # tidak gagal
        assert any("Tabel company 'company' tidak bisa dibaca" in m for m in pesan)
    finally:
        api.log.removeHandler(h)


def test_jawaban_api_tidak_boleh_disimpan_cache():
    class Jawaban:
        def __init__(self):
            self.headers = {}

    class Permintaan:
        def __init__(self, path):
            self.url = SimpleNamespace(path=path)

    async def lanjut(_req):
        return Jawaban()
    for path in ("/api/laporan/pr_po/dashboard", "/api/auth/saya", "/api/admin/pengguna", "/api/pekerjaan/x"):
        assert asyncio.run(api.tanpa_cache(Permintaan(path), lanjut)).headers == {"Cache-Control": "no-store"}, path
    assert asyncio.run(api.tanpa_cache(Permintaan("/aset/app.js"), lanjut)).headers == {}      # berkas statis tidak disentuh


# ---------- satu akun, satu sesi aktif ----------
def waktu(t):
    from datetime import datetime
    return datetime.fromtimestamp(t).strftime("%H:%M")


def test_sesi_tunggal_login_baru_mengakhiri_sesi_lama_dan_perangkat_lama_diberi_alasan():
    t = [86400.0 * 30 + 9 * 3600 + 5 * 60]
    berakhir = []
    s = Sesi(umur_detik=3600, jam=lambda: t[0], saat_berakhir=lambda k, u: berakhir.append((k[:4], u)), tunggal=True)
    a = s.buat("Budi", asal="IP 172.20.1.5")
    sari = s.buat("sari")
    t[0] += 120
    b = s.buat("budi", asal="IP 172.20.9.9")                      # akun yang sama (huruf besar-kecil diabaikan), perangkat lain
    assert s.ambil(a) is None and s.ambil(b) == "budi" and s.ambil(sari) == "sari"        # hanya sesi lama Budi yang berakhir
    pesan = s.alasan(a)
    assert "perangkat lain" in pesan and "(IP 172.20.9.9)" in pesan and waktu(t[0]) in pesan and "Masuk lagi" in pesan
    assert s.alasan(b) is None and s.alasan(sari) is None and s.alasan("kode-asing") is None
    assert berakhir == [(a[:4], "Budi")]                                                  # pemberitahuan (pembuangan data laporan) untuk sesi lama saja
    c = s.buat("budi")                                                                    # tanpa keterangan asal
    assert "perangkat lain pukul" in s.alasan(b) and "()" not in s.alasan(b) and s.ambil(c) == "budi" and s.ambil(b) is None


def test_sesi_tidak_tunggal_mengizinkan_banyak_sesi_dan_tanpa_alasan():
    s = Sesi(umur_detik=3600, tunggal=False)
    a, b = s.buat("budi"), s.buat("budi")
    assert s.ambil(a) == "budi" and s.ambil(b) == "budi" and s.alasan(a) is None
    assert Sesi().buat("x") and Sesi()._tunggal is False                                  # bawaan kelas: tidak membatasi (pemakai lama aman)


def test_alasan_dicabut_administrator_logout_biasa_tanpa_alasan_dan_alasan_lama_dibuang():
    t = [1000.0]
    s = Sesi(umur_detik=10 ** 9, jam=lambda: t[0])
    a, b, c = s.buat("budi"), s.buat("budi"), s.buat("sari")
    s.cabut("budi", "Password akun Anda diganti oleh administrator.")
    assert s.ambil(a) is None and s.ambil(b) is None and s.alasan(a) == s.alasan(b) == "Password akun Anda diganti oleh administrator."
    s.hapus(c)
    assert s.alasan(c) is None                                                            # keluar sendiri bukan pengakhiran paksa
    s.cabut("tidak-ada", "x")
    d = s.buat("rina"); s.cabut("rina")
    assert s.alasan(d) is None                                                            # dicabut tanpa pesan: tidak ada alasan
    t[0] += 24 * 3600 + 1
    s.buat("lain")                                                                         # penyapuan saat ada aktivitas
    s.cabut("lain2", "x")
    assert s.alasan(a) is None                                                            # alasan lebih dari sehari dibuang
    for i in range(1200):
        k = s.buat(f"u{i}")
        s.cabut(f"u{i}", "x")
    assert len(s._alasan) <= 1000                                                          # tidak membengkak


def test_sesi_tunggal_aman_saat_banyak_login_serentak():
    import threading
    berakhir = []
    s = Sesi(umur_detik=3600, saat_berakhir=lambda k, u: berakhir.append(k), tunggal=True)
    kode = []
    kunci = threading.Lock()

    def masuk_():
        k = s.buat("budi")
        with kunci:
            kode.append(k)
    pekerja = [threading.Thread(target=masuk_) for _ in range(30)]
    for p in pekerja:
        p.start()
    for p in pekerja:
        p.join()
    hidup = [k for k in kode if s.ambil(k)]
    assert len(kode) == 30 and len(hidup) == 1 and len(berakhir) == 29                   # persis satu sesi tersisa, 29 diakhiri


class AsalPalsu:
    def __init__(self, ip):
        self.client = SimpleNamespace(host=ip)


def test_login_di_perangkat_lain_mengakhiri_sesi_lama_dan_membuang_laporannya():
    segar()
    r1, r2 = Respons(), Respons()
    api.masuk(api.PermintaanLogin(username=ADMIN[0], sandi=ADMIN[1]), r1, AsalPalsu("172.20.111.50"))
    sid1 = r1.cookies["sesi"][0]
    user1 = api.pengguna_saat_ini(sesi_id=sid1)
    panggil = []
    p = muat_contoh(user1, panggil)
    assert api._dataset(LAP, p.data_id, user1).df is not None
    api.masuk(api.PermintaanLogin(username=ADMIN[0], sandi=ADMIN[1]), r2, AsalPalsu("172.20.111.77"))      # perangkat lain
    sid2 = r2.cookies["sesi"][0]
    assert sid1 != sid2
    k, pesan = kode(api.pengguna_saat_ini, sesi_id=sid1)
    assert k == 401 and "perangkat lain" in pesan and "IP 172.20.111.77" in pesan              # perangkat lama diberi tahu sebabnya
    assert api.pengguna_saat_ini(sesi_id=sid2)["username"] == ADMIN[0]                           # perangkat baru berfungsi
    assert api.gudang.ambil(p.data_id) is None and not api.gudang.dataset                        # laporan yang dimuat di perangkat lama dibuang
    user2 = api.pengguna_saat_ini(sesi_id=sid2)
    assert len(panggil) == 1 and muat_contoh(user2, panggil).data_id != p.data_id and len(panggil) == 2   # di perangkat baru harus dimuat ulang


def test_login_tanpa_keterangan_asal_tetap_berfungsi_dan_akun_lain_tidak_terganggu():
    segar()
    info_a, ra = masuk(*ADMIN)
    info_o, ro = masuk(*OPERATOR)
    masuk(*ADMIN)                                                                                 # admin masuk lagi
    assert kode(api.pengguna_saat_ini, sesi_id=ra.cookies["sesi"][0])[0] == 401
    assert api.pengguna_saat_ini(sesi_id=ro.cookies["sesi"][0])["username"] == OPERATOR[0]       # operator tidak ikut keluar
    assert "perangkat lain" in kode(api.pengguna_saat_ini, sesi_id=ra.cookies["sesi"][0])[1] and "(" not in kode(api.pengguna_saat_ini, sesi_id=ra.cookies["sesi"][0])[1]


def test_keluar_sendiri_tetap_pesan_umum_bukan_pesan_perangkat_lain():
    segar()
    _, r = masuk(*ADMIN)
    sid = r.cookies["sesi"][0]
    api.keluar(Respons(), sesi_id=sid)
    k, pesan = kode(api.pengguna_saat_ini, sesi_id=sid)
    assert k == 401 and pesan == "Belum masuk atau sesi berakhir. Silakan masuk lagi." and kode(api.pengguna_saat_ini, sesi_id=None)[1] == pesan


def test_akun_dihapus_perangkatnya_diberi_tahu_dan_pilihan_izinkan_mematikan_pembatasan(monkeypatch=None):
    t, _ = segar()
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    api.hapus_pengguna(str(t.cari(OPERATOR[0]).id), user=admin)
    assert "dihapus oleh administrator" in kode(api.pengguna_saat_ini, sesi_id=operator["_sid"])[1]
    from inti import konfigurasi
    asli = konfigurasi.LOGIN_BERSAMAAN
    try:
        konfigurasi.LOGIN_BERSAMAAN = "ganti"
        assert api.buat_sesi()._tunggal is True
        konfigurasi.LOGIN_BERSAMAAN = "izinkan"
        assert api.buat_sesi()._tunggal is False                                                  # .env LOGIN_BERSAMAAN=izinkan: boleh banyak perangkat
        api.sesi_login = api.buat_sesi()
        a, b = api.sesi_login.buat("budi"), api.sesi_login.buat("budi")
        assert api.sesi_login.ambil(a) == "budi" and api.sesi_login.ambil(b) == "budi"
    finally:
        konfigurasi.LOGIN_BERSAMAAN = asli
