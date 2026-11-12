"""Kartu, grafik, dan tabel detail laporan Weighbridge. Cross filter sama dengan PR/PO."""
import numpy as np
import pandas as pd

from inti import konfigurasi
from inti.banding import bagi, jendela_sebelumnya
from inti.filter import FilterTidakValid, daftar, kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from . import ukuran as U

# (kunci di URL, label, kolom data, tampil di panel filter). Filter tanpa panel diisi dengan klik grafik: tiket (titik sebaran), tanggal
# (tren harian), dan jam (peta operator per jam).
FILTER = [
    ("perusahaan", "Perusahaan", "comp", True), ("transaksi", "Jenis Transaksi", "jenis", True), ("risiko", "Indikator Risiko", "risiko", True), ("operator", "Operator", "operator", True),
    ("kendaraan", "No. Kendaraan", "kendaraan", True), ("supplier", "Supplier", "supplier", True), ("customer", "Customer", "customer", True),
    ("supir", "Nama Supir", "supir", True),
    ("produk", "Produk", "produk", True), ("split", "Splitted", "split", True), ("tiket", "No. Tiket", "ticket_no", False), ("tanggal", "Tanggal", "hari", False),
    ("jam", "Jam Masuk", "jam", False),
]
DIM = {kunci: kolom for kunci, _, kolom, _ in FILTER}
KOLOM_CARI = ["ticket_no", "kendaraan", "supir", "supplier", "kode_supplier", "customer", "kode_customer", "operator", "produk", "comp", "risiko", "jenis"]
KOLOM_DETAIL = [
    ("ticket_no", "No. Tiket", "teks"), ("tgl", "Tanggal", "tanggal"), ("masuk", "Waktu Masuk", "waktu"),
    ("keluar", "Waktu Keluar", "waktu"), ("jenis", "Jenis Transaksi", "teks"), ("produk", "Produk", "teks"), ("kendaraan", "No. Kendaraan", "teks"),
    ("operator", "Operator", "teks"), ("supir", "Nama Supir", "teks"), ("supplier", "Supplier", "teks"), ("customer", "Customer", "teks"), ("durasi", "Durasi (menit)", "angka"),
    ("bruto", "Bruto", "angka"), ("tara_aktual", "Tara Aktual", "angka"), ("tara_historis", "Tara Historis Maks", "angka"),
    ("tara_selisih", "Selisih Tara", "angka"), ("netto", "Netto", "angka"), ("potongan", "Potongan", "angka"),
    ("split", "Splitted", "teks"), ("risiko", "Indikator Risiko", "teks"), ("comp", "Perusahaan", "teks"),
]
JENIS_DETAIL = {"semua": "Semua transaksi", "berisiko": "Berisiko"}

_cache_pilihan = {}   # id(df) -> (df, pilihan)
FILTER_TANPA_BANDING = ("tiket", "tanggal")   # menunjuk transaksi atau hari periode ini; tidak ada padanannya di periode sebelumnya


def _hitung_pilihan(df):
    banyak = lambda k: df[k].value_counts().index.tolist()
    urut = lambda k: sorted(df[k].unique().tolist(), key=lambda s: (s == "(kosong)", s.lower()))
    return {"perusahaan": sorted(df["comp"].unique().tolist()), "transaksi": banyak("jenis"),   # kunci bukan "jenis": itu nama tab tabel detail
            "risiko": [r for r in U.URUTAN_RISIKO if r in set(df["risiko"])],
            "operator": banyak("operator"), "kendaraan": banyak("kendaraan"), "supplier": urut("supplier"), "customer": urut("customer"), "supir": urut("supir"),
            "produk": banyak("produk"), "split": sorted(df["split"].unique().tolist(), reverse=True)}   # Ya lebih dulu


def _pilihan(df):
    simpan = _cache_pilihan.get(id(df))
    if simpan and simpan[0] is df:
        return simpan[1]
    p = _hitung_pilihan(df)
    if len(_cache_pilihan) >= konfigurasi.MAKS_DATASET:
        _cache_pilihan.clear()
    _cache_pilihan[id(df)] = (df, p)
    return p


def _tanpa_daftar(df, kolom, nilai, nama):
    """Filter yang pilihannya tidak ditampilkan di panel (terlalu banyak atau diisi dari grafik): cukup dicek ada di data."""
    nilai = daftar(nilai)
    ada = set(df[kolom].values)
    salah = [v for v in nilai if v not in ada]
    if salah:
        raise FilterTidakValid(f"{nama} '{salah[0]}' tidak ada di data ini")
    return sorted(set(nilai))


def _rapikan(df, filt):
    p = _pilihan(df)
    # Penjualan adalah pilihan awal di tampilan. Data tanpa transaksi penjualan (mis. satu perusahaan saja) tidak dianggap filter salah.
    filt = {**filt, "transaksi": [v for v in daftar(filt.get("transaksi")) if v in p["transaksi"]]}
    hasil = {k: kanonik(filt.get(k), p[k], nama) for k, nama, _, panel in FILTER if panel}
    hasil.update({k: _tanpa_daftar(df, kolom, filt.get(k), nama) for k, nama, kolom, panel in FILTER if not panel})
    return hasil, p


def _bulat(x):
    return int(x) if float(x) == int(x) else round(float(x), 2)


def _sebaran(d, terpilih):
    """Titik durasi lawan selisih tara. Kalau terlalu banyak, disampel merata; titik ekstrem dan yang dipilih selalu ikut."""
    d = d.dropna(subset=["durasi", "tara_selisih"])
    total = len(d)
    maks, ekstrem_n = konfigurasi.PALM_MAKS_TITIK, konfigurasi.PALM_TITIK_EKSTREM
    if total > maks:
        ekstrem = pd.concat([d[d["ticket_no"].isin(terpilih)], d.nlargest(ekstrem_n, "durasi"),
                             d.assign(_m=d["tara_selisih"].abs()).nlargest(ekstrem_n, "_m").drop(columns="_m")])
        ekstrem = ekstrem[~ekstrem.index.duplicated()]
        sisa = d.drop(index=ekstrem.index)
        urut = np.linspace(0, len(sisa) - 1, max(maks - len(ekstrem), 0)).astype(int)
        d = pd.concat([ekstrem, sisa.iloc[urut]])
    titik = [{"tiket": r.ticket_no, "kendaraan": r.kendaraan, "durasi": _bulat(r.durasi), "tara": _bulat(r.tara_selisih),
              "risiko": U.KUNCI_RISIKO[r.risiko]} for r in d.itertuples()]
    return {"titik": titik, "total": int(total), "ditampilkan": len(titik)}


def _kendaraan(d, terpilih):
    """Rata-rata selisih tara per kendaraan, dari yang paling jauh menyimpang (naik atau turun)."""
    d = d.dropna(subset=["tara_selisih"])
    if d.empty:
        return []
    g = d.groupby("kendaraan")["tara_selisih"]
    t = pd.DataFrame({"jumlah": g.size(), "rata": g.mean(), "min": g.min(), "maks": g.max()})
    t = t.assign(_abs=t["rata"].abs()).sort_values(["_abs", "jumlah"], ascending=False, kind="stable")
    atas = t.head(konfigurasi.PALM_TOP_KENDARAAN)
    atas = pd.concat([atas, t[t.index.isin(terpilih) & ~t.index.isin(atas.index)]])
    return [{"kendaraan": k, "jumlah": int(r["jumlah"]), "rata": _bulat(round(r["rata"], 2)), "min": _bulat(r["min"]), "maks": _bulat(r["maks"])}
            for k, r in atas.iterrows()]


def _supplier(d, terpilih):
    """Dua urutan: menurut jumlah transaksi, dan menurut persentase berisiko (hanya supplier dengan minimal PALM_MIN_TRANSAKSI_PERSEN transaksi,
    supaya supplier dengan satu-dua transaksi tidak langsung 100%)."""
    t = _hitung_risiko(d, "supplier").drop(columns="berisiko")
    n = konfigurasi.PALM_TOP_SUPPLIER
    tambah = lambda atas: pd.concat([atas, t[t.index.isin(terpilih) & ~t.index.isin(atas.index)]])
    baris = lambda atas: [{"supplier": k, **{c: int(v) for c, v in r.items()}} for k, r in tambah(atas).iterrows()]
    cukup = t[t["total"] >= konfigurasi.PALM_MIN_TRANSAKSI_PERSEN]
    persen = cukup.assign(_p=(cukup["total"] - cukup["normal"]) / cukup["total"]).sort_values(["_p", "total"], ascending=False, kind="stable")
    return {"data": baris(t.sort_values("total", ascending=False, kind="stable").head(n)), "data_persen": baris(persen.drop(columns="_p").head(n)),
            "jumlah_supplier": int(len(t)), "jumlah_supplier_persen": int(len(cukup)), "min_transaksi": konfigurasi.PALM_MIN_TRANSAKSI_PERSEN}


def _hitung_risiko(d, kolom):
    """Per nilai kolom: total, berisiko, dan jumlah per indikator (normal, tara, durasi)."""
    t = d.groupby([kolom, "risiko"]).size().unstack(fill_value=0).reindex(columns=U.URUTAN_RISIKO, fill_value=0)
    t.columns = [U.KUNCI_RISIKO[c] for c in t.columns]
    t["total"] = t.sum(axis=1)
    t["berisiko"] = t["total"] - t["normal"]
    return t


def _tren(d, mulai, akhir):
    """Jumlah transaksi berisiko per hari dari `mulai` sampai `akhir` (hari tanpa transaksi bernilai nol). Seluruh periode yang dimuat dikirim;
    tampilan memilih rentang yang digambar tanpa meminta data lagi."""
    hari = pd.date_range(pd.Timestamp(mulai), pd.Timestamp(akhir)).strftime("%Y-%m-%d")
    t = _hitung_risiko(d[d["hari"].isin(hari)], "hari").reindex(hari, fill_value=0)
    return [{"hari": h, "total": int(r["total"]), "tara": int(r["tara"]), "durasi": int(r["durasi"]), "berisiko": int(r["berisiko"])}
            for h, r in t.iterrows()]


def _pelanggar(d, kolom, terpilih):
    """Nilai dengan transaksi WARNING terbanyak (pelanggar berulang), beserta persentasenya terhadap semua transaksinya."""
    t = _hitung_risiko(d[d[kolom] != "(kosong)"], kolom)
    t = t[(t["berisiko"] > 0) | t.index.isin(terpilih)].assign(persen=lambda x: x["berisiko"] / x["total"])
    atas = t.sort_values(["berisiko", "persen"], ascending=False, kind="stable").head(konfigurasi.PALM_TOP_PELANGGAR)
    atas = pd.concat([atas, t[t.index.isin(terpilih) & ~t.index.isin(atas.index)]])
    return [{"nama": k, "berisiko": int(r["berisiko"]), "tara": int(r["tara"]), "durasi": int(r["durasi"]), "total": int(r["total"]),
             "persen": round(float(r["persen"]), 4)} for k, r in atas.iterrows()]


def _operator_jam(d, terpilih):
    """Peta operator x jam masuk: transaksi dan yang berisiko per sel, untuk operator dengan transaksi terbanyak."""
    d = d[d["jam"] != "(kosong)"]
    per_op = d["operator"].value_counts()
    operator = per_op.head(konfigurasi.PALM_TOP_OPERATOR).index.tolist()
    operator += [o for o in terpilih if o in per_op.index and o not in operator]
    d = d[d["operator"].isin(operator)]
    t = d.assign(_b=d["risiko"] != U.NORMAL).groupby(["operator", "jam"])["_b"].agg(["size", "sum"])
    return {"operator": operator, "jam": sorted(d["jam"].unique().tolist()),
            "sel": [{"operator": o, "jam": j, "total": int(r["size"]), "berisiko": int(r["sum"])} for (o, j), r in t.iterrows()]}


def _dalam(df, mulai, akhir):
    """Baris dengan tanggal transaksi di antara mulai dan akhir (inklusif)."""
    return df[(df["hari"] >= tgl(mulai)) & (df["hari"] <= tgl(akhir))]


def _banding(semua, filt, dari, sampai, mulai_data):
    """KPI jumlah hari yang sama tepat sebelum rentang tampilan, dari seluruh baris yang dimuat (termasuk periode sebelumnya)."""
    if any(filt[k] for k in FILTER_TANPA_BANDING):
        return None
    ps, pe = jendela_sebelumnya(dari, sampai)
    if "lalu" not in semua.columns and pd.Timestamp(ps) < pd.Timestamp(mulai_data):
        return None   # data lama tanpa periode sebelumnya
    return {"mulai": tgl(ps), "akhir": tgl(pe), "kpi": U.kpi(saring(_dalam(semua, ps, pe), filt, DIM))}


def bangun(semua, ds, filt=None):
    kini, _ = bagi(semua)
    dari, sampai = rentang_tampil(ds, hari=konfigurasi.PALM_HARI_TREN)
    filt, pilihan = _rapikan(kini, filt or {})
    df = _dalam(kini, dari, sampai)
    d = saring(df, filt, DIM)
    tanpa = lambda nama: saring(df, filt, DIM, lewati=nama)

    hitung = tanpa("risiko")["risiko"].value_counts()
    mitra = "customer" if filt["transaksi"] == ["Penjualan"] else "supplier"
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": konfigurasi.PALM_HARI_TREN},
        "kpi": U.kpi(d),
        "banding": _banding(semua, filt, dari, sampai, ds.mulai),
        "ambang": {"tara_kg": U.AMBANG_TARA, "durasi_menit": U.AMBANG_DURASI},
        "filter": [{"kunci": k, "nama": nama, "panel": panel and k not in _tersembunyi(filt)} for k, nama, _, panel in FILTER],
        "indikator": [{"kunci": U.KUNCI_RISIKO[r], "nama": r} for r in U.URUTAN_RISIKO],
        "risiko": [{"kunci": U.KUNCI_RISIKO[r], "nama": r, "jumlah": int(hitung.get(r, 0))} for r in U.URUTAN_RISIKO],
        # Angka pada pengalih Penjualan / Pembelian di kepala laporan: jumlah tiap jenis dengan filter lain tetap berlaku
        "jumlah_jenis": {k: int(v) for k, v in tanpa("transaksi")["jenis"].value_counts().items()},
        "tara_kendaraan": _kendaraan(tanpa("kendaraan"), filt["kendaraan"]),
        # Penjualan: per customer; Pembelian dan Semua: per supplier. Baris tanpa nama (mis. Penjualan saat Semua) tidak ikut.
        "risiko_supplier": {**_supplier(tanpa((mitra, "risiko")).pipe(lambda x: x[x[mitra] != "(kosong)"]).assign(supplier=lambda x: x[mitra]),
                                        filt[mitra]), "dimensi": mitra},
        "sebaran": _sebaran(tanpa("tiket"), filt["tiket"]),
        "tren": _tren(tanpa("tanggal"), dari, sampai),
        "pelanggar": {"kendaraan": _pelanggar(tanpa("kendaraan"), "kendaraan", filt["kendaraan"]),
                      "supir": _pelanggar(tanpa("supir"), "supir", filt["supir"]),
                      "supplier": _pelanggar(tanpa("supplier"), "supplier", filt["supplier"])},
        "operator_jam": _operator_jam(tanpa(("operator", "jam")), filt["operator"]),
        "pilihan": _pilihan_per_jenis(kini, filt, pilihan),
    }


def _pilihan_per_jenis(df, filt, pilihan):
    """Kalau Jenis Transaksi dipilih (Pembelian atau Penjualan), menu filter lain hanya berisi nilai dari jenis itu, mis. produk TBS untuk
    Pembelian dan CPO, Kernel untuk Penjualan. Nilai yang sudah terpilih tetap ada di menu supaya bisa dilepas."""
    if not filt["transaksi"]:
        return pilihan
    sempit = _hitung_pilihan(df[df["jenis"].isin(filt["transaksi"])])
    hasil = {"transaksi": pilihan["transaksi"]}
    for k, nilai in sempit.items():
        if k != "transaksi":
            hasil[k] = nilai + [v for v in filt.get(k, []) if v not in nilai]
    return hasil


# Penjualan tidak punya supplier dan Pembelian tidak punya customer: filter dan kolomnya disembunyikan saat hanya satu jenis yang dipilih
SEMBUNYI_PER_JENIS = {"Penjualan": "supplier", "Pembelian": "customer"}


def _tersembunyi(filt):
    jenis = filt.get("transaksi") or []
    return {SEMBUNYI_PER_JENIS[jenis[0]]} if len(jenis) == 1 and jenis[0] in SEMBUNYI_PER_JENIS else set()


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'semua': semua transaksi sesuai filter (sama dengan kartu Transaksi). 'berisiko': yang bukan NORMAL."""
    periksa(jenis, JENIS_DETAIL, urut, KOLOM_DETAIL, arah)
    kini, _ = bagi(df)
    dari, sampai = rentang_tampil(ds, hari=konfigurasi.PALM_HARI_TREN)
    filt, _ = _rapikan(kini, filt or {})
    d = saring(_dalam(kini, dari, sampai), filt, DIM)
    t = (d if jenis == "semua" else d[d["risiko"] != U.NORMAL]).reset_index(drop=True)
    sembunyi = _tersembunyi(filt)
    kolom = [k for k in KOLOM_DETAIL if k[0] not in sembunyi]
    if urut in sembunyi:
        urut = None
    hasil = susun(t, kolom, KOLOM_CARI, cari, urut, arah, "tgl", "desc", halaman, ukuran, pembanding="ticket_no")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
