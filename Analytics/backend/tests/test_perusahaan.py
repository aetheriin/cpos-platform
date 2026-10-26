"""Perusahaan yang dipanggil stored procedure laporan dibaca dari tabel company, bukan tertanam di kode."""
import ahli  # noqa: F401
import importlib

from inti import konfigurasi
from inti.perusahaan import daftar_perusahaan
from inti.pengguna import PenyimpanPengguna
from test_pengguna import basis, sql, toko

sumber_pr = importlib.import_module("laporan.pr_po.sumber")
sumber_po = importlib.import_module("laporan.po_pi.sumber")


class KursorPalsu:
    def __init__(self, catat):
        self.catat, self.description, self._baris = catat, None, []

    def execute(self, perintah, *params):
        self.catat.append((perintah, params))
        self.description = [("nilai",), ("comp",)]
        self._baris = [(1, params[0])]

    def fetchall(self):
        return self._baris

    def nextset(self):
        return False


class KoneksiPalsu:
    def __init__(self, catat):
        self.catat = catat

    def cursor(self):
        return KursorPalsu(self.catat)

    def close(self):
        pass


def jalankan_sumber(modul, buka):
    """Jalankan ambil_data dengan koneksi data palsu, dan daftar perusahaan dari database uji. Mengembalikan panggilan SP."""
    catat = []
    asli_k, asli_d = modul.get_connection, modul.daftar_perusahaan
    modul.get_connection = lambda: KoneksiPalsu(catat)
    modul.daftar_perusahaan = lambda sumber: daftar_perusahaan(sumber, buka=buka)
    try:
        modul.ambil_data("20260101", "20260131")
    finally:
        modul.get_connection, modul.daftar_perusahaan = asli_k, asli_d
    return sorted(catat, key=lambda c: c[1][0])


def test_perusahaan_dari_tabel_company_menurut_jenis_aktif_dan_urutan_compid():
    t, buka, _ = toko()
    assert t.company_menurut_jenis("cloud") == ["YBS", "SUN", "SJN", "ORI", "RCM"]            # lima CLOUD; huruf besar-kecil diabaikan
    assert t.company_menurut_jenis("  CLOUD ") == ["YBS", "SUN", "SJN", "ORI", "RCM"]
    assert t.company_menurut_jenis("TRAINING") == ["YBS", "SUN"]                              # SJN TRAINING nonaktif (Status 0)
    assert t.company_menurut_jenis("PKS_LOKAL") == ["YBS", "SUN"] and t.company_menurut_jenis("tidak-ada") == [] and t.company_menurut_jenis(None) == []
    sql(buka, "UPDATE company SET Status = 0 WHERE CompName LIKE 'RCM%' AND CompType LIKE 'CLOUD%'")
    sql(buka, "INSERT INTO company (CompID, CompName, CompType, Status) VALUES (20, 'BARU', 'CLOUD', 1)")
    assert t.company_menurut_jenis("cloud") == ["YBS", "SUN", "SJN", "ORI", "BARU"]          # perubahan tabel langsung ikut, tanpa ubah kode
    sql(buka, "UPDATE company SET CompID = 0 WHERE CompName LIKE 'BARU%'")
    assert t.company_menurut_jenis("cloud")[0] == "BARU"                                       # urutan mengikuti CompID, bukan abjad atau urutan baris


def test_daftar_perusahaan_memakai_jenis_dari_konfigurasi_dan_menjelaskan_kegagalan():
    t, buka, _ = toko()
    assert daftar_perusahaan(buka=buka) == t.company_menurut_jenis(konfigurasi.SUMBER_LAPORAN)
    assert daftar_perusahaan("TRAINING", buka=buka) == ["YBS", "SUN"]
    for sumber, kata in (("tidak-ada", "tidak punya perusahaan aktif bertipe 'tidak-ada'"),):
        try:
            daftar_perusahaan(sumber, buka=buka)
        except RuntimeError as e:
            assert kata in str(e) and "CompType" in str(e) and "LAPORAN_SUMBER" in str(e)
        else:
            raise AssertionError("seharusnya gagal")
    sql(buka, "DROP TABLE company")
    try:
        daftar_perusahaan(buka=buka)
    except RuntimeError as e:
        assert "tidak bisa dibaca dari tabel company" in str(e) and "no such table" in str(e)
    else:
        raise AssertionError("seharusnya gagal")


def test_sp_dipanggil_satu_per_perusahaan_dari_tabel_dengan_parameter_dari_konfigurasi():
    _, buka, _ = toko()
    for modul, sp, status in ((sumber_pr, konfigurasi.SP_PR_PO, "4"), (sumber_po, konfigurasi.SP_PO_PI, 4)):
        panggilan = jalankan_sumber(modul, buka)
        assert [c[1][0] for c in panggilan] == ["ORI", "RCM", "SJN", "SUN", "YBS"]            # tepat satu panggilan per perusahaan di tabel
        assert all(c[0] == f"EXEC {sp} ?, ?, ?, ?, ?" for c in panggilan)
        assert all(c[1][1:] == (konfigurasi.SUMBER_LAPORAN, "20260101", "20260131", status) for c in panggilan)
        assert type(panggilan[0][1][4]) is type(status)                                         # tipe parameter status sama seperti sebelumnya (teks / angka)


def test_perusahaan_baru_dan_nonaktif_langsung_menentukan_panggilan_sp():
    _, buka, _ = toko()
    sql(buka, "UPDATE company SET Status = 0 WHERE CompName LIKE 'RCM%' AND CompType LIKE 'CLOUD%'")
    sql(buka, "INSERT INTO company (CompID, CompName, CompType, Status) VALUES (20, 'BARU', 'CLOUD', 1)")
    for modul in (sumber_pr, sumber_po):
        assert [c[1][0] for c in jalankan_sumber(modul, buka)] == ["BARU", "ORI", "SJN", "SUN", "YBS"]      # RCM hilang, BARU masuk


def test_tidak_ada_daftar_perusahaan_atau_nama_sp_tertanam_di_kode_laporan():
    import re
    from pathlib import Path
    akar = Path(__file__).resolve().parent.parent
    sumber = [akar / "laporan" / "pr_po" / "sumber.py", akar / "laporan" / "po_pi" / "sumber.py"]
    for berkas in sumber:
        teks = berkas.read_text(encoding="utf-8")
        assert not re.search(r'["\'](YBS|SUN|SJN|ORI|RCM)["\']\s*[,\]]', teks), f"{berkas.name}: daftar perusahaan tertanam"
        assert not re.search(r'["\']R_P[RO]_OUT', teks), f"{berkas.name}: nama stored procedure tertanam"
        assert "PERUSAHAAN =" not in teks
