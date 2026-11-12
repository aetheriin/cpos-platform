import numpy as np

from anpr.penstabil import PenstabilPlat, jarak_edit


class B:
    def __init__(self, plat, conf=0.9):
        self.plat, self.conf_ocr = plat, conf

    @property
    def diterima(self):
        return self.plat is not None


FRAME = np.zeros((4, 4, 3), np.uint8)


def jalankan(p, urutan, mulai=0.0, jarak=0.2):
    laporan = []
    for i, plat in enumerate(urutan):
        laporan += p.tambah(mulai + i * jarak, [B(plat)] if plat else [], FRAME)
    return laporan


def test_jarak_edit():
    assert jarak_edit("BM 1455 JJ", "BM 1455 J") == 1
    assert jarak_edit("BM 1455 JJ", "BM 1455 JJ") == 0


def test_lapor_setelah_min_frame():
    p = PenstabilPlat(min_frame=3)
    laporan = jalankan(p, ["BM 1455 JJ", "BM 1455 JJ", "BM 1455 JJ"])
    assert [l.plat for l in laporan] == ["BM 1455 JJ"]
    assert laporan[0].jumlah_frame == 3


def test_kendaraan_diam_hanya_sekali_dan_variasi_diredam():
    p = PenstabilPlat(min_frame=3, jeda_ulang_detik=60)
    urutan = ["BM 1455 JJ"] * 3 + ["BM 1455 J", "BM 1455 JJ"] * 300  # 2 menit berhenti
    assert len(jalankan(p, urutan)) == 1


def test_kendaraan_lain_tetap_dilaporkan():
    p = PenstabilPlat(min_frame=3)
    laporan = jalankan(p, ["BM 1455 JJ"] * 3 + ["BK 8812 TA"] * 3)
    assert [l.plat for l in laporan] == ["BM 1455 JJ", "BK 8812 TA"]


def test_datang_lagi_setelah_jeda():
    p = PenstabilPlat(min_frame=3, jeda_ulang_detik=60)
    pertama = jalankan(p, ["BM 1455 JJ"] * 3)
    kedua = jalankan(p, ["BM 1455 JJ"] * 3, mulai=200)
    assert len(pertama) == 1 and len(kedua) == 1


def test_bacaan_tersebar_di_luar_jendela_tidak_dilaporkan():
    p = PenstabilPlat(min_frame=3, jendela_detik=5)
    assert jalankan(p, ["BM 1455 JJ", None, "BM 1455 JJ", None, "BM 1455 JJ"], jarak=3) == []
