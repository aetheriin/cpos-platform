from datetime import datetime

import pandas as pd

from laporan.pi_gt import dashboard, sumber

KOLOM_GT = ["COMPID", "MutationNumber", "FromWarehouse", "ToWarehouse", "CreatedBy", "PRNumber", "PONumber", "PurchaseNumber", "PRImportance",
            "ItemCode", "ItemName", "ReceivedBy", "Aging", "MutationDate", "ReceivedDateTime", "PIDate", "CreateDate", "Quantity", "RequestedBy"]
KOLOM_PI = ["CompanyName", "PRNumber", "PONumber", "PurchaseNumber", "MutationNumber", "Importance", "ItemCode", "ItemName", "PICreateBy",
            "PIDate", "QtyPI", "ReqFrom"]
HARI_INI = "2026-10-23"


def t(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M") if " " in s else datetime.strptime(s, "%Y-%m-%d")


def gt(nomor, tanggal, aging="Completed", terima=None, oleh="rizky ramadan", dari="HO", ke="PKS", pi=None, dibuat=None):
    return {"COMPID": "YBS", "MutationNumber": nomor, "FromWarehouse": dari, "ToWarehouse": ke, "CreatedBy": oleh, "PRNumber": None,
            "PONumber": None, "PurchaseNumber": pi and f"YBS/PI/HO/{nomor[-1]}", "PRImportance": "Normal", "ItemCode": "A", "ItemName": "Baut",
            "ReceivedBy": None, "Aging": aging, "MutationDate": t(tanggal), "ReceivedDateTime": terima and t(terima),
            "PIDate": pi and t(pi), "CreateDate": t(dibuat or tanggal + " 10:00"), "Quantity": 1, "RequestedBy": ke}


def pi(nomor, tanggal, gt_nomor=None, lokasi="HO", peminta="PKS"):
    return {"CompanyName": "YBS", "PRNumber": f"PR/{nomor}", "PONumber": None, "PurchaseNumber": f"YBS/PI/{lokasi}/{nomor}", "MutationNumber": gt_nomor,
            "Importance": "Normal", "ItemCode": "A", "ItemName": "Baut", "PICreateBy": "x", "PIDate": tanggal, "QtyPI": 1, "ReqFrom": peminta}


def data():
    raw_gt = pd.DataFrame([
        gt("GT/A", "2026-10-02", terima="2026-10-04 08:00", pi="2026-10-01"),
        gt("GT/A", "2026-10-02", terima="2026-10-04 08:00", pi="2026-09-28"),         # barang kedua di GT yang sama
        gt("GT/B", "2026-10-03", aging="InCompleted", oleh="Indah", ke="RDH"),          # belum diterima, tanpa PI
        gt("GT/C", "2026-10-10", oleh="rudianto", dari="RDH", ke="PKS", terima="2026-10-11 09:00"),   # pindahan antar site, tanpa PI
        gt("GT/V", "2026-10-05", aging="Void"),                                         # void: dibuang
    ], columns=KOLOM_GT)
    raw_pi = pd.DataFrame([
        pi(4, "20261003"),                       # PI HO untuk PKS belum GT, 20 hari
        pi(5, "20261020"), pi(5, "20261020"),    # kembar persis: dihitung sekali
        pi(6, "20261001", gt_nomor="GT/A"),      # sudah di-GT: datanya diambil dari gt_out
        pi(7, "20261005", peminta="HO"),         # PI HO untuk HO: tidak perlu GT
        pi(8, "20261005", lokasi="PKS"),         # PI di gudang peminta sendiri: tidak perlu GT
    ], columns=KOLOM_PI)
    return sumber.gabung(sumber.bersihkan_gt(raw_gt, hari_ini=HARI_INI), sumber.bersihkan_pi(raw_pi, hari_ini=HARI_INI))


def test_lead_time_seperti_excel():
    d = data()
    assert sorted(d["gt_number"].unique()) == ["", "GT/A", "GT/B", "GT/C"]
    a = d[d["gt_number"] == "GT/A"]
    assert list(a["lead_logistik"]) == [2, 2] and list(a["lead_pengadaan"]) == [1, 4]
    b = d[d["gt_number"] == "GT/B"].iloc[0]
    assert b["status"] == sumber.BELUM_DITERIMA and b["lead_logistik"] == 20 and pd.isna(b["lead_pengadaan"])
    assert d[d["gt_number"] == "GT/C"].iloc[0]["gt_by"] == "Rudianto"
    belum = d[d["status"] == sumber.BELUM_GT]
    assert sorted(belum["pi_number"]) == ["YBS/PI/HO/4", "YBS/PI/HO/5"]   # PI/7 (HO untuk HO) dan PI/8 (di PKS) tidak perlu GT
    assert belum.set_index("pi_number").loc["YBS/PI/HO/4", "umur_pi"] == 20


DARI, SAMPAI = pd.Timestamp("2026-09-25"), pd.Timestamp("2026-10-23")   # dua bulan: 25-30 Sep dan 1-23 Okt


def test_kpi_bulanan():
    b = dashboard.bangun(data(), DARI, SAMPAI)
    k = b["kpi"]
    # PI yang perlu GT: GT/A x2 (PI 28/9 dan 1/10), PI/4 (3/10), PI/5 (20/10). Awal 25/9: belum ada. Akhir 23/10: PI/4 dan PI/5.
    assert (k["outstanding_awal"], k["new_pi"], k["outstanding_akhir"]) == (0, 4, 2)
    assert (k["new_gt"], k["barang_gt"], k["belum_diterima"]) == (3, 4, 1)
    assert k["lead_pengadaan"]["n"] == 2 and k["outstanding_lama"] == 1 and k["aging_maks"] == 20
    m = b["bulanan"]
    assert [x["label"] for x in m] == ["Sep 2026", "Okt 2026"] and m[0]["mulai"] == "2026-09-25"
    assert [(x["new_pi"], x["new_gt"], x["outstanding_akhir"]) for x in m] == [(1, 0, 1), (3, 2, 2)]
    assert all(x["outstanding_awal"] + x["new_pi"] - x["new_gt"] == x["outstanding_akhir"] for x in m)   # alur selalu cocok
    assert {r["nama"] for r in b["durasi_rute"]} == {"HO → PKS", "HO → RDH", "RDH → PKS"}
    assert "Rudianto" in b["pilihan"]["pembuat"] and "Ilias" in b["pilihan"]["pembuat"]   # orang Logistik selalu ada di pilihan


def test_filter_pembuat_hanya_untuk_angka_gt():
    df = data()
    b = dashboard.bangun(df, DARI, SAMPAI, filt={"pembuat": ["Ilias", "rizky ramadan", "Robby", "Rudianto"]})
    assert b["kpi"]["new_gt"] == 2 and b["kpi"]["outstanding_akhir"] == 2
    assert [p["nama"] for p in b["gt_per_pembuat"]] == ["Rizky Ramadan", "Rudianto"]
    assert dashboard.detail(df, "outstanding", DARI, SAMPAI, filt={"pembuat": ["Robby"]})["baris"][0]["pi_number"] == "YBS/PI/HO/4"
    assert dashboard.bangun(df, DARI, SAMPAI, bulan=1)["periode"] == {"mulai": "2026-10-01", "akhir": "2026-10-23", "jumlah_bulan": 2}
