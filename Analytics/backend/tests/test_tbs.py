import ahli  # noqa: F401
from types import SimpleNamespace

import numpy as np
import pandas as pd

from inti import konfigurasi
from laporan.tbs import dashboard as D, ukuran as U

POLA = [1.0, 1.2, 1.2, 1.1, 1.0, 0.9, 0.6]   # Senin..Minggu


def _data(hari=500, akhir="2026-10-18"):
    """Pembelian harian buatan: 100 ton x pola hari, satu supplier per tipe, harga tetap."""
    tanggal = pd.date_range(end=akhir, periods=hari, freq="D")
    baris = []
    for t in tanggal:
        for tipe, porsi, harga in (("MITRA A", 0.6, 3500.0), ("SUPER B", 0.4, 3700.0)):
            netto = 100_000 * POLA[t.weekday()] * porsi
            baris.append({"purchase_id": f"{t:%Y%m%d}{tipe}", "detail_id": 1, "tgl": t, "netto": netto, "harga": harga, "nilai": netto * harga,
                          "supplier": f"Supplier {tipe}", "grup": "Grup", "tipe": tipe, "comp": "PT. YBS", "kategori": tipe,
                          "hari": t.strftime("%Y-%m-%d"), "nama_hari": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][t.weekday()]})
    return pd.DataFrame(baris)


def test_kpi_harga_tertimbang_bukan_rata_rata_biasa():
    d = pd.DataFrame({"tgl": pd.to_datetime(["2026-10-01"] * 2), "netto": [100.0, 10_000.0], "nilai": [100.0 * 5000, 10_000.0 * 3000], "supplier": ["a", "b"]})
    k = U.kpi(d)
    assert k["harga"] == round((500_000 + 30_000_000) / 10_100, 2) and k["harga"] != 4000.0


def test_forecast_rata_rata_2_minggu_kali_bobot_hari_yang_sama_tahun_lalu():
    d = _data()
    f = U.forecast(d)
    n = konfigurasi.TBS_HARI_FORECAST
    assert f is not None and f["akhir_aktual"] == "2026-10-18" and len(f["hari"]) == n
    assert abs(f["dasar"]["rata_harian"] - 100_000 * sum(POLA) / 7) < 1e-6 and f["dasar"]["hari_masuk"] == 14   # rata-rata 14 hari terakhir
    assert f["dasar"]["blok_mulai"] == "2025-10-20"                                # hari pertama forecast - 364 hari (Senin juga)
    assert abs(sum(h["proporsi"] for h in f["hari"]) - 1) < 1e-9
    assert [round(h["netto"]) for h in f["hari"]] == [round(100_000 * p) for p in POLA]   # pola tetap: forecast = pola aslinya
    assert abs(f["dasar"]["harga"] - (0.6 * 3500 + 0.4 * 3700)) < 0.01
    u = f["uji"]                                                                   # forecast yang dibuat 7 hari lalu vs aktualnya
    assert (u["mulai"], u["akhir"]) == ("2026-10-12", "2026-10-18") and abs(u["selisih"]) < 1e-9 and u["meleset_harian"] < 1e-9
    # pola tetap: forecast minggu-minggu sebelumnya tepat, jadi interval menyempit ke angka forecast itu sendiri
    iv = f["interval"]
    assert iv["uji"] == konfigurasi.TBS_UJI_MINGGU and abs(iv["total_bawah"] - iv["total_atas"]) < 1e-6
    assert all(abs(h["bawah"] - h["netto"]) < 1e-6 and abs(h["atas"] - h["netto"]) < 1e-6 for h in f["hari"])


def test_interval_melebar_kalau_aktual_naik_turun_dan_hilang_kalau_riwayat_pendek():
    d = _data()
    goyang = 1 + 0.2 * np.sin(np.arange(len(d)) / 3)                   # aktual naik-turun di sekitar polanya
    d = d.assign(netto=d["netto"] * goyang)
    f = U.forecast(d)
    iv = f["interval"]
    assert iv["total_bawah"] < sum(h["netto"] for h in f["hari"]) < iv["total_atas"]
    assert all(h["bawah"] <= h["netto"] <= h["atas"] for h in f["hari"])
    assert U.forecast(_data(hari=380))["interval"] is None                 # baru cukup untuk satu forecast, belum untuk 4 minggu uji


def test_forecast_hari_tanpa_penerimaan_tidak_dihitung_dan_tidak_diramal_nol():
    """Minggu selalu kosong: rata-rata 2 minggu hanya dari 12 hari yang ada penerimaan. Forecast memperkirakan penerimaan kalau hari itu tetap
    ada yang masuk, jadi Minggu diisi rata-rata hari lain di blok tahun lalu, bukan nol."""
    d = _data()
    d = d[pd.to_datetime(d["tgl"]).dt.weekday != 6]
    f = U.forecast(d)
    assert f["dasar"]["hari_masuk"] == 12 and abs(f["dasar"]["rata_harian"] - 100_000 * sum(POLA[:6]) / 6) < 0.01
    assert f["akhir_aktual"] == "2026-10-17"                                       # data berakhir Sabtu, forecast mulai Minggu
    harap = [100_000 * sum(POLA[:6]) / 6] + [100_000 * p for p in POLA[:6]]
    assert all(abs(h["netto"] - x) < 1 for h, x in zip(f["hari"], harap))
    assert abs(sum(h["proporsi"] for h in f["hari"]) - 1) < 1e-3                   # proporsi dikirim dengan 4 desimal


def test_forecast_libur_tahun_lalu_diisi_dari_hari_yang_sama_minggu_sekitarnya():
    """Kamis tahun lalu (tanggal merah) kosong: proporsinya diambil dari Kamis seminggu sebelum dan sesudahnya, jadi forecast tetap seperti polanya."""
    d = _data()
    d = d[d["hari"] != "2025-10-23"]                                               # Kamis di blok tahun lalu (blok mulai Senin 20/10/2025)
    f = U.forecast(d)
    assert all(abs(h["netto"] - 100_000 * p) < 1 for h, p in zip(f["hari"], POLA))


def test_forecast_kosong_kalau_minggu_yang_sama_tahun_lalu_tidak_ada():
    assert U.forecast(_data(hari=40)) is None and U.forecast(_data(hari=360)) is None
    assert U.forecast(_data(hari=372)) is not None


def test_rata_rata_per_truk_dan_per_hari_lewati_hari_kosong_seperti_averagex():
    d = pd.DataFrame({"tgl": pd.to_datetime(["2026-10-12", "2026-10-12", "2026-10-19"]), "netto": [1000.0, 3000.0, 5000.0],
                      "nilai": [0.0, 0.0, 0.0], "supplier": ["a", "b", "a"]})
    assert U.kpi(d)["per_truk"] == (2000 + 5000) / 2
    senin = D._per_hari_minggu(d, "2026-10-12", "2026-10-25")[0]
    assert senin == {"nama": "Senin", "rata": 4500.0, "jumlah_hari": 2}

def test_dashboard_crossfilter_dan_forecast_abaikan_filter_hari():
    df = _data(hari=400)
    df["lalu"] = df["tgl"] < pd.Timestamp("2026-09-01")
    ds = SimpleNamespace(mulai="2026-09-01", akhir="2026-10-18")
    semua = D.bangun(df, ds, {})
    tipe = D.bangun(df, ds, {"tipe": ["MITRA A"]})
    assert abs(tipe["kpi"]["netto"] - semua["kpi"]["netto"] * 0.6) < 1
    assert [x["nama"] for x in tipe["per_tipe"]["data"]] == ["MITRA A", "SUPER B"]           # grafik sumber tetap menampilkan semua tipe
    senin = D.bangun(df, ds, {"hari_minggu": ["Senin"]})
    assert senin["forecast"]["hari"] == semua["forecast"]["hari"]                 # forecast tidak ikut filter hari
    assert senin["banding"] is not None and D.bangun(df, ds, {"tanggal": ["2026-10-01"]})["banding"] is None
    assert {x["nama"]: round(x["rata"]) for x in semua["per_hari_minggu"]}["Minggu"] == 60_000
    assert D.detail(df, "supplier", ds, {}, None, None, None, 1, 10)["total"] == 2
