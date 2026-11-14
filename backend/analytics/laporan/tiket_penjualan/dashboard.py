"""Kartu, peringkat, sebaran waktu, dan tabel detail laporan Tiket Penjualan.

Rentang tampilan dipilih di halaman sebagai satu hari, satu minggu (Senin sampai Minggu), atau satu bulan. Tanpa rentang: bulan dari tanggal
data terakhir. Pembanding kartu mengikuti bentuk rentangnya: hari sebelumnya, minggu sebelumnya, atau tanggal yang sama di bulan sebelumnya."""
import calendar
from datetime import date, datetime

import pandas as pd

from inti import ekspor, konfigurasi
from inti.banding import bagi, jendela_sebelumnya
from inti.filter import FilterTidakValid, daftar, kanonik, saring, tgl
from inti.tabel import periksa, susun

from . import ukuran as U

# (kunci di URL, label, kolom data, tampil di panel filter). Tanggal dan jam diisi dengan klik grafik sebaran waktu.
FILTER = [
    ("perusahaan", "Perusahaan", "comp", True), ("produk", "Produk", "produk", True), ("pengangkut", "Nama Pengangkutan", "pengangkut", True),
    ("pembeli", "Nama Pembeli", "pembeli", True), ("tanggal", "Tanggal", "hari", False), ("jam", "Jam Keluar", "jam", False),
]
DIM = {kunci: kolom for kunci, _, kolom, _ in FILTER}
FILTER_TANPA_BANDING = ("tanggal",)
KOLOM_CARI = ["tiket", "pembeli", "produk", "pengangkut", "kendaraan", "supir", "no_do", "kontrak", "comp"]
# Excel: urutan kolom sama dengan ekspor tiket timbangan di Ascend, ditambah Split dan Perusahaan.
KOLOM_TIKET = [
    ("tgl", "Tanggal", "tanggal"), ("jam_masuk", "Jam Masuk", "teks"), ("jam_keluar", "Jam Keluar", "teks"), ("pembeli", "Nama Pembeli", "teks"),
    ("no_do", "Nomor DO", "teks"), ("produk", "Produk", "teks"), ("pengangkut", "Nama Pengangkutan", "teks"), ("tiket", "No. Tiket", "teks"),
    ("kendaraan", "No. Kendaraan", "teks"), ("supir", "Nama Supir", "teks"), ("kontrak", "Nomor Kontrak", "teks"), ("bruto", "Bruto (kg)", "angka"),
    ("tara", "Tara (kg)", "angka"), ("potongan", "Potongan (kg)", "angka"), ("netto", "Netto (kg)", "angka"),
    ("netto_sumber", "Netto Sumber (kg)", "angka"), ("ffa", "FFA (%)", "angka"), ("air", "Kadar Air (%)", "angka"),
    ("kotoran", "Kadar Kotoran (%)", "angka"), ("dobi", "Dobi", "angka"), ("split", "Split", "teks"), ("comp", "Perusahaan", "teks"),
]
KOLOM_PENGANGKUT = [
    ("pengangkut", "Nama Pengangkutan", "teks"), ("rit", "Jumlah Pengiriman", "angka"), ("netto", "Netto (kg)", "angka"), ("per_rit", "Rata-rata Muatan per Truk (kg)", "angka"),
    ("produk", "Produk", "teks"), ("pembeli", "Jumlah Pembeli", "angka"), ("kendaraan", "Jumlah Truk", "angka"), ("hari_kirim", "Jumlah Hari Kirim", "angka"),
    ("terakhir", "Kirim Terakhir", "tanggal"),
]
# Layar: kolom yang paling sering dicari (tiket, produk, pengangkut, pembeli, berat) di depan, supaya tidak perlu menggulir ke samping.
_URUT_LAYAR = ["tgl", "tiket", "produk", "pengangkut", "pembeli", "kendaraan", "supir", "netto", "jam_masuk", "jam_keluar", "no_do", "kontrak",
               "bruto", "tara", "potongan", "netto_sumber", "ffa", "air", "kotoran", "dobi", "split", "comp"]
KOLOM_TIKET_LAYAR = sorted(KOLOM_TIKET, key=lambda k: _URUT_LAYAR.index(k[0]))
JENIS_DETAIL = {"tiket": "Per tiket", "pengangkut": "Per pengangkut"}
TANPA_NAMA = "Tanpa nama pengangkutan"

_cache = {}   # id(df) -> (df, kini, pilihan)


def _siapkan(df):
    simpan = _cache.get(id(df))
    if simpan and simpan[0] is df:
        return simpan[1:]
    kini, _ = bagi(df)
    banyak = lambda k: [v for v in kini.groupby(k)["netto"].sum().sort_values(ascending=False).index if v != ""]
    pilihan = {"perusahaan": sorted(kini["comp"].unique().tolist()), "produk": banyak("produk"), "pengangkut": banyak("pengangkut"),
               "pembeli": banyak("pembeli")}
    if len(_cache) >= konfigurasi.MAKS_DATASET:
        _cache.clear()
    _cache[id(df)] = (df, kini, pilihan)
    return kini, pilihan


def _rapikan(kini, pilihan, filt):
    hasil = {k: kanonik(filt.get(k), pilihan[k], nama) for k, nama, _, panel in FILTER if panel}
    tanggal = sorted(set(daftar(filt.get("tanggal"))))
    salah = [v for v in tanggal if v not in set(kini["hari"].values)]
    if salah:
        raise FilterTidakValid(f"Tanggal '{salah[0]}' tidak ada di data ini")
    jam = sorted(set(daftar(filt.get("jam"))))
    salah = [v for v in jam if v not in {f"{j:02d}" for j in range(24)}]
    if salah:
        raise FilterTidakValid(f"Jam '{salah[0]}' tidak dikenal. Isi 00 sampai 23")
    hasil["tanggal"], hasil["jam"] = tanggal, jam
    return hasil


def _rentang(ds):
    """(dari, sampai) rentang tampilan. Tanpa pilihan: bulan dari tanggal data terakhir (paling lambat hari ini)."""
    dari, sampai = getattr(ds, "dari", None), getattr(ds, "sampai", None)
    if dari is not None and sampai is not None:
        return pd.Timestamp(dari), pd.Timestamp(sampai)
    awal = pd.Timestamp(ds.mulai)
    akhir = max(min(pd.Timestamp(ds.akhir), pd.Timestamp(date.today())), awal)
    return max(awal, akhir.replace(day=1)), akhir


def _sebelumnya(dari, sampai):
    """Rentang pembanding: hari sebelumnya, minggu sebelumnya (rentang Senin sampai paling lama Minggu), tanggal yang sama di bulan
    sebelumnya (rentang mulai tanggal 1 di dalam satu bulan), selain itu jendela sama panjang tepat sebelumnya."""
    if dari == sampai:
        return dari - pd.Timedelta(days=1), sampai - pd.Timedelta(days=1)
    if dari.weekday() == 0 and (sampai - dari).days <= 6:
        return dari - pd.Timedelta(days=7), sampai - pd.Timedelta(days=7)
    if dari.day == 1 and (sampai.year, sampai.month) == (dari.year, dari.month):
        awal = (dari - pd.Timedelta(days=1)).replace(day=1)
        hari_terakhir = calendar.monthrange(awal.year, awal.month)[1]
        return awal, awal.replace(day=min(sampai.day, hari_terakhir))
    return tuple(pd.Timestamp(x) for x in jendela_sebelumnya(dari, sampai))


def _dalam(df, mulai, akhir):
    return df[(df["hari"] >= tgl(mulai)) & (df["hari"] <= tgl(akhir))]


def _banding(df, ds, filt, dari, sampai):
    """KPI rentang pembanding dari seluruh baris yang dimuat (termasuk hari sebelum periode). None kalau rentang itu di luar data.
    Rentang yang berakhir hari ini belum lengkap: hari terakhir pembandingnya juga dihitung sampai jam yang sama, supaya hari ini yang baru
    berjalan setengah hari tidak tampak turun jauh dibanding hari sebelumnya yang penuh."""
    if any(filt[k] for k in FILTER_TANPA_BANDING):
        return None
    ps, pe = _sebelumnya(dari, sampai)
    awal_data = pd.Timestamp(ds.mulai) - pd.Timedelta(days=konfigurasi.TIKET_PENJUALAN_HARI_LALU)
    if ps < awal_data:
        return None
    lalu = saring(_dalam(df, ps, pe), filt, DIM)
    sampai_jam = None
    if sampai.date() == date.today():
        sampai_jam = f"{datetime.now().hour:02d}"
        lalu = lalu[(lalu["hari"] != tgl(pe)) | (lalu["jam"] <= sampai_jam)]
    return {"mulai": tgl(ps), "akhir": tgl(pe), "sampai_jam": sampai_jam, "kpi": U.kpi(lalu)}


def bangun(df, ds, filt=None):
    kini_semua, pilihan = _siapkan(df)
    dari, sampai = _rentang(ds)
    filt = _rapikan(kini_semua, pilihan, filt or {})
    kini = _dalam(kini_semua, dari, sampai)
    d = saring(kini, filt, DIM)
    tanpa = lambda nama: saring(kini, filt, DIM, lewati=nama)
    n = konfigurasi.TIKET_PENJUALAN_TOP
    if dari == sampai:
        sebaran = {"satuan": "jam", "data": U.per_jam(tanpa("jam"))}
    else:
        sebaran = {"satuan": "hari", "data": U.per_hari(tanpa("tanggal"), dari, sampai)}
    k = U.kpi(d)
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari"},
        "kpi": k,
        "banding": _banding(df, ds, filt, dari, sampai),
        "filter": [{"kunci": kunci, "nama": nama, "panel": panel} for kunci, nama, _, panel in FILTER],
        "per_produk": U.peringkat(tanpa("produk"), "produk", n, filt["produk"]),
        "per_pengangkut": U.peringkat(tanpa("pengangkut"), "pengangkut", n, filt["pengangkut"]),
        "per_pembeli": U.peringkat(tanpa("pembeli"), "pembeli", n, filt["pembeli"]),
        "sebaran": sebaran,
        "jumlah": {"tiket": k["rit"], "pengangkut": int(d["pengangkut"].nunique())},
        "pilihan": pilihan,
    }


def _per_pengangkut(d):
    d = d.assign(pengangkut=d["pengangkut"].where(d["pengangkut"] != "", TANPA_NAMA))
    produk = d.groupby(["pengangkut", "produk"])["netto"].sum().reset_index().sort_values("netto", ascending=False, kind="stable")
    g = d.groupby("pengangkut").agg(rit=("netto", "size"), netto=("netto", "sum"), pembeli=("pembeli", "nunique"),
                                    kendaraan=("kendaraan", "nunique"), hari_kirim=("hari", "nunique"), terakhir=("tgl", "max")).reset_index()
    g["per_rit"] = (g["netto"] / g["rit"]).round(2)
    g["produk"] = g["pengangkut"].map(produk.groupby("pengangkut")["produk"].agg(", ".join))
    return g


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'tiket': satu baris per tiket (jumlah netto sama dengan kartu Total Netto). 'pengangkut': satu baris per nama pengangkutan."""
    ke_excel = ukuran >= ekspor.MAKS_BARIS   # dipanggil Export Excel (api.py), bukan halaman tabel di layar
    kolom = (KOLOM_TIKET if ke_excel else KOLOM_TIKET_LAYAR) if jenis == "tiket" else KOLOM_PENGANGKUT
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    kini, pilihan = _siapkan(df)
    dari, sampai = _rentang(ds)
    d = saring(_dalam(kini, dari, sampai), _rapikan(kini, pilihan, filt or {}), DIM)
    if jenis == "tiket":
        hasil = susun(d.reset_index(drop=True), kolom, KOLOM_CARI, cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="tiket")
    else:
        # Baris tanpa nama pengangkutan selalu paling bawah, apa pun urutannya
        t = _per_pengangkut(d)
        urut_pakai = urut or "netto"
        arah_pakai = arah or ("desc" if urut is None else "asc")
        kunci = t[urut_pakai].fillna("").astype(str).str.lower() if dict((k, tp) for k, _, tp in kolom)[urut_pakai] == "teks" else t[urut_pakai]
        t = (t.assign(_k=kunci).sort_values("_k", ascending=arah_pakai == "asc", kind="stable", na_position="last")
             .assign(_bawah=lambda x: x["pengangkut"] == TANPA_NAMA).sort_values("_bawah", kind="stable").reset_index(drop=True))
        t["_urutan"] = range(len(t))
        hasil = susun(t, kolom, ["pengangkut", "produk"], cari, None, None, "_urutan", "asc", halaman, ukuran)
        hasil.update(urut=urut_pakai, arah=arah_pakai)
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
