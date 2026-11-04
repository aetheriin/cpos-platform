"""Kartu, grafik, dan tabel detail laporan Cash Flow. Cross filter sama dengan laporan lain.

Saldo adalah milik rekening, jadi grafik dan kartu saldo hanya mengikuti filter perusahaan dan rekening; filter lain (lawan transaksi,
jenis dokumen, pembuat, tanggal) menyaring mutasi masuk/keluar dan tabel.
Semua nilai sudah dalam rupiah (rekening valas dikonversi di sumber.py); rekening yang tetap tanpa kurs tidak dihitung dan disebutkan.
Data dimuat dari 1 Januari; rentang tampilan bawaannya bulan berjalan (awal bulan sampai hari ini), dan bulan lain dipilih lewat filter
tanggal. Grafik running balance tidak mengikuti rentang itu: semua bulan sampai bulan terpilih dikirim, layar memilih berapa bulan ke belakang. Istilah mengikuti rekening koran / file cashflow: kredit = uang keluar,
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
JENIS_DETAIL = {"bank": "Rekap saldo bank", "harian": "Rekap harian", "mutasi": "Mutasi", "giro": "Jasa giro"}
SATUAN = "IDR"
# Nama bank di data memakai banyak ejaan (BANK CIMB NIAGA A/C ..., CIMB-NIAGA, CIMB USD); rekap jasa giro mengelompokkannya per bank
NAMA_BANK = [("CIMB", "CIMB NIAGA"), ("MANDIRI", "MANDIRI"), ("OCBC", "OCBC"), ("BNI", "BNI"), ("BRI", "BRI"), ("BCA", "BCA")]


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


def _peta_bank(df):
    return {a: _nama_bank(b) for a, b in df.drop_duplicates("akun").set_index("akun")["bank"].items()}


def _nama_rekening(akun):
    """'SUN · BANK CIMB NIAGA A/C 8001996683' -> 'CIMB NIAGA 8001996683'."""
    return akun.split(" · ", 1)[-1].removeprefix("BANK ").replace(" A/C", "").strip()


def _nama_bank(teks):
    t = str(teks).upper()
    return next((nama for kata, nama in NAMA_BANK if kata in t), t)


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


def _ringkas_giro(g, saldo, peta_bank):
    """Rekap per bank lalu per rekening, seperti sheet BANK GIRO: giro, AVG balance (rata-rata saldo akhir harian di rentang), dan % giro
    per tahun (giro ÷ AVG balance × 12, dibagi jumlah bulan rentang). Rekening bersaldo yang belum menerima giro ikut, supaya bulan berjalan
    tetap terisi. Semua dalam rupiah, termasuk rekening valas."""
    rata = saldo.mean() if not saldo.empty else pd.Series(dtype=float)
    nilai = g.groupby("akun")["nilai"].sum() if not g.empty else pd.Series(dtype=float)
    bulan = len(saldo.index.to_period("M").unique()) or 1
    persen = lambda n, r: _bulat(n / r * 12 / bulan, 8) if r and r > 0 else None
    baris = {}
    for akun in rata.index.union(nilai.index):
        n, r = float(nilai.get(akun, 0)), rata.get(akun)
        r = None if r is None or pd.isna(r) else float(r)
        if n or r:
            baris.setdefault(peta_bank.get(akun, _nama_bank(akun)), []).append({"akun": akun, "nilai": _bulat(n), "rata_saldo": _bulat(r), "imbal": persen(n, r)})
    bank = []
    for nama, isi in baris.items():
        n, r = sum(x["nilai"] for x in isi), sum(x["rata_saldo"] or 0 for x in isi)
        bank.append({"bank": nama, "nilai": _bulat(n), "rata_saldo": _bulat(r), "imbal": persen(n, r),
                     "rekening": sorted(isi, key=lambda x: -(x["rata_saldo"] or 0))})
    bank.sort(key=lambda b: -b["rata_saldo"])
    n, r = sum(b["nilai"] for b in bank), sum(b["rata_saldo"] for b in bank)
    return {"bank": bank, "total": _bulat(n), "rata_saldo": _bulat(r), "imbal": persen(n, r)}


def _saldo_bank(saldo, giro):
    """(kolom, tabel, kepala) tab Rekap saldo bank, seperti sheet SUMMARY: saldo akhir harian tiap rekening, dikelompokkan per perusahaan, dengan
    kolom Total dan baris Rata-rata. Kolom tanggal berupa teks hari/bulan/tahun supaya Rata-rata tetap di urutan terakhir dalam satu bulan.
    kepala: {kolom: (perusahaan, nama rekening)} untuk judul bertingkat di layar; judul kolom biasa (dipakai Excel) memuat keduanya."""
    akun = sorted((r["akun"] for b in giro["bank"] for r in b["rekening"]), key=lambda a: a.split(" · ")[0])   # stabil: dalam perusahaan tetap urut bank
    kepala = {f"r{i}": (a.split(" · ")[0], _nama_rekening(a)) for i, a in enumerate(akun)}
    kolom = [("hari", "Tanggal", "teks")] + [(k, f"{comp} {nama}", "angka") for k, (comp, nama) in kepala.items()] + [("total", "Total", "angka")]
    t = saldo[akun].copy()
    t.columns = [k for k, _, _ in kolom[1:-1]]
    t["total"] = t.sum(axis=1, min_count=1)
    rata = t.mean().to_frame().T
    t.insert(0, "hari", t.index.strftime("%d/%m/%Y"))
    rata.insert(0, "hari", "Rata-rata")
    return kolom, pd.concat([t, rata], ignore_index=True), kepala


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
    """(dari, sampai). Tanpa filter tanggal: awal bulan berjalan sampai akhir data (paling lambat hari ini)."""
    dari, sampai = rentang_tampil(ds)
    return (dari, sampai) if getattr(ds, "dari", None) is not None else (max(dari, sampai.replace(day=1)), sampai)


def _bulan_tersedia(ds):
    """Bulan yang bisa dipilih, terbaru dulu."""
    akhir = min(pd.Timestamp(ds.akhir), pd.Timestamp.today().normalize())
    return [str(p) for p in pd.period_range(pd.Timestamp(ds.mulai), max(akhir, pd.Timestamp(ds.mulai)), freq="M")][::-1]


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


def _per_bulan(t):
    """Debit, credit, dan ending balance tiap bulan dari tabel _harian; bulan terakhir sampai hari terakhirnya."""
    b = t.groupby(t["tgl"].dt.to_period("M")).agg(debit=("masuk", "sum"), kredit=("keluar", "sum"), saldo=("saldo", "last"))
    return [{"bulan": str(p), **{k: _bulat(v) for k, v in r.items()}} for p, r in b.iterrows()]


def _dokumen(d):
    """Debit dan kredit per jenis dokumen."""
    g = d.groupby("jenis_dok").agg(debit=("masuk", "sum"), kredit=("keluar", "sum"), jumlah=("nilai", "size"))
    g = g.assign(total=g["debit"] + g["kredit"]).sort_values("total", ascending=False)
    return [{"jenis": j, "debit": _bulat(r.debit), "kredit": _bulat(r.kredit), "jumlah": int(r.jumlah)} for j, r in g.iterrows()]


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
    g = _giro(df, filt, dari, sampai)
    valas = _dalam(df[df["mata_uang"] != SATUAN], dari, sampai)
    semua_hari = _harian(df, filt, ds, pd.Timestamp(ds.mulai), sampai)
    deret_hari, deret_bulan = _deret(semua_hari, dari)
    giro = _ringkas_giro(g, saldo, _peta_bank(df))
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "bulan": _bulan_tersedia(ds),
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
        "running": _per_bulan(semua_hari),
        "mitra": _mitra(tanpa("mitra")),
        "giro": giro,
        "filter": [{"kunci": k, "nama": nama, "panel": panel} for k, nama, _, panel in FILTER],
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    dari, sampai = _rentang(ds)
    filt, _ = _rapikan(df, filt or {})
    df, _ = _siap(df)
    kolom = {"giro": KOLOM_GIRO, "harian": KOLOM_HARIAN}.get(jenis, KOLOM_MUTASI)
    if jenis == "bank":
        saldo = _saldo_harian(df, filt, pd.date_range(dari, sampai))
        kolom, tabel, kepala = _saldo_bank(saldo, _ringkas_giro(_giro(df, filt, dari, sampai), saldo, _peta_bank(df)))
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    if jenis == "bank":
        hasil = susun(tabel, kolom, ["hari"], cari, urut, arah, "hari", "asc", halaman, ukuran)
        for k in hasil["kolom"]:
            if k["kunci"] in kepala:
                k["grup"], k["label"] = kepala[k["kunci"]]
    elif jenis == "harian":
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
        t["nilai_asli"] = t["nilai_asli"].abs()   # arah sudah ditunjukkan kolom Debit / Credit; di ledger uang keluar bertanda minus
        hasil = susun(t, KOLOM_MUTASI, KOLOM_CARI, cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="no")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
