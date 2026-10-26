import pandas as pd

from laporan.palm import sumber as S


def _raw(tara_kolom="MaxHistoricalTara", split=True):
    d = pd.DataFrame({
        "TicketNo": ["A", "B"], "TicketDate": ["2026-10-01", "2026-10-02"], "DurationMinutes": [30, 40], "VehicleNo": ["BM1", "BM2"],
        "ProductName": ["TBS", "TBS"], "Bruto": [40000, 41000], "ActualTara": [13000, 12000], tara_kolom: [13100, 12500],
        "TaraDeviation": [-100, -500], "Deduction": [0, 0], "Netto": [27000, 29000], "Operator": ["x", "y"], "NamaSupir": ["s", "t"],
        "SupplierCode": ["1", "2"], "SupplierName": ["P", "Q"],
    })
    if split:
        d["Splitted"] = [1, 0]
    return d


def test_tara_historis_maks_dan_splitted():
    d = S.bersihkan(_raw())
    assert d["tara_historis"].tolist() == [13100, 12500]
    assert d["split"].tolist() == [S.SPLIT_YA, S.SPLIT_TIDAK]


def test_ticket_type_menjadi_pembelian_atau_penjualan():
    raw = _raw().assign(TicketType=["TBSLuar", "Produk"])
    assert S.bersihkan(raw)["jenis"].tolist() == ["Pembelian", "Penjualan"]
    raw = _raw().assign(TicketType=["TBS Luar", None])
    assert S.bersihkan(raw)["jenis"].tolist() == ["Pembelian", S.KOSONG]


def test_pilihan_filter_menyempit_sesuai_jenis():
    from laporan.palm import dashboard as D
    raw = _raw().assign(TicketType=["TBSLuar", "Produk"], ProductName=["TBS", "CPO"])
    d = S.bersihkan(raw)
    semua = D._hitung_pilihan(d)
    assert set(semua["produk"]) == {"TBS", "CPO"}
    p = D._pilihan_per_jenis(d, {"transaksi": ["Penjualan"], "produk": ["TBS"]}, semua)
    assert p["produk"] == ["CPO", "TBS"]          # TBS tetap ada karena sedang terpilih
    assert p["transaksi"] == semua["transaksi"]
    assert D._pilihan_per_jenis(d, {"transaksi": []}, semua) is semua


def test_nama_kolom_lama_dan_tanpa_splitted_tetap_terbaca():
    d = S.bersihkan(_raw("AvgHistoricalTara", split=False))
    assert d["tara_historis"].tolist() == [13100, 12500]
    assert set(d["split"]) == {S.SPLIT_TIDAK}
