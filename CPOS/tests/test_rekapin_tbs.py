"""Laporan Pembelian TBS (modules/rekapin/laporan_tbs.py): susunan tabel sama dengan RekapIn."""
import unittest

from modules.rekapin import laporan_tbs as lt


class TestLaporanTbs(unittest.TestCase):
    def test_daily_urut_harga_dan_ringkasan(self):
        rows = [{"CATEGORY": "KEBUN", "HARGA_TBS_SPSI": 2600, "HARGA_CPO": 12400, "PERSENTASE": 0.21, "TONASE": 1, "TONASE_CPO": 1,
                 "TOTAL_TONASE": 3, "TOTAL_TONASE_CPO": 2, "PERSENTASE_TOTAL": 0.21, "PERSENTASE_KERNEL": 0.05, "OER_CPO": 21.5,
                 "BIAYA_OLAH_TBS": 155},
                {"CATEGORY": "AGEN", "HARGA_TBS_SPSI": 2650, "HARGA_CPO": 12400, "PERSENTASE": 0.2, "TONASE": 2, "TONASE_CPO": 1}]
        tabel = lt.susun_tabel("daily", [rows])
        self.assertEqual(len(tabel), 1)
        isi = tabel[0]["rows"]
        self.assertEqual([r["JENIS HARGA"] for r in isi[:2]], ["AGEN", "KEBUN"])        # harga tertinggi dulu
        self.assertEqual(isi[2]["JENIS HARGA"], "TOTAL")
        selisih = isi[-1]["TONASE CPO"]
        self.assertAlmostEqual(selisih, 21.5 + 5 - 21 - 155)

    def test_weekly_ringkasan_target(self):
        rows = [{"PERIODE": p, "JENIS_KEBUN": "AGEN", "GROUP": "G", "KATEGORI": "A", "TONASE_KG": t, "TOTAL_TONASE_MINGGU": tot,
                 "AGEN_TOTAL_TON": tot, "KEBUN_TOTAL_TON": 0, "BRONDOLAN_TOTAL_TON": 0} for p, t, tot in (("W1", 1, 2000), ("W2", 2, 4000))]
        tabel = lt.susun_tabel("weekly", [rows])
        self.assertEqual([t["kind"] for t in tabel], ["weekly", "weekly_summary"])
        capai = next(r for r in tabel[1]["rows"] if r["SUMMARY"] == "PENCAPAIAN %")
        self.assertEqual((capai["W1"], capai["W2"]), (50, 100))

    def test_format_angka_indonesia(self):
        self.assertEqual(lt.tbs_report_value(1234567.5, "TONASE", {}, "daily"), "1.234.568")
        self.assertEqual(lt.tbs_report_value(21.5, "X", {"_percent_columns": ("X",)}, "daily"), "21,50%")
        self.assertEqual(lt.susun_tabel("monthly", [[]]), [])


if __name__ == "__main__":
    unittest.main()
