from types import SimpleNamespace

import pandas as pd

from laporan.penilaian_pvr import dashboard, sumber

BOBOT = [("Angkutan Penjualan", 0.2), ("Angkutan", 0.2), ("Kontraktor", 7), ("Barang", 1)]
DS = SimpleNamespace(mulai="2026-01-01", akhir="2026-10-23")


def baris(pvr, cek, oleh="DINDA", tanggal="2026-09-10", ref="X", comp="YBS"):
    return {"__comp": comp, "VoucherDate": tanggal, "VoucherNo": pvr, "ItemRef": ref, "CheckNumber": cek, "CheckNoSource": "Asli" if cek else "Kosong",
            "ItemAmountPaid": 100, "CreatedBy": oleh, "SupplierName": "S", "RefType": "PI"}


def data():
    raw = pd.DataFrame([
        baris("PVR/1", "ANGKUTAN PENJUALAN", ref="T1"), baris("PVR/1", "ANGKUTAN PENJUALAN", ref="T2"), baris("PVR/1", "ANGKUTAN PENJUALAN", ref="T3"),
        baris("PVR/2", "angkutan", oleh="ferdinan"),
        baris("PVR/3", "kontraktor", ref="A"), baris("PVR/3", "kontraktor", ref="B"),     # bukan angkutan: dinilai sekali
        baris("PVR/4", "barang", oleh="Halim", tanggal="2026-08-01"),
        baris("PVR/5", None, oleh="intan"),
    ])
    return sumber.bersihkan(raw, BOBOT)


def test_angkutan_per_item_lainnya_sekali():
    d = data()
    assert d.groupby("pvr_number").size().to_dict() == {"PVR/1": 3, "PVR/2": 1, "PVR/3": 1, "PVR/4": 1, "PVR/5": 1}
    assert set(d.loc[d["pvr_number"].isin(["PVR/1", "PVR/2"]), "kategori"]) == {"Angkutan"}
    assert d.set_index("pvr_number").loc["PVR/3", "bobot"] == 7 and d.set_index("pvr_number").loc["PVR/5", "kategori"] == sumber.KOSONG


def test_pv_check_number_kosong_diisi_dari_supplier():
    from laporan.penilaian_pv.sumber import isi_dari_histori
    raw = pd.DataFrame([
        {**baris("PV/1", "Barang"), "SupplierName": "A"}, {**baris("PV/2", "Barang"), "SupplierName": "A"},
        {**baris("PV/3", "Expense"), "SupplierName": "A"}, {**baris("PV/4", None), "SupplierName": "A"}, {**baris("PV/5", None), "SupplierName": "B"},
    ]).drop(columns=["CheckNoSource", "RefType"]).assign(Source="PI")
    d = sumber.bersihkan(isi_dari_histori(raw), BOBOT).set_index("pvr_number")
    assert d.loc["PV/4", "kategori"] == "Barang" and d.loc["PV/4", "sumber_kategori"] == "Histori Supplier"
    assert d.loc["PV/5", "kategori"] == sumber.KOSONG and d.loc["PV/5", "sumber_kategori"] == "Kosong"


def test_rekap_dan_filter_pembuat():
    df = data()
    b = dashboard.bangun(df, DS, {"pembuat": ["Dinda", "Dwi", "Ferdinan", "Intan"]})
    assert b["kpi"]["skor"] == 7.8 and b["kpi"]["pvr"] == 4 and b["kpi"]["tanpa_kategori"] == 1
    assert b["rekap"]["pembuat"] == ["Dinda", "Ferdinan", "Intan"] and b["rekap"]["bulan"] == ["2026-09"]
    assert "Dwi" in b["pilihan"]["pembuat"] and "Halim" in b["pilihan"]["pembuat"]
    assert dashboard.bangun(df, DS)["kpi"]["skor"] == 8.8
    assert dashboard.detail(df, "kosong", DS)["baris"][0]["pvr_number"] == "PVR/5"
    assert "PVR/5" not in {r["pvr_number"] for r in dashboard.detail(df, "dinilai", DS)["baris"]}   # tanpa kategori hanya di tab sendiri
    assert sumber.KOSONG not in b["pilihan"]["kategori"]
