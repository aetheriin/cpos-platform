import ahli
import json

import pandas as pd

from inti.filter import FilterTidakValid
from laporan.pr_po import dashboard as D, ukuran as U

J = "2026-10-15"
T = pd.Timestamp


# Dashboard sekarang memakai rentang tampilan (dari, sampai). Uji ditulis dengan patokan lama "5 minggu sampai jangkar"; pembungkus ini
# menerjemahkannya, jadi arti tiap uji tidak berubah. n (jumlah minggu) selalu 5.
def bangun(df, n=5, jangkar=J, **kw):
    return D.bangun(df, *ahli.lima_minggu(jangkar, n), **kw)


def detail(df, jenis, n=5, jangkar=J, **kw):
    return D.detail(df, jenis, *ahli.lima_minggu(jangkar, n), **kw)


def df():
    """Data hasil bersihkan() dari data contoh (semua buyer)."""
    return ahli.df_pr_po()


def mgg():
    return U.daftar_minggu(df(), 5, J)


def tolak(fn, **kw):
    try:
        fn(**kw)
    except FilterTidakValid:
        return True
    return False


def test_pemetaan_kategori_tercatat():
    assert "kategori_mirip" in df().attrs["catatan"]


def test_bawaan_semua_buyer_tampil():
    d = df()
    mentah = ahli.raw_pr_po()["POBY"].dropna().astype(str).str.split(",").explode().str.strip().str.lower().str.capitalize()
    mentah = {b for b in mentah if b}
    assert mentah <= set(d["buyer"]) and {"Indra", "Andre", "Ari1", "Mita"} <= set(d["buyer"])
    r = bangun(d, 5, jangkar=J)
    assert [s["nama"] for s in r["new_po_per_buyer"]] == r["pilihan"]["buyer"]      # grafik dan menu memuat nama yang sama
    assert len(r["pilihan"]["buyer_semua"]) >= 8 and set(r["pilihan"]["buyer"]) <= set(r["pilihan"]["buyer_semua"])


def test_new_pr_sama_dengan_hitungan_langsung_dari_data_mentah():
    raw = ahli.raw_pr_po()
    tgl = pd.to_datetime(raw["CREATEDDATE"].astype(str).str.replace(r"\.0$", "", regex=True), format="%Y%m%d")
    garis = raw["COMPID"].astype(str) + raw["PRDETAILID"].astype(str)
    for s, e in mgg():
        langsung = garis[(tgl >= s) & (tgl <= e)].nunique()
        assert U.new_pr(df(), s, e) == langsung
    k = bangun(df(), 5, jangkar=J)["kpi"]
    assert detail(df(), "outstanding", 5, jangkar=J, ukuran=200)["total_semua"] == k["outstanding_akhir"]


def test_partial_hanya_po_berbeda():
    """PARTIAL = Y hanya untuk PR line yang nomor PO-nya lebih dari satu yang BERBEDA; nomor yang sama tertulis dua kali bukan partial."""
    d = df()
    raw = ahli.raw_pr_po()
    banyak = raw["PONUMBER"].fillna("").astype(str).map(lambda t: len({x.strip() for x in t.split(",") if x.strip()}))
    harapan = set((raw["COMPID"].astype(str) + raw["PRDETAILID"].astype(str))[banyak > 1])
    assert set(d.loc[d["partial"] == "Y", "line"]) == harapan and len(harapan) > 0


def test_multi_filter_menjumlah_dan_dimensi_sumber_tetap_lengkap():
    sun = bangun(df(), 5, comp=["SUN"], jangkar=J)
    ybs = bangun(df(), 5, comp=["YBS"], jangkar=J)
    dua = bangun(df(), 5, comp=["sun", "YBS"], jangkar=J)
    for k in ("outstanding_awal", "new_pr", "new_po", "outstanding_akhir"):
        assert dua["kpi"][k] == sun["kpi"][k] + ybs["kpi"][k]
    assert dua["filter"]["perusahaan"] == ["SUN", "YBS"] and len(dua["new_pr_per_perusahaan"]) == 5
    k1 = bangun(df(), 5, kategori=["Persediaan Bahan Bangunan"], jangkar=J)
    assert len(k1["pilihan"]["kategori"]) == len(bangun(df(), 5, jangkar=J)["pilihan"]["kategori"])


def test_filter_tidak_valid_ditolak():
    assert tolak(bangun, df=df(), comp=["XYZ"], jangkar=J)
    assert tolak(bangun, df=df(), minggu=9, jangkar=J)
    assert tolak(detail, df=df(), jenis="x", jangkar=J)
    assert tolak(detail, df=df(), jenis="po", urut="zzz", jangkar=J)
    assert tolak(detail, df=df(), jenis="po", arah="naik", jangkar=J)


def test_minggu_berpatokan_pada_jangkar():
    assert bangun(df(), 5, jangkar=J)["mingguan"][-1]["label"] == "09/10 - 15/10"
    assert bangun(df(), 5, jangkar="2026-10-01")["mingguan"][-1]["label"] == "25/09 - 01/10"


def test_tabel_detail_sama_dengan_kartu():
    kasus = [{}, {"minggu": 1}, {"minggu": 4}, {"comp": ["SUN"]}, {"comp": ["SUN", "YBS"], "minggu": 2},
             {"kategori": ["Persediaan Bahan Bangunan"]}, {"buyer": ["Elsa", "Indah"]}, {"buyer": ["(kosong)"]}]
    for kw in kasus:
        k = bangun(df(), 5, jangkar=J, **kw)["kpi"]
        assert detail(df(), "outstanding", 5, jangkar=J, ukuran=200, **kw)["total_semua"] == k["outstanding_akhir"], kw
        assert detail(df(), "po", 5, jangkar=J, ukuran=200, **kw)["total_semua"] == k["new_po"], kw


def test_tabel_pencarian_urutan_halaman_json():
    t = detail(df(), "outstanding", 5, jangkar=J)
    assert len(t["kolom"]) == 22 and t["urut"] == "aging" and t["arah"] == "desc"
    assert t["baris"][0]["aging"] >= t["baris"][-1]["aging"]
    assert "NaN" not in json.dumps(t) and "NaT" not in json.dumps(t)
    nm = [(r["itemname"] or "").lower() for r in detail(df(), "outstanding", 5, jangkar=J, urut="itemname", arah="asc", ukuran=200)["baris"]]
    assert nm == sorted(nm)
    h1 = detail(df(), "outstanding", 5, jangkar=J, halaman=1, ukuran=50)
    h2 = detail(df(), "outstanding", 5, jangkar=J, halaman=2, ukuran=50)
    assert len(h1["baris"]) == 50 and h1["baris"][0]["prnumber"] != h2["baris"][0]["prnumber"]
    assert detail(df(), "outstanding", 5, jangkar=J, halaman=999)["halaman"] == h1["jumlah_halaman"]
    kosong = detail(df(), "outstanding", 5, jangkar=J, cari="tidak-ada-yang-cocok-xyz")
    assert kosong["total"] == 0 and kosong["total_semua"] > 0 and kosong["baris"] == []


# ---------- Salah tautan PO antarperusahaan ----------
def _baris_open_tanpa_po(raw, comp):
    sub = raw[(raw["COMPID"] == comp) & (raw["POCREATEDATE"].isna() | (raw["POCREATEDATE"].astype(str).str.strip() == ""))]
    sub = sub[sub["ISOPEN"].astype(str).str.lower().isin(["true", "1"])]
    return sub.index[0]


def test_po_milik_perusahaan_lain_diabaikan():
    """Kasus nyata: PR milik SJN tertaut ke PO milik RCM. PO itu tidak boleh memengaruhi baris PR maupun angka."""
    from laporan.pr_po import sumber
    raw = ahli.raw_pr_po().copy()
    dasar = sumber.bersihkan(raw)
    idx = _baris_open_tanpa_po(raw, "SJN")
    line = "SJN" + str(raw.loc[idx, "PRDETAILID"]).replace(".0", "")
    raw.loc[idx, ["PONUMBER", "POCREATEDATE", "POBY", "SUPPLIERCODE", "SUPPLIERNAME"]] = ["RCM/PO/HO/2610/0107", "20261001", "Mita", "SPR-1", "PT SALAH"]
    d = sumber.bersihkan(raw)
    baris = d[d["line"] == line]
    assert len(baris) == 1 and baris.iloc[0]["po_number"] == "" and pd.isna(baris.iloc[0]["po_date"])
    assert baris.iloc[0]["buyer"] == "(kosong)" and baris.iloc[0]["supplier_name"] == "" and baris.iloc[0]["partial"] == "N"
    c = d.attrs["catatan"]
    assert c["po_beda_perusahaan"] == 1 and "RCM/PO/HO/2610/0107" in c["po_beda_perusahaan_contoh"][0] and len(c["peringatan"]) == 1
    # angka tidak terpengaruh PO salah tautan itu: sama dengan data tanpa salah tautan
    for s, e in mgg():
        assert U.new_po(d, s, e) == U.new_po(dasar, s, e)
        assert U.outstanding_akhir(d, e) == U.outstanding_akhir(dasar, e)
    assert "peringatan" not in dasar.attrs["catatan"] and dasar.attrs["catatan"]["po_beda_perusahaan"] == 0


def test_daftar_po_campuran_hanya_yang_milik_perusahaan_dipertahankan():
    from laporan.pr_po import sumber
    raw = ahli.raw_pr_po().copy()
    idx = _baris_open_tanpa_po(raw, "SJN")
    line = "SJN" + str(raw.loc[idx, "PRDETAILID"]).replace(".0", "")
    raw.loc[idx, ["PONUMBER", "POCREATEDATE", "POBY", "SUPPLIERCODE", "SUPPLIERNAME"]] = [
        "SJN/PO/HO/2609/1208,RCM/PO/HO/2610/0107", "20260925,20261001", "Elsa,Mita", "SPR-1,SPR-2", "PT BENAR,PT SALAH"]
    d = sumber.bersihkan(raw)
    b = d[d["line"] == line]
    assert len(b) == 1 and b.iloc[0]["po_number"] == "SJN/PO/HO/2609/1208" and b.iloc[0]["buyer"] == "Elsa"
    assert b.iloc[0]["supplier_name"] == "PT BENAR" and b.iloc[0]["partial"] == "N"      # tinggal satu PO, bukan partial
    assert str(b.iloc[0]["po_date"])[:10] == "2026-09-25" and d.attrs["catatan"]["po_beda_perusahaan"] == 1


def test_sp_dipanggil_satu_perusahaan_per_panggilan():
    """Memanggil SP dengan beberapa perusahaan sekaligus bisa menautkan PO perusahaan lain; harus satu per satu."""
    import threading
    from inti.gudang import KendaliBatal
    from laporan.pr_po import sumber
    raw = ahli.raw_pr_po()
    panggilan, kunci = [], threading.Lock()

    class Kursor:
        description = None

        def execute(self, sql, *params):
            with kunci:
                panggilan.append(params)
            sub = raw[raw["COMPID"] == params[0]]
            self._baris = [tuple(r) for r in sub.itertuples(index=False, name=None)]
            self.description = [(c,) for c in raw.columns]

        def fetchall(self):
            return self._baris

        def nextset(self):
            return False

    class Koneksi:
        def cursor(self):
            return Kursor()

        def close(self):
            pass

    asli, asli_daftar = sumber.get_connection, sumber.daftar_perusahaan
    sumber.get_connection = lambda: Koneksi()
    sumber.daftar_perusahaan = lambda jenis: ["YBS", "SUN", "SJN", "ORI", "RCM"]            # daftar ini sekarang dibaca dari tabel company
    try:
        kendali = KendaliBatal()
        df, catatan = sumber.muat("2025-10-01", "2026-10-12", kendali)
    finally:
        sumber.get_connection, sumber.daftar_perusahaan = asli, asli_daftar
    assert sorted(p[0] for p in panggilan) == ["ORI", "RCM", "SJN", "SUN", "YBS"]           # satu perusahaan per panggilan
    assert all(p[1:] == ("cloud", "20251001", "20261012", "4") for p in panggilan)
    assert len(kendali._kursor) == 5                                                       # tiap kursor bisa dibatalkan
    assert catatan["baris_sp"] == len(raw) and len(df) > 0


# ---------- Buyer tanpa New PO pada periode disembunyikan ----------
def _jendela(mg):
    m = mgg()
    return m[mg] if mg is not None else (m[0][0], m[-1][1])


def test_buyer_tanpa_new_po_pada_periode_disembunyikan():
    d = df()
    semua = bangun(d, 5, jangkar=J)["pilihan"]["buyer_semua"]
    ada_tersembunyi = False
    for mg in [None, 0, 1, 2, 3, 4]:
        r = bangun(d, 5, minggu=mg, jangkar=J)
        s, e = _jendela(mg)
        tampak = set(r["pilihan"]["buyer"])
        for b in semua:
            n = U.new_po(d[d["buyer"] == b], s, e)
            assert (b in tampak) == (n > 0), (mg, b, n)          # tampil kalau dan hanya kalau New PO-nya lebih dari 0
        assert [x["nama"] for x in r["new_po_per_buyer"]] == r["pilihan"]["buyer"]
        assert r["pilihan"]["buyer_semua"] == semua                # urutan tetap, supaya warna buyer tidak bergeser
        ada_tersembunyi |= len(tampak) < len(semua)
    assert ada_tersembunyi                                         # pada data ini memang ada buyer yang tidak membuat PO


def test_buyer_terpilih_tetap_tampil_walau_nol_dan_mengikuti_filter_lain():
    d = df()
    semua = bangun(d, 5, jangkar=J)["pilihan"]["buyer_semua"]
    for mg in range(5):
        r = bangun(d, 5, minggu=mg, jangkar=J)
        tersembunyi = [b for b in semua if b not in r["pilihan"]["buyer"]]
        if tersembunyi:
            b = tersembunyi[0]
            r2 = bangun(d, 5, minggu=mg, buyer=[b], jangkar=J)
            assert b in r2["pilihan"]["buyer"] and b in [x["nama"] for x in r2["new_po_per_buyer"]]    # yang dipilih tetap ada
            assert not tolak(detail, df=d, jenis="po", buyer=[b], minggu=mg, jangkar=J)             # dan tetap valid sebagai filter
            break
    else:
        raise AssertionError("tidak ada buyer tersembunyi untuk diuji")
    s, e = _jendela(None)
    r3 = bangun(d, 5, comp=["SUN"], jangkar=J)
    sun = d[d["comp"] == "SUN"]
    assert set(r3["pilihan"]["buyer"]) == {b for b in semua if U.new_po(sun[sun["buyer"] == b], s, e) > 0}   # mengikuti filter perusahaan


# ---------- Filter Umur (kategori aging) ----------
def test_filter_umur_laporan_pr_po():
    d = df()
    r = bangun(d, 5, jangkar=J)
    umur = r["pilihan"]["umur"]
    assert umur[0] == "Tepat Waktu(0-8 Hari)" and "COMPLETED" in umur
    per = {u: bangun(d, 5, umur=[u], jangkar=J)["kpi"]["outstanding_akhir"] for u in umur}
    assert sum(per.values()) == r["kpi"]["outstanding_akhir"]            # tiap baris PR punya tepat satu umur
    assert per["Perlu Tindakan(>30 Hari)"] > 0 and per["Tepat Waktu(0-8 Hari)"] > 0
    pilih = ["Telat(16-30 Hari)", "Perlu Tindakan(>30 Hari)"]
    dua = bangun(d, 5, umur=[pilih[1], pilih[0]], jangkar=J)           # urutan masukan tidak berpengaruh
    assert dua["filter"]["umur"] == pilih and dua["kpi"]["outstanding_akhir"] == per[pilih[0]] + per[pilih[1]]
    assert tolak(bangun, df=d, umur=["x"], jangkar=J) and tolak(detail, df=d, jenis="po", umur=["x"], jangkar=J)


def test_filter_umur_tabel_detail_dan_gabungan_filter():
    d = df()
    for kw in [{"umur": ["Telat(16-30 Hari)"]}, {"umur": ["Perlu Tindakan(>30 Hari)"], "comp": ["SJN"]},
               {"umur": ["Tepat Waktu(0-8 Hari)"], "minggu": 4}, {"umur": ["Telat(16-30 Hari)", "Perlu Perhatian(9-15 Hari)"], "buyer": ["(kosong)"]}]:
        k = bangun(d, 5, jangkar=J, **kw)["kpi"]
        assert detail(d, "outstanding", 5, jangkar=J, ukuran=200, **kw)["total_semua"] == k["outstanding_akhir"], kw
        assert detail(d, "po", 5, jangkar=J, ukuran=200, **kw)["total_semua"] == k["new_po"], kw
    baris = detail(d, "outstanding", 5, umur=["Telat(16-30 Hari)"], jangkar=J, ukuran=200)["baris"]
    assert baris and all(16 <= float(b["aging"]) <= 30 for b in baris)       # isi tabel memang berumur 16 sampai 30 hari


# ---------- New PO = jumlah PO per baris PR; PO Partial = persen dari New PO ----------
def test_new_po_split_dihitung_per_po_dan_po_identik_dihitung_sekali():
    t = pd.Timestamp
    s, e = t("2026-10-01"), t("2026-10-10")

    def baris(line, no, tgl="2026-10-05", partial="N", status="Completed", qtyout=0.0):
        return {"line": line, "po_number": no, "po_date": t(tgl), "partial": partial, "status": status, "qtyout": qtyout}
    df_ = pd.DataFrame([
        baris("A", "PO1"),                                   # PR biasa: satu PO
        baris("B", "PO2", partial="Y"), baris("B", "PO3", partial="Y"),            # split: dua PO berbeda, keduanya New PO
        baris("C", "PO4"), baris("C", "PO4"),                # PO yang sama (nomor dan tanggal sama): bukan split, dihitung sekali
        baris("D", "PO5", tgl="2026-09-01"),                 # di luar periode
        baris("E", "PO6", qtyout=3.0), baris("F", "PO7", status="Void"),           # qty belum habis, dibatalkan: bukan New PO
    ])
    assert U.new_po(df_, s, e) == 4                          # A, B(PO2), B(PO3), C
    assert U.po_partial(df_, s, e) == (2, 4, 0.5)            # kedua PO milik B partial


def test_po_partial_contoh_13_dari_2000_new_po():
    """Contoh dari pengguna: 13 PO partial dalam 2000 New PO = 0,65%. Status partial adalah sifat PR-nya: PO yang pasangannya jatuh di minggu
    lain tetap partial. Yang bukan New PO tidak boleh ikut di penyebut."""
    t = pd.Timestamp
    s, e = t("2026-10-01"), t("2026-10-10")
    n_biasa = 1987
    biasa = pd.DataFrame({"line": [f"N{i}" for i in range(n_biasa)], "po_number": [f"P{i}" for i in range(n_biasa)],
                          "po_date": t("2026-10-05"), "qtyout": 0.0, "status": "Completed", "partial": "N"})
    partial = []                                                                   # 13 PO partial: 6 PR dengan dua PO di periode, dan 1 PR yang PO keduanya di minggu lain
    for i in range(6):
        partial += [{"line": f"Y{i}", "po_number": f"YA{i}", "po_date": t("2026-10-05")}, {"line": f"Y{i}", "po_number": f"YB{i}", "po_date": t("2026-10-06")}]
    partial += [{"line": "Y6", "po_number": "YA6", "po_date": t("2026-10-05")}]
    partial = pd.DataFrame(partial).assign(qtyout=0.0, status="Completed", partial="Y")
    luar = pd.DataFrame({"line": ["B1", "B2", "B3", "B4", "Y6"], "po_number": ["Q1", "Q2", "Q3", "Q4", "YB6"], "qtyout": [0.0, 5.0, 0.0, 0.0, 0.0],
                         "po_date": [t("2026-09-01"), t("2026-10-05"), t("2026-10-05"), t("2026-10-05"), t("2026-09-20")],   # YB6: PO kedua Y6, di minggu lain
                         "status": ["Completed", "Open", "Void", "Closed", "Completed"], "partial": ["Y", "Y", "Y", "N", "Y"]})
    df_ = pd.concat([biasa, partial, partial.iloc[:3], luar], ignore_index=True)    # baris persis kembar (partial.iloc[:3]) tidak dihitung dua kali
    y, total, persen = U.po_partial(df_, s, e)
    assert (y, total) == (13, 2000) and abs(persen - 0.0065) < 1e-12 and U.new_po(df_, s, e) == 2000
    assert U.po_partial(df_, t("2026-09-15"), t("2026-09-25")) == (1, 1, 1.0)       # PO kedua Y6 dihitung di mingguannya sendiri, dan juga partial
    awal, akhir = t("2026-09-01"), t("2026-10-10")                                  # jumlah dua periode yang berurutan = jumlah periode gabungan
    assert U.po_partial(df_, awal, t("2026-09-30"))[0] + U.po_partial(df_, t("2026-10-01"), akhir)[0] == U.po_partial(df_, awal, akhir)[0]
    assert U.po_partial(df_.iloc[0:0], s, e) == (0, 0, 0.0)                        # tanpa New PO: 0, bukan error


def test_po_partial_penyebut_selalu_sama_dengan_kartu_new_po():
    d = df()
    kasus = [{}, {"minggu": 0}, {"minggu": 3}, {"comp": ["SUN"]}, {"comp": ["SUN", "YBS"], "minggu": 2},
             {"buyer": ["Elsa"]}, {"kategori": ["Persediaan Bahan Bangunan"]}, {"umur": ["COMPLETED"]}]
    for kw in kasus:
        k = bangun(d, 5, jangkar=J, **kw)["kpi"]
        p = k["po_partial"]
        assert p["dari"] == k["new_po"], kw                                       # penyebut = angka di kartu New PO
        assert 0 <= p["jumlah"] <= p["dari"] and abs(p["persen"] - (p["jumlah"] / p["dari"] if p["dari"] else 0)) < 1e-12, kw


def test_po_partial_sama_dengan_hitungan_independen_dari_data_mentah():
    """Partial ditentukan dari data mentah: PR line yang nomor PO-nya lebih dari satu yang berbeda, di periode mana pun. Yang dihitung PO-nya."""
    raw = ahli.raw_pr_po()
    nomor = raw["PONUMBER"].fillna("").astype(str).map(lambda t: len({x.strip() for x in t.split(",") if x.strip()}))
    partial = set((raw["COMPID"].astype(str) + raw["PRDETAILID"].astype(str))[nomor > 1])
    d = df()
    mg = mgg()
    for s, e in [(mg[0][0], mg[-1][1])] + mg:                                       # seluruh periode dan tiap minggu
        po = d.loc[U._mask_new_po(d, s, e), ["line", "po_number", "po_date"]].drop_duplicates()
        y, total, persen = U.po_partial(d, s, e)
        assert total == len(po) == U.new_po(d, s, e) and y == int(po["line"].isin(partial).sum())


def test_partial_per_minggu_dijumlahkan_sama_dengan_seluruh_periode():
    """PR yang PO-nya terpisah minggu tetap partial di tiap minggunya, dan tiap PO dihitung di minggunya sendiri. Kasus pada 11/09-17/09:
    3 PR dengan dua PO (6 PO) ditambah PO 1119 milik PR OIL SEAL (PO keduanya 1223 baru dibuat 29/09, di minggu lain)."""
    d = df()
    mg = mgg()
    k = bangun(d, 5, minggu=0, jangkar=J)["kpi"]
    assert k["po_partial"]["dari"] == k["new_po"] == U.new_po(d, *mg[0]) and k["po_partial"]["jumlah"] >= 7
    oil = d[(d["prnumber"] == "SJN/PR/PKS/2609/010") & (d["itemcode"] == "14.0483")]
    assert sorted(oil["po_number"]) == ["SJN/PO/HO/2609/1119", "SJN/PO/HO/2609/1223"] and set(oil["partial"]) == {"Y"}
    baris = oil["line"].iloc[0]
    for no, minggu in (("SJN/PO/HO/2609/1119", 0), ("SJN/PO/HO/2609/1223", 2)):         # tiap PO dihitung partial di minggunya sendiri
        p = U._po_baru(d, *mg[minggu])
        assert p[(p["line"] == baris) & (p["po_number"] == no)]["partial"].tolist() == ["Y"]
        lain = [m for m in range(5) if m != minggu]                                      # dan tidak dihitung di minggu lain
        assert all(baris not in set(U._po_baru(d, *mg[m]).loc[lambda x: x["po_number"] == no, "line"]) for m in lain)
    per_minggu = [U.po_partial(d, a, b)[0] for a, b in mg]
    total = U.po_partial(d, mg[0][0], mg[-1][1])[0]
    assert sum(per_minggu) == total and per_minggu[0] == k["po_partial"]["jumlah"]    # dijumlahkan per minggu = total seluruh periode
    assert sum(U.new_po(d, a, b) for a, b in mg) == U.new_po(d, mg[0][0], mg[-1][1])
    for kw in ({"comp": ["SJN"]}, {"buyer": ["Elsa"]}, {"kategori": ["Persediaan Bahan Bangunan"]}):   # juga benar dengan filter
        mingguan = sum(bangun(d, 5, minggu=i, jangkar=J, **kw)["kpi"]["po_partial"]["jumlah"] for i in range(5))
        assert mingguan == bangun(d, 5, jangkar=J, **kw)["kpi"]["po_partial"]["jumlah"], kw


def test_tabel_sudah_po_satu_baris_per_po_kecuali_nomor_duplikat():
    """Tabel Sudah PO: satu baris per PO (PR yang di-PO dua kali tampil dua baris). PO dengan nomor dan tanggal yang sama satu baris."""
    d = df()
    s, e = mgg()[0][0], mgg()[-1][1]
    k = bangun(d, 5, jangkar=J)["kpi"]
    t = detail(d, "po", 5, jangkar=J, ukuran=200)
    semua = [b for h in range(1, t["jumlah_halaman"] + 1) for b in detail(d, "po", 5, jangkar=J, ukuran=200, halaman=h)["baris"]]
    assert len(semua) == t["total_semua"] == k["new_po"] == len(U._po_baru(d, s, e))        # jumlah baris tabel = kartu New PO
    kolom = [c["kunci"] for c in t["kolom"]]
    assert kolom[-1] == "partial" and t["kolom"][-1]["judul"] == "Partial"
    assert all(", " not in (b["po_number"] or "") for b in semua)                           # nomor PO tidak digabung lagi
    unik = {(b["prnumber"], b["itemcode"], b["po_number"], b["po_date"]) for b in semua}
    assert len(semua) >= len(unik)                                                          # (baris PR berbeda boleh berbagi PR dan item yang sama)
    ya = [b for b in semua if b["partial"] == "Y"]
    assert len(ya) == k["po_partial"]["jumlah"] and all(b["partial"] in ("Y", "N") for b in semua)   # kolom Partial = angka di kartu
    o = detail(d, "outstanding", 5, jangkar=J, ukuran=200)["baris"]
    assert all(b["partial"] is None for b in o)                                             # kolom Partial hanya untuk tab Sudah PO
    t0 = detail(d, "po", 5, minggu=0, jangkar=J, ukuran=1000)                    # minggu 11/09-17/09 (semua baris dalam satu halaman)
    k0 = bangun(d, 5, minggu=0, jangkar=J)["kpi"]
    assert t0["jumlah_halaman"] == 1 and t0["total_semua"] == k0["new_po"]
    assert sum(b["partial"] == "Y" for b in t0["baris"]) == k0["po_partial"]["jumlah"]      # jumlah PO partial di tabel = kartu
