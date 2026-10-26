"""Kartu, grafik, dan tabel detail laporan Penerimaan TBS. Cross filter sama dengan PR/PO.

Forecast mengabaikan filter tanggal dan hari dalam seminggu (deret hariannya akan bolong), tapi ikut filter lain."""
import pandas as pd

from inti import konfigurasi
from inti.banding import bagi, jendela_sebelumnya
from inti.filter import FilterTidakValid, daftar, kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from . import ukuran as U
from .sumber import NAMA_HARI

# (kunci di URL, label, kolom data, tampil di panel filter). Tanggal diisi dengan klik grafik tren.
FILTER = [
    ("perusahaan", "Perusahaan", "comp", True), ("tipe", "Tipe Supplier", "tipe", True), ("grup", "Business Group", "grup", True),
    ("supplier", "Supplier", "supplier", True), ("kategori", "Kategori", "kategori", True), ("hari_minggu", "Hari", "nama_hari", True),
    ("tanggal", "Tanggal", "hari", False),
]
DIM = {kunci: kolom for kunci, _, kolom, _ in FILTER}
FILTER_TANPA_BANDING = ("tanggal",)
FILTER_TANPA_FORECAST = ("tanggal", "hari_minggu")
KOLOM_CARI = ["purchase_id", "supplier", "grup", "tipe", "kategori", "comp"]
KOLOM_PEMBELIAN = [
    ("tgl", "Tanggal", "tanggal"), ("purchase_id", "No. Pembelian", "teks"), ("supplier", "Supplier", "teks"), ("grup", "Business Group", "teks"),
    ("tipe", "Tipe Supplier", "teks"), ("kategori", "Kategori", "teks"), ("netto", "Netto (kg)", "angka"), ("harga", "Harga/kg", "angka"),
    ("nilai", "Nilai (Rp)", "angka"), ("comp", "Perusahaan", "teks"),
]
KOLOM_SUPPLIER = [
    ("supplier", "Supplier", "teks"), ("grup", "Business Group", "teks"), ("tipe", "Tipe Supplier", "teks"), ("netto", "Netto (kg)", "angka"),
    ("nilai", "Nilai (Rp)", "angka"), ("harga", "Harga Rata-rata/kg", "angka"), ("hari_kirim", "Hari Kirim", "angka"),
    ("terakhir", "Kirim Terakhir", "tanggal"),
]
JENIS_DETAIL = {"pembelian": "Per pembelian", "supplier": "Per supplier"}

_cache = {}   # id(df) -> (df, kini, lalu, pilihan)


def _siapkan(df):
    simpan = _cache.get(id(df))
    if simpan and simpan[0] is df:
        return simpan[1:]
    kini, lalu = bagi(df)
    banyak = lambda k: kini.groupby(k)["netto"].sum().sort_values(ascending=False).index.tolist()
    pilihan = {"perusahaan": sorted(kini["comp"].unique().tolist()), "tipe": banyak("tipe"), "grup": banyak("grup"), "supplier": banyak("supplier"),
               "kategori": banyak("kategori"), "hari_minggu": [h for h in NAMA_HARI if h in set(kini["nama_hari"])]}
    if len(_cache) >= konfigurasi.MAKS_DATASET:
        _cache.clear()
    _cache[id(df)] = (df, kini, lalu, pilihan)
    return kini, lalu, pilihan


def _rapikan(kini, pilihan, filt):
    hasil = {k: kanonik(filt.get(k), pilihan[k], nama) for k, nama, _, panel in FILTER if panel}
    tanggal = daftar(filt.get("tanggal"))
    ada = set(kini["hari"].values)
    salah = [v for v in tanggal if v not in ada]
    if salah:
        raise FilterTidakValid(f"Tanggal '{salah[0]}' tidak ada di data ini")
    hasil["tanggal"] = sorted(set(tanggal))
    return hasil


def _per(d, kolom, n=None, terpilih=()):
    """Netto, nilai, dan harga tertimbang per nilai kolom, dari netto terbesar. n: batas baris (yang dipilih tetap ikut)."""
    g = d.groupby(kolom)[["netto", "nilai"]].sum().sort_values("netto", ascending=False, kind="stable")
    atas = g if n is None else pd.concat([g.head(n), g[g.index.isin(terpilih) & ~g.index.isin(g.head(n).index)]])
    return [{"nama": k, "netto": round(float(r["netto"]), 2), "nilai": round(float(r["nilai"]), 2),
             "harga": round(float(r["nilai"] / r["netto"]), 2) if r["netto"] else None} for k, r in atas.iterrows()], int(len(g))


def _per_hari_minggu(d, mulai, akhir):
    """Rata-rata netto harian untuk tiap hari dalam seminggu, dari hari yang ada pembeliannya (measure Rata-rata di Excel: AVERAGEX atas
    tanggal melewati tanggal kosong)."""
    s = U.harian(d, mulai, akhir)["netto"]
    s = s[s > 0]
    rata = s.groupby(s.index.weekday).mean().reindex(range(7), fill_value=0.0)
    jumlah = s.groupby(s.index.weekday).size().reindex(range(7), fill_value=0)
    return [{"nama": NAMA_HARI[i], "rata": round(float(rata[i]), 2), "jumlah_hari": int(jumlah[i])} for i in range(7)]


def _harga_tipe(d, mulai, akhir, terpilih):
    """Per tipe (netto terbesar dulu, yang dipilih tetap ikut): harga tertimbang harian (total nilai / total kg) dari mulai sampai akhir, harga hari
    pertama dan terakhir yang ada pembeliannya, untuk garis kecil per tipe."""
    d = d[(d["tgl"] >= mulai) & (d["tgl"] <= akhir)]
    urut = d.groupby("tipe")["netto"].sum().sort_values(ascending=False)
    tipe = urut.index[:konfigurasi.TBS_TOP_TIPE_HARGA].tolist() + [t for t in terpilih if t in urut.index[konfigurasi.TBS_TOP_TIPE_HARGA:]]
    hari = pd.date_range(mulai, akhir, freq="D").strftime("%Y-%m-%d")
    g = d[d["tipe"].isin(tipe)].groupby(["tipe", "hari"])[["netto", "nilai"]].sum()
    harga = (g["nilai"] / g["netto"].where(g["netto"] > 0)).unstack().reindex(columns=hari)
    hasil = []
    for t in tipe:
        s = harga.loc[t] if t in harga.index else pd.Series(dtype=float)
        ada = s.dropna()
        hasil.append({"tipe": t, "netto": round(float(urut.get(t, 0)), 2), "awal": round(float(ada.iloc[0]), 2) if len(ada) else None,
                      "akhir": round(float(ada.iloc[-1]), 2) if len(ada) else None,
                      "harga": [{"hari": h, "harga": (round(float(v), 2) if pd.notna(v) else None)} for h, v in s.reindex(hari).items()]})
    return {"data": hasil, "jumlah": int(len(urut))}


def _dalam(df, mulai, akhir):
    """Baris dengan tanggal pembelian di antara mulai dan akhir (inklusif)."""
    return df[(df["hari"] >= tgl(mulai)) & (df["hari"] <= tgl(akhir))]


def _banding(df, filt, dari, sampai, mulai_data):
    """KPI jumlah hari yang sama tepat sebelum rentang tampilan, dari seluruh baris yang dimuat (termasuk periode sebelumnya)."""
    if any(filt[k] for k in FILTER_TANPA_BANDING):
        return None
    ps, pe = jendela_sebelumnya(dari, sampai)
    if "lalu" not in df.columns and pd.Timestamp(ps) < pd.Timestamp(mulai_data):
        return None   # data lama tanpa periode sebelumnya
    return {"mulai": tgl(ps), "akhir": tgl(pe), "kpi": U.kpi(saring(_dalam(df, ps, pe), filt, DIM))}


def bangun(df, ds, filt=None):
    kini_semua, _, pilihan = _siapkan(df)
    dari, sampai = rentang_tampil(ds, hari=konfigurasi.TBS_HARI_TREN)
    filt = _rapikan(kini_semua, pilihan, filt or {})
    kini = _dalam(kini_semua, dari, sampai)
    d = saring(kini, filt, DIM)
    tanpa = lambda nama: saring(kini, filt, DIM, lewati=nama)
    akhir_data = sampai
    awal_tren = dari
    tren = U.harian(tanpa("tanggal"), awal_tren, akhir_data)
    riwayat = saring(df, filt, DIM, lewati=FILTER_TANPA_FORECAST)   # forecast: seluruh riwayat yang dimuat, tidak dipotong rentang tampilan
    supplier, jumlah_supplier = _per(tanpa("supplier"), "supplier", konfigurasi.TBS_TOP_SUPPLIER, filt["supplier"])
    tipe, jumlah_tipe = _per(tanpa("tipe"), "tipe", konfigurasi.TBS_TOP_TIPE, filt["tipe"])
    grup, jumlah_grup = _per(tanpa("grup"), "grup", konfigurasi.TBS_TOP_SUPPLIER, filt["grup"])
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": konfigurasi.TBS_HARI_TREN},
        "kpi": U.kpi(d),
        "banding": _banding(df, filt, dari, sampai, ds.mulai),
        "filter": [{"kunci": k, "nama": nama, "panel": panel} for k, nama, _, panel in FILTER],
        "tren": [{"hari": t.strftime("%Y-%m-%d"), "netto": round(float(r["netto"]), 2), "nilai": round(float(r["nilai"]), 2)} for t, r in tren.iterrows()],
        "forecast": U.forecast(riwayat, U.akhir_lengkap(df)),
        "per_hari_minggu": _per_hari_minggu(tanpa("hari_minggu"), dari, akhir_data),
        "per_tipe": {"data": tipe, "jumlah": jumlah_tipe},
        "per_grup": {"data": grup, "jumlah": jumlah_grup},
        "per_supplier": {"data": supplier, "jumlah": jumlah_supplier},
        "harga_tipe": _harga_tipe(tanpa("tipe"), awal_tren, akhir_data, filt["tipe"]),
        "tren_mulai": awal_tren.strftime("%Y-%m-%d"),
        "pilihan": pilihan,
    }


def _per_supplier_tabel(d):
    g = d.groupby("supplier").agg(grup=("grup", "first"), tipe=("tipe", "first"), netto=("netto", "sum"), nilai=("nilai", "sum"),
                                  hari_kirim=("hari", "nunique"), terakhir=("tgl", "max")).reset_index()
    g["harga"] = (g["nilai"] / g["netto"].where(g["netto"] > 0)).round(2)
    return g


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'pembelian': satu baris per detail pembelian (jumlah netto sama dengan kartu Total Netto). 'supplier': satu baris per supplier."""
    kolom = KOLOM_PEMBELIAN if jenis == "pembelian" else KOLOM_SUPPLIER
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    kini, _, pilihan = _siapkan(df)
    dari, sampai = rentang_tampil(ds, hari=konfigurasi.TBS_HARI_TREN)
    d = saring(_dalam(kini, dari, sampai), _rapikan(kini, pilihan, filt or {}), DIM)
    if jenis == "pembelian":
        hasil = susun(d.reset_index(drop=True), kolom, KOLOM_CARI, cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="purchase_id")
    else:
        hasil = susun(_per_supplier_tabel(d), kolom, ["supplier", "grup", "tipe"], cari, urut, arah, "netto", "desc", halaman, ukuran)
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
