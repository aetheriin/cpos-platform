"""Laporan PO Spend Analysis: data dashboard dan tabel detail. Susunannya mengikuti sheet CALC di Excel PO AMT db."""
from inti.filter import kanonik, saring, tgl
from inti.tabel import periksa, susun

from .sumber import NAMA_BULAN, NAMA_KATEGORI

# (kunci filter, judul, kolom)
FILTER = [
    ("perusahaan", "Perusahaan", "comp"),
    ("tahun", "Tahun", "tahun"),
    ("bulan", "Bulan", "bulan"),
    ("mata_uang", "Mata Uang", "uang"),
    ("kategori", "Kategori", "kategori"),
]
DIM = {k: kolom for k, _, kolom in FILTER}

KOLOM_DETAIL = [
    ("comp", "Perusahaan", "teks"), ("po", "No. PO", "teks"), ("tgl", "Tgl PO Dibuat", "tanggal"), ("supplier", "Supplier", "teks"),
    ("uang", "Mata Uang", "teks"), ("nilai_po", "Nilai PO", "angka"), ("nilai_idr", "Nilai IDR", "angka"), ("kategori", "Kategori", "teks"),
]
KOLOM_CARI = ["comp", "po", "supplier", "uang", "kategori"]
JENIS_DETAIL = {"po": "Semua PO"}


def _pilihan(df):
    ada = set(df["bulan"]), set(df["kategori"])
    return {
        "perusahaan": sorted(df["comp"].unique()),
        "tahun": sorted(df["tahun"].unique()),
        "bulan": [b for b in NAMA_BULAN if b in ada[0]],
        "mata_uang": sorted(df["uang"].unique()),
        "kategori": [k for k in NAMA_KATEGORI if k in ada[1]],
    }


def _siapkan(df, dari, sampai, filt):
    pilihan = _pilihan(df)
    filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul) for k, judul, _ in FILTER}
    t = df[(df["tgl"] >= dari) & (df["tgl"] <= sampai)]
    return saring(t, filt, DIM), filt, pilihan


def _kategori(t):
    n, total = max(len(t), 1), t["nilai_idr"].sum() or 1
    g = t.groupby("kategori")["nilai_idr"].agg(["size", "sum"])
    hasil = []
    for k in NAMA_KATEGORI:
        po, nilai = (int(g.at[k, "size"]), float(g.at[k, "sum"])) if k in g.index else (0, 0.0)
        hasil.append({"nama": k, "po": po, "nilai": nilai, "pct_po": po / n, "pct_nilai": nilai / total})
    return hasil


def _banding_tahun(t):
    """Jumlah dan nilai PO tiap bulan kalender, satu kolom per tahun, supaya bulan yang sama bisa dibandingkan antar tahun."""
    g = t.groupby(["bulan", "tahun"])["nilai_idr"].agg(["size", "sum"])
    tahun = sorted(t["tahun"].unique())
    baris = []
    for b in NAMA_BULAN:
        r = {"bulan": b}
        for y in tahun:
            ada = (b, y) in g.index
            r[f"po_{y}"] = int(g.at[(b, y), "size"]) if ada else None
            r[f"nilai_{y}"] = float(g.at[(b, y), "sum"]) if ada else None
        baris.append(r)
    return {"tahun": tahun, "baris": baris}


def _seri_bulan(t):
    """Jumlah dan nilai PO tiap bulan berjalan per kategori. Kunci po_<i> dan nilai_<i> mengikuti urutan NAMA_KATEGORI."""
    if t.empty:
        return []
    g = t.groupby([t["tgl"].dt.to_period("M"), "kategori"])["nilai_idr"].agg(["size", "sum"])
    hasil = []
    for m in sorted(g.index.get_level_values(0).unique()):
        r = {"label": f"{NAMA_BULAN[m.month - 1]} {str(m.year)[2:]}", "po": 0, "nilai": 0.0}
        for i, k in enumerate(NAMA_KATEGORI):
            ada = (m, k) in g.index
            r[f"po_{i}"] = int(g.at[(m, k), "size"]) if ada else 0
            r[f"nilai_{i}"] = float(g.at[(m, k), "sum"]) if ada else 0.0
            r["po"] += r[f"po_{i}"]
            r["nilai"] += r[f"nilai_{i}"]
        hasil.append(r)
    return hasil


def bangun(df, dari, sampai, filt=None):
    t, filt, pilihan = _siapkan(df, dari, sampai, filt)
    return {
        "filter": {"minggu": None, **filt},
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "kpi": {"po": len(t), "nilai": float(t["nilai_idr"].sum())},
        "kategori": _kategori(t),
        "banding_tahun": _banding_tahun(t),
        "seri_bulan": _seri_bulan(t),
        "nama_kategori": NAMA_KATEGORI,
        "jumlah": {"po": len(t)},
        "pilihan": pilihan,
    }


def detail(df, jenis, dari, sampai, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    periksa(jenis, JENIS_DETAIL, urut, KOLOM_DETAIL, arah)
    t, _, _ = _siapkan(df, dari, sampai, filt)
    hasil = susun(t.reset_index(drop=True), KOLOM_DETAIL, KOLOM_CARI, cari, urut, arah, "nilai_idr", "desc", halaman, ukuran)
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
