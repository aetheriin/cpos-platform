import ahli  # noqa: F401
import sqlite3

from inti.pengguna import DataTidakValid, PenyimpanPengguna, periksa_divisi_baru, periksa_role_baru
from test_pengguna import basis, salah

SKEMA_DIVISI = """CREATE TABLE DIVISION (DivisionID INTEGER PRIMARY KEY AUTOINCREMENT, CompID INTEGER NOT NULL, DivisionName TEXT NOT NULL,
                  DivisionCode TEXT NOT NULL, Status INTEGER NOT NULL, CreatedAt TEXT)"""


def toko():
    path, buka = basis()
    c = sqlite3.connect(path)
    c.execute(SKEMA_DIVISI)
    c.execute("INSERT INTO DIVISION (CompID, DivisionName, DivisionCode, Status) VALUES (1, 'Information Technology', 'IT', 1)")
    c.commit()
    c.close()
    return PenyimpanPengguna(buka, cache_detik=0)


def test_tambah_divisi_lalu_muncul_di_pilihan_akun():
    t = toko()
    d = t.tambah_divisi(periksa_divisi_baru("  Supply   Chain ", "sc", 2))
    assert (d["nama"], d["kode"], d["comp_id"], d["aktif"]) == ("Supply Chain", "SC", 2, True)
    assert "Supply Chain" in t.opsi()["divisi"]


def test_divisi_kembar_atau_company_asing_ditolak():
    t = toko()
    assert "sudah ada" in salah(lambda: t.tambah_divisi(periksa_divisi_baru("information technology", "IT2", 1)))
    assert "sudah dipakai" in salah(lambda: t.tambah_divisi(periksa_divisi_baru("Teknologi", "it", 1)))
    assert "tidak aktif" in salah(lambda: t.tambah_divisi(periksa_divisi_baru("Lab", "LB", 8)))       # SJN TRAINING nonaktif
    assert "wajib dipilih" in salah(lambda: periksa_divisi_baru("Lab", "LB", None))


def test_tambah_role_lalu_bisa_dipakai_akun():
    t = toko()
    r = t.tambah_role(periksa_role_baru("Buyer", "Membeli barang", 1))
    assert (r["nama"], r["divisi_id"], r["deskripsi"]) == ("Buyer", 1, "Membeli barang")
    assert "Buyer" in t.role_aktif()


def test_role_kembar_atau_divisi_asing_ditolak():
    t = toko()
    assert "sudah ada" in salah(lambda: t.tambah_role(periksa_role_baru("  operator", "", 1)))
    assert "tidak ditemukan" in salah(lambda: t.tambah_role(periksa_role_baru("Buyer", "", 99)))
    assert "paling panjang" in salah(lambda: periksa_role_baru("x" * 31, "", 1), DataTidakValid)
