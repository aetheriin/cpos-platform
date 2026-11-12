import pytest

from anpr.plat import normalisasi_plat, rapikan_bacaan


@pytest.mark.parametrize("ocr, plat", [
    ("BM1455JJ", "BM 1455 JJ"),
    ("bm 1455 jj", "BM 1455 JJ"),
    ("B1234ABC", "B 1234 ABC"),
    ("BK8812", "BK 8812"),
    ("BM1455JJ0627", "BM 1455 JJ"),   # masa berlaku ikut terbaca
    ("8M1455JJ", "BM 1455 JJ"),       # 8 di bagian huruf -> B
    ("BM14S5JJ", "BM 1455 JJ"),       # S di bagian angka -> 5
    ("BMI455JJ", "BM 1455 JJ"),       # I di bagian angka -> 1
    ("AA456SJU", "AA 456 SJU"),
])
def test_rapikan_bacaan_valid(ocr, plat):
    assert rapikan_bacaan(ocr)[0] == plat


@pytest.mark.parametrize("ocr", ["", "12345", "XX1234AB", "BM0123AB", "BM1455JJKK", "BMXX"])
def test_rapikan_bacaan_ditolak(ocr):
    assert rapikan_bacaan(ocr)[0] is None


def test_tanpa_koreksi_diutamakan():
    assert rapikan_bacaan("BM1455JJ") == ("BM 1455 JJ", 0)


def test_koreksi_terlalu_banyak_ditolak():
    assert rapikan_bacaan("8MI4SSJJ")[0] is None


def test_normalisasi_sama_dengan_website():
    assert normalisasi_plat("BM-1455-JJ") == ("BM 1455 JJ", None)
    assert normalisasi_plat("XX 1 A")[0] is None
