"""Ringkasan, tren mingguan, kartu grup dengan atensi, dan tabel atensi (bentuk Excel rekapan TBS mingguan) Pembelian TBS Mingguan.

Hanya minggu lengkap (Senin sampai Minggu) yang ditampilkan; minggu berjalan dan minggu pertama yang terpotong periode dibuang.
Perusahaan boleh dipilih lebih dari satu (kosong = semua); tonasenya dijumlahkan per minggu. Kalau lebih dari satu perusahaan tampil,
grup dibedakan per perusahaan supaya grup bernama sama di dua perusahaan tidak tercampur."""
import pandas as pd

from inti import konfigurasi
from inti.filter import kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from . import ukuran as U

# (kunci di URL, label, kolom data, tampil di panel filter)
FILTER = [
    ("perusahaan", "Perusahaan", "comp", True), ("kategori", "Kategori", "kategori", True), ("tipe", "Jenis Kebun", "tipe", True),
    ("grup", "Business Group", "grup", True),
]
DIM = {kunci: kolom for kunci, _, kolom, _ in FILTER}
URUT_KATEGORI = ["Kebun", "Agen", "Brondolan"]
MINGGU_TAMPIL = konfigurasi.TBS_MINGGUAN_MINGGU_TAMPIL
JENIS_DETAIL = {"atensi": "Per jenis kebun dan grup"}

_cache = {}   # id(df) -> (df, pilihan)


def _siapkan(df):
    simpan = _cache.get(id(df))
    if simpan and simpan[0] is df:
        return simpan[1]
    banyak = lambda k: df.groupby(k)["netto"].sum().sort_values(ascending=False).index.tolist()
    kategori = banyak("kategori")
    pilihan = {"perusahaan": list(dict.fromkeys(df["comp"])), "kategori": [k for k in URUT_KATEGORI if k in kategori] + [k for k in kategori if k not in URUT_KATEGORI],
               "tipe": banyak("tipe"), "grup": banyak("grup")}
    if len(_cache) >= konfigurasi.MAKS_DATASET:
        _cache.clear()
    _cache[id(df)] = (df, pilihan)
    return pilihan


def _rapikan(pilihan, filt):
    return {k: kanonik(filt.get(k), pilihan[k], nama) for k, nama, _, _ in FILTER}


def _angka(v, n=2):
    return None if v is None or pd.isna(v) else round(float(v), n)


def _rentang(ds):
    """Tanpa filter tanggal: MINGGU_TAMPIL minggu Senin-Minggu terakhir, walau data dimuat sejak awal tahun."""
    dari, sampai = rentang_tampil(ds)
    if getattr(ds, "dari", None) is None or getattr(ds, "sampai", None) is None:
        senin = sampai - pd.Timedelta(days=sampai.weekday())
        dari = max(dari, senin - pd.Timedelta(days=7 * (MINGGU_TAMPIL - 1)))
    return dari, sampai


def _persiapan(df, filt, ds):
    """(minggu lengkap, minggu dinilai, riwayat, data tersaring semua filter, banyak perusahaan). Minggu diambil dari data perusahaan
    terpilih tanpa filter lain, supaya minggu tanpa kiriman tetap ada sebagai 0. Filter tanggal (dari..sampai): hanya minggu lengkap yang
    seluruhnya di dalam rentang itu."""
    dari, sampai = _rentang(ds)
    dasar = saring(df, filt, DIM, lewati=[k for k in DIM if k != "perusahaan"])
    minggu = [m for m in U.daftar_minggu(dasar) if m["lengkap"] and m["awal"] >= dari and m["akhir"] <= sampai] if len(dasar) else []
    dinilai, riwayat = U.minggu_dinilai(minggu)
    d = saring(df, filt, DIM)
    d = d[d["minggu"].isin([m["minggu"] for m in minggu])]
    return minggu, dinilai, riwayat, d, dasar["comp"].nunique() > 1


def _pivot(d, indeks, kolom_minggu):
    if d.empty:
        return pd.DataFrame(columns=kolom_minggu, dtype=float)
    return d.pivot_table(index=indeks, columns="minggu", values="netto", aggfunc="sum").reindex(columns=kolom_minggu).fillna(0.0)


def _urut_kategori(k):
    return URUT_KATEGORI.index(k) if k in URUT_KATEGORI else len(URUT_KATEGORI)


def _baris_tabel(d, minggu, dinilai, riwayat, filt_grup):
    kunci = [m["minggu"] for m in minggu]
    t = _pivot(d, ["comp", "kategori", "tipe", "grup"], kunci)
    at = U.atensi(t, dinilai, riwayat)
    hasil = []
    for (comp, kategori, tipe, grup), seri in t.iterrows():
        if filt_grup and grup not in filt_grup:
            continue
        a = at.loc[(comp, kategori, tipe, grup)] if not at.empty else None
        hasil.append({"comp": comp, "kategori": kategori, "tipe": tipe, "grup": grup, "seri": [_angka(v, 0) for v in seri.tolist()],
                      "sd": _angka(a["sd"], 0) if a is not None else None, "rata": _angka(a["rata"], 0) if a is not None else None,
                      "selisih": _angka(a["selisih"], 0) if a is not None else None, "status": a["status"] if a is not None else None})
    hasil.sort(key=lambda r: (r["comp"], _urut_kategori(r["kategori"]), r["tipe"], r["grup"]))
    return hasil


def bangun(df, ds, filt=None):
    pilihan = _siapkan(df)
    filt = _rapikan(pilihan, filt or {})
    minggu, dinilai, riwayat, d, banyak = _persiapan(df, filt, ds)
    dari, sampai = _rentang(ds)
    kunci = [m["minggu"] for m in minggu]
    total = d.groupby("minggu")["netto"].sum().reindex(kunci, fill_value=0.0)

    # Kartu: satu per grup (per perusahaan kalau lebih dari satu perusahaan tampil)
    indeks = ["comp", "grup"] if banyak else ["grup"]
    tabel = _pivot(d, indeks, kunci)
    at = U.atensi(tabel, dinilai, riwayat)
    tipe = d.groupby(indeks + ["tipe"])["netto"].sum().reset_index().sort_values("netto", ascending=False).drop_duplicates(indeks).set_index(indeks)["tipe"]
    grup = []
    for k, seri in tabel.iterrows():
        a = at.loc[k] if not at.empty else None
        comp, nama = (k if banyak else (None, k))
        rata = a["rata"] if a is not None else None
        grup.append({
            "nama": nama, "comp": comp, "tipe": tipe.get(k), "tonase": _angka(seri.sum()), "seri": [_angka(v) for v in seri.tolist()],
            "rata": _angka(rata), "sd": _angka(a["sd"] if a is not None else None), "nilai": _angka(a["nilai"] if a is not None else None),
            "persen": _angka(a["selisih"] / rata * 100, 1) if a is not None and rata else None, "status": a["status"] if a is not None else None,
        })

    lalu = total[riwayat[-1]] if riwayat else None
    nilai = total[dinilai] if dinilai else None
    henti = [g for g in grup if g["status"] == "TURUN" and not g["nilai"]]
    return {
        "periode": {"mulai": tgl(minggu[0]["awal"]) if minggu else tgl(pd.Timestamp(ds.mulai)), "akhir": tgl(minggu[-1]["akhir"]) if minggu else tgl(pd.Timestamp(ds.akhir))},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "minggu", "bawaan": MINGGU_TAMPIL},
        "perusahaan": filt["perusahaan"] or pilihan["perusahaan"],
        "banyak_perusahaan": bool(banyak),
        "minggu": [{"minggu": m["minggu"], "awal": tgl(m["awal"]), "akhir": tgl(m["akhir"]), "netto": _angka(total[m["minggu"]])} for m in minggu],
        "dinilai": dinilai,
        "jumlah_riwayat": len(riwayat),
        "min_minggu": U.MIN_MINGGU,
        "batas_sd": U.BATAS,
        "ringkasan": {
            "nilai": _angka(nilai), "lalu": _angka(lalu), "persen_lalu": _angka((nilai - lalu) / lalu * 100, 1) if lalu else None,
            "rata": _angka(total[riwayat].mean()) if riwayat else None, "target": konfigurasi.TBS_MINGGUAN_TARGET_TON * 1000,
            "naik": int((at["status"] == "NAIK").sum()) if not at.empty else 0, "turun": int((at["status"] == "TURUN").sum()) if not at.empty else 0,
            "berhenti": len(henti),
        },
        "grup": grup,
        "tabel_baris": len(_baris_tabel(d, minggu, dinilai, riwayat, filt["grup"])),
        "filter": [{"kunci": k, "nama": nama, "panel": panel} for k, nama, _, panel in FILTER],
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'atensi': baris tabel atensi yang sama dengan dashboard, untuk Export Excel. Kolom minggu dalam kg."""
    pilihan = _siapkan(df)
    filt = _rapikan(pilihan, filt or {})
    minggu, dinilai, riwayat, d, _ = _persiapan(df, filt, ds)
    baris = _baris_tabel(d, minggu, dinilai, riwayat, filt["grup"])
    judul = lambda m: f"{m['awal'].strftime('%d/%m')} sd {m['akhir'].strftime('%d/%m/%Y')}"
    kolom = [("comp", "Perusahaan", "teks"), ("kategori", "Kategori", "teks"), ("tipe", "Jenis Kebun", "teks"), ("grup", "Grup", "teks")]
    kolom += [(f"m{i}", judul(m), "angka") for i, m in enumerate(minggu) if m["minggu"] != dinilai]
    kolom += [("sd", "Std Dev", "angka"), ("rata", "Mean", "angka"), ("selisih", "Difference", "angka")]
    kolom += [(f"m{i}", judul(m), "angka") for i, m in enumerate(minggu) if m["minggu"] == dinilai]
    kolom += [("status", "Atensi", "teks")]
    periksa(jenis, JENIS_DETAIL, urut, kolom, arah)
    t = pd.DataFrame([{**{k: r[k] for k in ("comp", "kategori", "tipe", "grup", "sd", "rata", "selisih")}, "status": r["status"] or "",
                       "_u": i, **{f"m{j}": v for j, v in enumerate(r["seri"])}} for i, r in enumerate(baris)],
                     columns=["comp", "kategori", "tipe", "grup", "sd", "rata", "selisih", "status", "_u"] + [f"m{j}" for j in range(len(minggu))])
    hasil = susun(t, kolom + [("_u", "", "angka")], ["comp", "kategori", "tipe", "grup"], cari, urut, arah, "_u", "asc", halaman, ukuran)
    hasil["kolom"] = hasil["kolom"][:-1]
    hasil["baris"] = [{k: v for k, v in b.items() if k != "_u"} for b in hasil["baris"]]
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(pd.Timestamp(ds.mulai)), "akhir": tgl(pd.Timestamp(ds.akhir))}, **hasil}
