"""Laporan PO PI: rumus perhitungan KPI dan pembagian minggu."""
import pandas as pd

from inti.kecepatan import sekarang
from inti.umur import URUTAN_UMUR  # noqa: F401  (dipakai dashboard.py lewat ukuran.URUTAN_UMUR)

STATUS_PI = ["Open", "Completed"]
# Sudah PI penuh: qtyout <= 0. Negatif berarti qty PI melebihi qty PO, tetap dihitung sudah PI.


AGING_BUKAN_ANGKA = {"COMPLETED", "VOID", "CLOSED"}


def _unik(df, mask):
    return df.loc[mask, "line"].nunique()


def new_po(df, mulai, akhir):
    """PO yang dibuat dalam rentang, bukan Void. Unik per baris PO."""
    return _unik(df, (df["cd"] >= mulai) & (df["cd"] <= akhir) & (df["status"] != "Void"))


def mask_pi(df, mulai, akhir):
    return (
        (df["qtyout"] <= 0)
        & (df["pi_date"] >= mulai) & (df["pi_date"] <= akhir)
        & df["status"].isin(STATUS_PI)
    )


def new_pi(df, mulai, akhir):
    """Penerimaan (PI) dalam rentang untuk PO yang sudah terpenuhi. Menghitung BARIS (satu per PI)."""
    return int(mask_pi(df, mulai, akhir).sum())


def outstanding_awal(df, mulai):
    k1 = (df["cd"] < mulai) & (df["qtyout"] > 0) & (df["status"] == "Open")
    k2 = (df["cd"] < mulai) & (df["qtyout"] <= 0) & (df["pi_date"] >= mulai)
    return _unik(df, k1) + _unik(df, k2)


def outstanding_akhir(df, akhir):
    k1 = (df["cd"] <= akhir) & (df["qtyout"] > 0) & (df["status"] == "Open")
    k2 = (df["cd"] <= akhir) & (df["qtyout"] <= 0) & (df["pi_date"] > akhir)
    return _unik(df, k1) + _unik(df, k2)


def mask_outstanding_akhir(df, akhir):
    k1 = (df["cd"] <= akhir) & (df["qtyout"] > 0) & (df["status"] == "Open")
    k2 = (df["cd"] <= akhir) & (df["qtyout"] <= 0) & (df["pi_date"] > akhir)
    return k1 | k2


def completion_rate(df, mulai, akhir):
    dibuat = (df["cd"] >= mulai) & (df["cd"] <= akhir)
    total = _unik(df, dibuat)
    selesai = _unik(df, dibuat & ((df["status"] != "Open") | (df["qtyout"] <= 0)))
    return selesai / total if total else 0.0


def pi_partial(df, mulai, akhir):
    """Dari penerimaan dalam rentang, berapa baris yang PO-nya punya lebih dari satu PI.
    Mengembalikan (jumlah_partial, jumlah_pi, persen)."""
    m = mask_pi(df, mulai, akhir)
    total = int(m.sum())
    y = int((m & (df["partial"] == "Y")).sum())
    return y, total, (y / total if total else 0.0)


def _umur_angka(df):
    aktif = df[~df["aging"].str.upper().isin(AGING_BUKAN_ANGKA)]
    return pd.to_numeric(aktif["aging"], errors="coerce").dropna()


def aging_rata_rata(df):
    u = _umur_angka(df)
    return float(u.mean()) if len(u) else 0.0


def aging_maks(df):
    u = _umur_angka(df)
    return float(u.max()) if len(u) else 0.0


def daftar_minggu(jumlah, jangkar):
    """Minggu Jumat sampai Kamis; minggu terakhir memuat tanggal jangkar (tanggal akhir pilihan)."""
    terbaru = pd.Timestamp(jangkar)
    mundur = (terbaru.weekday() - 4) % 7  # Jumat = 4
    awal = (terbaru - pd.Timedelta(days=mundur)).normalize()
    return [
        (awal - pd.Timedelta(days=7 * k), awal - pd.Timedelta(days=7 * k) + pd.Timedelta(days=6))
        for k in range(jumlah - 1, -1, -1)
    ]


def penyelesaian(df, hari_ini=None):
    """Satu baris per PO line yang Open atau sudah Completed (Void dan Closed bukan bagian dari ukuran kecepatan).
    awal = tanggal dokumen PO. selesai = tanggal PI terakhir, hanya untuk yang Completed (kosong untuk yang masih Open).
    lama = selesai - awal, dalam hari (jam yang sama dengan Aging). PO Completed yang tidak punya tanggal PI yang sah
    tidak bisa diukur dan dibuang. Tanggal PI setelah hari ini (salah ketik, mis. tahun 2205) diabaikan."""
    batas = pd.Timestamp(hari_ini).normalize() if hari_ini is not None else sekarang()
    satu = df.drop_duplicates("line").set_index("line")
    satu = satu[satu["status"].isin(["Open", "Completed"])]
    terakhir = df[(df["status"] == "Completed") & df["pi_date"].notna() & (df["pi_date"] <= batas)].groupby("line")["pi_date"].max()
    g = pd.DataFrame({"awal": satu["po_date"], "selesai": terakhir.reindex(satu.index)})
    g = g[(satu["status"] == "Open") | g["selesai"].notna()].copy()
    g["lama"] = (g["selesai"] - g["awal"]).dt.days
    return g
