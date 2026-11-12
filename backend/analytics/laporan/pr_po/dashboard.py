"""Grafik dan tabel detail laporan PR/PO.

Cross filter: ATAU dalam satu filter, DAN antarfilter; grafik sumber sebuah filter tetap menampilkan semua pilihannya. Minggu hanya satu.
"""
import pandas as pd

from inti import kecepatan
from inti.banding import bagi, jendela_sebelumnya, kpi_sebelumnya
from inti.filter import FilterTidakValid, kanonik as _kanonik, saring, tgl as _tgl
from inti.laporan import MINGGU_BAWAAN, minggu_rentang
from inti.tabel import periksa, susun
from inti.umur import URUTAN_UMUR

from . import ukuran as m

DIMENSI = {"perusahaan": "comp", "kategori": "category", "buyer": "buyer", "umur": "umur"}
KOLOM_CARI = ["prnumber", "itemcode", "itemname", "supplier_name", "po_number", "buyer", "category", "comp"]


def _saring(df, comp, kategori, buyer, lewati=None, umur=None):
    return saring(df, {"perusahaan": comp, "kategori": kategori, "buyer": buyer, "umur": umur}, DIMENSI, lewati)


def _periode(dari, sampai, minggu):
    """Minggu Jumat-Kamis di dalam rentang tampilan (dipotong ke rentang itu), serta awal dan akhir jendela hitung (satu minggu terpilih,
    atau seluruh rentang)."""
    daftar = minggu_rentang(dari, sampai)
    if minggu is not None and not (0 <= minggu < len(daftar)):
        raise FilterTidakValid(f"minggu harus antara 0 dan {len(daftar) - 1} (0 = minggu paling lama)")
    ws, we = daftar[minggu] if minggu is not None else (daftar[0][0], daftar[-1][1])
    return daftar, ws, we


def _pilihan(df):
    perusahaan = sorted(df["comp"].unique().tolist())
    buyers = urutan_buyer(df)
    kategori = sorted(df["category"].unique().tolist(), key=lambda k: (k == "(kosong)", k.lower()))
    umur = [u for u in URUTAN_UMUR if u in set(df["umur"])]
    return perusahaan, buyers, kategori, umur


def urutan_buyer(df):
    """Buyer diurutkan dari PO terbanyak (tanpa baris yang belum punya PO)."""
    ada = df[df["po_date"].notna() & (df["buyer"] != "(kosong)")]
    return ada.groupby("buyer")["line"].nunique().sort_values(ascending=False).index.tolist()


def _kpi_jendela(semua, ws, we):
    """Kartu yang bergantung pada jendela waktu (bisa dibandingkan dengan jendela sebelumnya)."""
    partial_y, partial_total, partial_pct = m.po_partial(semua, ws, we)
    return {
        "outstanding_awal": int(m.outstanding_awal(semua, ws)),
        "new_pr": int(m.new_pr(semua, ws, we)),
        "new_po": int(m.new_po(semua, ws, we)),                # jumlah PO (PR yang di-PO dua kali dihitung dua)
        "outstanding_akhir": int(m.outstanding_akhir(semua, we)),
        "completion_rate": float(m.completion_rate(semua, ws, we)),
        "po_partial": {"jumlah": int(partial_y), "dari": int(partial_total), "persen": float(partial_pct)},
    }


def bangun(data, dari, sampai, minggu=None, comp=None, kategori=None, buyer=None, umur=None, mulai_data=None):
    """data: seluruh baris yang dimuat, termasuk baris `lalu` untuk perbandingan."""
    df, lalu = bagi(data)
    daftar, ws, we = _periode(dari, sampai, minggu)
    label = [f"{s:%d/%m} - {e:%d/%m}" for s, e in daftar]
    perusahaan, buyers, daftar_kategori, daftar_umur = _pilihan(df)
    comp = _kanonik(comp, perusahaan, "perusahaan")
    buyer = _kanonik(buyer, buyers + ["(kosong)"], "buyer")
    kategori = _kanonik(kategori, daftar_kategori, "kategori")
    umur = _kanonik(umur, daftar_umur, "umur")

    # ---- Kartu ringkasan (semua filter berlaku) ----
    semua = _saring(df, comp, kategori, buyer, umur=umur)
    kpi = {**_kpi_jendela(semua, ws, we), "aging_rata_rata": round(m.aging_rata_rata(semua), 1), "aging_maks": float(m.aging_maks(semua))}
    ps, pe = jendela_sebelumnya(ws, we)
    kpi_lalu = kpi_sebelumnya(_kpi_jendela, semua, _saring(data, comp, kategori, buyer, umur=umur) if lalu is not None else semua,
                              lalu is not None, ps, pe, mulai_data, stok=("outstanding_awal", "outstanding_akhir"))
    banding = {"mulai": _tgl(ps), "akhir": _tgl(pe), "kpi": kpi_lalu} if kpi_lalu else None

    selesai = m.penyelesaian(semua)   # PR yang sudah selesai, untuk kartu dan grafik kecepatan

    # ---- Weekly summary (tanpa filter minggu) ----
    mingguan = []
    for i, (s, e) in enumerate(daftar):
        mingguan.append({
            "indeks": i,
            "mulai": _tgl(s),
            "akhir": _tgl(e),
            "label": label[i],
            "outstanding_awal": int(m.outstanding_awal(semua, s)),
            "new_pr": int(m.new_pr(semua, s, e)),
            "new_po": int(m.new_po(semua, s, e)),
            "outstanding_akhir": int(m.outstanding_akhir(semua, e)),
        })

    # ---- Grafik per kategori (filter kategori dilewati) ----
    dasar_kat = _saring(df, comp, kategori, buyer, lewati="kategori", umur=umur)
    kat_out, kat_pr, kat_po = [], [], []
    for nama, g in dasar_kat.groupby("category"):
        awal = int(m.outstanding_awal(g, ws))
        akhir = int(m.outstanding_akhir(g, we))
        if awal or akhir:
            kat_out.append({"kategori": nama, "outstanding_awal": awal, "outstanding_akhir": akhir})
        n_pr = int(m.new_pr(g, ws, we))
        n_po = int(m.new_po(g, ws, we))
        if n_pr:
            kat_pr.append({"kategori": nama, "jumlah": n_pr})
        if n_po:
            kat_po.append({"kategori": nama, "jumlah": n_po})
    kat_out.sort(key=lambda d: (-d["outstanding_akhir"], -d["outstanding_awal"]))
    kat_pr.sort(key=lambda d: -d["jumlah"])
    kat_po.sort(key=lambda d: -d["jumlah"])

    # ---- Garis per perusahaan (filter perusahaan dilewati) ----
    dasar_comp = _saring(df, comp, kategori, buyer, lewati="perusahaan", umur=umur)
    per_comp_pr, per_comp_po = [], []
    for c in perusahaan:
        g = dasar_comp[dasar_comp["comp"] == c]
        per_comp_pr.append({"nama": c, "nilai": [int(m.new_pr(g, s, e)) for s, e in daftar]})
        per_comp_po.append({"nama": c, "nilai": [int(m.new_po(g, s, e)) for s, e in daftar]})

    # ---- Garis per buyer (filter buyer dilewati), urut dari PO terbanyak ----
    # Hanya buyer yang membuat PO baru pada periode yang tampil (minggu terpilih, atau seluruh minggu yang ditampilkan).
    # Buyer yang sedang dipilih tetap ditampilkan supaya bisa dilepas.
    dasar_buyer = _saring(df, comp, kategori, buyer, lewati="buyer", umur=umur)
    per_buyer = []
    for b in buyers:
        g = dasar_buyer[dasar_buyer["buyer"] == b]
        if m.new_po(g, ws, we) > 0 or b in buyer:
            per_buyer.append({"nama": b, "nilai": [int(m.new_po(g, s, e)) for s, e in daftar]})
    tampil = [s["nama"] for s in per_buyer]

    return {
        "filter": {"minggu": minggu, "perusahaan": comp, "kategori": kategori, "buyer": buyer, "umur": umur},
        "periode": {"mulai": _tgl(ws), "akhir": _tgl(we), "jumlah_minggu": len(daftar)},
        "rentang": {"dari": _tgl(dari), "sampai": _tgl(sampai), "satuan": "minggu", "bawaan": MINGGU_BAWAAN},
        # buyer: yang tampil di menu dan grafik. buyer_semua: seluruh nama, urutan tetap (dipakai untuk warna yang stabil)
        "pilihan": {"perusahaan": perusahaan, "buyer": tampil, "buyer_semua": buyers, "kategori": daftar_kategori, "umur": daftar_umur},
        "kpi": kpi,
        "banding": banding,
        "mingguan": mingguan,
        "kecepatan": kecepatan.ringkas(selesai, ws, we),                    # PR dibuat sampai PO terakhir
        "kategori_outstanding": kat_out,
        "kategori_new_pr": kat_pr,
        "kategori_new_po": kat_po,
        "new_pr_per_perusahaan": per_comp_pr,
        "new_po_per_perusahaan": per_comp_po,
        "new_po_per_buyer": per_buyer,
    }


# Tabel detail: baris PR yang outstanding, dan baris PR yang sudah di-PO
# (kunci, judul, tipe). tipe: teks, tanggal, angka, campur (angka atau teks, mis. aging)
KOLOM_DETAIL = [
    ("prnumber", "PR Number", "teks"),
    ("comp", "Perusahaan", "teks"),
    ("pr_date", "Tgl PR", "tanggal"),
    ("aging", "Aging (hari)", "campur"),
    ("lama", "Lama selesai (hari)", "angka"),    # hanya terisi untuk PR yang sudah selesai
    ("approve_by", "Approve By", "teks"),
    ("approve_date", "Tgl Approve", "tanggal"),
    ("itemcode", "Kode Item", "teks"),
    ("itemname", "Nama Item", "teks"),
    ("category", "Kategori", "teks"),
    ("qtyreq", "Qty Req", "angka"),
    ("qtyorder", "Qty Order", "angka"),
    ("qtyout", "Qty Out", "angka"),
    ("uom", "Satuan", "teks"),
    ("itemtype", "Tipe Item", "teks"),
    ("supplier_code", "Kode Supplier", "teks"),
    ("supplier_name", "Supplier", "teks"),
    ("status", "Status", "teks"),
    ("buyer", "Buyer", "teks"),
    ("po_number", "No PO", "teks"),
    ("po_date", "Tgl PO", "tanggal"),
    ("harga_po", "Harga Satuan", "angka"),              # harga satuan di PO (mata uang PO), dari ERP
    ("total_po", "Total PO", "angka"),
    ("mata_uang_po", "Mata Uang", "teks"),
    ("partial", "Partial", "teks"),                 # hanya terisi di tab Sudah PO: Y kalau PR itu di-PO lebih dari satu nomor PO berbeda
]


_KOLOM_PO = ["po_number", "buyer", "supplier_code", "supplier_name", "po_date"]


JENIS_DETAIL = {
    "outstanding": "Outstanding akhir",
    "po": "Sudah PO",
}


def _gabung(seri):
    return ", ".join(dict.fromkeys(v for v in seri if v and v != "(kosong)"))


def _satu_baris_per_pr(sub):
    """Satu baris per baris PR. Kalau punya beberapa PO, nomor PO, buyer, dan supplier digabung."""
    sub = sub.sort_values(["line", "po_date"], kind="stable")
    dasar = sub.drop_duplicates("line", keep="first").set_index("line")
    g = sub.groupby("line")
    po = pd.DataFrame({
        "po_number": g["po_number"].agg(_gabung),
        "buyer": g["buyer"].agg(_gabung),
        "supplier_code": g["supplier_code"].agg(_gabung),
        "supplier_name": g["supplier_name"].agg(_gabung),
        "po_date": g["po_date"].max(),
    })
    if "harga_po" in sub:   # beberapa PO: total dijumlah, harga satuan hanya kalau sama
        po["total_po"] = g["total_po"].sum(min_count=1)
        po["harga_po"] = g["harga_po"].agg(lambda s: s.iloc[0] if s.dropna().nunique() == 1 else float("nan"))
        po["mata_uang_po"] = g["mata_uang_po"].agg(_gabung)
        dasar = dasar.drop(columns=["harga_po", "total_po", "mata_uang_po"])
    return dasar.drop(columns=_KOLOM_PO).join(po).reset_index()


def detail(data, jenis, dari, sampai, minggu=None, comp=None, kategori=None, buyer=None,
           cari=None, urut=None, arah=None, halaman=1, ukuran=50, umur=None):
    """Daftar baris PR untuk tabel detail.

    jenis 'outstanding': satu baris per baris PR yang dihitung di kartu Outstanding akhir (posisi di akhir jendela).
    jenis 'po'         : satu baris per PO yang dihitung di kartu New PO (PO dibuat dalam jendela). PR yang di-PO dua kali tampil dua baris;
                         PO dengan nomor dan tanggal sama satu baris. Kolom Partial = Y kalau PR itu di-PO lebih dari satu nomor PO berbeda.
    Jumlah baris (sebelum pencarian) sama dengan angka di kartu yang bersangkutan."""
    periksa(jenis, JENIS_DETAIL, urut, KOLOM_DETAIL, arah)
    df, _ = bagi(data)
    daftar, ws, we = _periode(dari, sampai, minggu)
    perusahaan, buyers, daftar_kategori, daftar_umur = _pilihan(df)
    comp = _kanonik(comp, perusahaan, "perusahaan")
    buyer = _kanonik(buyer, buyers + ["(kosong)"], "buyer")
    kategori = _kanonik(kategori, daftar_kategori, "kategori")
    umur = _kanonik(umur, daftar_umur, "umur")
    semua = _saring(df, comp, kategori, buyer, umur=umur)

    if jenis == "outstanding":
        pilih = semua[m.mask_outstanding_akhir(semua, we)]   # himpunan yang sama dengan kartu Outstanding akhir
        urut_awal, arah_awal = "aging", "desc"
    else:
        pilih = semua[m._mask_new_po(semua, ws, we)]      # himpunan yang sama dengan kartu New PO
        urut_awal, arah_awal = "po_date", "desc"

    if pilih.empty:
        t = pd.DataFrame(columns=[k for k, _, _ in KOLOM_DETAIL])
    elif jenis == "outstanding":
        t = _satu_baris_per_pr(pilih)           # satu baris per baris PR (Outstanding akhir menghitung baris PR)
        t["partial"] = None
    else:
        # Satu baris per PO (New PO menghitung PO): PR yang di-PO dua kali tampil dua baris. PO dengan nomor dan tanggal sama satu baris.
        t = pilih.drop_duplicates(["line", "po_number", "po_date"]).reset_index(drop=True)   # kolom partial sudah ada (sifat PR-nya)
    if not t.empty:
        t["lama"] = t["line"].map(m.penyelesaian(df)["lama"])   # dari seluruh baris PR itu, bukan hanya yang lolos filter
    for k, _, _ in KOLOM_DETAIL:   # data yang dimuat sebelum ada kolom harga: kolomnya kosong sampai dimuat ulang
        if k not in t:
            t[k] = None
    hasil = susun(t, KOLOM_DETAIL, KOLOM_CARI, cari, urut, arah, urut_awal, arah_awal, halaman, ukuran,
                  pembanding="pr_date" if jenis == "outstanding" else None)
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": _tgl(ws), "akhir": _tgl(we)}, **hasil}
