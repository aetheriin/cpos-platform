"""Laporan PI & GT: rumus KPI per periode (pola PO & PI), lead time, dan temuan.

Outstanding = baris barang yang perlu GT, sudah PI tapi belum di-GT pada suatu tanggal. Jumlah GT = dokumen GT (nomor unik), bukan baris barang.
"""
from inti import konfigurasi

AMBANG = konfigurasi.PIGT_AMBANG_HARI
MIN_GT_RUTE = 5     # rute dengan GT sesedikit ini tidak diangkat jadi temuan


def _hari(x):
    return f"{x:.1f}".replace(".", ",").removesuffix(",0")


def _durasi(seri):
    s = seri.dropna()
    return {"rata": float(s.mean()), "median": float(s.median()), "n": int(len(s))} if len(s) else {"rata": None, "median": None, "n": 0}


# ---------- Alur per periode. pi: baris yang punya PI. gt: baris GT (dengan atau tanpa PI). ----------

def mask_outstanding(pi, t, sebelum=False):
    """PI yang belum di-GT pada tanggal t (akhir hari t). sebelum=True: pada awal hari t (untuk outstanding awal)."""
    if sebelum:
        return (pi["pi_date"] < t) & (pi["gt_date"].isna() | (pi["gt_date"] >= t))
    return (pi["pi_date"] <= t) & (pi["gt_date"].isna() | (pi["gt_date"] > t))


def outstanding_awal(pi, mulai):
    return int(mask_outstanding(pi, mulai, sebelum=True).sum())


def outstanding_akhir(pi, akhir):
    return int(mask_outstanding(pi, akhir).sum())


def new_pi(pi, mulai, akhir):
    return int(((pi["pi_date"] >= mulai) & (pi["pi_date"] <= akhir)).sum())


def pi_di_gt(pi, mulai, akhir):
    """Barang PI yang di-GT dalam rentang."""
    return int(((pi["gt_date"] >= mulai) & (pi["gt_date"] <= akhir)).sum())


def gt_dalam(gt, mulai, akhir):
    return gt[(gt["gt_date"] >= mulai) & (gt["gt_date"] <= akhir)]


def new_gt(gt, mulai, akhir):
    """Dokumen GT yang dibuat dalam rentang."""
    return int(gt_dalam(gt, mulai, akhir)["gt_number"].nunique())


def mask_belum_diterima(gt, akhir):
    """GT yang sudah dibuat tapi belum diterima pada akhir hari `akhir`."""
    return (gt["gt_date"] <= akhir) & (gt["terima_date"].isna() | (gt["terima_date"] > akhir))


def kpi(pi, gt, mulai, akhir):
    """pi: baris PI (filter perusahaan dan importance). gt: baris GT (semua filter)."""
    dalam = gt_dalam(gt, mulai, akhir)
    out = pi[mask_outstanding(pi, akhir)]
    return {
        "outstanding_awal": outstanding_awal(pi, mulai),
        "new_pi": new_pi(pi, mulai, akhir),
        "new_gt": int(dalam["gt_number"].nunique()),
        "barang_gt": len(dalam),
        "outstanding_akhir": len(out),
        "outstanding_lama": int(((akhir - out["pi_date"]).dt.days > AMBANG).sum()),
        "aging_maks": int((akhir - out["pi_date"]).dt.days.max()) if len(out) else 0,
        "lead_pengadaan": _durasi(dalam["lead_pengadaan"]),
        "lead_logistik": _durasi(dalam["lead_logistik"]),
        "belum_diterima": int(gt.loc[mask_belum_diterima(gt, akhir), "gt_number"].nunique()),
    }


_NAMA_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def per_periode(pi, gt, daftar, tgl):
    """Satu baris per periode (bulan). singkat dan tahun: label sumbu grafik."""
    return [
        {
            "indeks": i, "mulai": tgl(s), "akhir": tgl(e), "label": f"{_NAMA_BULAN[s.month - 1]} {s.year}",
            "singkat": _NAMA_BULAN[s.month - 1], "tahun": str(s.year),
            "outstanding_awal": outstanding_awal(pi, s),
            "new_pi": new_pi(pi, s, e),
            # barang PI yang di-GT pada periode itu, supaya outstanding awal + New PI - New GT = outstanding akhir
            "new_gt": pi_di_gt(pi, s, e),
            "outstanding_akhir": outstanding_akhir(pi, e),
        }
        for i, (s, e) in enumerate(daftar)
    ]


def gt_per(gt, kolom, nama, daftar):
    """Dokumen GT per periode untuk tiap nilai `kolom` (urut dari GT terbanyak)."""
    hasil = []
    for n in nama:
        g = gt[gt[kolom] == n]
        hasil.append({"nama": n, "nilai": [new_gt(g, s, e) for s, e in daftar]})
    return hasil


def outstanding_per(pi, kolom, mulai, akhir):
    """Outstanding awal dan akhir per perusahaan (bentuk data grafik Kategori Outstanding)."""
    hasil = []
    for n, g in pi.groupby(kolom):
        awal, akh = outstanding_awal(g, mulai), outstanding_akhir(g, akhir)
        if awal or akh:
            hasil.append({"kategori": n, "outstanding_awal": awal, "outstanding_akhir": akh})
    return sorted(hasil, key=lambda d: (-d["outstanding_akhir"], -d["outstanding_awal"]))


def durasi_per(gt, kolom, nama):
    """Rata-rata dan median per kelompok, urut dari yang paling banyak GT-nya. kolom: str atau daftar kolom (digabung dengan " → ")."""
    if gt.empty:
        return []
    kunci = gt[kolom].agg(" → ".join, axis=1) if isinstance(kolom, list) else gt[kolom]
    hasil = []
    for k, sub in gt.groupby(kunci):
        d = _durasi(sub[nama])
        if d["n"]:
            hasil.append({"nama": k, **d, "gt": int(sub["gt_number"].nunique())})
    return sorted(hasil, key=lambda r: (-r["gt"], r["nama"]))


def temuan(gt, out, belum, akhir):
    """Kalimat singkat yang paling perlu diperhatikan. gt: GT dalam periode. out: outstanding akhir. belum: GT belum diterima pada akhir
    periode (sama dengan kartu). Urutan = kepentingan."""
    hasil = []
    dok = gt.drop_duplicates("gt_number")

    # 1. Rute paling lambat (Logistics Lead Time), dibanding rute lain
    rute = [r for r in durasi_per(gt, ["dari_gudang", "ke_gudang"], "lead_logistik") if r["gt"] >= MIN_GT_RUTE]
    if len(rute) >= 2:
        lambat = max(rute, key=lambda r: r["rata"])
        lain = gt[(gt["dari_gudang"] + " → " + gt["ke_gudang"]) != lambat["nama"]]["lead_logistik"].median()
        umumnya = "di hari yang sama" if lain < 1 else f"dalam {_hari(lain)} hari"
        hasil.append({"jenis": "rute", "rute": lambat["nama"].split(" → "),
                      "teks": f"Rute {lambat['nama']} paling lambat: rata-rata {_hari(lambat['rata'])} hari dari GT sampai diterima "
                              f"(nilai tengah {_hari(lambat['median'])} hari, {lambat['gt']} GT). Rute lain umumnya diterima {umumnya}."})

    # 2. GT yang belum diterima, dan yang paling lama
    belum = belum.drop_duplicates("gt_number")
    if len(belum):
        tua = belum.sort_values("gt_date").iloc[0]
        hasil.append({"jenis": "belum_diterima",
                      "teks": f"{len(belum)} GT belum diterima di gudang tujuan. Paling lama {tua['gt_number']} ke {tua['ke_gudang']}, "
                              f"sudah {(akhir - tua['gt_date']).days} hari."})

    # 3. PI yang tertahan belum di-GT
    lama = out[(akhir - out["pi_date"]).dt.days > AMBANG]
    if len(lama):
        per_pt = lama.groupby("comp").size().sort_values(ascending=False)
        hasil.append({"jenis": "outstanding",
                      "teks": f"{len(lama):,} barang sudah PI lebih dari {AMBANG} hari tapi belum dibuatkan GT; terbanyak di {per_pt.index[0]} ({per_pt.iloc[0]:,}).".replace(",", ".")})

    # 4. Ketergantungan pada satu pembuat
    if dok["gt_by"].nunique() >= 2:
        per_org = dok["gt_by"].value_counts()
        porsi = per_org.iloc[0] / per_org.sum()
        if porsi >= 0.5:
            hasil.append({"jenis": "pembuat",
                          "teks": f"{per_org.index[0]} membuat {porsi:.0%} dari GT periode ini ({per_org.iloc[0]:,} dari {per_org.sum():,}).".replace(",", ".")})
    return hasil
