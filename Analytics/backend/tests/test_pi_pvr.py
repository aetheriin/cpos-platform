from datetime import date
from types import SimpleNamespace

import pandas as pd

from laporan.pi_pvr import dashboard, sumber


def _raw(baris):
    kolom = ["__comp", "DetailID", "PurchaseNumber", "PICreateDate", "QtyPI", "ItemCode", "ItemName", "PVRNumber", "PVRDate", "PICreateBy", "PVRCreateBy"]
    return pd.DataFrame(baris, columns=kolom).assign(LineTotal=1500.0, PONumber="PO/1", SupplierCode="S01", SupplierName="Toko Baut")


def test_pi_dengan_dua_pvr_jadi_satu_baris():
    d = sumber.bersihkan(_raw([
        ("YBS", 1, "YBS/PI/1", "2026-10-01", 5, "A", "Baut", "PVR/2", "2026-10-05", "ana", "budi"),
        ("YBS", 1, "YBS/PI/1", "2026-10-01", 5, "A", "Baut", "PVR/1", "2026-10-03", "ana", "cici"),
        ("SUN", 1, "SUN/PI/9", "2026-10-02", 2, "B", "Mur", None, None, "ana", None),
    ]))
    assert len(d) == 2
    ybs = d[d["comp"] == "YBS"].iloc[0]
    assert ybs["pvr_number"] == "PVR/1, PVR/2" and ybs["pvr_date"] == pd.Timestamp("2026-10-03") and ybs["lama_pvr"] == 2 and ybs["line_total"] == 1500 and ybs["supplier_name"] == "Toko Baut"
    assert not d[d["comp"] == "SUN"].iloc[0]["sudah_pvr"]


def test_tabel_belum_dan_sudah_dipisah():
    df = sumber.bersihkan(_raw([
        ("YBS", 1, "YBS/PI/1", "2026-10-01", 5, "A", "Baut", "PVR/1", "2026-10-03", "ana", "cici"),
        ("SUN", 2, "SUN/PI/9", "2026-10-02", 2, "B", "Mur", None, None, "ana", None),
    ]))
    ds = SimpleNamespace(mulai="2026-10-01", akhir="2026-10-22")
    b = dashboard.bangun(df, ds)
    assert b["jumlah"] == {"belum": 1, "pv_tanpa_pvr": 0, "sudah": 1}
    k = b["kpi"]
    assert (k["belum"], k["sudah"], k["nilai_belum"], k["lama_pvr"]["median"]) == (1, 1, 1500.0, 2.0)
    assert [b["pi_number"] for b in dashboard.detail(df, "belum", ds)["baris"]] == ["SUN/PI/9"]
    assert dashboard.detail(df, "sudah", ds, {"perusahaan": ["sun"]})["total"] == 0


def test_status_pv_tanpa_pvr():
    raw = _raw([
        ("YBS", 1, "YBS/PI/1", "2026-10-01", 5, "A", "Baut", None, None, "ana", None),          # dibayar PV tanpa PVR
        ("YBS", 1, "YBS/PI/1", "2026-10-01", 5, "A", "Baut", None, None, "ana", None),          # PV kedua untuk PI yang sama
        ("SUN", 2, "SUN/PI/9", "2026-10-02", 2, "B", "Mur", None, None, "ana", None),           # belum apa-apa
        ("ORI", 3, "ORI/PI/5", "2026-10-02", 2, "B", "Mur", "PVR/7", "2026-10-03", "ana", "x"), # PVR, belum PV
    ]).assign(PVNumber=["PV/1", "PV/2", None, None], PVDate=["2026-10-04", "2026-10-06", None, None], PVCreateBy=["kasir", "kasir", None, None])
    d = sumber.bersihkan(raw).set_index("comp")
    assert d.loc["YBS", "status"] == sumber.PV_TANPA_PVR and d.loc["YBS", "pv_number"] == "PV/1, PV/2"
    assert d.loc["SUN", "status"] == sumber.BELUM and d.loc["ORI", "status"] == sumber.PVR_BELUM_PV
    ds = SimpleNamespace(mulai="2026-10-01", akhir="2026-10-22")
    k = dashboard.bangun(d.reset_index(), ds)["kpi"]
    assert (k["belum"], k["pv_tanpa_pvr"], k["sudah"]) == (1, 1, 1)
    assert [b["pi_number"] for b in dashboard.detail(d.reset_index(), "pv_tanpa_pvr", ds)["baris"]] == ["YBS/PI/1"]
    assert [b["pi_number"] for b in dashboard.detail(d.reset_index(), "belum", ds)["baris"]] == ["SUN/PI/9"]


def test_query_memakai_database_tiap_perusahaan():
    sql = sumber.perintah(("SUN", "ASCEND_CLOUD", "AS_SUN_YBS"), date(2026, 10, 1), date(2026, 10, 22))
    assert "OPENQUERY([ASCEND_CLOUD]" in sql and "AS_SUN_YBS.dbo.ap_purchases" in sql
    assert "''2026-10-01''" in sql and "''2026-10-23''" in sql


def test_nama_database_aneh_ditolak():
    try:
        sumber.perintah(("X", "ASCEND_CLOUD", "AS_X]; DROP"), date(2026, 10, 1), date(2026, 10, 2))
    except RuntimeError as e:
        assert "CompDataBase" in str(e)
    else:
        raise AssertionError("nama database tidak ditolak")
