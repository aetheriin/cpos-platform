"""Laporan Outstanding: kartu ringkas dan tabel hutang (per dokumen, per supplier), piutang (per dokumen, per customer), serta PR dan
PO yang masih outstanding (per item). Nilai hutang/piutang dalam rupiah; rentang tampilan memakai tanggal dokumen."""
import pandas as pd

from inti.filter import kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

DIM = {"perusahaan": "comp", "sumber": "sumber"}
JENIS_DETAIL = {"hutang": "Hutang per dokumen", "supplier": "Hutang per supplier", "piutang": "Piutang per dokumen", "customer": "Piutang per customer",
                "pr": "PR outstanding", "po": "PO outstanding"}
ARAP = ("hutang", "piutang")

_KURS = [("mata_uang", "Mata Uang", "teks"), ("kurs", "Kurs", "angka"), ("sumber_kurs", "Sumber Kurs", "teks")]
# Urutan kolom: siapa dan dokumen apa, umur dan status, lalu Sisa (angka yang paling dicari) dan rinciannya, lalu nomor tindak lanjut,
# terakhir kurs untuk dokumen valas.
KOLOM = {
    "hutang": [
        ("comp", "Perusahaan", "teks"), ("mitra", "Supplier", "teks"), ("no_dok", "No. Dokumen", "teks"), ("sumber", "Sumber", "teks"),
        ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"), ("status", "Status", "teks"),
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
        ("tgl", "Tanggal", "tanggal"), ("umur", "Umur (hari)", "angka"), ("status", "Status", "teks"),
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
        ("comp", "Perusahaan", "teks"), ("no_dok", "No. PR", "teks"), ("tgl", "Tanggal PR", "tanggal"), ("umur", "Umur (hari)", "angka"),
        ("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"),
        ("qty_minta", "Qty Diminta", "angka"), ("qty_proses", "Qty Sudah PO", "angka"), ("qty_sisa", "Qty Outstanding", "angka"),
        ("no_lanjut", "No. PO", "teks"), ("mitra", "Supplier", "teks"), ("kategori", "Kategori", "teks"),
        ("dibuat_oleh", "Dibuat Oleh", "teks"), ("approve_oleh", "Approve Oleh", "teks"),
    ],
    "po": [
        ("comp", "Perusahaan", "teks"), ("no_dok", "No. PO", "teks"), ("tgl", "Tanggal PO", "tanggal"), ("umur", "Umur (hari)", "angka"),
        ("mitra", "Supplier", "teks"), ("kode_barang", "Kode Barang", "teks"), ("nama_barang", "Nama Barang", "teks"), ("satuan", "Satuan", "teks"),
        ("qty_minta", "Qty Order", "angka"), ("qty_proses", "Qty Diterima", "angka"), ("qty_sisa", "Qty Outstanding", "angka"),
        ("no_lanjut", "No. PI", "teks"), ("kategori", "Kategori", "teks"), ("dibuat_oleh", "Dibuat Oleh", "teks"),
    ],
}
KOLOM_CARI = {
    "hutang": ["comp", "mitra", "sumber", "no_dok", "status", "no_pvr", "no_pv_depan", "no_bayar"],
    "supplier": ["comp", "mitra", "sumber"],
    "piutang": ["comp", "mitra", "sumber", "no_dok", "no_do", "no_kontrak", "no_tc", "no_bayar", "keterangan"],
    "customer": ["comp", "mitra", "sumber"],
    "pr": ["comp", "no_dok", "kode_barang", "nama_barang", "no_lanjut", "mitra", "kategori", "dibuat_oleh"],
    "po": ["comp", "no_dok", "mitra", "kode_barang", "nama_barang", "no_lanjut", "kategori", "dibuat_oleh"],
}
URUT_AWAL = {"hutang": ("umur", "desc"), "supplier": ("sisa", "desc"), "piutang": ("umur", "desc"), "customer": ("sisa", "desc"),
             "pr": ("umur", "desc"), "po": ("umur", "desc")}


def _gabung(nilai):
    return ", ".join(sorted({v for v in nilai if v}))


def _saring(df, ds, filt):
    dari, sampai = rentang_tampil(ds)
    if getattr(ds, "dari", None) is None and len(df):   # data selalu semua riwayat; tanpa filter tanggal, dokumen lama tetap tampil
        dari = min(dari, df["tgl"].min())
    arap = df["jenis"].isin(ARAP)
    pilihan = {"perusahaan": sorted(df["comp"].unique()), "sumber": sorted(df.loc[arap, "sumber"].dropna().unique(), key=str.casefold)}
    filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul) for k, judul in (("perusahaan", "Perusahaan"), ("sumber", "Sumber"))}
    d = df[(df["tgl"] >= dari) & (df["tgl"] <= sampai)]
    # filter sumber hanya untuk hutang/piutang; PR dan PO cukup filter perusahaan
    d_arap = saring(d[d["jenis"].isin(ARAP)], filt, DIM)
    d_pp = saring(d[~d["jenis"].isin(ARAP)], {"perusahaan": filt["perusahaan"]}, {"perusahaan": "comp"})
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
        **_kpi_pengadaan(d, "pr"), **_kpi_pengadaan(d, "po"),
    }


def _kpi_pengadaan(d, jenis):
    t = d[d["jenis"] == jenis]
    umur = t.groupby(["comp", "no_dok"])["umur"].max()
    return {f"{jenis}_dok": int(len(umur)), f"{jenis}_item": int(len(t)), f"{jenis}_lama": int((umur > 30).sum()),
            f"{jenis}_umur_maks": int(umur.max()) if len(umur) else None}


def _tabel(d, jenis):
    if jenis in ("hutang", "piutang", "pr", "po"):
        return d[d["jenis"] == jenis]
    return rekap(d[d["jenis"] == ("hutang" if jenis == "supplier" else "piutang")], jenis)


def bangun(df, ds, filt=None):
    d, dari, sampai, pilihan = _saring(df, ds, filt)
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
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
