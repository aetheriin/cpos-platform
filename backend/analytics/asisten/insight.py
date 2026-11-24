"""Insight per menu: cek tetap per sumber data, hanya yang melewati ambang yang ditampilkan, diurutkan dari yang paling penting.

Hasil tiap cek berupa data terstruktur (kode, tingkat, skor, data, tanya); kalimatnya disusun terpisah di KALIMAT. Kalau nanti kalimat
dirangkai model bahasa lokal, model cukup menerima `data` yang sama, perhitungannya tidak berubah."""
from datetime import date

import pandas as pd

from .pembaca import NAMA_BULAN
from .pengolah import _bil, fmt, rp

# Ambang bisnis. Ubah di sini; berlaku setelah backend dijalankan ulang.
AMBANG = {
    "umur_lama": 30,          # hari: dokumen dianggap lama (sama dengan kelompok aging Perlu Tindakan)
    "basi": 90,               # hari: dokumen outstanding yang kemungkinan sudah tidak dibutuhkan
    "tertahan": 14,           # hari: PVR yang belum juga dibayar
    "penumpukan": 0.4,        # porsi 3 teratas yang dianggap menumpuk
    "ubah": 0.2,              # perubahan dibanding pembanding yang dianggap berarti
    "lambat": 1.5,            # kali rata-rata keseluruhan yang dianggap lambat
    "min_baris": 10,          # baris minimal supaya rata-rata kelompok layak dibandingkan
}
MAKS_POIN = 5
TINGKAT = {"tinggi": 3, "sedang": 2, "info": 1}


def _dok(df, nomor):
    return int(df[["comp", nomor]].drop_duplicates().shape[0])


def _pct(x):
    return f"{x * 100:.0f}%"


def _poin(kode, tingkat, skor, data, tanya=None):
    return {"kode": kode, "tingkat": tingkat, "skor": TINGKAT[tingkat] * 1000 + skor, "data": data, "tanya": tanya}


def _tingkat_porsi(porsi):
    return "tinggi" if porsi >= 0.5 else "sedang" if porsi >= 0.25 else "info"


def _penumpukan(df, kol, nilai, kode, tanya, data_lain=None):
    """3 kelompok teratas memegang porsi besar dari total nilai."""
    df = df[~df[kol].fillna("").astype(str).str.strip().isin(["", "(kosong)", "-"])]
    total = float(df[nilai].sum()) if nilai else len(df)
    if total <= 0:
        return None
    g = (df.groupby(kol)[nilai].sum() if nilai else df.groupby(kol).size()).sort_values(ascending=False)
    if len(g) < 4:
        return None
    porsi = float(g.iloc[:3].sum()) / total
    if porsi < AMBANG["penumpukan"]:
        return None
    atas = [{"nama": str(k), "nilai": float(v), "porsi": float(v) / total} for k, v in g.iloc[:3].items()]
    return _poin(kode, "sedang", porsi * 100, {"porsi": porsi, "atas": atas, "total": total, "jumlah_kelompok": int(len(g)), **(data_lain or {})},
                 tanya)


def _tren(df, kol_tgl, kol_nilai, hari_ini, kode, tanya, data_lain=None):
    """Rata-rata bulan berjalan (atau bulan lalu kalau bulan ini masih sedikit datanya) dibanding rata-rata 3 bulan sebelumnya."""
    d = df[df[kol_nilai].notna() & df[kol_tgl].notna()]
    if d.empty:
        return None
    bln = d[kol_tgl].dt.to_period("M")
    kini = pd.Period(hari_ini, "M")
    if (bln == kini).sum() < AMBANG["min_baris"]:
        kini -= 1
    a = d.loc[bln == kini, kol_nilai]
    b = d.loc[(bln < kini) & (bln >= kini - 3), kol_nilai]
    if len(a) < AMBANG["min_baris"] or len(b) < AMBANG["min_baris"] or b.mean() <= 0:
        return None
    ubah = (a.mean() - b.mean()) / b.mean()
    if abs(ubah) < AMBANG["ubah"]:
        return None
    return _poin(kode, "sedang" if ubah > 0 else "info", abs(ubah) * 100,
                 {"bulan": f"{NAMA_BULAN[kini.month - 1]} {kini.year}", "kini": float(a.mean()), "dulu": float(b.mean()), "ubah": float(ubah),
                  **(data_lain or {})}, tanya)


def _lambat(df, kol, kol_nilai, kode, tanya, data_lain=None):
    """Kelompok (buyer, supplier, perusahaan) yang rata-ratanya jauh di atas rata-rata keseluruhan."""
    d = df[df[kol_nilai].notna()]
    d = d.assign(**{kol: d[kol].fillna("").astype(str).str.split(", ")}).explode(kol)
    # nama kosong atau hanya bentuk usaha (data master belum lengkap) tidak disebut sebagai pelaku
    d = d[~d[kol].str.strip().str.upper().str.strip(". ").isin(["", "PT", "CV", "LTD", "TBK", "UD", "-"])]
    umum = d[kol_nilai].mean()
    if d.empty or not umum or umum < 1:
        return None
    g = d.groupby(kol)[kol_nilai].agg(["mean", "size"])
    g = g[g["size"] >= AMBANG["min_baris"]]
    if len(g) < 2:
        return None
    g = g.sort_values("mean", ascending=False)
    kali = g["mean"].iloc[0] / umum
    if kali < AMBANG["lambat"]:
        return None
    return _poin(kode, "sedang", min(kali, 5) * 8, {"nama": str(g.index[0]), "rata": float(g["mean"].iloc[0]), "umum": float(umum), "kali": float(kali),
                                            "baris": int(g["size"].iloc[0]), **(data_lain or {})}, tanya)


def _banding_bulan(df, kol_tgl, hitung, hari_ini, kode, tanya, data_lain=None):
    """Tanggal 1 sampai hari ini dibanding tanggal yang sama bulan lalu."""
    if hari_ini.day < 7:
        return None
    awal = pd.Timestamp(hari_ini.replace(day=1))
    akhir = pd.Timestamp(hari_ini) + pd.Timedelta(days=1)
    awal_l = awal - pd.offsets.MonthBegin(1)
    akhir_l = min(awal_l + (akhir - awal), awal)
    a = hitung(df[(df[kol_tgl] >= awal) & (df[kol_tgl] < akhir)])
    b = hitung(df[(df[kol_tgl] >= awal_l) & (df[kol_tgl] < akhir_l)])
    if not b or not a:
        return None
    ubah = (a - b) / b
    if abs(ubah) < AMBANG["ubah"]:
        return None
    return _poin(kode, "info", abs(ubah) * 50, {"kini": float(a), "dulu": float(b), "ubah": float(ubah), "hari": hari_ini.day,
                                               "bulan_lalu": NAMA_BULAN[awal_l.month - 1], **(data_lain or {})}, tanya)


# ---------- cek per sumber ----------

def _outstanding(df, hari_ini):
    hasil = []
    h = df[df["jenis"] == "hutang"]
    total = float(h["sisa_rp"].sum())
    batas = AMBANG["umur_lama"]
    if total > 0:
        tua = h[h["umur"] > batas]
        nilai = float(tua["sisa_rp"].sum())
        if nilai > 0:
            porsi = nilai / total
            hasil.append(_poin("hutang_tua", _tingkat_porsi(porsi), porsi * 100,
                               {"nilai": nilai, "total": total, "porsi": porsi, "dokumen": _dok(tua, "no_dok"), "batas": batas},
                               "Daftar hutang terlama"))
        belum = float(tua["belum_diajukan_rp"].sum())
        if belum > 0:
            porsi = belum / total
            hasil.append(_poin("hutang_tua_belum_pvr", _tingkat_porsi(porsi), porsi * 100,
                               {"nilai": belum, "porsi": porsi, "dokumen": _dok(tua[tua["belum_diajukan_rp"] > 0], "no_dok"), "batas": batas},
                               "Daftar hutang belum PVR terlama"))
        hasil.append(_penumpukan(h, "mitra", "sisa_rp", "hutang_supplier", "10 supplier dengan hutang terbesar"))
    if "tgl_pvr" in h:
        tahan = h[(h["status"] == "PVR pending") & (h["tgl_pvr"] <= pd.Timestamp(hari_ini) - pd.Timedelta(days=AMBANG["tertahan"]))]
        if not tahan.empty:
            nilai = float(tahan["dalam_pvr_rp"].sum())
            hasil.append(_poin("pvr_tertahan", "sedang", min(nilai / total * 100, 99) if total else 0,
                               {"dokumen": _dok(tahan, "no_dok"), "nilai": nilai, "hari": AMBANG["tertahan"]}, "Daftar hutang PVR pending terlama"))
    if "tgl_pv_depan" in h:
        kini = pd.Timestamp(hari_ini)
        segera = h[(h["tgl_pv_depan"] >= kini) & (h["tgl_pv_depan"] <= kini + pd.Timedelta(days=7))]
        nilai = float(segera["pv_depan_rp"].sum())
        if nilai > 0:
            hasil.append(_poin("pv_minggu_ini", "info", 50, {"nilai": nilai, "dokumen": _dok(segera, "no_dok")},
                               "Jadwal bayar per perusahaan"))
    p = df[df["jenis"] == "piutang"]
    tp = float(p["sisa_rp"].sum())
    if tp > 0:
        tua = p[p["umur"] > batas]
        nilai = float(tua["sisa_rp"].sum())
        if nilai > 0:
            porsi = nilai / tp
            hasil.append(_poin("piutang_tua", "sedang" if porsi >= 0.5 else "info", porsi * 50,
                               {"nilai": nilai, "total": tp, "porsi": porsi, "dokumen": _dok(tua, "no_dok"), "batas": batas}, "Piutang per customer"))
        per = p.groupby("mitra").agg(sisa=("sisa_rp", "sum"), umur=("umur", "max")).sort_values("sisa", ascending=False)
        if len(per) >= 3 and per["sisa"].iloc[0] / tp >= 0.3:
            hasil.append(_poin("piutang_satu", "info", 30, {"nama": str(per.index[0]), "nilai": float(per["sisa"].iloc[0]),
                                                           "porsi": float(per["sisa"].iloc[0] / tp)}, "Piutang per customer"))
        lama = per[(per["umur"] > AMBANG["umur_lama"] * 2) & (per["sisa"] >= 1e9)]
        if not lama.empty:
            hasil.append(_poin("piutang_lama_mitra", "tinggi", 60, {"nama": str(lama.index[0]), "nilai": float(lama["sisa"].iloc[0]),
                                                                   "umur": int(lama["umur"].iloc[0])}, "Daftar piutang terlama"))
    if total > 0:
        setahun = h[h["umur"] > 365]
        nilai = float(setahun["sisa_rp"].sum())
        if nilai >= 1e9:
            g = setahun.groupby("sumber")["sisa_rp"].agg(["sum", "size"]).sort_values("sum", ascending=False)
            hasil.append(_poin("hutang_setahun", "sedang", 40, {"nilai": nilai, "sumber": str(g.index[0]), "sumber_nilai": float(g["sum"].iloc[0]),
                                                               "sumber_dok": int(g["size"].iloc[0])}, "Daftar hutang terlama"))
    if total > 0 and tp > 0:
        def kunci(s):
            return s.fillna("").str.upper().str.replace(r"[^A-Z0-9 ]", "", regex=True).str.split().str.join(" ")
        dua = sorted(set(kunci(h.loc[h["sisa_rp"] > 0, "mitra"])) & set(kunci(p.loc[p["sisa_rp"] > 0, "mitra"])) - {""})
        if dua:
            hasil.append(_poin("mitra_dua_arah", "info", 20, {"jumlah": len(dua), "nama": dua[:3]}))
    return hasil


def _pr(df, hari_ini):
    hasil = []
    batas = AMBANG["umur_lama"]
    belum = df[df["status"] == "Belum PO"]
    if not belum.empty:
        n = _dok(belum, "prnumber")
        tua = belum[belum["umur"] > batas]
        nt = _dok(tua, "prnumber")
        porsi = nt / n
        hasil.append(_poin("pr_belum_po", _tingkat_porsi(porsi) if nt else "info", 50 + porsi * 100,
                           {"dokumen": n, "tua": nt, "porsi": porsi, "terlama": int(belum["umur"].max()), "batas": batas},
                           "Daftar PR belum PO terlama"))
        g = belum.drop_duplicates(["comp", "prnumber"]).assign(_n=1)
        hasil.append(_penumpukan(g, "category", "_n", "pr_belum_kategori", "PR yang belum PO per kategori", {"satuan": "PR"}))
    hasil.append(_tren(df, "po_date", "lama_po", hari_ini, "pr_lama_tren", "Lama PR jadi PO per bulan"))
    hasil.append(_lambat(df, "buyer", "lama_po", "pr_buyer_lambat", "Lama PR jadi PO per buyer", {"peran": "buyer"}))
    hasil.append(_banding_bulan(df, "pr_date", lambda d: _dok(d, "prnumber"), hari_ini, "pr_jumlah_bulan", "Jumlah PR per bulan",
                                {"satuan": "PR"}))
    return hasil


def _po(df, hari_ini):
    hasil = []
    batas = AMBANG["umur_lama"]
    belum = df[df["status"] == "Belum PI"]
    if not belum.empty:
        n = _dok(belum, "po_number")
        tua = belum[belum["umur"] > batas]
        nt = _dok(tua, "po_number")
        porsi = nt / n
        nilai_tua = float(tua.loc[tua["rupiah"], "total_po"].sum())
        hasil.append(_poin("po_belum_pi", _tingkat_porsi(porsi) if nt else "info", 50 + porsi * 100,
                           {"dokumen": n, "tua": nt, "porsi": porsi, "nilai": float(belum.loc[belum["rupiah"], "total_po"].sum()),
                            "nilai_tua": nilai_tua, "terlama": int(belum["umur"].max()), "batas": batas}, "Daftar PO belum PI terlama"))
    rp_po = df[df["rupiah"]]
    hasil.append(_penumpukan(rp_po, "supplier_name", "total_po", "po_supplier", "10 supplier dengan nilai PO terbesar", {"satuan": "rp"}))
    hasil.append(_banding_bulan(rp_po, "cd", lambda d: float(d["total_po"].sum()), hari_ini, "po_nilai_bulan",
                                "Nilai PO bulan ini dibanding bulan lalu", {"satuan": "rp"}))
    hasil.append(_tren(df, "pi_date", "lama_pi", hari_ini, "po_lama_tren", "Lama PO jadi PI per bulan"))
    hasil.append(_lambat(df, "supplier_name", "lama_pi", "po_supplier_lambat", "Lama PO jadi PI per supplier", {"peran": "supplier"}))
    return hasil


def _pi(df, hari_ini):
    hasil = []
    batas = AMBANG["umur_lama"]
    belum = df[df["status"] == "Belum PVR & PV"]
    if not belum.empty:
        n = _dok(belum, "pi_number")
        tua = belum[belum["umur"] > batas]
        nt = _dok(tua, "pi_number")
        porsi = nt / n
        hasil.append(_poin("pi_belum_pvr", _tingkat_porsi(porsi) if nt else "info", 50 + porsi * 100,
                           {"dokumen": n, "tua": nt, "porsi": porsi, "nilai": float(belum["line_total"].sum()),
                            "nilai_tua": float(tua["line_total"].sum()), "batas": batas}, "Daftar PI belum PVR terlama"))
    semua = _dok(df, "pi_number")
    tanpa = df[df["status"] == "PV tanpa PVR"]
    if semua and not tanpa.empty:
        nt = _dok(tanpa, "pi_number")
        porsi = nt / semua
        if porsi >= 0.05:
            pembuat = tanpa.drop_duplicates(["comp", "pi_number"])["pv_by"].fillna("").replace("", "(kosong)").value_counts()
            nilai = float(tanpa["line_total"].sum())
            dibayar = float(df.loc[df["status"].isin(["PV tanpa PVR", "PVR & PV"]), "line_total"].sum())
            porsi_nilai = nilai / dibayar if dibayar else 0
            hasil.append(_poin("pi_tanpa_pvr", "tinggi" if porsi_nilai >= 0.2 else "sedang" if porsi >= 0.1 else "info", 60 + porsi_nilai * 100,
                               {"dokumen": nt, "porsi": porsi, "nilai": nilai, "porsi_nilai": porsi_nilai, "pembuat": str(pembuat.index[0]),
                                "pembuat_dok": int(pembuat.iloc[0])},
                               "PI yang dibayar tanpa PVR per pembuat"))
    tahan = df[(df["status"] == "PVR, belum PV") & (df["pvr_date"] <= pd.Timestamp(hari_ini) - pd.Timedelta(days=AMBANG["tertahan"]))]
    if not tahan.empty:
        hasil.append(_poin("pi_pvr_tertahan", "sedang", 20, {"dokumen": _dok(tahan, "pi_number"), "nilai": float(tahan["line_total"].sum()),
                                                            "hari": AMBANG["tertahan"]}, "Daftar PI PVR belum PV terlama"))
    hasil.append(_tren(df, "pvr_dibuat", "lama_pvr", hari_ini, "pi_lama_tren", "Lama PI jadi PVR per bulan"))
    hasil.append(_lambat(df, "comp", "lama_pvr", "pi_pt_lambat", "Lama PI jadi PVR per perusahaan", {"peran": "perusahaan"}))
    return hasil


def _satu_pt(g, kode, tanya, data_lain=None):
    """Satu perusahaan memegang porsi besar dari yang outstanding. g: Series nilai per perusahaan."""
    g = g[g > 0].sort_values(ascending=False)
    if len(g) < 2:
        return None
    porsi = float(g.iloc[0]) / float(g.sum())
    if porsi < AMBANG["penumpukan"]:
        return None
    return _poin(kode, "info", porsi * 40, {"nama": str(g.index[0]), "nilai": float(g.iloc[0]), "porsi": porsi, **(data_lain or {})}, tanya)


def _pr_out(df, hari_ini):
    """Menu PR & PO Outstanding: hanya PR yang belum atau baru sebagian jadi PO."""
    hasil = [x for x in _pr(df, hari_ini) if x and x["kode"] in ("pr_belum_po", "pr_lama_tren")]
    out = df[df["status"].isin(["Belum PO", "PO sebagian"])]
    if out.empty:
        return hasil
    dok = out.groupby(["comp", "prnumber"]).agg(umur=("umur", "max"), setuju=("approve_date", lambda s: s.notna().any()),
                                                tgl=("pr_date", "min")).reset_index()
    n = len(dok)
    basi = dok[dok["umur"] > AMBANG["basi"]]
    if not basi.empty:
        porsi = len(basi) / n
        pt = basi["comp"].value_counts()
        bulan = pd.to_datetime(basi.loc[basi["comp"] == pt.index[0], "tgl"]).dt.month.value_counts()
        hasil = [x for x in hasil if x["kode"] != "pr_belum_po"]   # sudah tercakup, hindari dua poin yang mirip
        hasil.append(_poin("pr_out_basi", "tinggi" if porsi >= 0.25 else "sedang", 60 + porsi * 100,
                           {"dokumen": len(basi), "porsi": porsi, "batas": AMBANG["basi"], "median": float(dok["umur"].median()),
                            "rata": float(dok["umur"].mean()), "pt": str(pt.index[0]), "pt_n": int(pt.iloc[0]),
                            "bulan": [NAMA_BULAN[int(b) - 1] for b in bulan.index[:2]]}, "Daftar PR belum PO terlama"))
    belum_setuju = dok[~dok["setuju"]]
    if not belum_setuju.empty:
        hasil.append(_poin("pr_out_belum_setuju", "sedang", len(belum_setuju) / n * 50,
                           {"dokumen": len(belum_setuju), "porsi": len(belum_setuju) / n,
                            "terlama": int(belum_setuju["umur"].max())}, "Daftar PR belum PO terlama"))
    hasil.append(_satu_pt(dok.groupby("comp").size(), "pr_out_pt", "PR yang belum PO per perusahaan", {"satuan": "PR"}))
    sebagian = _dok(out[out["status"] == "PO sebagian"], "prnumber")
    if sebagian:
        hasil.append(_poin("pr_out_sebagian", "info", 5, {"dokumen": sebagian}, "Daftar PR PO sebagian"))
    return hasil


def _po_out(df, hari_ini):
    """Menu PO & PI Outstanding: hanya PO yang belum atau baru sebagian jadi PI."""
    hasil = [x for x in _po(df, hari_ini) if x and x["kode"] in ("po_belum_pi", "po_lama_tren", "po_supplier_lambat")]
    out = df[df["status"].isin(["Belum PI", "PI sebagian"])]
    if out.empty:
        return hasil
    out = out.assign(_sisa=out["qtyout"].clip(lower=0) * out["harga_po"])
    rp_out = out[out["rupiah"]]
    dok = out.groupby(["comp", "po_number"]).agg(umur=("umur", "max")).reset_index()
    basi = out[out["umur"] > AMBANG["basi"]]
    if not basi.empty:
        nb = _dok(basi, "po_number")
        porsi = nb / len(dok)
        hasil = [x for x in hasil if x["kode"] != "po_belum_pi"]
        hasil.append(_poin("po_out_basi", "tinggi" if porsi >= 0.25 else "sedang", 60 + porsi * 100,
                           {"dokumen": nb, "porsi": porsi, "nilai": float(basi.loc[basi["rupiah"], "_sisa"].sum()), "batas": AMBANG["basi"]},
                           "Daftar PO belum PI terlama"))
    sebagian = out[out["status"] == "PI sebagian"]
    if not sebagian.empty:
        hasil.append(_poin("po_out_sebagian", "info", 10, {"dokumen": _dok(sebagian, "po_number"),
                                                          "nilai": float(sebagian.loc[sebagian["rupiah"], "_sisa"].sum())}, "Daftar PO PI sebagian"))
    hasil.append(_penumpukan(rp_out, "supplier_name", "_sisa", "po_out_supplier", "PO yang belum PI per supplier", {"satuan": "rp"}))
    tua = out[out["umur"] > AMBANG["umur_lama"]].drop_duplicates(["comp", "po_number"])
    if len(tua) >= AMBANG["min_baris"]:
        g = tua["creator"].fillna("").replace("", "(kosong)").value_counts()
        porsi = float(g.iloc[0]) / len(tua)
        if porsi >= AMBANG["penumpukan"]:
            hasil.append(_poin("po_out_pembuat", "info", porsi * 30, {"nama": str(g.index[0]), "dokumen": int(g.iloc[0]), "porsi": porsi,
                                                                     "batas": AMBANG["umur_lama"]}, "PO yang belum PI per pembuat"))
    hasil.append(_satu_pt(rp_out.groupby("comp")["_sisa"].sum(), "po_out_pt", "PO yang belum PI per perusahaan", {"satuan": "rp"}))
    return hasil


CEK = {"outstanding": _outstanding, "pr": _pr, "po": _po, "pi": _pi}
CEK_MENU = {"pr_po": _pr_out, "po_pi": _po_out}      # menu outstanding memakai sumber yang sama dengan sudut pandang berbeda


# ---------- kalimat (terpisah dari hitungan) ----------

def _sebut_atas(atas, satuan):
    return ", ".join(f"{a['nama']} ({rp(a['nilai']) if satuan == 'rp' else _bil(a['nilai'])})" for a in atas)


def _kali(x):
    return f"{x:.1f}".replace(".", ",")


def _arah(ubah):
    return f"naik {_pct(abs(ubah))}" if ubah > 0 else f"turun {_pct(abs(ubah))}"


KALIMAT = {
    "hutang_tua": lambda d: f"{rp(d['nilai'])} ({_pct(d['porsi'])}) dari hutang {rp(d['total'])} sudah lebih dari {d['batas']} hari, "
                            f"tersebar di {_bil(d['dokumen'])} dokumen.",
    "hutang_tua_belum_pvr": lambda d: f"{rp(d['nilai'])} hutang yang sudah lebih dari {d['batas']} hari belum diajukan PVR sama sekali "
                                      f"({_bil(d['dokumen'])} dokumen).",
    "hutang_supplier": lambda d: f"3 supplier memegang {_pct(d['porsi'])} hutang: {_sebut_atas(d['atas'], 'rp')}.",
    "pvr_tertahan": lambda d: f"{_bil(d['dokumen'])} dokumen hutang sudah masuk PVR lebih dari {d['hari']} hari tapi belum dibayar, "
                              f"nilainya {rp(d['nilai'])}.",
    "pv_minggu_ini": lambda d: f"{rp(d['nilai'])} dijadwalkan dibayar lewat PV dalam 7 hari ke depan ({_bil(d['dokumen'])} dokumen).",
    "piutang_tua": lambda d: f"{rp(d['nilai'])} ({_pct(d['porsi'])}) piutang sudah lebih dari {d['batas']} hari belum diterima.",
    "pr_belum_po": lambda d: f"{_bil(d['dokumen'])} PR belum jadi PO, {_bil(d['tua'])} di antaranya sudah lebih dari {d['batas']} hari. "
                             f"Yang paling lama {_bil(d['terlama'])} hari." if d["tua"] else
                             f"{_bil(d['dokumen'])} PR belum jadi PO, semuanya masih di bawah {d['batas']} hari.",
    "pr_belum_kategori": lambda d: f"PR yang belum PO menumpuk di 3 kategori ({_pct(d['porsi'])}): {_sebut_atas(d['atas'], '')}.",
    "pr_lama_tren": lambda d: f"Lama PR jadi PO di {d['bulan']} rata-rata {fmt(d['kini'], 'hari')}, {_arah(d['ubah'])} "
                              f"dari rata-rata 3 bulan sebelumnya ({fmt(d['dulu'], 'hari')}).",
    "pr_buyer_lambat": lambda d: f"PR yang dipegang buyer {d['nama']} rata-rata {fmt(d['rata'], 'hari')} sampai jadi PO, "
                                 f"{_kali(d['kali'])} kali rata-rata semua buyer ({fmt(d['umum'], 'hari')}).",
    "pr_jumlah_bulan": lambda d: f"PR yang dibuat tanggal 1 sampai {d['hari']} bulan ini {_bil(d['kini'])}, {_arah(d['ubah'])} "
                                 f"dari periode yang sama bulan {d['bulan_lalu']} ({_bil(d['dulu'])}).",
    "po_belum_pi": lambda d: f"{_bil(d['dokumen'])} PO belum jadi PI senilai {rp(d['nilai'])}. {_bil(d['tua'])} di antaranya sudah lebih dari "
                             f"{d['batas']} hari ({rp(d['nilai_tua'])}), yang paling lama {_bil(d['terlama'])} hari." if d["tua"] else
                             f"{_bil(d['dokumen'])} PO belum jadi PI senilai {rp(d['nilai'])}, semuanya masih di bawah {d['batas']} hari.",
    "po_supplier": lambda d: f"3 supplier menerima {_pct(d['porsi'])} nilai PO tahun ini: {_sebut_atas(d['atas'], 'rp')}.",
    "po_nilai_bulan": lambda d: f"Nilai PO tanggal 1 sampai {d['hari']} bulan ini {rp(d['kini'])}, {_arah(d['ubah'])} dari periode yang sama "
                                f"bulan {d['bulan_lalu']} ({rp(d['dulu'])}).",
    "po_lama_tren": lambda d: f"Lama PO jadi PI di {d['bulan']} rata-rata {fmt(d['kini'], 'hari')}, {_arah(d['ubah'])} "
                              f"dari rata-rata 3 bulan sebelumnya ({fmt(d['dulu'], 'hari')}).",
    "po_supplier_lambat": lambda d: f"PO ke supplier {d['nama']} rata-rata {fmt(d['rata'], 'hari')} sampai jadi PI, "
                                    f"{_kali(d['kali'])} kali rata-rata semua supplier ({fmt(d['umum'], 'hari')}).",
    "pi_belum_pvr": lambda d: f"{_bil(d['dokumen'])} PI belum punya PVR maupun PV, nilainya {rp(d['nilai'])}. {_bil(d['tua'])} di antaranya "
                              f"sudah lebih dari {d['batas']} hari ({rp(d['nilai_tua'])})." if d["tua"] else
                              f"{_bil(d['dokumen'])} PI belum punya PVR maupun PV ({rp(d['nilai'])}), semuanya masih di bawah {d['batas']} hari.",
    "pi_tanpa_pvr": lambda d: f"{_bil(d['dokumen'])} PI senilai {rp(d['nilai'])} dibayar PV tanpa PVR, sekitar {_pct(d['porsi_nilai'])} dari nilai PI "
                              f"yang sudah dibayar. Paling banyak dibuat oleh {d['pembuat']} ({_bil(d['pembuat_dok'])} PI).",
    "piutang_satu": lambda d: f"{_pct(d['porsi'])} piutang ada di satu customer, {d['nama']} ({rp(d['nilai'])}).",
    "piutang_lama_mitra": lambda d: f"Piutang {d['nama']} {rp(d['nilai'])} dengan dokumen tertua {_bil(d['umur'])} hari.",
    "hutang_setahun": lambda d: f"Hutang lebih dari setahun {rp(d['nilai'])}, terbanyak dari {d['sumber']} ({rp(d['sumber_nilai'])}, "
                                f"{_bil(d['sumber_dok'])} dokumen).",
    "mitra_dua_arah": lambda d: f"{_bil(d['jumlah'])} mitra sekaligus punya hutang dan piutang, antara lain {', '.join(x.title() for x in d['nama'])}.",
    "pi_pvr_tertahan": lambda d: f"{_bil(d['dokumen'])} PI sudah punya PVR lebih dari {d['hari']} hari tapi belum dibayar PV "
                                 f"({rp(d['nilai'])}).",
    "pi_lama_tren": lambda d: f"Lama PI jadi PVR di {d['bulan']} rata-rata {fmt(d['kini'], 'hari')}, {_arah(d['ubah'])} "
                              f"dari rata-rata 3 bulan sebelumnya ({fmt(d['dulu'], 'hari')}).",
    "pi_pt_lambat": lambda d: f"PI di {d['nama']} rata-rata {fmt(d['rata'], 'hari')} sampai jadi PVR, "
                              f"{_kali(d['kali'])} kali rata-rata semua perusahaan ({fmt(d['umum'], 'hari')}).",
    "pr_out_basi": lambda d: (f"{_bil(d['dokumen'])} PR ({_pct(d['porsi'])}) sudah lebih dari {d['batas']} hari belum jadi PO"
                              + (f", {_bil(d['pt_n'])} di antaranya milik {d['pt']}"
                                 + (f" yang sebagian besar dibuat {' dan '.join(d['bulan'])}" if d.get("bulan") else "") if d.get("pt") and d["pt_n"] < d["dokumen"] else "")
                              + "."
                              + (f" Rata-rata umur {_bil(round(d['rata']))} hari terlihat tinggi karena PR lama ini, padahal separuh PR "
                                 f"outstanding umurnya di bawah {_bil(round(d['median']))} hari." if d.get("median") is not None
                                 and d["rata"] > d["median"] * 2 else "")),
    "pr_out_belum_setuju": lambda d: f"{_bil(d['dokumen'])} PR outstanding ({_pct(d['porsi'])}) belum disetujui, jadi Purchasing belum bisa "
                                     f"membuat PO. Yang paling lama menunggu {_bil(d['terlama'])} hari.",
    "pr_out_pt": lambda d: f"{_pct(d['porsi'])} PR yang belum PO ada di {d['nama']} ({_bil(d['nilai'])} PR).",
    "pr_out_sebagian": lambda d: f"{_bil(d['dokumen'])} PR baru sebagian jumlahnya dibuatkan PO, sisanya masih menunggu.",
    "po_out_basi": lambda d: f"{_bil(d['dokumen'])} PO yang belum atau baru sebagian jadi PI ({_pct(d['porsi'])}) sudah lebih dari {d['batas']} hari, sisa nilainya "
                             f"{rp(d['nilai'])}.",
    "po_out_sebagian": lambda d: f"{_bil(d['dokumen'])} PO baru sebagian ditagih (PI sebagian). Sisa barang yang belum di-PI senilai {rp(d['nilai'])}.",
    "po_out_supplier": lambda d: f"3 supplier memegang {_pct(d['porsi'])} sisa nilai PO yang belum PI: {_sebut_atas(d['atas'], 'rp')}.",
    "po_out_pembuat": lambda d: f"{_pct(d['porsi'])} PO yang belum PI lebih dari {d['batas']} hari dibuat oleh {d['nama']} "
                                f"({_bil(d['dokumen'])} PO).",
    "po_out_pt": lambda d: f"{_pct(d['porsi'])} sisa nilai PO yang belum PI ada di {d['nama']} ({rp(d['nilai'])}).",
}
LABEL_TINGKAT = {"tinggi": "Perlu tindakan", "sedang": "Perhatikan", "info": "Info"}


def hitung(sumber, df, perusahaan=None, hari_ini=None, menu=None, potong=True):
    """-> daftar insight terurut (paling penting dulu), sudah dengan kalimatnya."""
    hari_ini = hari_ini or date.today()
    if perusahaan:
        df = df[df["comp"].isin(perusahaan)]
    if df.empty:
        return []
    poin = [x for x in CEK_MENU.get(menu, CEK[sumber])(df, hari_ini) if x]
    for x in poin:
        x["teks"] = KALIMAT[x["kode"]](x["data"])
    return urutkan(poin) if potong else poin


def urutkan(poin):
    """Paling penting dulu, paling banyak MAKS_POIN, dengan label tingkatnya."""
    poin = sorted(poin, key=lambda x: -x["skor"])[:MAKS_POIN]
    for x in poin:
        x["label"] = LABEL_TINGKAT[x["tingkat"]]
    return poin
