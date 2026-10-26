import ahli  # noqa: F401
import os
import sqlite3
import tempfile

from inti import alat_pengguna as alat
from inti import sandi as ks
from inti.pengguna import (
    ROLE_ADMIN, DataTidakValid, IzinTidakTerbaca, PenyimpanPengguna, PenyimpanTidakTersedia, TidakPunyaIzin,
    adalah_admin, daftar_company_akun, kanonik_role, periksa_pengguna_baru, periksa_ubah_pengguna,
)
from types import SimpleNamespace

# Nama role contoh untuk fixture. Di program TIDAK ada daftar role: role dibaca dari tabel role, hak aksesnya dari tabel izin.
ROLE_OPERATOR, ROLE_PPIC, ROLE_SOFTWARE = "Operator", "PPIC", "SoftwareEngineer"
from laporan import SEMUA as _LAPORAN
LAPORAN_UJI = list(_LAPORAN)                                            # semua laporan yang terdaftar, urut seperti menu
from test_sandi import argon2_palsu, pustaka_palsu

SKEMA = """CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
           full_name TEXT NOT NULL, role TEXT NOT NULL, division TEXT, company TEXT, created_at TEXT)"""


SKEMA_ROLE = """CREATE TABLE role (RoleId INTEGER PRIMARY KEY AUTOINCREMENT, DivisionId INTEGER, RoleName TEXT NOT NULL,
                RoleDescription TEXT, Status TEXT, CreatedAt TEXT)"""
ROLE_AWAL = [ROLE_ADMIN, ROLE_OPERATOR, ROLE_PPIC, ROLE_SOFTWARE]       # RoleId 1 sampai 4, semuanya aktif
ROLE_TABEL = list(ROLE_AWAL)
# Tabel izin milik bersama aplikasi lain: kolom role berisi NAMA role, page_key berisi id laporan (atau halaman lain milik aplikasi lain)
SKEMA_IZIN = """CREATE TABLE PERMISSIONS (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, page_key TEXT NOT NULL,
                can_access INTEGER NOT NULL DEFAULT 0, can_edit INTEGER NOT NULL DEFAULT 0, can_delete INTEGER NOT NULL DEFAULT 0,
                can_approve INTEGER NOT NULL DEFAULT 0, can_reject INTEGER NOT NULL DEFAULT 0, can_done INTEGER NOT NULL DEFAULT 0)"""
SKEMA_COMPANY = """CREATE TABLE company (CompID INTEGER PRIMARY KEY, CompName TEXT, CompType TEXT, CompAddr TEXT, CompDataBase TEXT, Status INTEGER)"""
# Isi tabel company seperti contoh dari pengguna: nama berspasi (kolom CHAR), satu nama punya beberapa jenis, SJN TRAINING nonaktif
COMPANY_AWAL = [
    (1, "YBS", "CLOUD", "ASCEND_CLOUD", "AS_YBS222", 1), (2, "SUN", "CLOUD", "ASCEND_CLOUD", "AS_SUN_YBS", 1),
    (3, "SJN", "CLOUD", "ASCEND_CLOUD", "AS_SJN", 1), (4, "ORI", "CLOUD", "ASCEND_CLOUD", "AS_ORI", 1),
    (5, "RCM", "CLOUD", "ASCEND_CLOUD", "AS_YBS_VRA", 1), (6, "YBS", "TRAINING", "YBS_TRAINING", "TEST_YBS222", 1),
    (7, "SUN", "TRAINING", "SUN_TRAINING", "TEST_SUN_YBS", 1), (8, "SJN", "TRAINING", "SJN_TRAINING", "TEST_AS_SJN", 0),
    (9, "YBS", "PKS_LOKAL", "YBS_LOKAL", "AS_WB_YBS", 1), (10, "YBS", "REF_LOKAL", "YBS_LOKAL", "AS_WB_YBS_REFINERY", 1),
    (11, "SUN", "PKS_LOKAL", "SUN_LOKAL", "AS_WB_SUN", 1),
]
COMPANY_TABEL = ["ORI", "RCM", "SJN", "SUN", "YBS"]                     # nama unik, urut abjad


def basis(skema=SKEMA, status="1"):
    """Database SQLite sementara dengan tabel users dan tabel role (empat role), dan pabrik koneksinya.
    SQL yang dipakai aplikasi adalah SQL standar."""
    path = os.path.join(tempfile.mkdtemp(), "app.db")
    c = sqlite3.connect(path)
    c.execute(skema)
    c.execute(SKEMA_ROLE)
    c.execute(SKEMA_COMPANY)
    c.execute(SKEMA_IZIN)
    for role in ROLE_AWAL[1:]:                             # role selain System Administrator: akses ke semua laporan (awal)
        for lap in LAPORAN_UJI:
            c.execute("INSERT INTO PERMISSIONS (role, page_key, can_access) VALUES (?, ?, 1)", (role, lap))
    for r in COMPANY_AWAL:
        c.execute("INSERT INTO company VALUES (?, ?, ?, ?, ?, ?)", (r[0], r[1].ljust(20), *r[2:]))      # CompName berspasi seperti kolom CHAR(20)
    for nama in ROLE_AWAL:
        c.execute("INSERT INTO role (DivisionId, RoleName, RoleDescription, Status, CreatedAt) VALUES (1, ?, ?, ?, '2026-01-01')", (nama, f"Deskripsi {nama}", status))
    c.commit()
    c.close()
    return path, (lambda: sqlite3.connect(path))


def toko(cache=0, jam=None, **kw):
    path, buka = basis()
    return (PenyimpanPengguna(buka, cache_detik=cache, **({"jam": jam} if jam else {}), **kw)), buka, path


def baru(username="budi", sandi="rahasia123", nama="Budi Santoso", role=ROLE_OPERATOR, divisi="Purchasing", company="YBS"):
    return periksa_pengguna_baru(username, sandi, nama, role, divisi, company, ROLE_TABEL, COMPANY_TABEL)


def isi(t, *akun):
    for a in akun:
        t.tambah(a, ks.hash_sandi(a["sandi"]))


def salah(fn, jenis=DataTidakValid):
    try:
        fn()
    except jenis as e:
        return str(e)
    raise AssertionError("seharusnya melempar " + jenis.__name__)


# ---------- role ----------
def test_role_dikenali_tanpa_peduli_huruf_besar_kecil_dan_spasi():
    assert kanonik_role("system administrator", ROLE_TABEL) == ROLE_ADMIN and kanonik_role("  OPERATOR ", ROLE_TABEL) == ROLE_OPERATOR
    assert kanonik_role("Software Engineer", ROLE_TABEL) == ROLE_SOFTWARE and kanonik_role("ppic", ROLE_TABEL) == ROLE_PPIC     # spasi diabaikan
    assert kanonik_role("Manager", ROLE_TABEL) is None and kanonik_role(None, ROLE_TABEL) is None and kanonik_role("", ROLE_TABEL) is None
    assert adalah_admin("system   administrator") and adalah_admin("SystemAdministrator")
    assert adalah_admin("SYSTEM ADMINISTRATOR") and not adalah_admin("Operator") and not adalah_admin(None)


def test_hak_role_dibaca_dari_tabel_izin_bukan_dari_kode():
    t, buka, _ = toko()
    assert t.izin_role("Operator") == set(LAPORAN_UJI)
    assert t.izin_role("operator") == t.izin_role("  OPERATOR ") == t.izin_role("Operator")                 # huruf besar-kecil dan spasi diabaikan
    assert t.izin_role("Software Engineer") == t.izin_role("SoftwareEngineer") != set()                       # nama role boleh berspasi
    assert t.izin_role("Manager") == set() and t.izin_role(None) == set() and t.izin_role("") == set()      # tidak ada di tabel izin: tanpa akses
    assert adalah_admin("System Administrator") and adalah_admin("system   administrator") and not adalah_admin("Operator")
    sql(buka, "UPDATE PERMISSIONS SET can_access = 0 WHERE role = 'Operator' AND page_key = 'po_pi'")
    t.bersihkan_cache()
    assert "po_pi" not in t.izin_role("Operator") and "pr_po" in t.izin_role("Operator")
    sql(buka, "DELETE FROM PERMISSIONS WHERE role = 'PPIC'")
    t.bersihkan_cache()
    assert t.izin_role("PPIC") == set()                                                                      # tanpa baris: tanpa akses


def test_nilai_bit_dari_database_dibaca_apa_adanya():
    t, buka, _ = toko()
    sql(buka, "DELETE FROM PERMISSIONS")
    for role, lap, a in (("Operator", "pr_po", 1), ("Operator", "po_pi", "1"), ("PPIC", "pr_po", 0), ("PPIC", "po_pi", ""),
                         ("SoftwareEngineer", "pr_po", "True"), ("SoftwareEngineer", "po_pi", "false")):
        sql(buka, "INSERT INTO PERMISSIONS (role, page_key, can_access) VALUES (?, ?, ?)", (role, lap, a))
    t.bersihkan_cache()
    assert t.izin_role("Operator") == {"pr_po", "po_pi"}
    assert t.izin_role("PPIC") == set()
    assert t.izin_role("SoftwareEngineer") == {"pr_po"}


def test_atur_izin_menambah_memperbarui_dan_langsung_berlaku():
    t, buka, path = toko(cache=60)                                              # cache 60 detik: perubahan tetap harus langsung terlihat
    assert "pr_po" in t.izin_role("Operator")
    sql(buka, "UPDATE PERMISSIONS SET can_edit = 1 WHERE role = 'Operator' AND page_key = 'pr_po'")
    assert t.atur_izin("operator", "pr_po", False) == {"role": "Operator", "laporan": "pr_po", "akses": False}
    assert "pr_po" not in t.izin_role("Operator")                                                            # tanpa menunggu cache
    t.atur_izin("Operator", "baru_lagi", True)                                                                # laporan yang belum punya baris: ditambahkan
    assert "baru_lagi" in t.izin_role("Operator")
    t.atur_izin("Operator", "baru_lagi", False)
    assert "baru_lagi" not in t.izin_role("Operator")
    c = sqlite3.connect(path)
    kolom = "role, can_access, can_edit, can_delete, can_approve, can_reject, can_done"
    assert c.execute(f"SELECT {kolom} FROM PERMISSIONS WHERE page_key = 'baru_lagi'").fetchall() == [("Operator", 0, 0, 0, 0, 0, 0)]   # satu baris, kolom lain nol
    assert c.execute(f"SELECT {kolom} FROM PERMISSIONS WHERE role = 'Operator' AND page_key = 'pr_po'").fetchall() == [("Operator", 0, 1, 0, 0, 0, 0)]  # hanya can_access diubah
    assert c.execute("SELECT COUNT(*) FROM PERMISSIONS WHERE role = 'Operator'").fetchone()[0] == len(LAPORAN_UJI) + 1      # tidak ada baris ganda
    c.close()
    assert "tidak ada di tabel role" in salah(lambda: t.atur_izin("Manager", "pr_po", True))


def test_hak_tidak_terbaca_menolak_akses_bukan_membukanya():
    t, buka, _ = toko()
    sql(buka, "DROP TABLE PERMISSIONS")
    assert "no such table" in salah(t.periksa_izin, PenyimpanTidakTersedia)
    assert "no such table" in salah(lambda: t.izin_role("Operator"), IzinTidakTerbaca)                       # bukan {} yang bisa disangka "tidak ada aturan"
    assert "no such table" in salah(lambda: t.izin_semua_role(LAPORAN_UJI), PenyimpanTidakTersedia)
    t2, buka2, _ = toko()
    sql(buka2, "DROP TABLE role")
    assert t2.izin_role("Operator") == set(LAPORAN_UJI)                                                     # tabel izin memakai nama role: tidak butuh tabel role
    assert "tidak valid" in salah(lambda: PenyimpanPengguna(buka, tabel_izin="izin; DROP TABLE users"), ValueError)


def test_izin_semua_role_untuk_halaman_permission_control():
    t, buka, _ = toko()
    sql(buka, "UPDATE PERMISSIONS SET can_access = 0 WHERE role = 'PPIC' AND page_key = 'pr_po'")
    sql(buka, "INSERT INTO role (DivisionId, RoleName, RoleDescription, Status) VALUES (1, 'Auditor', 'Audit', '0')")
    hasil = {r["nama"]: r for r in t.izin_semua_role(LAPORAN_UJI)}
    assert list(hasil) == ["System Administrator", "Operator", "PPIC", "SoftwareEngineer", "Auditor"]          # semua role di tabel role
    assert hasil["Operator"]["izin"] == {i: True for i in LAPORAN_UJI}
    assert hasil["PPIC"]["izin"]["pr_po"] is False and hasil["PPIC"]["izin"]["po_pi"] is True
    assert hasil["System Administrator"]["izin"] == {i: False for i in LAPORAN_UJI}                           # admin tidak disimpan
    assert hasil["Auditor"]["aktif"] is False and hasil["Operator"]["aktif"] is True
    assert t.izin_semua_role(["laporan_baru"])[1]["izin"] == {"laporan_baru": False}                         # laporan baru: belum ada yang boleh


# ---------- masukan akun baru ----------
def test_masukan_akun_baru_divalidasi_dan_dirapikan():
    ok = periksa_pengguna_baru("  budi.s ", "rahasia123", " Budi Santoso ", "operator", " Purchasing ", " YBS ", ROLE_TABEL, COMPANY_TABEL)
    assert ok == {"username": "budi.s", "sandi": "rahasia123", "nama": "Budi Santoso", "role": ROLE_OPERATOR, "divisi": "Purchasing", "company": "YBS"}
    kasus = [(dict(username="ab"), "Username"), (dict(username="a b c"), "Username"), (dict(username="x" * 51), "Username"),
             (dict(sandi="pendek"), "Password"), (dict(sandi="x" * 201), "Password"), (dict(nama="  "), "Nama lengkap"), (dict(nama="n" * 151), "Nama lengkap"),
             (dict(role="Manager"), "Role harus"), (dict(role=""), "Role harus"), (dict(divisi=""), "Divisi"), (dict(company=" "), "Company")]
    for ubah, kata in kasus:
        dasar = dict(username="budi", sandi="rahasia123", nama="Budi", role=ROLE_OPERATOR, divisi="IT", company="YBS")
        dasar.update(ubah)
        assert kata in salah(lambda: periksa_pengguna_baru(*dasar.values(), ROLE_TABEL, COMPANY_TABEL)), ubah
    assert ROLE_ADMIN in salah(lambda: periksa_pengguna_baru("budi", "rahasia123", "Budi", "x", "IT", "YBS", ROLE_TABEL, COMPANY_TABEL))   # pesan menyebut pilihan role
    assert "tabel role kosong" in salah(lambda: periksa_pengguna_baru("budi", "rahasia123", "Budi", "Operator", "IT", "YBS", [], COMPANY_TABEL))
    assert "tabel company kosong" in salah(lambda: periksa_pengguna_baru("budi", "rahasia123", "Budi", "Operator", "IT", "YBS", ROLE_TABEL, []))
    assert "ORI, RCM, SJN, SUN, YBS" in salah(lambda: periksa_pengguna_baru("budi", "rahasia123", "Budi", "Operator", "IT", "ACME", ROLE_TABEL, COMPANY_TABEL))
    assert periksa_pengguna_baru("budi", "rahasia123", "Budi", "Operator", "IT", " rcm ", ROLE_TABEL, COMPANY_TABEL)["company"] == "RCM"      # ditulis seperti di tabel


def test_akun_boleh_punya_lebih_dari_satu_company():
    baru = lambda company: periksa_pengguna_baru("budi", "rahasia123", "Budi", "Operator", "IT", company, ROLE_TABEL, COMPANY_TABEL)["company"]
    assert baru(["ybs", "ORI", "YBS"]) == "ORI, YBS"                           # urut seperti tabel company, tanpa duplikat
    assert baru("SUN, rcm") == "RCM, SUN"                                      # teks dipisah koma juga diterima
    assert "Company" in salah(lambda: baru([])) and "Company" in salah(lambda: baru(["ORI", "ACME"]))   # kosong, atau ada yang tidak dikenal
    assert daftar_company_akun("ORI, RCM") == ["ORI", "RCM"] and daftar_company_akun(None) == []
    lama = SimpleNamespace(role=ROLE_OPERATOR, company="LAMA, YBS")              # LAMA sudah tidak aktif di tabel company
    ubah = lambda company: periksa_ubah_pengguna("Budi", ROLE_OPERATOR, "IT", company, "", ROLE_TABEL, COMPANY_TABEL, lama)["company"]
    assert ubah(["LAMA", "YBS", "ORI"]) == "ORI, YBS, LAMA"                    # company lama yang tidak diubah boleh tetap
    assert "Company" in salah(lambda: ubah(["ACME"]))


# ---------- penyimpan ----------
def test_tambah_cari_daftar_dan_hapus():
    t, _, _ = toko()
    isi(t, baru("Budi"), baru("sari", nama="Sari Dewi", role="system administrator", divisi="IT", company="SUN"))
    p = t.cari("BUDI")                                                         # username tidak peka huruf besar-kecil
    assert (p.username, p.nama, p.role, p.divisi, p.company) == ("Budi", "Budi Santoso", ROLE_OPERATOR, "Purchasing", "YBS")
    assert ks.cocok("rahasia123", p.sandi) and "rahasia123" not in p.sandi and p.dibuat[:2] == "20" and p.id == t.cari_id(p.id).id
    assert t.cari("sari").role == ROLE_ADMIN                                   # role disimpan dalam nama resmi
    assert [x.username for x in t.daftar()] == ["Budi", "sari"] and t.cari("hantu") is None and t.cari_id(999) is None
    assert t.jumlah_admin() == 1
    assert t.opsi() == {"divisi": ["IT", "Purchasing"]}
    hapus = t.hapus(p.id)
    assert hapus.username == "Budi" and t.cari("budi") is None and [x.username for x in t.daftar()] == ["sari"]
    assert "tidak ditemukan" in salah(lambda: t.hapus(p.id))


def test_username_ganda_ditolak_tanpa_peduli_huruf():
    t, _, _ = toko()
    isi(t, baru("Budi"))
    assert "sudah dipakai" in salah(lambda: t.tambah(baru("BUDI"), "x"))
    assert len(t.daftar()) == 1


def test_kolom_kosong_di_database_menjadi_teks_kosong():
    t, buka, _ = toko()
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role, division, company, created_at) VALUES ('lama','h','Lama','Operator',NULL,NULL,NULL)")
    c.commit()
    c.close()
    p = t.cari("lama")
    assert (p.divisi, p.company, p.dibuat) == ("", "", "") and t.opsi() == {"divisi": []}


def test_cache_singkat_dan_langsung_dibersihkan_oleh_perubahan_dari_aplikasi():
    jam = [1000.0]
    path, buka = basis()
    web = PenyimpanPengguna(buka, cache_detik=30, jam=lambda: jam[0])           # seperti server web
    luar = PenyimpanPengguna(buka, cache_detik=0)                                # perubahan langsung di database (proses lain)
    isi(luar, baru("budi"))
    assert web.cari("budi").nama == "Budi Santoso"
    c = buka()
    c.execute("DELETE FROM users WHERE username = 'budi'")
    c.commit()
    c.close()
    jam[0] += 29
    assert web.cari("budi") is not None                                         # masih memakai hasil lama
    jam[0] += 2
    assert web.cari("budi") is None                                             # lewat 30 detik: terbaca ulang
    isi(web, baru("sari"))
    assert web.cari("sari") is not None
    web.hapus(web.cari("sari").id)
    assert web.cari("sari") is None                                             # hapus lewat aplikasi: berlaku langsung, tanpa menunggu


def test_database_tidak_terjangkau_dan_izin_ditolak():
    def putus():
        raise ConnectionError("server mati")
    rusak = PenyimpanPengguna(putus)
    for fn in (lambda: rusak.cari("x"), rusak.daftar, rusak.periksa, rusak.jumlah_admin, lambda: rusak.tambah(baru(), "h")):
        assert "ConnectionError" in salah(fn, PenyimpanTidakTersedia)
    assert rusak.izin_tulis() is None and rusak.id_otomatis() is None

    def ditolak():
        raise PermissionError("The INSERT permission was denied on the object 'users'")
    assert "permission was denied" in salah(lambda: PenyimpanPengguna(ditolak).tambah(baru(), "h"), TidakPunyaIzin)
    assert issubclass(TidakPunyaIzin, PenyimpanTidakTersedia)


def test_pemeriksaan_awal_tabel_dan_nama_tabel():
    t, _, _ = toko()
    t.periksa()                                                                  # tabel lengkap: lolos
    _, buka = basis("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, full_name TEXT, role TEXT)")
    assert "division" in salah(PenyimpanPengguna(buka).periksa, PenyimpanTidakTersedia)     # kolom kurang: pesan dari database menyebut kolomnya
    assert "no such table" in salah(PenyimpanPengguna(buka, tabel="tidak_ada").periksa, PenyimpanTidakTersedia)
    for buruk in ["users; DROP TABLE users", "us ers", "", "a.b.c.d", "1users", "users--"]:
        assert "tidak valid" in salah(lambda: PenyimpanPengguna(buka, tabel=buruk), ValueError)
    PenyimpanPengguna(buka, tabel="dbo.users")                                   # nama dengan skema boleh


def test_jenis_hash_di_tabel_dihitung():
    t, buka, _ = toko()
    isi(t, baru("aaa"), baru("bbb"))
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('c', 'pbkdf2_sha256$1$s$AA==', 'C', 'Operator')")
    c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('d', 'teks-biasa', 'D', 'Operator')")
    c.commit()
    c.close()
    assert t.jenis_hash() == {"scrypt": 2, "django-pbkdf2": 1, None: 1}


# ---------- alat bantu (cek dan buat-admin) ----------
def jalan(argv, t, sandi=(), teks=()):
    keluar, ps, pt = [], iter(sandi), iter(teks)
    kode = alat.main(argv, penyimpan=t, baca_sandi=lambda p: next(ps), baca_teks=lambda p: next(pt), keluar=keluar.append)
    return kode, "\n".join(keluar)


def test_alat_cek_melaporkan_tanpa_menampilkan_hash():
    t, buka, _ = toko()
    isi(t, baru("admin", role=ROLE_ADMIN), baru("opr"))
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('x', '$argon2id$v=19$m=1,t=1,p=1$garam$hashrahasia', 'X', 'Manager')")
    c.commit()
    c.close()
    with pustaka_palsu(argon2=None):                                            # argon2-cffi belum terpasang
        kode, o = jalan(["cek"], t)
    assert kode == 1
    assert "Jumlah akun: 3" in o and "'Manager': 1 akun" in o and "tidak cocok dengan nama maupun RoleId" in o
    assert "Tabel role 'role': 4 role" in o and "3: PPIC" in o and "4: SoftwareEngineer" in o and "Kolom users.role menyimpan: nama role" in o
    assert "argon2: 1 akun" in o and "BELUM terpasang (pip install argon2-cffi)" in o and "scrypt: 2 akun" in o
    assert "System Administrator: 1" in o and "Akun baru akan memakai hash: scrypt" in o
    assert "hashrahasia" not in o and "scrypt$" not in o                        # hash tidak pernah ditampilkan
    assert "tidak bisa diperiksa" in o                                          # izin tulis hanya bisa diperiksa di SQL Server


def test_alat_cek_bersih_dan_gagal_membaca():
    t, _, _ = toko()
    isi(t, baru("admin", role=ROLE_ADMIN))
    kode, o = jalan(["cek"], t)
    assert kode == 0 and "Koneksi dan kolom: OK" in o and "System Administrator: 1" in o
    kosong, _, _ = toko()
    assert "belum ada; buat dengan: python -m inti.alat_pengguna buat-admin" in jalan(["cek"], kosong)[1]

    def putus():
        raise ConnectionError("server mati")
    kode, o = jalan(["cek"], PenyimpanPengguna(putus))
    assert kode == 2 and "GAGAL membaca tabel" in o and "ConnectionError" in o


def test_alat_buat_admin_pertama():
    t, _, _ = toko()
    kode, o = jalan(["buat-admin"], t, sandi=["rahasia123", "rahasia123"], teks=["admin", "Admin Utama", "IT", "YBS"])
    assert kode == 0 and "dibuat" in o and "rahasia123" not in o
    a = t.cari("admin")
    assert a.role == ROLE_ADMIN and (a.nama, a.divisi, a.company) == ("Admin Utama", "IT", "YBS") and ks.cocok("rahasia123", a.sandi)
    kode, o = jalan(["buat-admin"], t)                                          # sudah ada administrator: ditolak, tanpa bertanya apa pun
    assert kode == 1 and "Sudah ada 1 System Administrator" in o
    kode, o = jalan(["buat-admin", "--paksa"], t, sandi=["rahasia123", "rahasia123"], teks=["admin2", "Admin Dua", "IT", "SUN"])
    assert kode == 0 and t.jumlah_admin() == 2


def test_alat_buat_admin_menolak_masukan_buruk_dan_database_mati():
    t, _, _ = toko()
    assert jalan(["buat-admin"], t, sandi=["rahasia123", "lain-lagi-123"], teks=["admin", "A", "IT", "YBS"])[0] == 1       # konfirmasi beda
    k, o = jalan(["buat-admin"], t, sandi=["pendek", "pendek"], teks=["admin", "A", "IT", "YBS"])
    assert k == 1 and "Password minimal 8" in o
    k, o = jalan(["buat-admin"], t, sandi=["rahasia123", "rahasia123"], teks=["a", "A", "IT", "YBS"])
    assert k == 1 and "Username" in o and t.daftar() == []                      # tidak ada yang tersimpan

    def putus():
        raise ConnectionError("server mati")
    assert jalan(["buat-admin"], PenyimpanPengguna(putus))[0] == 2


def test_alat_buat_admin_memakai_hash_yang_sama_dengan_tabel():
    t, buka, _ = toko()
    c = buka()
    c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('lama', 'pbkdf2_sha256$1$s$AA==', 'Lama', 'Operator')")
    c.commit()
    c.close()
    kode, o = jalan(["buat-admin"], t, sandi=["rahasia123", "rahasia123"], teks=["admin", "Admin", "IT", "YBS"])
    assert kode == 0 and "hash django-pbkdf2" in o and ks.jenis_hash(t.cari("admin").sandi) == "django-pbkdf2"
    with pustaka_palsu(argon2=None):                                            # hash di tabel argon2 tetapi pustaka tidak ada: pesan jelas
        t2, buka2, _ = toko()
        c = buka2()
        c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES ('lama', '$argon2id$v=19$m=1,t=1,p=1$g$h', 'Lama', 'Operator')")
        c.commit()
        c.close()
        kode, o = jalan(["buat-admin"], t2, sandi=["rahasia123", "rahasia123"], teks=["admin", "Admin", "IT", "YBS"])
        assert kode == 1 and "argon2-cffi" in o and t2.cari("admin") is None


# ---------- tabel role ----------
def sql(buka, perintah, params=()):
    c = buka()
    c.execute(perintah, params)
    c.commit()
    c.close()


def tambah_mentah(buka, username, role):
    sql(buka, "INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES (?, ?, ?, ?, 'IT', 'YBS')",
        (username, ks.hash_sandi("rahasia123"), username.capitalize(), role))


def test_role_diambil_dari_tabel_role_dengan_status():
    t, buka, _ = toko()
    r = t.daftar_role()
    assert [x["nama"] for x in r] == ROLE_AWAL and all(x["aktif"] for x in r) and r[0]["id"] == 1 and r[2]["deskripsi"] == "Deskripsi PPIC"
    for st in ("0", "false", "No", "nonaktif", "Tidak Aktif", " 0 ", "Inactive", "disabled"):
        sql(buka, "UPDATE role SET Status = ? WHERE RoleId = 2", (st,))
        assert t.role_aktif() == [ROLE_ADMIN, ROLE_PPIC, ROLE_SOFTWARE], st            # Operator nonaktif: tidak ditawarkan untuk akun baru
    for st in ("1", "Active", "aktif", "true", "Y", None, 1):
        sql(buka, "UPDATE role SET Status = ? WHERE RoleId = 2", (st,))
        assert ROLE_OPERATOR in t.role_aktif(), st


def test_users_role_berisi_roleid_diubah_menjadi_nama():
    t, buka, _ = toko()
    for u, rid in (("adm1", "1"), ("opr1", "2"), ("ppic1", "3")):
        tambah_mentah(buka, u, rid)
    assert t.cari("adm1").role == ROLE_ADMIN and adalah_admin(t.cari("adm1").role)
    assert t.cari("opr1").role == ROLE_OPERATOR and t.cari("ppic1").role == ROLE_PPIC
    assert [p.role for p in t.daftar()] == [ROLE_ADMIN, ROLE_OPERATOR, ROLE_PPIC] and t.jumlah_admin() == 1
    assert t.role_disimpan() == "id"


def test_role_disimpan_mengikuti_akun_yang_sudah_ada_dan_bisa_dipaksa():
    t, buka, _ = toko()
    assert t.role_disimpan() == "nama"                                           # tabel kosong: nama
    tambah_mentah(buka, "satu", "Operator")
    assert t.role_disimpan() == "nama"
    tambah_mentah(buka, "dua", "2")
    assert t.role_disimpan() == "nama"                                           # campur nama dan angka: tidak dianggap id
    sql(buka, "UPDATE users SET role = '2'")
    assert t.role_disimpan() == "id"
    assert PenyimpanPengguna(buka, role_disimpan="nama").role_disimpan() == "nama"       # dipaksa lewat ROLE_DISIMPAN
    assert PenyimpanPengguna(basis()[1], role_disimpan="id").role_disimpan() == "id"
    assert "ROLE_DISIMPAN" in salah(lambda: PenyimpanPengguna(buka, role_disimpan="x"), ValueError)


def test_akun_baru_disimpan_sebagai_nama_atau_roleid_menurut_tabel():
    t, buka, path = toko()
    isi(t, baru("pakai_nama", role=ROLE_PPIC))
    c = sqlite3.connect(path)
    assert c.execute("SELECT role FROM users WHERE username = 'pakai_nama'").fetchone()[0] == "PPIC"
    c.close()
    sql(buka, "UPDATE users SET role = '2'")                                      # sekarang semua akun memakai RoleId
    isi(t, baru("pakai_id", role=ROLE_SOFTWARE))
    c = sqlite3.connect(path)
    assert str(c.execute("SELECT role FROM users WHERE username = 'pakai_id'").fetchone()[0]) == "4"        # RoleId SoftwareEngineer
    c.close()
    assert t.cari("pakai_id").role == ROLE_SOFTWARE                               # dibaca kembali sebagai nama
    sql(buka, "DELETE FROM role WHERE RoleName = 'PPIC'")
    t.bersihkan_cache()
    assert "tidak ditemukan di tabel role" in salah(lambda: t.tambah(baru("hantu1", role=ROLE_PPIC), "h"))


def test_tabel_role_tidak_terbaca_tidak_menghalangi_login_lama():
    t, buka, _ = toko()
    tambah_mentah(buka, "lama1", "Operator")
    sql(buka, "DROP TABLE role")
    assert "no such table" in salah(t.periksa_role, PenyimpanTidakTersedia) and "no such table" in salah(t.role_aktif, PenyimpanTidakTersedia)
    assert t.cari("lama1").role == "Operator" and [p.username for p in t.daftar()] == ["lama1"]      # nilai mentah dipakai apa adanya
    isi(t, baru("baru1", role=ROLE_PPIC))                                        # role disimpan sebagai nama: tidak butuh tabel role
    assert t.cari("baru1").role == ROLE_PPIC


def test_nama_tabel_role_divalidasi():
    _, buka, _ = toko()
    for buruk in ["role; DROP TABLE users", "ro le", "", "a.b.c.d"]:
        assert "tidak valid" in salah(lambda: PenyimpanPengguna(buka, tabel_role=buruk), ValueError)
    PenyimpanPengguna(buka, tabel_role="dbo.role")


def test_alat_cek_menandai_role_tanpa_aturan_nonaktif_dan_roleid_tak_dikenal():
    t, buka, _ = toko()
    sql(buka, "INSERT INTO role (DivisionId, RoleName, RoleDescription, Status) VALUES (2, 'Auditor', 'Audit', '0')")
    tambah_mentah(buka, "adm1", "1")
    tambah_mentah(buka, "aud1", "5")
    tambah_mentah(buka, "hantu", "99")
    kode, o = jalan(["cek"], t)
    assert kode == 1 and "Tabel role 'role': 5 role" in o and "5: Auditor" in o
    assert "nonaktif, tidak ditawarkan untuk akun baru" in o and "LAPORAN_PER_ROLE" not in o
    assert "Auditor: 1 akun" in o and "'99': 1 akun" in o and "tidak cocok dengan nama maupun RoleId" in o
    assert "Kolom users.role menyimpan: RoleId (angka)" in o and "System Administrator: 1" in o
    assert "1: System Administrator" in o and "3: PPIC" in o and "4: SoftwareEngineer" in o


def test_alat_cek_dan_buat_admin_saat_tabel_role_bermasalah():
    t, buka, _ = toko()
    isi(t, baru("admin1", role=ROLE_ADMIN))
    sql(buka, "DROP TABLE role")
    kode, o = jalan(["cek"], t)
    assert kode == 1 and "Tabel role 'role': GAGAL dibaca" in o and "Jumlah akun: 1" in o
    t2, buka2, _ = toko()
    sql(buka2, "DELETE FROM role WHERE RoleName = 'System Administrator'")
    kode, o = jalan(["buat-admin"], t2)
    assert kode == 1 and "tidak punya role 'System Administrator'" in o and t2.daftar() == []
    t3, buka3, path3 = toko()
    tambah_mentah(buka3, "lama1", "2")                                            # tabel memakai RoleId
    kode, o = jalan(["buat-admin", "--paksa"], t3, sandi=["rahasia123", "rahasia123"], teks=["admin9", "Admin Sembilan", "IT", "YBS"])
    c = sqlite3.connect(path3)
    assert kode == 0 and str(c.execute("SELECT role FROM users WHERE username = 'admin9'").fetchone()[0]) == "1" and t3.cari("admin9").role == ROLE_ADMIN
    c.close()


def test_tabel_seperti_milik_pengguna_cek_bersih_dan_akun_baru_memakai_nama_role_dari_tabel():
    """Meniru hasil `cek` pada tabel pengguna: role 'Software Engineer' (dengan spasi), empat akun dengan hash Werkzeug scrypt."""
    t, buka, _ = toko()
    sql(buka, "DELETE FROM role")
    for rid, nama in ((1, "Software Engineer"), (2, "System Administrator"), (3, "PPIC"), (4, "Operator")):
        sql(buka, "INSERT INTO role (RoleId, DivisionId, RoleName, RoleDescription, Status, CreatedAt) VALUES (?, 1, ?, ?, 'Active', '2026-01-01')", (rid, nama, nama))
    for u, r, dv in (("adm_a", "System Administrator", "Information Technology"), ("adm_b", "System Administrator", "Manufacturing"),
                     ("ppic_a", "PPIC", "Manufacturing"), ("opr_a", "Operator", "Information Technology")):
        sql(buka, "INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES (?, ?, ?, ?, ?, 'YBS')",
            (u, ks.hash_sandi("rahasia123", "werkzeug-scrypt"), u, r, dv))
    kode, o = jalan(["cek"], t)
    assert kode == 0 and "<-" not in o                                           # tidak ada yang ditandai bermasalah
    assert "Tabel role 'role': 4 role" in o and "1: Software Engineer" in o and "System Administrator: 2 akun" in o and "PPIC: 1 akun" in o
    assert "Kolom users.role menyimpan: nama role" in o and "werkzeug-scrypt: 4 akun" in o and "Akun baru akan memakai hash: werkzeug-scrypt" in o
    assert "Information Technology (2)" in o and "Manufacturing (2)" in o and "YBS (4)" in o and "System Administrator: 2" in o
    assert t.role_aktif() == ["Software Engineer", "System Administrator", "PPIC", "Operator"]
    t.bersihkan_cache()                                                           # RoleId berubah urutan: hak disimpan per nama role, jadi tetap berlaku
    assert all(t.izin_role(r) == set(LAPORAN_UJI) for r in ("Software Engineer", "PPIC", "Operator")) and t.izin_role("System Administrator") == set()
    data = periksa_pengguna_baru("swe12345", "rahasia123", "Engineer Baru", "softwareengineer", "Information Technology", "YBS", t.role_aktif(), t.company_aktif())
    assert data["role"] == "Software Engineer"                                    # nama persis seperti di tabel role, bukan ketikan pengguna
    t.tambah(data, ks.hash_sandi("rahasia123", "werkzeug-scrypt"))
    assert t.cari("swe12345").role == "Software Engineer" and not adalah_admin(t.cari("swe12345").role) and t.jumlah_admin() == 2


# ---------- tabel company ----------
def test_company_nama_unik_dari_tabel_company_dengan_status():
    t, buka, _ = toko()
    t.periksa_company()
    daftar = t.daftar_company()
    assert [c["nama"] for c in daftar] == COMPANY_TABEL and all(c["aktif"] for c in daftar)    # lima nama dari sebelas baris; spasi CHAR dibuang
    assert t.company_aktif() == COMPANY_TABEL
    sql(buka, "UPDATE company SET Status = 0 WHERE CompName LIKE 'SJN%'")                         # semua baris SJN nonaktif
    assert t.company_aktif() == ["ORI", "RCM", "SUN", "YBS"]
    assert {c["nama"]: c["aktif"] for c in t.daftar_company()}["SJN"] is False
    sql(buka, "UPDATE company SET Status = '1' WHERE CompID = 8")                                  # satu baris aktif sudah cukup
    assert "SJN" in t.company_aktif()
    sql(buka, "INSERT INTO company (CompID, CompName, Status) VALUES (12, '   ', 1)")             # nama kosong diabaikan
    assert len(t.daftar_company()) == 5


def test_tabel_company_tidak_terbaca_dan_nama_tabel_divalidasi():
    t, buka, _ = toko()
    sql(buka, "DROP TABLE company")
    assert "no such table" in salah(t.periksa_company, PenyimpanTidakTersedia) and "no such table" in salah(t.company_aktif, PenyimpanTidakTersedia)
    assert t.cari("tidak.ada") is None                                                              # tabel lain tidak terpengaruh
    assert "tidak valid" in salah(lambda: PenyimpanPengguna(buka, tabel_company="company; DROP TABLE users"), ValueError)


def test_alat_cek_melaporkan_company():
    t, buka, _ = toko()
    isi(t, baru("adm1", role=ROLE_ADMIN, company="YBS"))
    sql(buka, "INSERT INTO users (username, password_hash, full_name, role, division, company) VALUES ('acme1', ?, 'Acme', 'Operator', 'IT', 'ACME')",
        (ks.hash_sandi("rahasia123"),))
    kode, o = jalan(["cek"], t)
    assert kode == 1 and "Tabel company 'company': 5 company aktif (ORI, RCM, SJN, SUN, YBS)" in o
    assert "Company di akun yang tidak ada di tabel company: ACME" in o
    sql(buka, "UPDATE company SET Status = 0 WHERE CompName LIKE 'RCM%'")
    assert "5 company aktif" not in jalan(["cek"], t)[1] and "4 company aktif (ORI, SJN, SUN, YBS); tidak aktif: RCM" in jalan(["cek"], t)[1]
    sql(buka, "DROP TABLE company")
    kode, o = jalan(["cek"], t)
    assert kode == 1 and "Tabel company 'company': GAGAL dibaca" in o
    kode, o = jalan(["buat-admin", "--paksa"], t, sandi=["rahasia123", "rahasia123"], teks=["admin9", "Admin", "IT", "YBS"])
    assert kode == 2 and "company" in o
