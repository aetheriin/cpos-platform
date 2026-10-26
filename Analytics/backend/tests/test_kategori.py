import ahli
import sqlite3

import pandas as pd

from inti import kategori as K

PETA = ahli.PETA_KATEGORI
INDEKS = K._indeks(PETA)


def test_persis_dan_abaikan_huruf_dan_spasi():
    t = PETA["YBS"]
    k0 = list(t)[0]
    assert K.petakan_satu("YBS", k0, INDEKS) == (t[k0], "tepat")
    assert K.petakan_satu("YBS", k0.lower().replace(" ", "   "), INDEKS) == (t[k0], "tepat")


def test_perusahaan_tanpa_peta_dan_kosong():
    assert K.petakan_satu("SJN", "Persediaan X", INDEKS) == ("Persediaan X", "tanpa_peta")
    assert K.petakan_satu("ORI", None, INDEKS) == (None, "tanpa_peta")
    assert K.petakan_satu("YBS", "", INDEKS)[0] is None and K.petakan_satu("SUN", None, INDEKS)[0] is None


def test_mirip_dan_tidak_cocok():
    t = PETA["YBS"]
    assert K.petakan_satu("YBS", "PERSEDIAAN CHEMICAL", INDEKS) == (t["PERSEDIAAN CHEMICALS"], "mirip")
    assert K.petakan_satu("YBS", "Barang Aneh Sekali", INDEKS) == (None, "tidak_cocok")


def test_petakan_seri_dan_catatan():
    t = PETA["YBS"]
    k0 = list(t)[0]
    s, c = K.petakan_seri(pd.Series(["YBS", "SJN", "SUN", "YBS"]), pd.Series([k0, "Lain", None, "Zzz Qqq"]), PETA)
    assert s.iloc[0] == t[k0] and s.iloc[1] == "Lain" and pd.isna(s.iloc[2]) and pd.isna(s.iloc[3])
    assert c["kategori_tidak_cocok"] == ["YBS: Zzz Qqq"]


def _tabel(isi):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE MappingCategory (id INTEGER, CompID INTEGER, Company TEXT, OldCategory TEXT, Category TEXT)")
    conn.executemany("INSERT INTO MappingCategory VALUES (?, ?, ?, ?, ?)", isi)

    class Kursor:   # SQLite tidak punya skema dbo
        def __init__(self):
            self.cur = conn.cursor()

        def execute(self, sql, *a):
            return self.cur.execute(sql.replace("[dbo].", ""), *a)

        def fetchall(self):
            return self.cur.fetchall()

    class Koneksi:   # close() tidak boleh membuang database di memori
        def cursor(self):
            return Kursor()

        def close(self):
            pass
    return Koneksi


def test_peta_dibaca_dari_tabel_dengan_spasi_dibuang_dan_baris_kosong_dilewati():
    buka = _tabel([(1, 1, "YBS ", " PERSEDIAAN BBM ", "Persediaan BBM"), (2, 2, "SUN", "ATK", "Alat Tulis"), (3, 2, "SUN", "", "X"),
                   (4, 2, "SUN", "SPAREPART", None)])
    assert ahli.BACA_PETA_ASLI(buka) == {"YBS": {"PERSEDIAAN BBM": "Persediaan BBM"}, "SUN": {"ATK": "Alat Tulis"}}


def test_tabel_tidak_terbaca_atau_kosong_menghentikan_pemuatan_dengan_pesan_jelas():
    def gagal():
        raise RuntimeError("login gagal")
    for buka, kata in ((gagal, "tidak bisa dibaca"), (_tabel([]), "kosong")):
        try:
            ahli.BACA_PETA_ASLI(buka)
            assert False, kata
        except RuntimeError as e:
            assert kata in str(e) and "MappingCategory" in str(e)
