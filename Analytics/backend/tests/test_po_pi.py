import ahli
import json

import pandas as pd

from inti.filter import FilterTidakValid
from laporan.po_pi import dashboard as D, ukuran as P

J = "2026-10-15"


# Dashboard sekarang memakai rentang tampilan (dari, sampai). Uji ditulis dengan patokan lama "5 minggu sampai jangkar"; pembungkus ini
# menerjemahkannya, jadi arti tiap uji tidak berubah.
def bangun(df, jangkar=J, **kw):
    return D.bangun(df, *ahli.lima_minggu(jangkar), **kw)


def detail(df, jenis, jangkar=J, **kw):
    return D.detail(df, jenis, *ahli.lima_minggu(jangkar), **kw)


def df():
    """Data hasil bersihkan() dari data contoh (semua pembuat)."""
    return ahli.df_po_pi()


def minggu():
    return P.daftar_minggu(5, J)


def tolak(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except FilterTidakValid:
        return True
    return False


def test_nama_pembuat_dinormalkan():
    pembuat = set(df()["creator"])
    assert "Demak" in pembuat and "demak" not in pembuat and "DEMAK" not in pembuat


def test_bawaan_semua_pembuat_tampil():
    d = df()
    assert "Kevin muliawan" in set(d["creator"])                                          # tidak ada pembuat yang disembunyikan
    r = bangun(d, J)
    assert [s["nama"] for s in r["new_po_per_pembuat"]] == r["pilihan"]["pembuat"]       # grafik dan menu memuat nama yang sama
    assert len(r["pilihan"]["pembuat_semua"]) == len(set(d["creator"]))
    assert all(o["jumlah"] > 0 for o in r["outstanding_per_pembuat"])                    # batang outstanding: yang punya outstanding
    assert sum(o["jumlah"] for o in r["outstanding_per_pembuat"]) == r["kpi"]["outstanding_akhir"]
    assert detail(d, "outstanding", J, ukuran=200)["total_semua"] == r["kpi"]["outstanding_akhir"]


def test_bangun_kpi_dan_konsistensi_grafik():
    r = bangun(df(), J)
    k = r["kpi"]
    assert 0 <= k["completion_rate"] <= 1 and k["outstanding_akhir"] > 0
    assert sum(c["outstanding_akhir"] for c in r["kategori_outstanding"]) == k["outstanding_akhir"]
    assert sum(c["jumlah"] for c in r["kategori_new_po"]) == k["new_po"]
    assert sum(c["jumlah"] for c in r["kategori_new_pi"]) == k["new_pi"]
    assert [sum(s["nilai"][i] for s in r["new_pi_per_perusahaan"]) for i in range(5)] == [w["new_pi"] for w in r["mingguan"]]
    assert [s["nama"] for s in r["new_po_per_pembuat"]] == r["pilihan"]["pembuat"]
    assert r["pilihan"]["umur"][0] == "Tepat Waktu(0-8 Hari)"


def test_filter_pilihan_banyak():
    a = bangun(df(), J, perusahaan=["sun", "ybs"])
    b = bangun(df(), J, perusahaan=["SUN"])
    c = bangun(df(), J, perusahaan=["YBS"])
    assert a["kpi"]["outstanding_akhir"] == b["kpi"]["outstanding_akhir"] + c["kpi"]["outstanding_akhir"]
    assert len(a["new_po_per_perusahaan"]) == 5 and a["filter"]["perusahaan"] == ["SUN", "YBS"]
    u = bangun(df(), J, umur=["Perlu Tindakan(>30 Hari)"])
    assert 0 < u["kpi"]["outstanding_akhir"] < bangun(df(), J)["kpi"]["outstanding_akhir"]
    assert "Indra" in [s["nama"] for s in bangun(df(), J, pembuat=["indra"])["new_po_per_pembuat"]]
    assert bangun(df(), J, minggu=1)["kpi"]["new_po"] == bangun(df(), J)["mingguan"][1]["new_po"]


def test_filter_tidak_valid_ditolak():
    assert tolak(bangun, df(), J, perusahaan=["QQQ"])
    assert tolak(bangun, df(), J, minggu=9)
    assert tolak(bangun, df(), J, umur=["x"])
    assert tolak(detail, df(), "x", J)


def test_minggu_berpatokan_pada_jangkar():
    assert bangun(df(), "2026-10-01")["mingguan"][-1]["label"] == "25/09 - 01/10"


def test_tabel_detail_sama_dengan_kartu():
    kasus = [{}, {"minggu": 1}, {"perusahaan": ["SUN", "YBS"]},
             {"kategori": ["Persediaan Bahan Bangunan"], "pembuat": ["Elsa", "Indah"]},
             {"umur": ["Telat(16-30 Hari)"], "minggu": 3}]
    for kw in kasus:
        k = bangun(df(), J, **kw)["kpi"]
        assert detail(df(), "outstanding", J, ukuran=200, **kw)["total_semua"] == k["outstanding_akhir"], kw
        assert detail(df(), "pi", J, ukuran=200, **kw)["total_semua"] == k["new_pi"], kw


def test_tabel_isi_dan_pencarian():
    o = detail(df(), "outstanding", J)
    assert o["total_semua"] == bangun(df(), J)["kpi"]["outstanding_akhir"] and len(o["kolom"]) == 19 and o["urut"] == "aging"
    assert "NaN" not in json.dumps(o) and "NaT" not in json.dumps(o)
    s = detail(df(), "pi", J, cari="  semen  ", ukuran=200)
    assert 0 < s["total"] < s["total_semua"]


def test_pi_milik_perusahaan_lain_diabaikan():
    from laporan.po_pi import sumber
    raw = ahli.raw_po_pi().copy()
    dasar = sumber.bersihkan(raw)
    sub = raw[(raw["COMPID"] == "YBS") & raw["PURCHASENUMBER"].isna()]
    idx = sub.index[0]
    line = "YBS" + str(raw.loc[idx, "PODETAILID"]).replace(".0", "")
    raw.loc[idx, ["PURCHASENUMBER", "PURCHASEDATE", "PURCHASEID"]] = ["RCM/PI/HO/2610/009", "20261010", "99"]
    d = sumber.bersihkan(raw)
    b = d[d["line"] == line]
    assert len(b) == 1 and b.iloc[0]["pi_number"] == "" and pd.isna(b.iloc[0]["pi_date"]) and b.iloc[0]["partial"] == "N"
    c = d.attrs["catatan"]
    assert c["pi_beda_perusahaan"] == 1 and len(c["peringatan"]) == 1 and "peringatan" not in dasar.attrs["catatan"]
    s, e = minggu()[0][0], minggu()[-1][1]
    assert P.new_pi(d, s, e) == P.new_pi(dasar, s, e) and P.outstanding_akhir(d, e) == P.outstanding_akhir(dasar, e)
    # daftar campuran: hanya PI milik YBS yang dipertahankan
    raw.loc[idx, ["PURCHASENUMBER", "PURCHASEDATE", "PURCHASEID"]] = ["YBS/PI/HO/2610/001,RCM/PI/HO/2610/009", "20261001,20261010", "5,99"]
    d2 = sumber.bersihkan(raw)
    b2 = d2[d2["line"] == line]
    assert len(b2) == 1 and b2.iloc[0]["pi_number"] == "YBS/PI/HO/2610/001" and b2.iloc[0]["partial"] == "N"


def test_pembuat_tanpa_new_po_pada_periode_disembunyikan():
    d = df()
    semua = bangun(d, J)["pilihan"]["pembuat_semua"]
    m = minggu()
    ada_tersembunyi = False
    for mg in [None, 0, 1, 2, 3, 4]:
        r = bangun(d, J, minggu=mg)
        s, e = m[mg] if mg is not None else (m[0][0], m[-1][1])
        tampak = set(r["pilihan"]["pembuat"])
        for b in semua:
            assert (b in tampak) == (P.new_po(d[d["creator"] == b], s, e) > 0), (mg, b)
        assert [x["nama"] for x in r["new_po_per_pembuat"]] == r["pilihan"]["pembuat"]
        assert r["pilihan"]["pembuat_semua"] == semua                      # urutan tetap untuk warna yang stabil
        assert all(o["jumlah"] > 0 for o in r["outstanding_per_pembuat"])  # batang outstanding tanpa nol
        assert sum(o["jumlah"] for o in r["outstanding_per_pembuat"]) == r["kpi"]["outstanding_akhir"]
        ada_tersembunyi |= len(tampak) < len(semua)
    assert ada_tersembunyi


def test_pembuat_terpilih_tetap_tampil_walau_nol():
    d = df()
    semua = bangun(d, J)["pilihan"]["pembuat_semua"]
    r = bangun(d, J, minggu=4)
    b = next(x for x in semua if x not in r["pilihan"]["pembuat"])
    r2 = bangun(d, J, minggu=4, pembuat=[b])
    assert b in r2["pilihan"]["pembuat"] and b in [x["nama"] for x in r2["new_po_per_pembuat"]]
    assert b in [o["pembuat"] for o in r2["outstanding_per_pembuat"]]       # yang dipilih tetap ada walau nol
