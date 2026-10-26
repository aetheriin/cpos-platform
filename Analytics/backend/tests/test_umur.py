import ahli  # noqa: F401

from inti.umur import URUTAN_UMUR, kategori_umur


def test_batas_kategori_umur():
    assert kategori_umur(0) == kategori_umur("8") == "Tepat Waktu(0-8 Hari)"
    assert kategori_umur(9) == kategori_umur(15) == "Perlu Perhatian(9-15 Hari)"
    assert kategori_umur(16) == kategori_umur(30.0) == "Telat(16-30 Hari)"
    assert kategori_umur(31) == kategori_umur("698") == "Perlu Tindakan(>30 Hari)"
    assert kategori_umur("COMPLETED") == "COMPLETED" and kategori_umur(None) == "None"
    assert URUTAN_UMUR[:4] == ["Tepat Waktu(0-8 Hari)", "Perlu Perhatian(9-15 Hari)", "Telat(16-30 Hari)", "Perlu Tindakan(>30 Hari)"]
