"""Laporan PR/PO: rumus perhitungan KPI dan pembagian minggu."""
import pandas as pd

from inti.kecepatan import sekarang

STATUS_AKTIF = ["Open", "Completed"]


AGING_BUKAN_ANGKA = {"COMPLETED", "VOID", "CLOSED"}


def _unik(df, mask):
    return df.loc[mask, "line"].nunique()


def new_pr(df, mulai, akhir):
    """Baris PR yang dibuat dalam rentang (semua status), unik per baris PR."""
    return _unik(df, (df["pr_date"] >= mulai) & (df["pr_date"] <= akhir))


def _mask_new_po(df, mulai, akhir):
    """New PO: PR yang sudah selesai di-PO (QTYOUT <= 0; negatif berarti qty PO melebihi qty PR), PO dibuat dalam rentang, status Open atau Completed.
    Satu-satunya definisi, dipakai kartu New PO, PO Partial, dan tabel detailnya."""
    return (
        (df["qtyout"] <= 0)
        & (df["po_date"] >= mulai) & (df["po_date"] <= akhir)
        & df["status"].isin(STATUS_AKTIF)
    )


def _po_baru(df, mulai, akhir):
    """Satu baris per PO: PR yang di-PO dua kali jadi dua baris, tapi PO dengan nomor dan tanggal sama hanya satu."""
    return df.loc[_mask_new_po(df, mulai, akhir)].drop_duplicates(["line", "po_number", "po_date"])


def new_po(df, mulai, akhir):
    """Jumlah PO (lihat _po_baru), bukan jumlah PR."""
    return len(_po_baru(df, mulai, akhir))


def outstanding_awal(df, mulai):
    """Posisi sebelum tanggal `mulai`."""
    k1 = (df["pr_date"] < mulai) & (df["qtyout"] > 0) & (df["status"] == "Open")
    k2 = (df["pr_date"] < mulai) & (df["qtyout"] <= 0) & (df["po_date"] >= mulai)
    return _unik(df, k1) + _unik(df, k2)


def outstanding_akhir(df, akhir):
    """Posisi pada akhir tanggal `akhir`."""
    k1 = (df["pr_date"] <= akhir) & (df["qtyout"] > 0) & (df["status"] == "Open")
    k2 = (df["pr_date"] <= akhir) & (df["qtyout"] <= 0) & (df["po_date"] > akhir)
    return _unik(df, k1) + _unik(df, k2)


def mask_outstanding_akhir(df, akhir):
    """Baris yang dihitung outstanding_akhir, untuk tabel detail."""
    return ((df["pr_date"] <= akhir) & (df["qtyout"] > 0) & (df["status"] == "Open")) | (
        (df["pr_date"] <= akhir) & (df["qtyout"] <= 0) & (df["po_date"] > akhir))


def completion_rate(df, mulai, akhir):
    """Bagian PR yang selesai (bukan Open, atau QTYOUT <= 0) dari PR yang dibuat dalam rentang."""
    dibuat = (df["pr_date"] >= mulai) & (df["pr_date"] <= akhir)
    total = _unik(df, dibuat)
    selesai = _unik(df, dibuat & ((df["status"] != "Open") | (df["qtyout"] <= 0)))
    return selesai / total if total else 0.0


def po_partial(df, mulai, akhir):
    """KPI PO Partial = persen dari New PO.
    Dari New PO, berapa PO yang berasal dari PR yang di-PO lebih dari satu nomor berbeda (PARTIAL = Y). Status partial adalah sifat PR-nya,
    jadi kedua PO tetap partial walau jatuh di minggu berbeda, dan tiap PO dihitung di periode tanggal POnya sendiri: jumlah per minggu
    selalu sama dengan jumlah seluruh periode. Mengembalikan (jumlah_partial, jumlah_new_po, persen); jumlah_new_po selalu sama dengan
    angka di kartu New PO."""
    p = _po_baru(df, mulai, akhir)
    total = len(p)
    y = int((p["partial"] == "Y").sum())
    return y, total, (y / total if total else 0.0)


def _umur(df):
    satu = df.drop_duplicates("line")
    aktif = satu[~satu["aging"].str.upper().isin(AGING_BUKAN_ANGKA)]
    return pd.to_numeric(aktif["aging"], errors="coerce").dropna()


def aging_rata_rata(df):
    """Rata-rata umur (hari) PR yang belum selesai."""
    u = _umur(df)
    return float(u.mean()) if len(u) else 0.0


def aging_maks(df):
    """Umur terlama (hari) PR yang belum selesai."""
    u = _umur(df)
    return float(u.max()) if len(u) else 0.0


def daftar_minggu(df, jumlah=5, jangkar=None):
    """Minggu Jumat-Kamis; minggu terakhir memuat `jangkar`, atau tanggal data terbaru kalau tanpa jangkar."""
    terbaru = pd.Timestamp(jangkar) if jangkar is not None else max(df["pr_date"].max(), df["po_date"].max())
    mundur = (terbaru.weekday() - 4) % 7  # Jumat = 4
    awal_terakhir = (terbaru - pd.Timedelta(days=mundur)).normalize()
    return [
        (awal_terakhir - pd.Timedelta(days=7 * k), awal_terakhir - pd.Timedelta(days=7 * k) + pd.Timedelta(days=6))
        for k in range(jumlah - 1, -1, -1)
    ]


def penyelesaian(df, hari_ini=None):
    """Satu baris per PR line yang Open atau sudah Completed (Void dan Closed bukan bagian dari ukuran kecepatan).
    awal = tanggal PR dibuat. selesai = tanggal PO terakhir, hanya untuk yang Completed (kosong untuk yang masih Open).
    lama = selesai - awal, dalam hari (jam yang sama dengan Aging). PR Completed yang tidak punya tanggal PO yang sah
    tidak bisa diukur dan dibuang. Tanggal PO setelah hari ini (salah ketik) diabaikan."""
    batas = pd.Timestamp(hari_ini).normalize() if hari_ini is not None else sekarang()
    satu = df.drop_duplicates("line").set_index("line")
    satu = satu[satu["status"].isin(["Open", "Completed"])]
    terakhir = df[(df["status"] == "Completed") & df["po_date"].notna() & (df["po_date"] <= batas)].groupby("line")["po_date"].max()
    g = pd.DataFrame({"awal": satu["pr_date"], "selesai": terakhir.reindex(satu.index)})
    g = g[(satu["status"] == "Open") | g["selesai"].notna()].copy()
    g["lama"] = (g["selesai"] - g["awal"]).dt.days
    return g
