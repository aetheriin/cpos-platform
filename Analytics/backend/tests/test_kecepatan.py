import ahli
import json

import pandas as pd

from inti import kecepatan as K
from laporan.po_pi import dashboard as DI, ukuran as PI
from laporan.pr_po import dashboard as DP, ukuran as PR

J = "2026-10-15"
HARI = pd.Timestamp.today().normalize()
T = pd.Timestamp


# Dashboard sekarang memakai rentang tampilan (dari, sampai). Uji ditulis dengan patokan lama "5 minggu sampai jangkar"; pembungkus ini
# menerjemahkannya, jadi arti tiap uji tidak berubah.
def bangun_pr(df, n=5, jangkar=J, **kw):
    return DP.bangun(df, *ahli.lima_minggu(jangkar, n), **kw)


def detail_pr(df, jenis, n=5, jangkar=J, **kw):
    return DP.detail(df, jenis, *ahli.lima_minggu(jangkar, n), **kw)


def bangun_pi(df, jangkar=J, **kw):
    return DI.bangun(df, *ahli.lima_minggu(jangkar), **kw)


def detail_pi(df, jenis, jangkar=J, **kw):
    return DI.detail(df, jenis, *ahli.lima_minggu(jangkar), **kw)


# ---------- ringkasan (uji murni, angka dihitung dengan tangan) ----------
def test_ringkas_menghitung_yang_dibuat_pada_periode():
    nat = pd.NaT
    g = pd.DataFrame({                                        # periode: 1 sampai 7 Oktober
        "awal":    [T("2026-10-02"), T("2026-10-03"), T("2026-10-05"), T("2026-10-06"), T("2026-10-04"), T("2026-09-28"), T("2026-10-09")],
        "selesai": [T("2026-10-04"), T("2026-10-10"), nat,             T("2026-10-06"), T("2026-10-01"), T("2026-10-02"), T("2026-10-10")],
        "lama":    [2,               7,               float("nan"),    0,               -3,              4,               1],
    }, index=list("ABCDEFG"))
    # A: selesai dalam periode (2 hari). B: dibuat di periode, selesai setelah periode (7 hari). C: masih open.
    # D: selesai dalam periode (0 hari). E: data janggal (selesai sebelum dibuat). F: dibuat sebelum periode. G: dibuat setelah periode.
    r = K.ringkas(g, T("2026-10-01"), T("2026-10-07"))
    assert r["selesai_periode"] == {"jumlah": 2, "dari": 4, "persen": 0.5}      # A dan D dari A, B, C, D (E dikeluarkan)
    assert r["rata_rata"] == 3.0 and r["diukur"] == 3                           # (2 + 7 + 0) / 3: B ikut walau selesai setelah periode
    assert r["dikecualikan"] == 1                                               # E
    kosong = K.ringkas(g, T("2027-01-01"), T("2027-01-31"))
    assert kosong["rata_rata"] is None and kosong["diukur"] == 0 and kosong["selesai_periode"] == {"jumlah": 0, "dari": 0, "persen": None}
    assert "NaN" not in json.dumps(kosong)
    hanya_open = K.ringkas(g.loc[["C"]], T("2026-10-01"), T("2026-10-07"))      # semua masih open: 0%, bukan kosong
    assert hanya_open["selesai_periode"] == {"jumlah": 0, "dari": 1, "persen": 0.0} and hanya_open["rata_rata"] is None
    assert K.ringkas(g, T("2026-10-02"), T("2026-10-02"))["selesai_periode"]["dari"] == 1                  # batas tanggal inklusif


# ---------- hitungan independen dari data mentah ----------
def _tanggal(seri):
    return pd.to_datetime(seri.astype(str).str.replace(r"\.0$", "", regex=True).str.strip(), format="%Y%m%d", errors="coerce")


def _terakhir(teks):
    """Tanggal terakhir yang sah (tidak melewati hari ini) dari daftar tanggal dipisah koma."""
    if not isinstance(teks, str) or not teks.strip():
        return pd.NaT
    d = pd.to_datetime([x.strip() for x in teks.split(",") if x.strip()], format="%Y%m%d", errors="coerce")
    d = d[d <= HARI]
    return d.max() if len(d) else pd.NaT


def _benar(seri):
    return seri.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))


def _susun(line, awal, selesai, status):
    x = pd.DataFrame({"line": line, "awal": awal, "selesai": selesai, "status": status})
    x = x[x["status"].isin(["Open", "Completed"])].copy()
    x.loc[x["status"] == "Open", "selesai"] = pd.NaT                            # yang masih open tidak dianggap selesai
    x = x[(x["status"] == "Open") | x["selesai"].notna()].set_index("line")
    x["lama"] = (x["selesai"] - x["awal"]).dt.days
    return x


def independen_pr():
    raw = ahli.raw_pr_po()
    st = pd.Series("Tidak diketahui", index=raw.index)                          # urutan PR/PO: Completed menang atas Void dan Closed
    st[_benar(raw["ISOPEN"])] = "Open"
    st[_benar(raw["ISCLOSE"])] = "Closed"
    st[_benar(raw["ISVOID"])] = "Void"
    st[_benar(raw["ISCOMPLETE"])] = "Completed"
    return _susun(raw["COMPID"].astype(str) + raw["PRDETAILID"].astype(str), _tanggal(raw["CREATEDDATE"]), raw["POCREATEDATE"].map(_terakhir), st)


def independen_po():
    raw = ahli.raw_po_pi()
    st = pd.Series("Tidak diketahui", index=raw.index)                          # urutan PO/PI: Void menang atas Completed
    st[_benar(raw["ISOPEN"])] = "Open"
    st[_benar(raw["ISCLOSE"]) | _benar(raw["POISCLOSE"])] = "Closed"
    st[_benar(raw["ISCOMPLETE"])] = "Completed"
    st[_benar(raw["ISVOID"])] = "Void"
    return _susun(raw["COMPID"].astype(str) + raw["PODETAILID"].astype(str).str.replace(r"\.0$", "", regex=True),
                  _tanggal(raw["PODATE"]), raw["PURCHASEDATE"].map(_terakhir), st)


def ringkasan_independen(x, mulai, akhir):
    w = x[(x["awal"] >= mulai) & (x["awal"] <= akhir)]
    sel = w[w["selesai"].notna()]
    sah = sel[sel["lama"] >= 0]
    dibuat = len(w) - int((sel["lama"] < 0).sum())
    dalam = int((sah["selesai"] <= akhir).sum())
    return {"rata_rata": round(sah["lama"].mean(), 1) if len(sah) else None, "diukur": len(sah),
            "dalam": dalam, "dari": dibuat, "dikecualikan": int((sel["lama"] < 0).sum())}


def cocok(k, i):
    assert (k["rata_rata"], k["diukur"], k["selesai_periode"]["jumlah"], k["selesai_periode"]["dari"], k["dikecualikan"]) == \
           (i["rata_rata"], i["diukur"], i["dalam"], i["dari"], i["dikecualikan"])
    assert k["selesai_periode"]["persen"] == (i["dalam"] / i["dari"] if i["dari"] else None)


def test_penyelesaian_pr_sama_dengan_hitungan_independen():
    g, x = PR.penyelesaian(ahli.df_pr_po()), independen_pr()
    assert set(g.index) == set(x.index) and len(g) > 10000
    assert g["selesai"].equals(x.loc[g.index, "selesai"]) and g["lama"].equals(x.loc[g.index, "lama"])
    assert int(g["selesai"].isna().sum()) == int((x["selesai"].isna()).sum())    # PR yang masih Open


def test_penyelesaian_po_sama_dengan_hitungan_independen_dan_tanpa_selisih_negatif():
    g, x = PI.penyelesaian(ahli.df_po_pi()), independen_po()
    assert set(g.index) == set(x.index) and len(g) > 10000
    assert g["selesai"].equals(x.loc[g.index, "selesai"]) and g["lama"].equals(x.loc[g.index, "lama"])
    assert int(g["selesai"].isna().sum()) == int((x["selesai"].isna()).sum())    # PO yang masih Open
    assert (g["lama"] < 0).sum() == 0                                           # tanggal dokumen PO tidak pernah setelah PI-nya
    assert g["selesai"].max() <= HARI                                           # tanggal PI tahun 2205 tidak ikut


def test_kartu_kecepatan_pr_sama_dengan_hitungan_independen():
    x, d = independen_pr(), ahli.df_pr_po()
    mg = PR.daftar_minggu(d, 5, J)
    k = bangun_pr(d, 5, jangkar=J)["kecepatan"]
    cocok(k, ringkasan_independen(x, mg[0][0], mg[-1][1]))
    jumlah_dari = jumlah_diukur = 0
    for i, (a, b) in enumerate(mg):                                             # memilih satu minggu: kelompok PR yang dibuat minggu itu
        m = bangun_pr(d, 5, minggu=i, jangkar=J)["kecepatan"]
        cocok(m, ringkasan_independen(x, a, b))
        jumlah_dari += m["selesai_periode"]["dari"]
        jumlah_diukur += m["diukur"]
    assert jumlah_dari == k["selesai_periode"]["dari"] and jumlah_diukur == k["diukur"]     # kelompok per minggu = kelompok seluruh periode
    assert k["selesai_periode"]["jumlah"] >= sum(bangun_pr(d, 5, minggu=i, jangkar=J)["kecepatan"]["selesai_periode"]["jumlah"] for i in range(5)) - 0
    assert 0 <= k["selesai_periode"]["persen"] <= 1


def test_kartu_kecepatan_po_pi_sama_dengan_hitungan_independen():
    x, d = independen_po(), ahli.df_po_pi()
    mg = PI.daftar_minggu(5, J)
    k = bangun_pi(d, J)["kecepatan"]
    cocok(k, ringkasan_independen(x, mg[0][0], mg[-1][1]))
    assert k["dikecualikan"] == 0
    for i, (a, b) in enumerate(mg):
        cocok(bangun_pi(d, J, minggu=i)["kecepatan"], ringkasan_independen(x, a, b))


def test_persen_selesai_dalam_periode_lebih_kecil_untuk_satu_minggu_daripada_seluruh_periode():
    d = ahli.df_pr_po()
    seluruh = bangun_pr(d, 5, jangkar=J)["kecepatan"]["selesai_periode"]["persen"]
    minggu_terakhir = bangun_pr(d, 5, minggu=4, jangkar=J)["kecepatan"]["selesai_periode"]["persen"]
    minggu_pertama = bangun_pr(d, 5, minggu=0, jangkar=J)["kecepatan"]["selesai_periode"]["persen"]
    assert 0 < minggu_terakhir < minggu_pertama < 1 and seluruh > minggu_pertama   # periode lebih panjang: lebih banyak waktu untuk selesai


def test_kecepatan_mengikuti_filter_dan_tidak_memuat_data_lama():
    d = ahli.df_pr_po()
    tot = bangun_pr(d, 5, jangkar=J)
    k = tot["kecepatan"]
    per = [bangun_pr(d, 5, comp=[c], jangkar=J)["kecepatan"] for c in tot["pilihan"]["perusahaan"]]
    assert sum(p["selesai_periode"]["dari"] for p in per) == k["selesai_periode"]["dari"]      # per perusahaan dijumlah = total
    assert sum(p["selesai_periode"]["jumlah"] for p in per) == k["selesai_periode"]["jumlah"]
    assert sum(p["diukur"] for p in per) == k["diukur"]
    telat = bangun_pr(d, 5, umur=["Telat(16-30 Hari)"], jangkar=J)["kecepatan"]               # hanya PR yang masih berjalan
    assert telat["diukur"] == 0 and telat["rata_rata"] is None and telat["selesai_periode"]["jumlah"] == 0
    assert telat["selesai_periode"]["dari"] > 0 and telat["selesai_periode"]["persen"] == 0.0 and "NaN" not in json.dumps(telat)
    for nama in ("median", "tepat_waktu", "target_hari", "selesai"):                           # ukuran lama sudah dihapus
        assert nama not in k
    assert "kecepatan_mingguan" not in tot and "kecepatan_mingguan" not in bangun_pi(ahli.df_po_pi(), J)
    assert bangun_pi(ahli.df_po_pi(), J, minggu=1)["kecepatan"]["selesai_periode"]["dari"] > 0


def test_tanggal_po_masa_depan_diabaikan():
    from laporan.pr_po import sumber
    raw = ahli.raw_pr_po().copy()
    ok = raw[_benar(raw["ISCOMPLETE"]) & raw["POCREATEDATE"].notna() & ~raw["POCREATEDATE"].astype(str).str.contains(",")].iloc[0]
    idx = ok.name
    asli = str(raw.loc[idx, "POCREATEDATE"]).replace(".0", "")
    raw.loc[idx, "POCREATEDATE"] = f"22051231,{asli}"                          # satu tanggal PO salah ketik (tahun 2205)
    raw.loc[idx, "PONUMBER"] = f"{raw.loc[idx, 'COMPID']}/PO/X/1,{raw.loc[idx, 'PONUMBER']}"
    raw.loc[idx, "POBY"] = f"Elsa,{raw.loc[idx, 'POBY']}"
    d = sumber.bersihkan(raw)
    line = str(raw.loc[idx, "COMPID"]) + str(raw.loc[idx, "PRDETAILID"])
    g = PR.penyelesaian(d)
    assert str(g.loc[line, "selesai"])[:10] == f"{asli[:4]}-{asli[4:6]}-{asli[6:8]}"   # memakai tanggal PO yang sah, bukan 2205


def test_kolom_lama_selesai_di_tabel_detail():
    d = ahli.df_pr_po()
    g = PR.penyelesaian(d)
    t = detail_pr(d, "po", 5, jangkar=J, ukuran=200)
    assert t["kolom"][4]["kunci"] == "lama" and t["kolom"][4]["tipe"] == "angka"
    assert any(b["lama"] is not None for b in t["baris"])
    urut = detail_pr(d, "po", 5, jangkar=J, urut="lama", arah="desc", ukuran=200)
    angka = [b["lama"] for b in urut["baris"] if b["lama"] is not None]
    assert angka == sorted(angka, reverse=True)                                 # urut turun menurut lama selesai
    semua = [b["lama"] for h in range(1, urut["jumlah_halaman"] + 1)
             for b in detail_pr(d, "po", 5, jangkar=J, urut="lama", arah="desc", ukuran=200, halaman=h)["baris"] if b["lama"] is not None]
    assert angka[0] == max(semua) and set(semua) <= set(g["lama"].dropna())     # terlama di paling atas; nilainya berasal dari penyelesaian()
    o = detail_pr(d, "outstanding", 5, jangkar=J, ukuran=200)["baris"]
    assert all(b["lama"] is None for b in o)                                    # yang masih outstanding belum punya lama selesai
    tp = detail_pi(ahli.df_po_pi(), "pi", J, ukuran=200)["baris"]
    assert any(b["lama"] is not None for b in tp) and "NaN" not in json.dumps(tp)
