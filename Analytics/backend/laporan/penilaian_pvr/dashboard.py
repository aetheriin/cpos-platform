"""Laporan PVR KPI (dan PV KPI, yang memakai modul ini juga): data dashboard dan tabel detail. Rentang tampilan memakai tanggal voucher."""
from inti import konfigurasi
from inti.filter import kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from . import ukuran as U
from .sumber import KOSONG

# (kunci filter, judul, kolom)
FILTER = [
    ("perusahaan", "Perusahaan", "comp"),
    ("pembuat", "Pembuat PVR", "pembuat"),
    ("kategori", "Kategori", "kategori"),
]
DIM = {k: kolom for k, _, kolom in FILTER}

def label_filter(voucher="PVR"):
    return {k: (f"Pembuat {voucher}" if k == "pembuat" else judul) for k, judul, _ in FILTER}


def kolom_detail(voucher="PVR"):
    """Judul kolom mengikuti jenis voucher: 'PVR' untuk PVR KPI, 'PV' untuk PV KPI."""
    return [
        ("comp", "Perusahaan", "teks"), ("tanggal", f"Tgl {voucher}", "tanggal"), ("pvr_number", f"No. {voucher}", "teks"), ("pembuat", "Dibuat Oleh", "teks"),
        ("kategori", "Kategori", "teks"), ("bobot", "Bobot", "angka"), ("sumber_kategori", "Asal Check Number", "teks"),
        ("supplier", "Supplier", "teks"), ("item_ref", "Item Ref", "teks"), ("jenis_ref", "Jenis Ref", "teks"),
        ("jumlah", "Item Amount Paid", "angka"), ("item_pvr", f"Item di {voucher}", "angka"),
    ]


KOLOM_DETAIL = kolom_detail()
KOLOM_CARI = ["comp", "pvr_number", "pembuat", "kategori", "supplier", "item_ref"]
JENIS_DETAIL = {"dinilai": "Baris dinilai", "kosong": "Tanpa kategori"}


def _pilihan(df, dinilai):
    return {
        "perusahaan": sorted(df["comp"].unique()),
        # Pembuat yang dinilai selalu ada di pilihan, supaya tampilan awal tetap sah walau salah satunya belum membuat voucher
        "pembuat": sorted(set(df["pembuat"]) | {n.title() for n in dinilai}, key=str.casefold),
        "kategori": sorted(set(df["kategori"]) - {KOSONG}, key=str.casefold),   # voucher tanpa kategori punya tab sendiri
    }


def _siapkan(df, ds, filt, dinilai):
    dari, sampai = rentang_tampil(ds)
    pilihan = _pilihan(df, dinilai)
    filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul) for k, judul, _ in FILTER}
    d = saring(df[(df["tanggal"] >= dari) & (df["tanggal"] <= sampai)], filt, DIM)
    return d, pilihan, dari, sampai


def bangun(df, ds, filt=None, dinilai=konfigurasi.PVR_PENILAIAN_PEMBUAT):
    d, pilihan, dari, sampai = _siapkan(df, ds, filt, dinilai)
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "kpi": U.kpi(d),
        "rekap": U.rekap(d),
        "kategori": U.per_kategori(d[d["kategori"] != KOSONG]),
        "jumlah": {"dinilai": int((d["kategori"] != KOSONG).sum()), "kosong": int((d["kategori"] == KOSONG).sum())},
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50, dinilai=konfigurasi.PVR_PENILAIAN_PEMBUAT, voucher="PVR"):
    """'dinilai': baris yang menambah skor, terbaru di atas. 'kosong': voucher tanpa Check Number (bernilai 0), hanya di tab ini."""
    kolom = kolom_detail(voucher)
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    d, _, dari, sampai = _siapkan(df, ds, filt, dinilai)
    t = d[(d["kategori"] == KOSONG) == (jenis == "kosong")]
    hasil = susun(t.reset_index(drop=True), kolom, KOLOM_CARI, cari, urut, arah, "tanggal", "desc", halaman, ukuran, pembanding="pvr_number")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
