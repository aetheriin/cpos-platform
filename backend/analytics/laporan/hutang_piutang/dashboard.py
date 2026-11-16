"""Laporan Outstanding: kartu ringkas dan tabel hutang (per dokumen, per supplier), piutang (per dokumen, per customer), serta PR dan
PO yang masih outstanding (per item). Nilai hutang/piutang dalam rupiah; rentang tampilan memakai tanggal dokumen."""
import re

import pandas as pd

from inti.filter import FilterTidakValid, kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import nilai, periksa, susun
from inti.umur import URUTAN_KELOMPOK_UMUR as URUTAN_AGING, kelompok_umur
from .sumber import BELUM_RV, RV_SEBAGIAN, URUTAN_STATUS, ambil_rincian

DIM = {"perusahaan": "comp", "sumber": "sumber", "status": "status", "kategori": "kategori", "aging": "aging"}
# Filter yang berlaku untuk tiap kelompok tabel; perusahaan dan aging untuk semua
DIM_ARAP = ("perusahaan", "sumber", "status", "aging")
DIM_PENGADAAN = ("perusahaan", "kategori", "aging")


def _aging(df):
    """Kolom & filter Aging: Tepat Waktu / Perlu Perhatian / Telat / Perlu Tindakan (inti/umur.py), sama dengan laporan Reports lain."""
    return [kelompok_umur(u) for u in df["umur"]]


JENIS_DETAIL = {"hutang": "Hutang per dokumen", "supplier": "Hutang per supplier", "piutang": "Piutang per dokumen", "customer": "Piutang per customer",
                "pr": "PR outstanding", "po": "PO outstanding", "po_supplier": "PO outstanding per supplier"}
ARAP = ("hutang", "piutang")

_KURS = [("mata_uang", "Mata Uang", "teks"), ("kurs", "Kurs", "angka"), ("sumber_kurs", "Sumber Kurs", "teks")]
# Urutan kolom: siapa dan dokumen apa, umur dan status, lalu Sisa (angka yang paling dicari) dan rinciannya, lalu nomor tindak lanjut,
# terakhir kurs untuk dokumen valas.
KOLOM = {
    "hutang": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Supplier", "teks"), ("no_dok", "No. Dokumen", "teks"), ("sumber", "Sumber", "teks"),
        ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"), ("status", "Status", "teks"),
        ("sisa_rp", "Sisa", "angka"), ("nilai_rp", "Nilai", "angka"), ("sudah_bayar_rp", "Sudah PV", "angka"),
        ("dalam_pvr_rp", "Sudah Diajukan PVR", "angka"), ("pv_depan_rp", "PV Belum Jatuh Tempo", "angka"), ("belum_diajukan_rp", "Belum Diajukan", "angka"),
        ("no_pvr", "No. PVR", "teks"), ("tgl_pvr", "Tanggal PVR", "tanggal"), ("approve_pvr", "Approve PVR", "teks"),
        ("nilai_pvr", "Nilai PVR Setelah Potongan", "angka"),
        ("no_pv_depan", "No. PV Belum Jatuh Tempo", "teks"), ("tgl_pv_depan", "Tanggal PV", "tanggal"), ("no_bayar", "No. PV", "teks"),
    ] + _KURS,
    "supplier": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Supplier", "teks"), ("sisa", "Sisa Bersih", "angka"), ("dokumen", "Dokumen", "angka"),
        ("tagihan", "Tagihan", "angka"), ("potongan", "Potongan", "angka"),
        ("dalam_pvr", "Sudah Diajukan PVR", "angka"), ("pv_depan", "PV Belum Jatuh Tempo", "angka"), ("belum_diajukan", "Belum Diajukan", "angka"),
        ("tertua", "Dokumen Tertua", "tanggal"), ("umur", "Umur (hari)", "angka"), ("sumber", "Sumber Tagihan", "teks"), ("mata_uang", "Mata Uang", "teks"),
    ],
    "piutang": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Customer", "teks"), ("no_dok", "No. Dokumen", "teks"), ("sumber", "Sumber", "teks"),
        ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"), ("status", "Status", "teks"),
        ("sisa_rp", "Sisa", "angka"), ("nilai_rp", "Nilai", "angka"), ("sudah_bayar_rp", "Sudah RV", "angka"),
        ("no_do", "No. DO", "teks"), ("no_kontrak", "No. Kontrak", "teks"), ("no_tc", "No. TC", "teks"), ("no_bayar", "No. RV", "teks"),
        ("keterangan", "Keterangan", "teks"),
    ] + _KURS,
    "customer": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Customer", "teks"), ("sisa", "Sisa", "angka"), ("dokumen", "Dokumen", "angka"),
        ("nilai", "Nilai", "angka"), ("sudah_bayar", "Sudah RV", "angka"),
        ("tertua", "Dokumen Tertua", "tanggal"), ("umur", "Umur (hari)", "angka"), ("sumber", "Sumber", "teks"), ("mata_uang", "Mata Uang", "teks"),
    ],
    # PR dan PO: identitas dokumen, lalu barang dan sisanya, lalu tindak lanjut (PO/PI dan supplier), terakhir orang
    "pr": [
        ("comp", "Perusahaan", "teks"), ("no_dok", "No. PR", "teks"), ("tgl", "Tanggal PR", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"),
        ("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"),
        ("qty_minta", "Qty Diminta", "angka"), ("qty_proses", "Qty Sudah PO", "angka"), ("qty_sisa", "Qty Outstanding", "angka"),
        ("no_lanjut", "No. PO", "teks"), ("mitra", "Supplier", "teks"), ("kategori", "Kategori", "teks"),
        ("dibuat_oleh", "Dibuat Oleh", "teks"), ("approve_oleh", "Approve Oleh", "teks"),
    ],
    "po": [
        ("comp", "Perusahaan", "teks"), ("no_dok", "No. PO", "teks"), ("tgl", "Tanggal PO", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"),
        ("mitra", "Supplier", "teks"), ("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"),
        ("qty_minta", "Qty Order", "angka"), ("qty_proses", "Qty Diterima", "angka"), ("qty_sisa", "Qty Outstanding", "angka"),
        ("harga_po", "Harga Satuan", "angka"), ("nilai_sisa", "Nilai Outstanding", "angka"), ("mata_uang_po", "Mata Uang", "teks"),
        ("no_lanjut", "No. PI", "teks"), ("kategori", "Kategori", "teks"), ("dibuat_oleh", "Dibuat Oleh", "teks"),
    ],
    # Nilai hanya dijumlahkan kalau semua PO supplier itu satu mata uang (kolom Mata Uang menunjukkannya)
    "po_supplier": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Supplier", "teks"), ("po", "PO", "angka"), ("item", "Item", "angka"),
        ("nilai_sisa", "Nilai Outstanding", "angka"), ("mata_uang", "Mata Uang", "teks"), ("tertua", "PO Tertua", "tanggal"),
        ("umur", "Umur (hari)", "angka"), ("kategori", "Kategori", "teks"),
    ],
}
KOLOM_CARI = {
    "hutang": ["comp", "mitra", "sumber", "no_dok", "status", "no_pvr", "no_pv_depan", "no_bayar"],
    "supplier": ["comp", "mitra", "sumber"],
    "piutang": ["comp", "mitra", "sumber", "no_dok", "no_do", "no_kontrak", "no_tc", "no_bayar", "keterangan"],
    "customer": ["comp", "mitra", "sumber"],
    "pr": ["comp", "no_dok", "kode_barang", "nama_barang", "no_lanjut", "mitra", "kategori", "dibuat_oleh"],
    "po": ["comp", "no_dok", "mitra", "kode_barang", "nama_barang", "no_lanjut", "kategori", "dibuat_oleh"],
    "po_supplier": ["comp", "mitra", "kategori"],
}
URUT_AWAL = {"hutang": ("umur", "desc"), "supplier": ("sisa", "desc"), "piutang": ("umur", "desc"), "customer": ("sisa", "desc"),
             "pr": ("umur", "desc"), "po": ("umur", "desc"), "po_supplier": ("umur", "desc")}


def _gabung(nilai):
    return ", ".join(sorted({v for v in nilai if v}))


def _saring(df, ds, filt):
    dari, sampai = rentang_tampil(ds)
    if getattr(ds, "dari", None) is None and len(df):   # data selalu semua riwayat; tanpa filter tanggal, dokumen lama tetap tampil
        dari = min(dari, df["tgl"].min())
    df = df.assign(aging=_aging(df))
    arap = df["jenis"].isin(ARAP)
    ada = lambda kolom, bagian: set(df.loc[bagian, kolom].dropna()) - {""}
    pilihan = {
        "perusahaan": sorted(df["comp"].unique()),
        "sumber": sorted(ada("sumber", arap), key=str.casefold),
        "status": [s for s in [*URUTAN_STATUS, BELUM_RV, RV_SEBAGIAN] if s in ada("status", arap)],
        "kategori": sorted(ada("kategori", ~arap), key=str.casefold),
        "aging": [u for u in URUTAN_AGING if u in set(df["aging"])],
    }
    judul = {"perusahaan": "Perusahaan", "sumber": "Sumber", "status": "Status", "kategori": "Kategori", "aging": "Aging"}
    filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul[k]) for k in DIM}
    d = df[(df["tgl"] >= dari) & (df["tgl"] <= sampai)]
    # tiap filter hanya menyaring kelompok tabel yang punya kolomnya
    d_arap = saring(d[d["jenis"].isin(ARAP)], {k: filt[k] for k in DIM_ARAP}, {k: DIM[k] for k in DIM_ARAP})
    d_pp = saring(d[~d["jenis"].isin(ARAP)], {k: filt[k] for k in DIM_PENGADAAN}, {k: DIM[k] for k in DIM_PENGADAAN})
    return pd.concat([d_arap, d_pp]), dari, sampai, pilihan


def rekap(d, jenis):
    """Satu baris per perusahaan dan mitra. Hutang: potongan mengurangi tagihan."""
    if d.empty:
        return pd.DataFrame(columns=[k for k, _, _ in KOLOM[jenis]])
    g = d.assign(tagihan=d["sisa_rp"].clip(lower=0), potongan=-d["sisa_rp"].clip(upper=0),
                 sumber_tagihan=d["sumber"].where(d["sisa_rp"] > 0, "")).groupby(["comp", "mitra"], as_index=False)
    hasil = g.agg(dokumen=("no_dok", "size"), tagihan=("tagihan", "sum"), potongan=("potongan", "sum"), sisa=("sisa_rp", "sum"),
                  nilai=("nilai_rp", "sum"), sudah_bayar=("sudah_bayar_rp", "sum"), dalam_pvr=("dalam_pvr_rp", "sum"),
                  pv_depan=("pv_depan_rp", "sum"), belum_diajukan=("belum_diajukan_rp", "sum"), tertua=("tgl", "min"), umur=("umur", "max"),
                  mata_uang=("mata_uang", _gabung), sumber=("sumber_tagihan" if jenis == "supplier" else "sumber", _gabung))
    return hasil


def rekap_po(t):
    """Satu baris per perusahaan dan supplier dari item PO outstanding."""
    if t.empty:
        return pd.DataFrame(columns=[k for k, _, _ in KOLOM["po_supplier"]])
    t = t.assign(mata_uang_po=t["mata_uang_po"].fillna("").astype(str), kategori=t["kategori"].fillna("").astype(str))
    g = t.groupby(["comp", "mitra"], as_index=False).agg(
        po=("no_dok", "nunique"), item=("no_dok", "size"), nilai_sisa=("nilai_sisa", "sum"), mata_uang=("mata_uang_po", _gabung),
        tertua=("tgl", "min"), umur=("umur", "max"), kategori=("kategori", _gabung))
    g.loc[g["mata_uang"].str.contains(","), "nilai_sisa"] = None
    return g


def kpi(d):
    h, p = d[d["jenis"] == "hutang"], d[d["jenis"] == "piutang"]
    sup = h.groupby(["comp", "mitra"])["sisa_rp"].sum()
    cus = p.groupby(["comp", "mitra"])["sisa_rp"].sum()
    return {
        "hutang": float(h["sisa_rp"].sum()), "hutang_dok": int(len(h)),
        "potongan": float(-h["sisa_rp"].clip(upper=0).sum()),
        "supplier": int((sup > 0.5).sum()), "supplier_teratas": (sup.idxmax()[1] if len(sup) else None),
        "supplier_teratas_nilai": float(sup.max()) if len(sup) else 0.0,
        "piutang": float(p["sisa_rp"].sum()), "piutang_dok": int(len(p)),
        "customer": int((cus > 0.5).sum()), "customer_teratas": (cus.idxmax()[1] if len(cus) else None),
        "customer_teratas_nilai": float(cus.max()) if len(cus) else 0.0,
        "dalam_pvr": float(h["dalam_pvr_rp"].sum()), "pv_depan": float(h["pv_depan_rp"].sum()),
        "tanpa_kurs": int(d["tanpa_kurs"].fillna(False).astype(bool).sum()) if "tanpa_kurs" in d else 0,
        **_kpi_pengadaan(d, "pr"), **_kpi_pengadaan(d, "po"), **_kpi_supplier_po(d),
    }


def _kpi_supplier_po(d):
    """Supplier dengan PO outstanding, dan yang PO-nya paling banyak."""
    po = d[d["jenis"] == "po"].groupby(["comp", "mitra"])["no_dok"].nunique()
    return {"po_supplier": int(len(po)), "po_supplier_teratas": po.idxmax()[1] if len(po) else None,
            "po_supplier_teratas_po": int(po.max()) if len(po) else 0}


def _kpi_pengadaan(d, jenis):
    t = d[d["jenis"] == jenis]
    umur = t.groupby(["comp", "no_dok"])["umur"].max()
    return {f"{jenis}_dok": int(len(umur)), f"{jenis}_item": int(len(t)), f"{jenis}_lama": int((umur > 30).sum()),
            f"{jenis}_umur_maks": int(umur.max()) if len(umur) else None}


def _tabel(d, jenis):
    if jenis in ("hutang", "piutang", "pr", "po"):
        return d[d["jenis"] == jenis]
    if jenis == "po_supplier":
        return rekap_po(d[d["jenis"] == "po"])
    return rekap(d[d["jenis"] == ("hutang" if jenis == "supplier" else "piutang")], jenis)


def bangun(df, ds, filt=None):
    d, dari, sampai, pilihan = _saring(df, ds, filt)
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        # isian filter Tanggal tetap di dalam data yang dimuat; dokumen lama sebelum itu tetap ikut selama filter Tanggal tidak dipakai
        "rentang": {"dari": tgl(max(dari, pd.Timestamp(ds.mulai))), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "kpi": kpi(d),
        "jumlah": {j: int(len(_tabel(d, j))) for j in JENIS_DETAIL},
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    periksa(jenis, JENIS_DETAIL, urut, KOLOM.get(jenis, []), arah)
    d, dari, sampai, _ = _saring(df, ds, filt)
    t = _tabel(d, jenis).reset_index(drop=True)
    urut_awal, arah_awal = URUT_AWAL[jenis]
    hasil = susun(t, KOLOM[jenis], KOLOM_CARI[jenis], cari, urut, arah, urut_awal, arah_awal, halaman, ukuran, pembanding="mitra")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}


# Jendela rincian (klik ganda baris tabel). Semua isi diambil dari data yang sudah dimuat, tanpa query baru.
_RINCI_HUTANG = [
    ("Dokumen", [("sumber", "Sumber", "teks"), ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"),
                 ("aging", "Aging", "teks"), ("status", "Status", "teks"), ("keterangan", "Keterangan", "teks")]),
    ("Nilai", [("nilai_rp", "Nilai", "angka"), ("sudah_bayar_rp", "Sudah PV", "angka"), ("sisa_rp", "Sisa", "angka"),
               ("pv_depan_rp", "PV belum jatuh tempo", "angka"), ("belum_diajukan_rp", "Belum diajukan", "angka")]),
    # Nilai PVR adalah total satu PVR (bisa berisi banyak dokumen); bagian dokumen ini ada di "Dokumen ini di PVR"
    ("PVR", [("no_pvr", "No. PVR", "teks"), ("tgl_pvr", "Tanggal PVR", "tanggal"), ("approve_pvr", "Approve", "teks"),
             ("dalam_pvr_rp", "Dokumen ini di PVR", "angka"), ("tagihan_pvr", "Total semua tagihan di PVR", "angka"),
             ("potongan_pvr", "Total potongan di PVR", "angka"), ("nilai_pvr", "Total PVR setelah potongan", "angka")]),
    ("PV", [("no_bayar", "No. PV", "teks"), ("no_pv_depan", "No. PV belum jatuh tempo", "teks"), ("tgl_pv_depan", "Tanggal PV itu", "tanggal")]),
    ("Kurs", [("mata_uang", "Mata uang", "teks"), ("kurs", "Kurs", "angka"), ("sumber_kurs", "Sumber kurs", "teks")]),
]
_RINCI_PIUTANG = [
    ("Dokumen", [("sumber", "Sumber", "teks"), ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"),
                 ("aging", "Aging", "teks"), ("status", "Status", "teks"), ("keterangan", "Keterangan", "teks")]),
    ("Nilai", [("nilai_rp", "Nilai", "angka"), ("sudah_bayar_rp", "Sudah RV", "angka"), ("sisa_rp", "Sisa", "angka")]),
    ("Dokumen terkait", [("no_do", "No. DO", "teks"), ("no_kontrak", "No. Kontrak", "teks"), ("no_tc", "No. TC", "teks"), ("no_bayar", "No. RV", "teks")]),
    ("Kurs", [("mata_uang", "Mata uang", "teks"), ("kurs", "Kurs", "angka"), ("sumber_kurs", "Sumber kurs", "teks")]),
]
_RINCI_PENGADAAN = {
    "po": [("Dokumen", [("tgl", "Tanggal PO", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"),
                        ("mitra", "Supplier", "teks"), ("kategori", "Kategori", "teks"), ("mata_uang_po", "Mata uang", "teks"), ("dibuat_oleh", "Dibuat oleh", "teks")])],
    "pr": [("Dokumen", [("tgl", "Tanggal PR", "tanggal"), ("umur", "Umur (hari)", "angka"), ("aging", "Aging", "teks"),
                        ("kategori", "Kategori", "teks"), ("dibuat_oleh", "Dibuat oleh", "teks"), ("approve_oleh", "Approve oleh", "teks")])],
}
_KOLOM_ITEM = {
    "po": [("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"), ("qty_minta", "Qty Order", "angka"),
           ("qty_proses", "Qty Diterima", "angka"), ("qty_sisa", "Qty Outstanding", "angka"), ("harga_po", "Harga Satuan", "angka"),
           ("nilai_sisa", "Nilai Outstanding", "angka"), ("no_lanjut", "No. PI", "teks")],
    "pr": [("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"), ("qty_minta", "Qty Diminta", "angka"),
           ("qty_proses", "Qty Sudah PO", "angka"), ("qty_sisa", "Qty Outstanding", "angka"), ("no_lanjut", "No. PO", "teks"), ("mitra", "Supplier", "teks")],
}
# Daftar dokumen satu supplier/customer: kolom tabel per dokumen tanpa perusahaan dan mitra (sudah di judul)
_KOLOM_DOK = {j: [k for k in KOLOM[j] if k[0] not in ("comp", "mitra")][:11] for j in ARAP}
_KOLOM_DOK["piutang"].append(("keterangan", "Keterangan", "teks"))


def _isian(r, bagian):
    hasil = []
    for judul, kolom in bagian:
        isi = [{"label": lbl, "nilai": (_bermakna(r.get(k)) or None) if k == "keterangan" else nilai(r.get(k), tp), "tipe": tp}
               for k, lbl, tp in kolom if k in r]
        isi = [i for i in isi if i["nilai"] not in (None, 0)]
        if isi:
            hasil.append({"judul": judul, "isian": isi})
    return hasil


_KOLOM_BAYAR = [("jenis", "Jenis", "teks"), ("no", "No. Voucher", "teks"), ("tgl", "Tanggal", "tanggal"), ("nilai", "Nilai", "angka"),
                ("status", "Status", "teks"), ("ket", "Keterangan", "teks")]
_KOLOM_BARANG = [("kode", "Kode Barang", "teks"), ("nama", "Nama Barang", "teks"), ("qty", "Qty", "angka"), ("harga", "Harga Satuan", "angka"),
                 ("nilai", "Jumlah", "angka"), ("no_po", "No. PO", "teks"), ("no_pr", "No. PR", "teks"), ("tgl_pr", "Tanggal PR", "tanggal"),
                 ("pembuat_pr", "PR Dibuat Oleh", "teks"), ("ket", "Keterangan", "teks")]
_ASAL = {"NoPO": "no_po", "NoPR": "no_pr", "TglPR": "tgl_pr", "PembuatPR": "pembuat_pr"}
_SAMPAH = re.compile(r"^[\W_0]*$")   # "-", ".", "0", "--" dan sejenisnya bukan keterangan


def _bermakna(teks):
    t = "" if teks is None or (not isinstance(teks, str) and pd.isna(teks)) else str(teks).strip()
    return t if len(t) >= 3 and not _SAMPAH.match(t) else ""


def _gabung_ket(r, kolom):
    """Keterangan dari beberapa kolom jadi satu; yang kosong, asal isi, atau sama persis (abaikan besar kecil huruf) hanya sekali."""
    hasil, lihat = [], set()
    for k in kolom:
        t = _bermakna(r.get(k))
        if t and t.casefold() not in lihat:
            lihat.add(t.casefold())
            hasil.append(t)
    return " · ".join(hasil) or None


def _dari_erp(r, jenis):
    """Bagian dan tabel tambahan dari SP rincian: info dokumen, PVR/PV/RV, dan baris barang PI. Catatan kalau SP belum ada."""
    try:
        e = ambil_rincian(r["comp"], r["kode"], r["no_dok"])
    except Exception as ex:   # rincian dasar tetap tampil walau ERP sedang tidak bisa dibaca
        return [], [], f"Rincian dari ERP belum bisa dibaca: {ex}"
    if e is None:
        return [], [], "Rincian PVR, PV, dan barang belum tersedia: SP rincian belum dibuat di database."
    e = e.sort_values(["Bagian", "Urut"])
    info = e[e["Bagian"] == "info"]
    isian = [{"label": x.Nama, "nilai": _bermakna(x.Ket), "tipe": "teks"} for x in info.itertuples() if _bermakna(x.Ket)]
    bagian = [{"judul": "Dari dokumen", "isian": isian}] if isian else []
    tabel = []
    bayar = e[e["Bagian"] == "bayar"].rename(columns={"Nama": "jenis", "No": "no", "Tgl": "tgl", "Nilai": "nilai", "Status": "status"})
    bayar = bayar.assign(ket=[_gabung_ket(r, ["Ket"]) for r in bayar.to_dict("records")])
    nama_bayar = "PVR dan PV" if jenis == "hutang" else "RV"
    tabel.append(_tabel_rinci(bayar, _KOLOM_BAYAR, f"{nama_bayar} yang memuat dokumen ini"))
    item = e[e["Bagian"] == "item"].rename(columns={"No": "kode", "Nama": "nama", "Qty": "qty", "Harga": "harga", "Nilai": "nilai", **_ASAL})
    item = item.assign(ket=[_gabung_ket(r, ["Ket", "PerluPR", "KetPR", "KetPO"]) for r in item.to_dict("records")])
    if len(item):
        tabel.append(_tabel_rinci(item, _KOLOM_BARANG, "Barang"))
    return bagian, tabel, None


def _asal_pr(t, comp, kode, no):
    """Tempel No. PR, tanggal, dan pembuatnya ke item PO (dicocokkan per No. PO dan kode barang). (t, berhasil, catatan)."""
    try:
        e = ambil_rincian(comp, kode, no)
    except Exception as ex:
        return t, False, f"Asal PR belum bisa dibaca dari ERP: {ex}"
    if e is None:
        return t, False, "Asal PR belum tersedia: SP rincian belum dibuat di database."
    asal = e[e["Bagian"] == "item"].rename(columns={"No": "kode_barang", "NoPO": "no_dok", "NoPR": "no_pr", "TglPR": "tgl_pr", "PembuatPR": "pembuat_pr"})
    if asal.empty:
        return t, False, None
    asal = asal.assign(ket_asal=[_gabung_ket(r, ["Ket", "PerluPR", "KetPR", "KetPO"]) for r in asal.to_dict("records")])
    asal = asal[["no_dok", "kode_barang", "no_pr", "tgl_pr", "pembuat_pr", "ket_asal"]].drop_duplicates(["no_dok", "kode_barang"])
    return t.merge(asal, on=["no_dok", "kode_barang"], how="left"), True, None


def _tabel_rinci(t, kolom, judul):
    return {"judul": judul, "kolom": [{"kunci": k, "judul": j, "tipe": tp} for k, j, tp in kolom],
            "baris": [{k: nilai(r.get(k), tp) for k, _, tp in kolom} for r in t.to_dict("records")]}


def rincian(df, ds, jenis, kunci, filt=None):
    """kunci: {comp, mitra} untuk supplier/customer, {comp, no_dok, sumber?} untuk dokumen dan PR/PO."""
    periksa(jenis, JENIS_DETAIL, None, [], None)
    d, _, _, _ = _saring(df, ds, filt)
    comp = str(kunci.get("comp") or "")
    if jenis == "po_supplier":
        mitra = str(kunci.get("mitra") or "")
        t = d[(d["jenis"] == "po") & (d["comp"] == comp) & (d["mitra"] == mitra)].sort_values("umur", ascending=False)
        ringkas = {"po": t["no_dok"].nunique(), "item": len(t), "tertua": t["tgl"].min(), "umur": t["umur"].max()}
        bagian = _isian(ringkas, [("Ringkasan", [("po", "PO outstanding", "angka"), ("item", "Item", "angka"),
                                                 ("tertua", "PO tertua", "tanggal"), ("umur", "Umur terlama (hari)", "angka")])])
        kolom = [("no_dok", "No. PO", "teks"), ("tgl", "Tanggal PO", "tanggal"), ("umur", "Umur (hari)", "angka"), ("nama_barang", "Nama Barang", "teks"),
                 ("qty_sisa", "Qty Outstanding", "angka"), ("satuan", "Satuan", "teks"), ("nilai_sisa", "Nilai Outstanding", "angka"),
                 ("mata_uang_po", "Mata Uang", "teks"), ("no_lanjut", "No. PI", "teks")]
        t, tambah, catatan = _asal_pr(t, comp, "#SUP", mitra)
        if tambah:
            kolom = kolom + [("no_pr", "No. PR", "teks"), ("tgl_pr", "Tanggal PR", "tanggal"), ("pembuat_pr", "PR Dibuat Oleh", "teks"),
                             ("ket_asal", "Keterangan", "teks")]
        return {"kecil": f"Supplier PO · {comp}", "judul": mitra, "bagian": bagian, "tabel": [_tabel_rinci(t, kolom, "Item PO yang belum diterima")],
                "catatan": catatan}
    if jenis in ("supplier", "customer"):
        asal = "hutang" if jenis == "supplier" else "piutang"
        mitra = str(kunci.get("mitra") or "")
        t = d[(d["jenis"] == asal) & (d["comp"] == comp) & (d["mitra"] == mitra)].sort_values("umur", ascending=False)
        ringkas = {"dokumen": len(t), "sisa_rp": t["sisa_rp"].sum(), "tertua": t["tgl"].min(), "umur": t["umur"].max()}
        bagian = _isian(ringkas, [("Ringkasan", [("dokumen", "Dokumen outstanding", "angka"), ("sisa_rp", "Sisa", "angka"),
                                                 ("tertua", "Dokumen tertua", "tanggal"), ("umur", "Umur terlama (hari)", "angka")])])
        return {"kecil": f"{'Supplier' if asal == 'hutang' else 'Customer'} · {comp}", "judul": mitra, "bagian": bagian,
                "tabel": [_tabel_rinci(t, _KOLOM_DOK[asal], "Dokumen yang belum lunas")]}
    no = str(kunci.get("no_dok") or "")
    t = d[(d["jenis"] == jenis) & (d["comp"] == comp) & (d["no_dok"] == no)]
    if jenis in ARAP:
        if kunci.get("sumber"):
            t = t[t["sumber"] == kunci["sumber"]]
        if t.empty:
            raise FilterTidakValid("Dokumen tidak ditemukan di data yang dimuat. Muat ulang data lalu coba lagi.")
        r = t.iloc[0].to_dict()
        bagian = (_RINCI_HUTANG if jenis == "hutang" else _RINCI_PIUTANG)[:None if r.get("mata_uang") != "IDR" else -1]   # kurs hanya untuk valas
        tambah, tabel, catatan = _dari_erp(r, jenis)
        return {"kecil": f"{'Hutang' if jenis == 'hutang' else 'Piutang'} · {comp} · {r['mitra']}", "judul": no,
                "bagian": _isian(r, bagian) + tambah, "tabel": tabel, "catatan": catatan}
    if t.empty:
        raise FilterTidakValid("Dokumen tidak ditemukan di data yang dimuat. Muat ulang data lalu coba lagi.")
    r = t.sort_values("umur", ascending=False).iloc[0].to_dict()
    kolom, catatan = _KOLOM_ITEM[jenis], None
    if jenis == "po":   # asal PR tiap item dari SP rincian; tabel tetap tampil tanpa kolom PR kalau SP belum ada
        t, tambah, catatan = _asal_pr(t, comp, "#PO", no)
        if tambah:
            kolom = kolom + [("no_pr", "No. PR", "teks"), ("tgl_pr", "Tanggal PR", "tanggal"), ("pembuat_pr", "PR Dibuat Oleh", "teks"),
                             ("ket_asal", "Keterangan", "teks")]
    return {"kecil": f"{jenis.upper()} · {comp}", "judul": no, "bagian": _isian(r, _RINCI_PENGADAAN[jenis]),
            "tabel": [_tabel_rinci(t, kolom, "Item yang masih outstanding")], "catatan": catatan}
