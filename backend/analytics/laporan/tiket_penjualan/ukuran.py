"""Laporan Tiket Penjualan: kartu, peringkat, dan sebaran waktu. Satu tiket = satu rit."""
import pandas as pd


def kpi(d):
    netto = float(d["netto"].sum())
    rit = int(len(d))
    return {
        "netto": round(netto, 2),
        "rit": rit,
        "per_rit": round(netto / rit, 2) if rit else None,
        "pengangkut": int(d.loc[d["pengangkut"] != "", "pengangkut"].nunique()),
        "pembeli": int(d.loc[d["pembeli"] != "", "pembeli"].nunique()),
        "produk": int(d["produk"].nunique()),
    }


def peringkat(d, kolom, n, terpilih=()):
    """Netto dan rit per nilai kolom, netto terbesar dulu. n baris teratas (yang dipilih tetap ikut); sisanya diringkas di `lainnya`.
    Nilai kosong tidak masuk peringkat. Persen terhadap netto semua baris `d`."""
    total = float(d["netto"].sum())
    g = d[d[kolom] != ""].groupby(kolom).agg(netto=("netto", "sum"), rit=("netto", "size")).sort_values(["netto", "rit"], ascending=False, kind="stable")
    atas = g.head(n)
    atas = pd.concat([atas, g[g.index.isin(terpilih) & ~g.index.isin(atas.index)]])
    sisa = g[~g.index.isin(atas.index)]
    baris = [{"nama": k, "netto": round(float(r["netto"]), 2), "rit": int(r["rit"]),
              "persen": round(float(r["netto"]) / total, 4) if total else 0} for k, r in atas.iterrows()]
    lainnya = {"jumlah": int(len(sisa)), "netto": round(float(sisa["netto"].sum()), 2), "rit": int(sisa["rit"].sum())} if len(sisa) else None
    return {"data": baris, "jumlah": int(len(g)), "lainnya": lainnya}


def per_jam(d):
    """Netto dan rit per jam keluar timbangan, 00 sampai 23."""
    g = d[d["jam"] != ""].groupby("jam").agg(netto=("netto", "sum"), rit=("netto", "size"))
    return [{"kunci": f"{j:02d}", "netto": round(float(g["netto"].get(f"{j:02d}", 0)), 2), "rit": int(g["rit"].get(f"{j:02d}", 0))}
            for j in range(24)]


def per_hari(d, dari, sampai):
    """Netto dan rit per tanggal dari `dari` sampai `sampai`; hari tanpa tiket bernilai nol."""
    hari = pd.date_range(pd.Timestamp(dari), pd.Timestamp(sampai), freq="D")
    g = d.groupby("hari").agg(netto=("netto", "sum"), rit=("netto", "size"))
    return [{"kunci": h.strftime("%Y-%m-%d"), "netto": round(float(g["netto"].get(h.strftime("%Y-%m-%d"), 0)), 2),
             "rit": int(g["rit"].get(h.strftime("%Y-%m-%d"), 0))} for h in hari]
