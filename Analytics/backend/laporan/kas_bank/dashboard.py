"""Kartu, grafik, dan tabel detail laporan Cash Flow. Cross filter sama dengan laporan lain.

Saldo adalah milik rekening, jadi grafik dan kartu saldo hanya mengikuti filter perusahaan dan rekening; filter lain (lawan transaksi,
jenis dokumen, pembuat, tanggal) menyaring mutasi masuk/keluar dan tabel.
Semua nilai sudah dalam rupiah (rekening valas dikonversi di sumber.py); rekening yang tetap tanpa kurs tidak dihitung dan disebutkan.
Data dimuat dari 1 Januari; rentang tampilan bawaannya KAS_HARI_BAWAAN hari terakhir. Istilah mengikuti rekening koran / file cashflow: kredit = uang keluar,
debit = uang masuk; kredit/debit to date dihitung sejak awal data.
"""
import pandas as pd

from inti import konfigurasi
from inti.filter import FilterTidakValid, daftar, kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from .sumber import KOSONG

# (kunci di URL, label, kolom data, tampil di panel filter). Tanggal diisi dengan klik grafik harian.
FILTER = [
    ("perusahaan", "Perusahaan", "comp", True), ("rekening", "Rekening", "akun", True), ("dokumen", "Jenis Dokumen", "jenis_dok", True),   # bukan "jenis": itu nama tab tabel detail
    ("mitra", "Lawan Transaksi", "mitra", True), ("pembuat", "Pembuat Voucher", "pembuat", True), ("tanggal", "Tanggal", "hari", False),
]
DIM = {kunci: kolom for kunci, _, kolom, _ in FILTER}
FILTER_SALDO = ("perusahaan", "rekening")   # filter yang berlaku untuk saldo
KOLOM_CARI = ["no", "mitra", "akun", "keterangan", "pembuat", "jenis_dok"]
KOLOM_MUTASI = [
    ("tgl", "Tanggal", "tanggal"), ("no", "No. Dokumen", "teks"), ("jenis_dok", "Jenis", "teks"), ("mitra", "Lawan Transaksi", "teks"),
    ("akun", "Rekening", "teks"), ("masuk", "Debit", "angka"), ("keluar", "Credit", "angka"), ("saldo", "Balance", "angka"),
    ("mata_uang", "Mata Uang", "teks"), ("nilai_asli", "Nilai Asli", "angka"), ("kurs", "Kurs", "angka"), ("keterangan", "Keterangan", "teks"), ("pembuat", "Pembuat", "teks"),
]
KOLOM_GIRO = [
    ("tgl", "Tanggal", "tanggal"), ("no", "No. Voucher", "teks"), ("akun", "Rekening", "teks"), ("bank", "Bank", "teks"),
    ("nilai", "Jasa Giro", "angka"), ("mata_uang", "Mata Uang", "teks"), ("nilai_asli", "Nilai Asli", "angka"), ("kurs", "Kurs", "angka"),
]
KOLOM_HARIAN = [
    ("tgl", "Tanggal", "tanggal"), ("masuk", "Debit", "angka"), ("keluar", "Credit", "angka"), ("debit", "Debit to Date", "angka"),
    ("kredit", "Credit to Date", "angka"), ("saldo", "Ending Balance", "angka"), ("mutasi", "Transaksi", "angka"),
]
JENIS_DETAIL = {"harian": "Rekap harian", "mutasi": "Mutasi", "giro": "Jasa giro"}
SATUAN = "IDR"


def _pilihan(df):
    urut = lambda k: sorted((v for v in df[k].unique() if v != KOSONG), key=str.lower)
    return {"perusahaan": sorted(df["comp"].unique().tolist()), "rekening": urut("akun"), "dokumen": urut("jenis_dok"),
            "mitra": urut("mitra"), "pembuat": urut("pembuat")}


def _rapikan(df, filt):
    p = _pilihan(df)
    hasil = {k: kanonik(filt.get(k), p[k], nama) for k, nama, _, panel in FILTER if panel}
    hasil["tanggal"] = sorted(set(daftar(filt.get("tanggal"))))
    for h in hasil["tanggal"]:
        try:
            pd.Timestamp(h)
        except ValueError:
            raise FilterTidakValid(f"Tanggal '{h}' tidak valid") from None
    return hasil, p


def _saldo_harian(df, filt, hari):
    """DataFrame: indeks tanggal (hari), satu kolom per rekening, berisi saldo akhir hari (diteruskan ke hari tanpa mutasi)."""
    d = saring(df, {k: filt[k] for k in FILTER_SALDO}, DIM)
    kolom = {}
    for akun, g in d.groupby("akun", sort=False):
        s = g.groupby("tgl")["saldo"].last()   # baris sudah urut; per tanggal ambil saldo setelah mutasi terakhir
        kolom[akun] = s.reindex(s.index.union(hari)).sort_index().ffill().reindex(hari)
    return pd.DataFrame(kolom, index=hari)


def _bulat(x, digit=2):
    return None if x is None or pd.isna(x) else round(float(x), digit)


def _giro(df, filt, dari, sampai):
    g = pd.DataFrame(df.attrs.get("giro") or [])
    if g.empty:
        return g
    g["tgl"] = pd.to_datetime(g["tgl"])
    if filt["perusahaan"]:
        g = g[g["comp"].isin(filt["perusahaan"])]
    if filt["rekening"]:
        g = g[g["akun"].isin(filt["rekening"])]
    return g[(g["tgl"] >= dari) & (g["tgl"] <= sampai) & ~g["tanpa_kurs"].astype(bool)]


def _ringkas_giro(g, saldo):
    """Per rekening: jasa giro, rata-rata saldo harian di rentang, dan perbandingannya. Per bulan: total jasa giro."""
    if g.empty:
        return {"rekening": [], "bulan": [], "total": 0, "imbal": None}
    rata = saldo.mean() if not saldo.empty else pd.Series(dtype=float)
    # per rekening; nama bank di data giro bisa berbeda-beda untuk rekening yang sama
    per = g.groupby("akun", as_index=False).agg(bank=("bank", "first"), nilai=("nilai", "sum")).sort_values("nilai", ascending=False)
    baris = []
    for r in per.itertuples():
        rs = rata.get(r.akun)
        baris.append({"akun": r.akun, "bank": r.bank, "nilai": _bulat(r.nilai), "rata_saldo": _bulat(rs),
                      "imbal": _bulat(r.nilai / rs, 8) if rs and rs > 0 else None})
    bulan = g.groupby(g["tgl"].dt.strftime("%Y-%m"))["nilai"].sum()
    total_rata = saldo.sum(axis=1).mean() if not saldo.empty else None
    total = float(g["nilai"].sum())
    return {"rekening": baris, "bulan": [{"bulan": b, "nilai": _bulat(v)} for b, v in bulan.items()], "total": _bulat(total),
            "imbal": _bulat(total / total_rata, 8) if total_rata and total_rata > 0 else None}


def _mitra(d):
    """Lawan transaksi dengan uang keluar terbesar dan uang masuk terbesar, tanpa transfer antar rekening sendiri."""
    d = d[(d["mitra"] != KOSONG) & ~d["transfer"]]
    hasil = {}
    for arah in ("keluar", "masuk"):
        t = d[d[arah] > 0].groupby("mitra")[arah].agg(["sum", "size"]).sort_values("sum", ascending=False)
        hasil[arah] = [{"nama": n, "nilai": _bulat(r["sum"]), "jumlah": int(r["size"])} for n, r in t.head(konfigurasi.KAS_TOP_MITRA).iterrows()]
    return hasil


def _dalam(df, dari, sampai):
    return df[(df["tgl"] >= dari) & (df["tgl"] <= sampai) & ~df["awal"]]


def _siap(df):
    """(baris yang bisa dijumlahkan, rekening tanpa kurs). attrs ikut tersalin oleh pandas, jadi data giro tetap terbawa."""
    return df[~df["tanpa_kurs"]], sorted(df.loc[df["tanpa_kurs"], "akun"].unique())


def _rentang(ds):
    return rentang_tampil(ds, hari=konfigurasi.KAS_HARI_BAWAAN)


def _harian(df, filt, ds, dari, sampai):
    """Satu baris per hari dari..sampai: in, out, kredit/debit to date (kumulatif sejak awal data yang dimuat, 1 Januari), dan running
    balance (saldo akhir hari rekening terpilih). In/out mengikuti semua filter kecuali tanggal; klik tanggal hanya memilih barisnya."""
    hari = pd.date_range(min(pd.Timestamp(ds.mulai), dari), sampai)
    d = saring(_dalam(df, hari[0], sampai), filt, DIM, lewati="tanggal")
    g = d.groupby("tgl").agg(masuk=("masuk", "sum"), keluar=("keluar", "sum"), mutasi=("nilai", "size")).reindex(hari, fill_value=0)
    t = pd.DataFrame({"tgl": hari, "masuk": g["masuk"].values, "keluar": g["keluar"].values, "mutasi": g["mutasi"].values})
    t["debit"] = t["masuk"].cumsum()
    t["kredit"] = t["keluar"].cumsum()
    t["saldo"] = _saldo_harian(df, filt, hari).sum(axis=1, min_count=1).values
    t["hari"] = t["tgl"].dt.strftime("%Y-%m-%d")
    return t[t["tgl"] >= dari].reset_index(drop=True)


def _deret(t, dari):
    """Deret waktu rentang tampilan dari tabel _harian (yang dimulai di awal data): per hari, dan per bulan (bulan pertama/terakhir hanya
    hari di dalam rentang). Debit = masuk, kredit = keluar; kredit/debit to date dijumlahkan sejak awal data; saldo = saldo akhir hari/bulan."""
    hari = [{"hari": h, "debit": _bulat(m), "kredit": _bulat(k), "debit_td": _bulat(dt), "kredit_td": _bulat(kt), "saldo": _bulat(sd)}
            for h, m, k, dt, kt, sd, tg in zip(t["hari"], t["masuk"], t["keluar"], t["debit"], t["kredit"], t["saldo"], t["tgl"]) if tg >= dari]
    t = t[t["tgl"] >= dari]
    b = t.groupby(t["tgl"].dt.to_period("M")).agg(debit=("masuk", "sum"), kredit=("keluar", "sum"), debit_td=("debit", "last"),
                                                  kredit_td=("kredit", "last"), saldo=("saldo", "last"))
    bulan = [{"bulan": str(p), **{k: _bulat(v) for k, v in r.items()}} for p, r in b.iterrows()]
    return hari, bulan


def _dokumen(d):
    """Debit dan kredit per jenis dokumen."""
    g = d.groupby("jenis_dok").agg(debit=("masuk", "sum"), kredit=("keluar", "sum"), jumlah=("nilai", "size"))
    g = g.assign(total=g["debit"] + g["kredit"]).sort_values("total", ascending=False)
    return [{"jenis": j, "debit": _bulat(r.debit), "kredit": _bulat(r.kredit), "jumlah": int(r.jumlah)} for j, r in g.iterrows()]


def _ramalan(df, filt, ds, dari, sampai):
    """Running balance total per hari dalam rentang, ditambah perkiraan KAS_HARI_RAMAL hari ke depan: tren linier dari 60 hari terakhir,
    dengan batas bawah/atas = tren ± 1,96 × simpangan baku sisaan (mirip Forecast Sheet di Excel, tapi tanpa musiman)."""
    hari = pd.date_range(min(pd.Timestamp(ds.mulai), dari), sampai)
    total = _saldo_harian(df, filt, hari).sum(axis=1, min_count=1)
    titik = [{"hari": tgl(h), "saldo": _bulat(v)} for h, v in total.items() if h >= dari]
    dasar = total.dropna().iloc[-60:]
    n = konfigurasi.KAS_HARI_RAMAL
    if len(dasar) < 14 or not n:
        return titik
    x = (dasar.index - dasar.index[0]).days.to_numpy(dtype=float)
    import numpy as np
    a, b = np.polyfit(x, dasar.to_numpy(dtype=float), 1)
    sisa = float(np.std(dasar.to_numpy(dtype=float) - (a * x + b), ddof=1))
    titik[-1].update(ramal=titik[-1]["saldo"], bawah=titik[-1]["saldo"], atas=titik[-1]["saldo"])   # garis perkiraan menyambung dari hari terakhir
    for i in range(1, n + 1):
        h = sampai + pd.Timedelta(days=i)
        y = a * (x[-1] + i) + b
        lebar = 1.96 * sisa * (1 + i / len(x)) ** 0.5
        titik.append({"hari": tgl(h), "saldo": None, "ramal": _bulat(y), "bawah": _bulat(y - lebar), "atas": _bulat(y + lebar)})
    return titik


def bangun(df, ds, filt=None):
    dari, sampai = _rentang(ds)
    filt, pilihan = _rapikan(df, filt or {})
    df, tanpa_kurs = _siap(df)
    hari = pd.date_range(dari, sampai)
    tampil = _dalam(df, dari, sampai)
    d = saring(tampil, filt, DIM)
    tanpa = lambda nama: saring(tampil, filt, DIM, lewati=nama)

    saldo = _saldo_harian(df, filt, hari)
    total_saldo = saldo.sum(axis=1, min_count=1)
    patokan = pd.Timestamp(max(filt["tanggal"])) if filt["tanggal"] else sampai
    harian = tanpa("tanggal").groupby("hari")[["masuk", "keluar"]].sum()
    g = _giro(df, filt, dari, sampai)
    valas = _dalam(df[df["mata_uang"] != SATUAN], dari, sampai)
    deret_hari, deret_bulan = _deret(_harian(df, filt, ds, pd.Timestamp(ds.mulai), sampai), dari)
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": konfigurasi.KAS_HARI_BAWAAN},
        "satuan": SATUAN,
        # per mata uang asing: sumber kurs yang dipakai di rentang ini dan kurs terakhirnya; rekening tanpa kurs tidak dihitung
        "valas": [{"mata_uang": u, "sumber": sorted(set(g["sumber_kurs"])), "kurs": _bulat(g.sort_values("tgl")["kurs"].iloc[-1]),
                   "rekening": sorted(g["akun"].unique())} for u, g in valas.groupby("mata_uang")],
        "tanpa_kurs": tanpa_kurs,
        "kpi": {
            "saldo_akhir": _bulat(total_saldo.get(patokan)), "saldo_awal": _bulat(total_saldo.iloc[0]) if len(total_saldo) else None,
            "tanggal_saldo": tgl(patokan),
            "masuk": _bulat(d["masuk"].sum()), "jumlah_masuk": int((d["masuk"] > 0).sum()),
            "keluar": _bulat(d["keluar"].sum()), "jumlah_keluar": int((d["keluar"] > 0).sum()),
            "mutasi": int(len(d)), "hari": int(len(filt["tanggal"]) or len(hari)),
            "awal_data": tgl(pd.Timestamp(ds.mulai)),
            "jumlah_giro": int(len(g[g["hari"].isin(filt["tanggal"])] if filt["tanggal"] and not g.empty else g)),   # sama dengan tab Jasa giro
            # bagian masuk/keluar yang hanya pindah antar rekening sendiri, supaya total tidak dibaca sebagai uang baru
            "transfer_masuk": _bulat(d.loc[d["transfer"], "masuk"].sum()), "transfer_keluar": _bulat(d.loc[d["transfer"], "keluar"].sum()),
        },
        # lebih dari KAS_HARI_GRAFIK hari ditampilkan per bulan, selain itu per hari
        "deret": {"hari": deret_hari, "bulan": deret_bulan, "periode": "bulan" if len(hari) > konfigurasi.KAS_HARI_GRAFIK else "hari"},
        "dokumen": _dokumen(tanpa("dokumen")),
        # in/out per hari ikut di grafik running balance (seperti tabel kalkulasi di file cashflow)
        "running": [{**t, "masuk": _bulat(harian["masuk"].get(t["hari"], 0)), "keluar": _bulat(harian["keluar"].get(t["hari"], 0))}
                    if t.get("saldo") is not None else t for t in _ramalan(df, filt, ds, dari, sampai)],
        "mitra": _mitra(tanpa("mitra")),
        "giro": _ringkas_giro(g, saldo),
        "filter": [{"kunci": k, "nama": nama, "panel": panel} for k, nama, _, panel in FILTER],
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    kolom = {"giro": KOLOM_GIRO, "harian": KOLOM_HARIAN}.get(jenis, KOLOM_MUTASI)
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    dari, sampai = _rentang(ds)
    filt, _ = _rapikan(df, filt or {})
    df, _ = _siap(df)
    if jenis == "harian":
        t = _harian(df, filt, ds, dari, sampai)
        if filt["tanggal"]:
            t = t[t["hari"].isin(filt["tanggal"])]
        hasil = susun(t.reset_index(drop=True), KOLOM_HARIAN, ["hari"], cari, urut, arah, "tgl", "asc", halaman, ukuran)
    elif jenis == "giro":
        t = _giro(df, filt, dari, sampai)
        if filt["tanggal"] and not t.empty:
            t = t[t["hari"].isin(filt["tanggal"])]
        t = (t if not t.empty else pd.DataFrame(columns=[k for k, _, _ in KOLOM_GIRO])).reset_index(drop=True)
        hasil = susun(t, KOLOM_GIRO, ["no", "akun", "bank"], cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="no")
    else:
        t = saring(_dalam(df, dari, sampai), filt, DIM).reset_index(drop=True)
        hasil = susun(t, KOLOM_MUTASI, KOLOM_CARI, cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="no")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
