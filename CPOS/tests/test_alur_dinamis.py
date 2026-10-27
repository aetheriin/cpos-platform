"""Alur tiket dinamis (utils/alur.py): validasi urutan, aturan Area + Produk, tahap yang ditunggu (paralel)."""
import unittest

from utils import alur


class TestValidasi(unittest.TestCase):
    def test_alur_sah(self):
        for k in ([["SECURITY"], ["TIMBANG_1"], ["SORTASI"], ["TIMBANG_2"]],
                  [["SECURITY"], ["LAB"], ["TIMBANG_1"], ["TIMBANG_2"], ["SECURITY_KELUAR"]],
                  [["SECURITY"], ["TIMBANG_1"], ["SORTASI", "LAB"], ["TIMBANG_2"]],
                  [["SECURITY"], ["SORTASI"], ["TIMBANG_1"]],
                  [["SECURITY"]]):
            self.assertEqual(alur.validasi_kelompok(k), k)

    def test_alur_tidak_sah(self):
        salah = {
            "security bukan pertama": [["TIMBANG_1"], ["SECURITY"]],
            "security paralel": [["SECURITY", "LAB"], ["TIMBANG_1"]],
            "timbang 2 sebelum 1": [["SECURITY"], ["TIMBANG_2"], ["TIMBANG_1"]],
            "timbang 2 bersamaan 1": [["SECURITY"], ["TIMBANG_1", "TIMBANG_2"]],
            "timbang 2 tanpa 1": [["SECURITY"], ["TIMBANG_2"]],
            "keluar bukan terakhir": [["SECURITY"], ["SECURITY_KELUAR"], ["TIMBANG_1"]],
            "keluar paralel": [["SECURITY"], ["TIMBANG_1"], ["LAB", "SECURITY_KELUAR"]],
            "dobel": [["SECURITY"], ["LAB"], ["LAB"]],
            "asing": [["SECURITY"], ["GUDANG"]],
            "kosong": [],
        }
        for nama, k in salah.items():
            with self.subTest(nama), self.assertRaises(ValueError):
                alur.validasi_kelompok(k)


class TestAturan(unittest.TestCase):
    ATURAN = [{"id_comp_area": 1, "id_produk": None, "id_alur": 10, "is_active": True},
              {"id_comp_area": 1, "id_produk": 5, "id_alur": 11, "is_active": True},
              {"id_comp_area": 2, "id_produk": 5, "id_alur": 12, "is_active": False}]

    def test_paling_spesifik(self):
        self.assertEqual(alur.pilih_aturan(self.ATURAN, 1, 5)["id_alur"], 11)       # area + produk
        self.assertEqual(alur.pilih_aturan(self.ATURAN, 1, 7)["id_alur"], 10)       # area + semua produk
        self.assertIsNone(alur.pilih_aturan(self.ATURAN, 2, 5))                     # nonaktif -> bawaan produk
        self.assertIsNone(alur.pilih_aturan(self.ATURAN, 3, 5))                     # area tanpa aturan

    def test_alur_nonaktif_dilewati(self):
        aturan = [{"id_comp_area": 1, "id_produk": 5, "id_alur": 11, "is_active": True, "alur_aktif": False},
                  {"id_comp_area": 1, "id_produk": None, "id_alur": 10, "is_active": True, "alur_aktif": True}]
        self.assertEqual(alur.pilih_aturan(aturan, 1, 5)["id_alur"], 10)


class TestMenunggu(unittest.TestCase):
    def tahap(self, *isi):
        return [{"kode_tahap": k, "grup": g, "status": s, "urutan": i} for i, (k, g, s) in enumerate(isi)]

    def test_paralel(self):
        t = self.tahap(("SECURITY", 1, "SELESAI"), ("TIMBANG_1", 2, "SELESAI"), ("SORTASI", 3, "MENUNGGU"),
                       ("LAB", 3, "MENUNGGU"), ("TIMBANG_2", 4, "MENUNGGU"))
        self.assertEqual(alur.tahap_menunggu(t), ["SORTASI", "LAB"])
        t[3]["status"] = "SELESAI"                       # lab duluan
        self.assertEqual(alur.tahap_menunggu(t), ["SORTASI"])
        t[2]["status"] = "SELESAI"
        self.assertEqual(alur.tahap_menunggu(t), ["TIMBANG_2"])
        t[4]["status"] = "SELESAI"
        self.assertEqual(alur.tahap_menunggu(t), [])

    def test_lab_sebelum_timbang(self):
        t = self.tahap(("SECURITY", 1, "SELESAI"), ("LAB", 2, "MENUNGGU"), ("TIMBANG_1", 3, "MENUNGGU"))
        self.assertEqual(alur.tahap_menunggu(t), ["LAB"])


if __name__ == "__main__":
    unittest.main()


class TestDurasi(unittest.TestCase):
    def test_paralel_dan_berjalan(self):
        from datetime import datetime
        j = lambda h, m: datetime(2026, 10, 27, h, m)
        tahap = [{"kode_tahap": "SECURITY", "grup": 1, "status": "SELESAI", "selesai": j(8, 0)},
                 {"kode_tahap": "TIMBANG_1", "grup": 2, "status": "SELESAI", "selesai": j(8, 10)},
                 {"kode_tahap": "SORTASI", "grup": 3, "status": "SELESAI", "selesai": j(8, 40)},
                 {"kode_tahap": "LAB", "grup": 3, "status": "MENUNGGU", "selesai": None},
                 {"kode_tahap": "TIMBANG_2", "grup": 4, "status": "MENUNGGU", "selesai": None}]
        d = {x["kode"]: x for x in alur.durasi_tahap(tahap, j(9, 0))}
        self.assertIsNone(d["SECURITY"]["menit"])
        self.assertEqual(d["TIMBANG_1"]["menit"], 10)
        self.assertEqual(d["SORTASI"]["menit"], 30)                # paralel: mulai setelah timbang 1
        self.assertEqual(d["LAB"]["menit"], 50)                    # masih berjalan, dihitung sampai sekarang
        self.assertTrue(d["LAB"]["berjalan"])
        self.assertIsNone(d["TIMBANG_2"]["menit"])                 # belum mulai
