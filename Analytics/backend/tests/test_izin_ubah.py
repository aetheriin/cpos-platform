"""Edit akun oleh admin, dan Permission Control (hak akses laporan per role): penyimpan, endpoint, dan penegakannya."""
import ahli  # noqa: F401
import logging
import sqlite3
from types import SimpleNamespace

import api
from inti import sandi as ks
from inti.pengguna import DataTidakValid, TidakPunyaIzin, periksa_ubah_pengguna
from test_auth import ADMIN, LAP, OPERATOR, Respons, kode, masuk, muat_contoh, pengguna, segar
from test_pengguna import LAPORAN_UJI, ROLE_OPERATOR, ROLE_PPIC, ROLE_SOFTWARE, COMPANY_TABEL, ROLE_TABEL, baru as akun_data, isi, salah, sql, toko


def perm_ubah(**ubah):
    d = dict(nama="Operator Baru", role=ROLE_OPERATOR, divisi="Purchasing", company="YBS", sandi=None)
    d.update(ubah)
    return api.PermintaanUbahPengguna(**d)


def id_dari(t, username):
    return str(t.cari(username).id)


# ================= edit akun: validasi dan penyimpanan =================
def lama_pengguna(**ubah):
    d = dict(id=1, username="budi", nama="Budi", role=ROLE_OPERATOR, divisi="IT", company="YBS", sandi="h", dibuat="")
    d.update(ubah)
    return SimpleNamespace(**d)


def test_validasi_ubah_akun():
    lama = lama_pengguna()
    ok = periksa_ubah_pengguna("  Budi S ", "operator", " Purchasing ", "sun", "", ROLE_TABEL, COMPANY_TABEL, lama)
    assert ok == {"nama": "Budi S", "role": "Operator", "divisi": "Purchasing", "company": "SUN", "sandi": None}          # sandi kosong: tidak diganti
    assert periksa_ubah_pengguna("Budi", "PPIC", "IT", "YBS", "rahasia123", ROLE_TABEL, COMPANY_TABEL, lama)["sandi"] == "rahasia123"
    for ubah, kata in ((dict(nama="  "), "Nama lengkap"), (dict(nama="x" * 151), "Nama lengkap"), (dict(role="Manager"), "Role harus salah satu dari"),
                       (dict(divisi=""), "Divisi"), (dict(divisi="d" * 101), "Divisi"), (dict(company="ACME"), "Company harus dipilih minimal satu"),
                       (dict(company=""), "Company harus dipilih minimal satu"), (dict(sandi="pendek"), "Password baru minimal 8"), (dict(sandi="x" * 201), "Password baru")):
        d = dict(nama="Budi", role="Operator", divisi="IT", company="YBS", sandi=None)
        d.update(ubah)
        assert kata in salah(lambda: periksa_ubah_pengguna(d["nama"], d["role"], d["divisi"], d["company"], d["sandi"], ROLE_TABEL, COMPANY_TABEL, lama)), ubah


def test_role_dan_company_lama_boleh_tetap_walau_sudah_tidak_ada_di_pilihan():
    lama = lama_pengguna(role="Auditor", company="LAMA")
    ok = periksa_ubah_pengguna("Budi", "auditor", "IT", "lama", None, ROLE_TABEL, COMPANY_TABEL, lama)                  # tidak diubah: tetap sah
    assert ok["role"] == "Auditor" and ok["company"] == "LAMA"
    assert "Role harus salah satu dari" in salah(lambda: periksa_ubah_pengguna("Budi", "Manager", "IT", "YBS", None, ROLE_TABEL, COMPANY_TABEL, lama))   # yang baru harus dari pilihan
    assert "Company harus" in salah(lambda: periksa_ubah_pengguna("Budi", "Auditor", "IT", "ACME", None, ROLE_TABEL, COMPANY_TABEL, lama))


def test_penyimpan_ubah_hanya_menulis_kolom_yang_berubah_dan_role_mentah_tidak_rusak():
    t, buka, path = toko()
    isi(t, akun_data("budi", role=ROLE_OPERATOR, company="YBS"))
    sql(buka, "UPDATE users SET role = '2'")                                                          # tabel menyimpan RoleId
    t.bersihkan_cache()
    b = t.cari("budi")
    hasil = t.ubah(b.id, {"nama": "Budi Baru", "role": "Operator", "divisi": "Finance", "company": "SUN"})   # role tidak diubah
    c = sqlite3.connect(path)
    assert str(c.execute("SELECT role FROM users WHERE username = 'budi'").fetchone()[0]) == "2"           # nilai asli (RoleId) tidak disentuh
    assert hasil.nama == "Budi Baru" and hasil.divisi == "Finance" and hasil.company == "SUN" and hasil.role == "Operator" and hasil.id == b.id
    t.ubah(b.id, {"nama": "Budi Baru", "role": "PPIC", "divisi": "Finance", "company": "SUN"})            # role diubah: disimpan menurut cara tabel (RoleId)
    assert str(c.execute("SELECT role FROM users WHERE username = 'budi'").fetchone()[0]) == "3" and t.cari("budi").role == "PPIC"
    c.close()
    t2, buka2, path2 = toko()
    isi(t2, akun_data("sari", role=ROLE_OPERATOR))
    b2 = t2.cari("sari")
    t2.ubah(b2.id, {"nama": "Sari", "role": "PPIC", "divisi": "IT", "company": "YBS"}, "hash-baru")
    c2 = sqlite3.connect(path2)
    assert c2.execute("SELECT role, password_hash, username FROM users").fetchone() == ("PPIC", "hash-baru", "sari")       # nama role; password diganti; username tetap
    c2.close()
    assert "tidak ditemukan" in salah(lambda: t2.ubah(9999, {"nama": "x", "role": "PPIC", "divisi": "IT", "company": "YBS"}))


def test_ubah_langsung_terlihat_walau_cache_pengguna_panjang():
    t, buka, _ = toko(cache=60)
    isi(t, akun_data("budi"))
    sebelum = t.cari("budi")                                                                           # masuk ke cache 60 detik
    t.ubah(sebelum.id, {"nama": "Nama Lain", "role": "Operator", "divisi": "IT", "company": "YBS"})
    assert t.cari("budi").nama == "Nama Lain"                                                          # cache dibersihkan setelah ubah


# ================= edit akun: endpoint =================
def test_admin_mengedit_akun_dan_perubahan_langsung_berlaku():
    t, _ = segar()
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    hasil = api.ubah_pengguna(id_dari(t, OPERATOR[0]), perm_ubah(nama="Operator Dua", role="ppic", divisi="Finance", company="sun"), user=admin)
    assert hasil["nama"] == "Operator Dua" and hasil["role"] == "PPIC" and hasil["divisi"] == "Finance" and hasil["company"] == "SUN" and hasil["admin"] is False
    assert "sandi" not in hasil and "password_hash" not in hasil and hasil["username"] == OPERATOR[0]
    info = api.pengguna_saat_ini(sesi_id=operator["_sid"])                                              # sesi berjalan: role baru berlaku tanpa masuk ulang
    assert info["role"] == "PPIC" and info["nama"] == "Operator Dua" and info["laporan"] == LAPORAN_UJI
    assert api.saya(user=info)["divisi"] == "Finance"
    daftar = {p["username"]: p for p in api.daftar_pengguna(user=admin)}
    assert daftar[OPERATOR[0]]["role"] == "PPIC" and daftar[OPERATOR[0]]["company"] == "SUN"


def test_ganti_password_oleh_admin_mencabut_sesi_dan_membuang_laporan_akun_itu():
    t, _ = segar()
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    p = muat_contoh(operator, [])
    assert api.gudang.ambil(p.data_id) is not None
    api.ubah_pengguna(id_dari(t, OPERATOR[0]), perm_ubah(sandi="passwordbaru123"), user=admin)
    k, pesan = kode(api.pengguna_saat_ini, sesi_id=operator["_sid"])
    assert k == 401 and "Password akun Anda diganti oleh administrator" in pesan                         # perangkat lama diberi tahu sebabnya
    assert api.gudang.ambil(p.data_id) is None                                                          # laporan yang dimuat ikut dibuang
    assert kode(lambda: masuk(OPERATOR[0], OPERATOR[1]))[0] == 401                                       # password lama tidak berlaku
    assert masuk(OPERATOR[0], "passwordbaru123")[0]["username"] == OPERATOR[0]                           # password baru berlaku
    assert ks.jenis_hash(t.cari(OPERATOR[0]).sandi) is not None


def test_ganti_password_akun_sendiri_tidak_mengeluarkan_admin():
    t, _ = segar()
    admin = pengguna(ADMIN)
    api.ubah_pengguna(id_dari(t, ADMIN[0]), perm_ubah(nama="Admin Satu", role=ROLE_ADMIN_NAMA, divisi="IT", company="YBS", sandi="adminbaru123"), user=admin)
    assert api.pengguna_saat_ini(sesi_id=admin["_sid"])["username"] == ADMIN[0]                          # sesi yang sedang dipakai tetap hidup
    assert kode(lambda: masuk(ADMIN[0], ADMIN[1]))[0] == 401 and masuk(ADMIN[0], "adminbaru123")[0]["admin"] is True


ROLE_ADMIN_NAMA = "System Administrator"


def test_aturan_pengaman_edit_akun():
    t, _ = segar()
    admin = pengguna(ADMIN)
    k, pesan = kode(api.ubah_pengguna, id_dari(t, ADMIN[0]), perm_ubah(role=ROLE_OPERATOR), user=admin)   # mengubah role akun sendiri
    assert k == 400 and "role akun Anda sendiri" in pesan and t.cari(ADMIN[0]).role == ROLE_ADMIN_NAMA
    orang_lain = dict(admin, id=999)                                                                     # admin lain yang tidak ada di tabel; admin1 satu-satunya admin
    k, pesan = kode(api.ubah_pengguna, id_dari(t, ADMIN[0]), perm_ubah(role=ROLE_OPERATOR), user=orang_lain)
    assert k == 400 and "terakhir" in pesan and t.cari(ADMIN[0]).role == ROLE_ADMIN_NAMA
    api.ubah_pengguna(id_dari(t, OPERATOR[0]), perm_ubah(role=ROLE_ADMIN_NAMA), user=admin)              # menaikkan akun lain jadi admin diizinkan
    assert t.cari(OPERATOR[0]).role == ROLE_ADMIN_NAMA and t.jumlah_admin() == 2
    api.ubah_pengguna(id_dari(t, OPERATOR[0]), perm_ubah(role=ROLE_OPERATOR), user=admin)                # sekarang ada dua admin: boleh diturunkan
    assert t.cari(OPERATOR[0]).role == ROLE_OPERATOR


def test_edit_akun_menolak_masukan_salah_dan_menjelaskan_masalah_izin():
    t, _ = segar()
    admin = pengguna(ADMIN)
    uid = id_dari(t, OPERATOR[0])
    assert kode(api.ubah_pengguna, "9999", perm_ubah(), user=admin)[0] == 404
    assert kode(api.ubah_pengguna, "bukan-angka-atau-id", perm_ubah(), user=admin)[0] in (400, 404, 422)
    for ubah, kata in ((dict(nama=""), "Nama lengkap"), (dict(role="Manager"), "Role harus"), (dict(company="ACME"), "Company harus"),
                       (dict(sandi="pendek"), "Password baru"), (dict(divisi=" "), "Divisi")):
        k, pesan = kode(api.ubah_pengguna, uid, perm_ubah(**ubah), user=admin)
        assert k == 422 and kata in pesan, ubah
    assert t.cari(OPERATOR[0]).nama == "Operator Satu"                                                    # tidak ada yang berubah
    asli = t.ubah
    t.ubah = lambda *a, **k: (_ for _ in ()).throw(TidakPunyaIzin("UPDATE permission was denied"))
    try:
        k, pesan = kode(api.ubah_pengguna, uid, perm_ubah(nama="X"), user=admin)
    finally:
        t.ubah = asli
    assert k == 503 and "UPDATE" in pesan and "administrator database" in pesan
    assert kode(api.wajib_admin, user=pengguna(OPERATOR))[0] == 403                                       # hanya System Administrator


def test_akun_dengan_role_nonaktif_tetap_bisa_disunting_tanpa_mengubah_role():
    t, buka = segar()
    sql(buka, "UPDATE role SET Status = '0' WHERE RoleName = 'Operator'")                                  # role Operator dinonaktifkan
    t.bersihkan_cache()
    admin = pengguna(ADMIN)
    hasil = api.ubah_pengguna(id_dari(t, OPERATOR[0]), perm_ubah(nama="Masih Bisa", role=ROLE_OPERATOR), user=admin)
    assert hasil["nama"] == "Masih Bisa" and hasil["role"] == ROLE_OPERATOR
    assert "Operator" not in api.opsi_pengguna(user=admin)["role"]                                         # tidak ditawarkan untuk akun baru


# ================= Permission Control: penyimpan dan endpoint =================
def tangkap_log():
    pesan = []

    class H(logging.Handler):
        def emit(self, rec):
            pesan.append(rec.getMessage())
    h = H()
    api.log.addHandler(h)
    return pesan, h


def hapus_izin(buka, role=None):
    sql(buka, "DELETE FROM PERMISSIONS" + (" WHERE role = ?" if role else ""), (role,) if role else ())


def tanpa(*ids):
    """Laporan yang terdaftar, kecuali ids, urut seperti menu."""
    return [i for i in LAPORAN_UJI if i not in ids]


def test_halaman_permission_control_memuat_semua_laporan_dan_hak_tiap_role():
    t, buka = segar()
    sql(buka, "UPDATE PERMISSIONS SET can_access = 0 WHERE role = 'PPIC' AND page_key = 'pr_po'")             # PPIC tanpa akses PR/PO
    sql(buka, "INSERT INTO role (DivisionId, RoleName, RoleDescription, Status) VALUES (1, 'Auditor', 'x', '0')")
    h = api.daftar_izin(user=pengguna(ADMIN))
    assert [l["id"] for l in h["laporan"]] == LAPORAN_UJI and all({"id", "nama", "deskripsi"} <= set(l) for l in h["laporan"])
    assert [r["nama"] for r in h["role"]] == ["Operator", "PPIC", "SoftwareEngineer", "System Administrator"]      # abjad; role nonaktif tidak tampil
    per = {r["nama"]: r for r in h["role"]}
    assert per["System Administrator"]["admin"] is True and per["System Administrator"]["izin"] == {i: True for i in LAPORAN_UJI}
    assert per["Operator"]["admin"] is False and per["Operator"]["izin"] == {i: True for i in LAPORAN_UJI}
    assert per["PPIC"]["izin"]["pr_po"] is False and per["PPIC"]["izin"]["po_pi"] is True
    hapus_izin(buka, "SoftwareEngineer")
    assert {r["nama"]: r for r in api.daftar_izin(user=pengguna(ADMIN))["role"]}["SoftwareEngineer"]["izin"]["po_pi"] is False
    assert kode(api.wajib_admin, user=pengguna(OPERATOR))[0] == 403


def test_admin_mengatur_hak_dan_langsung_berlaku_untuk_sesi_yang_berjalan():
    t, buka = segar()
    admin, operator = pengguna(ADMIN), pengguna(OPERATOR)
    assert operator["laporan"] == LAPORAN_UJI
    hasil = api.atur_izin(api.PermintaanIzin(role="operator", laporan="po_pi", akses=False), user=admin)
    assert hasil == {"role": "Operator", "laporan": "po_pi", "akses": False}
    info = api.pengguna_saat_ini(sesi_id=operator["_sid"])                                                 # tanpa masuk ulang
    assert info["laporan"] == tanpa("po_pi")
    assert [l["id"] for l in api.daftar_laporan(user=info)] == tanpa("po_pi")
    api.atur_izin(api.PermintaanIzin(role="Operator", laporan="po_pi", akses=True), user=admin)
    info = api.pengguna_saat_ini(sesi_id=operator["_sid"])
    assert info["laporan"] == LAPORAN_UJI
    c = sqlite3.connect(sqlite_path(buka))
    assert c.execute("SELECT can_access FROM PERMISSIONS WHERE role = 'Operator' AND page_key = 'po_pi'").fetchall() == [(1,)]   # satu baris, diperbarui
    c.close()


def sqlite_path(buka):
    c = buka()
    path = c.execute("PRAGMA database_list").fetchone()[2]
    c.close()
    return path


def test_atur_izin_menolak_yang_tidak_sah():
    t, buka = segar()
    admin = pengguna(ADMIN)
    P = api.PermintaanIzin
    assert kode(api.atur_izin, P(role="Operator", laporan="tidak-ada", akses=True), user=admin)[0] == 422
    k, pesan = kode(api.atur_izin, P(role="Manager", laporan="pr_po", akses=True), user=admin)
    assert k == 422 and "tidak ada di tabel role" in pesan
    k, pesan = kode(api.atur_izin, P(role="system administrator", laporan="pr_po", akses=False), user=admin)
    assert k == 400 and "selalu punya akses penuh" in pesan                                                 # admin tidak bisa dibatasi
    assert api.pengguna_saat_ini(sesi_id=admin["_sid"])["laporan"] == LAPORAN_UJI
    asli = t.atur_izin
    t.atur_izin = lambda *a, **k: (_ for _ in ()).throw(TidakPunyaIzin("INSERT permission was denied"))
    try:
        k, pesan = kode(api.atur_izin, P(role="Operator", laporan="pr_po", akses=True), user=admin)
    finally:
        t.atur_izin = asli
    assert k == 503 and "INSERT dan UPDATE" in pesan
    assert kode(api.wajib_admin, user=pengguna(OPERATOR))[0] == 403


def test_tabel_izin_tidak_ada_halaman_menjelaskan_dan_non_admin_ditolak_admin_tetap_penuh():
    t, buka = segar()
    admin = pengguna(ADMIN)
    sql(buka, "DROP TABLE PERMISSIONS")
    t.bersihkan_cache()
    k, pesan = kode(api.daftar_izin, user=admin)
    assert k == 503 and "DB_APP_TABEL_IZIN" in pesan and "PERMISSIONS" in pesan
    k, pesan = kode(api.atur_izin, api.PermintaanIzin(role="Operator", laporan="pr_po", akses=True), user=admin)
    assert k == 503 and "DB_APP_TABEL_IZIN" in pesan
    assert masuk(*ADMIN)[0]["laporan"] == LAPORAN_UJI                                                       # admin tidak bergantung pada tabel izin
    k, pesan = kode(lambda: masuk(*OPERATOR))
    assert k == 503 and "hak akses" in pesan.lower()                                                        # bukan dibuka diam-diam


def test_role_tanpa_baris_izin_tidak_melihat_laporan_dan_laporan_baru_tertutup_sampai_diberi_akses():
    t, buka = segar()
    admin = pengguna(ADMIN)
    hapus_izin(buka, "Operator")
    t.bersihkan_cache()
    info, r = masuk(*OPERATOR)
    assert info["laporan"] == [] and api.daftar_laporan(user=api.pengguna_saat_ini(sesi_id=r.cookies["sesi"][0])) == []
    api.atur_izin(api.PermintaanIzin(role="Operator", laporan="pr_po", akses=True), user=admin)
    asli = dict(api.LAPORAN)
    api.LAPORAN["baru"] = SimpleNamespace(id="baru", nama="Laporan Baru", deskripsi="x", mulai_bawaan="2026-01-01")
    try:
        assert pengguna(ADMIN)["laporan"] == LAPORAN_UJI + ["baru"]                                          # admin langsung bisa
        op = pengguna(OPERATOR)
        assert op["laporan"] == ["pr_po"]                                                                     # laporan baru: belum ada yang boleh sampai diberi akses
        assert kode(api._izinkan, op, "baru")[0] == 403
        assert "baru" in [x["id"] for x in api.daftar_izin(user=admin)["laporan"]]                            # tetapi muncul di halaman Permission Control
    finally:
        api.LAPORAN.clear()
        api.LAPORAN.update(asli)


def test_muat_ditolak_tanpa_hak_dan_diizinkan_dengan_hak():
    t, buka = segar()
    admin = pengguna(ADMIN)
    api.atur_izin(api.PermintaanIzin(role="Operator", laporan="po_pi", akses=False), user=admin)
    op = pengguna(OPERATOR)
    assert [l["id"] for l in api.daftar_laporan(user=op)] == tanpa("po_pi")
    assert all(l["maks_hari"] == api.MAKS_HARI for l in api.daftar_laporan(user=op))                          # tampilan diberi tahu batas hari
    assert kode(api.muat_laporan, "po_pi", api.PermintaanMuat(mulai=__import__("datetime").date(2026, 1, 1), akhir=__import__("datetime").date(2026, 1, 31)), user=op)[0] == 403
    assert kode(api.status_pekerjaan, "x", user=op)[0] in (403, 404)
    api.atur_izin(api.PermintaanIzin(role="Operator", laporan="po_pi", akses=True), user=admin)
    op2 = api.pengguna_saat_ini(sesi_id=op["_sid"])
    assert "po_pi" in [l["id"] for l in api.daftar_laporan(user=op2)] and api._izinkan(op2, "po_pi") is None   # dengan hak: diizinkan


def test_peringatan_saat_server_menyala_untuk_tabel_izin_dan_role_tanpa_akses():
    t, buka = segar()
    pesan, h = tangkap_log()
    try:
        api.periksa_izin_awal()
        assert pesan == []                                                                                   # semua role berhak: diam
        hapus_izin(buka, "PPIC")
        t.bersihkan_cache()
        api.periksa_izin_awal()
        assert len(pesan) == 0                                                                               # PPIC tidak punya akun di fixture ini: tidak perlu diperingatkan
        isi(t, akun_data("ppic1234", role=ROLE_PPIC))
        api.periksa_izin_awal()
        assert len(pesan) == 1 and "PPIC" in pesan[0] and "Permission Control" in pesan[0] and "Operator" not in pesan[0]
        pesan.clear()
        sql(buka, "DROP TABLE PERMISSIONS")
        t.bersihkan_cache()
        api.periksa_izin_awal()
        assert len(pesan) == 1 and "DB_APP_TABEL_IZIN" in pesan[0] and "PERMISSIONS" in pesan[0]
    finally:
        api.log.removeHandler(h)


def test_akun_dengan_role_yang_tidak_bisa_dipetakan_tetap_bisa_disunting_dan_nilai_mentahnya_dipertahankan():
    """users.role berisi RoleId yang sudah tidak ada di tabel role: mengganti nama saja tidak boleh gagal atau mengubah nilai role itu."""
    t, buka, path = toko()
    isi(t, akun_data("budi", role=ROLE_OPERATOR))
    sql(buka, "UPDATE users SET role = '99'")                                                           # semua akun memakai RoleId; 99 tidak ada di tabel role
    t.bersihkan_cache()
    b = t.cari("budi")
    assert b.role == "99" and t.role_disimpan() == "id"
    hasil = t.ubah(b.id, {"nama": "Nama Baru", "role": "99", "divisi": "IT", "company": "YBS"})            # role tidak diubah
    c = sqlite3.connect(path)
    assert str(c.execute("SELECT role FROM users WHERE username = 'budi'").fetchone()[0]) == "99" and hasil.nama == "Nama Baru"
    c.close()
    # lewat endpoint: role "99" tidak ada di pilihan, tetapi tidak diubah, jadi sah
    t3, buka3 = segar()
    sql(buka3, "UPDATE users SET role = CASE username WHEN 'admin1' THEN '1' ELSE '99' END")
    t3.bersihkan_cache()
    admin3 = pengguna(ADMIN)
    h = api.ubah_pengguna(id_dari(t3, OPERATOR[0]), perm_ubah(nama="Masih Bisa", role="99"), user=admin3)
    assert h["nama"] == "Masih Bisa" and h["role"] == "99"
    assert kode(api.ubah_pengguna, id_dari(t3, OPERATOR[0]), perm_ubah(role="Manager"), user=admin3)[0] == 422      # role baru tetap harus dari pilihan
