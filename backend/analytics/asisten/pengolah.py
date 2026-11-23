"""Pengolah jawaban Asisten: permintaan terstruktur (pembaca.py) -> angka, tabel, grafik, dan kalimat.

Angka dihitung dari data laporan yang sama dengan halaman laporannya (sudah disaring menurut cakupan perusahaan pengguna)."""
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from inti.umur import kelompok_umur

from . import kamus
from .pembaca import NAMA_BULAN, normal

MAKS_BARIS = 15        # kelompok yang ditampilkan di grafik/tabel
MAKS_DAFTAR = 20       # dokumen yang ditampilkan di daftar
NAMA_LAPORAN = {"outstanding": "Outstanding", "purchase_request": "Purchase Request", "purchase_order": "Purchase Order",
                "pi_pvr": "Purchase Invoice"}


class Memuat(Exception):
    """Data laporan sumber masih dimuat dari SQL Server."""

    def __init__(self, sumber):
        super().__init__(sumber)
        self.sumber = sumber


class TanpaAkses(Exception):
    def __init__(self, sumber):
        super().__init__(sumber)
        self.sumber = sumber


# ---------- buku konteks ----------

def muat_istilah(folder=Path(__file__).parent / "konteks"):
    """{judul: {"teks", "sebutan"}} dari konteks/*.md (judul "## ")."""
    hasil = {}
    for berkas in sorted(folder.glob("*.md")):
        judul, isi = None, []
        for baris in re.sub(r"<!--.*?-->", "", berkas.read_text(encoding="utf-8"), flags=re.S).splitlines() + ["## "]:
            if baris.startswith("## "):
                if judul:
                    sebutan = [s.strip() for b in isi if b.startswith("Sebutan:") for s in b[8:].split(",")]
                    hasil[judul] = {"teks": " ".join(b for b in isi if b.strip() and not b.startswith("Sebutan:")).strip(),
                                    "sebutan": [judul.casefold()] + [s.casefold() for s in sebutan if s]}
                judul, isi = baris[3:].strip(), []
            elif judul:
                isi.append(baris.strip())
    return hasil


def _cari_istilah(kata, istilah):
    kata = normal(kata)
    if not kata:
        return None
    nilai = []
    for judul, d in istilah.items():
        # frasa yang muncul utuh menang, yang lebih panjang lebih menang ("aging pr" mengalahkan "aging")
        skor = max(SequenceMatcher(None, kata, s).ratio() + (0.5 + len(s) / 100 if re.search(rf"\b{re.escape(s)}\b", kata) else 0)
                   for s in d["sebutan"])
        nilai.append((skor, judul))
    for k, u in kamus.UKURAN.items():
        skor = max(SequenceMatcher(None, kata, s).ratio() + (0.4 if re.search(rf"\b{re.escape(s)}\b", kata) else 0) for s in u["sebutan"])
        nilai.append((skor - 0.05, f"ukuran:{k}"))
    skor, judul = max(nilai)
    return judul if skor >= 0.75 else None


# ---------- format ----------

def rp(x):
    """Sama dengan rupiah() di frontend (lib/data.js): satuan ditulis, paling banyak satu desimal."""
    if x is None or pd.isna(x):
        return "-"
    a = abs(x)
    bagi, satuan = (1e12, " triliun") if a >= 1e12 else (1e9, " miliar") if a >= 1e9 else (1e6, " juta") if a >= 1e6 else (1, "")
    n = round(x / bagi, 1 if bagi > 1 else 0)
    teks = f"{n:,.1f}" if bagi > 1 and n != int(n) else f"{n:,.0f}"
    return "Rp " + teks.replace(",", "X").replace(".", ",").replace("X", ".") + satuan


def _bil(x):
    return f"{x:,.0f}".replace(",", ".")


def fmt(x, satuan):
    if satuan == "rp":
        return rp(x)
    if x is None or pd.isna(x):
        return "-"
    if satuan == "hari":
        return (f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")) + " hari"
    return f"{_bil(x)} {satuan}"


def _tgl(t):
    t = pd.Timestamp(t)
    return f"{t.day} {NAMA_BULAN[t.month - 1][:3]} {t.year}"


# ---------- data ----------

def _pemecah_untuk(nama, ukuran):
    """Nama pemecah yang sah untuk ukuran ini (supplier/customer ditukar sesuai hutang/piutang)."""
    u = kamus.UKURAN[ukuran]
    if nama == "siapa":
        return {"piutang": "customer", "jumlah_pr": "buyer", "lama_pr_po": "buyer", "item_pr": "buyer", "umur_pr": "buyer",
                "supplier_po": "pembuat", "jumlah_pi": "supplier", "nilai_pi": "supplier", "lama_pi_pvr": "pembuat",
                "lama_pi_pv": "supplier"}.get(ukuran, "supplier")
    jenis = (u.get("saring") or {}).get("jenis", [None])[0]
    if nama == "supplier" and jenis == "piutang":
        return "customer"
    if nama == "customer" and jenis != "piutang":
        return "supplier" if u["sumber"] != "pr" else None
    return nama


def _bisa(nama, ukuran):
    u = kamus.UKURAN[ukuran]
    p = kamus.PEMECAH[nama]
    if p.get("waktu"):
        return True
    if u["sumber"] not in p["kolom"]:
        return False
    hanya = (p.get("hanya") or {}).get(u["sumber"])
    return not hanya or (u.get("saring") or {}).get("jenis", [None])[0] in hanya


def _siapkan(df, sumber):
    if "aging" not in df.columns and "umur" in df.columns:
        df = df.assign(aging=[kelompok_umur(x) for x in df["umur"]])
    return df


def _saring(df, p, ukuran, periode, abaikan_periode=False):
    """Baris yang masuk hitungan dan daftar keterangan saringannya."""
    u = kamus.UKURAN[ukuran]
    s = kamus.SUMBER[u["sumber"]]
    for kolom, nilai in (u.get("saring") or {}).items():
        df = df[df[kolom].isin(nilai)]
    ket = []
    for i in p.get("status") or []:
        st = kamus.STATUS[i]
        kolom = st.get("kolom", "status")
        if st.get("sumber") and st["sumber"] != u["sumber"]:
            continue
        df = df[df[kolom].isin(st["nilai"])]
        if st.get("kosong"):                      # mis. PR belum disetujui: tanggal persetujuan masih kosong
            df = df[df[st["kosong"]].isna()]
        ket.append(("Status", st.get("label") or ", ".join(st["nilai"])))
    if p.get("perusahaan"):
        df = df[df["comp"].isin(p["perusahaan"])]
        ket.append(("Perusahaan", ", ".join(p["perusahaan"])))
    if periode and not abaikan_periode:
        kol = s["tanggal"]
        df = df[(df[kol] >= pd.Timestamp(periode["dari"])) & (df[kol] <= pd.Timestamp(periode["sampai"]))]
    return df, ket


_KOLOM_CARI = {"outstanding": ["mitra", "no_dok", "sumber", "keterangan"], "pr": ["itemname", "category", "buyer", "supplier_name", "prnumber"],
               "po": ["supplier_name", "itemname", "category", "creator", "po_number"],
               "pi": ["supplier_name", "itemname", "pi_by", "pi_number", "po_number"]}


def _saring_cari(df, cari, sumber):
    """Kata sisa (mis. "anpa") dicari di kolom nama. Hanya dipakai kalau ada yang cocok; selainnya diabaikan dan disebut di jawaban."""
    if not cari:
        return df, None
    if df.empty:
        return df, False
    kata = cari.split()
    for kol in _KOLOM_CARI[sumber]:
        if kol not in df.columns:
            continue
        teks = df[kol].astype(str).str.casefold()
        cocok = pd.Series(True, index=df.index)
        for k in kata:
            cocok &= teks.str.contains(re.escape(k), regex=True)
        if cocok.any():
            label = {"mitra": "Nama", "supplier_name": "Supplier", "itemname": "Barang", "category": "Kategori", "buyer": "Buyer",
                     "creator": "Dibuat oleh", "no_dok": "No. dokumen", "prnumber": "No. PR", "po_number": "No. PO", "sumber": "Sumber",
                     "keterangan": "Keterangan", "pi_by": "PI dibuat oleh", "pi_number": "No. PI"}[kol]
            return df[cocok], (label, f"memuat \"{cari}\"")
    return df, False


def _hitung(df, u):
    if u["hitung"] == "jumlah":
        return float(df[u["kolom"]].sum())
    if u["hitung"] == "rata":
        s = df[u["kolom"]].dropna()
        return float(s.mean()) if len(s) else None
    if u["hitung"] == "baris":
        return int(len(df))
    if u["hitung"] == "unik":
        return int(df[u["kolom"]].replace("", None).dropna().nunique())
    return int(df[["comp", u["nomor"]]].drop_duplicates().shape[0])


def _kelompok(df, u, nama, sumber):
    """Series nilai per kelompok."""
    p = kamus.PEMECAH[nama]
    if p.get("waktu"):
        kol = kamus.SUMBER[sumber]["tanggal"]
        df = df[df[kol].notna()]
        kunci = df[kol].dt.to_period(p["waktu"]).dt.start_time
    else:
        kol = p["kolom"][sumber]
        if p.get("banyak"):
            df = df.assign(**{kol: df[kol].astype(str).str.split(", ")}).explode(kol)
        kunci = df[kol].fillna("").astype(str).replace("", "(kosong)")
    g = df.assign(_k=kunci.values)
    if u["hitung"] == "jumlah":
        return g.groupby("_k")[u["kolom"]].sum()
    if u["hitung"] == "rata":
        return g.groupby("_k")[u["kolom"]].mean().dropna()
    if u["hitung"] == "baris":
        return g.groupby("_k").size()
    if u["hitung"] == "unik":
        return g.groupby("_k")[u["kolom"]].nunique()
    return g[["_k", "comp", u["nomor"]]].drop_duplicates().groupby("_k").size()


def _label_kelompok(k, nama):
    if nama == "bulan":
        return f"{NAMA_BULAN[k.month - 1][:3]} {k.year}"
    if nama == "minggu":
        return f"{k.day:02d}-{k.month:02d}-{k.year}"
    return str(k)


# ---------- jawaban ----------

def _lingkup(p, periode, s):
    bagian = []
    if p.get("perusahaan"):
        bagian.append(", ".join(p["perusahaan"]))
    if periode:
        bagian.append(periode["label"])
    elif s["posisi"]:
        bagian.append("saat ini")
    return " ".join(bagian)


def _tafsiran(p, u, nama_pemecah, periode, ket, info, ket_cari):
    t = [{"label": "Ukuran", "nilai": u["label"]}]
    if nama_pemecah:
        t.append({"label": "Per", "nilai": kamus.PEMECAH[nama_pemecah]["label"]})
    t += [{"label": a, "nilai": b} for a, b in ket]
    if ket_cari:
        t.append({"label": ket_cari[0], "nilai": ket_cari[1]})
    if periode:
        t.append({"label": "Periode", "nilai": f"{periode['label']} ({_tgl(periode['dari'])} sampai {_tgl(periode['sampai'])})"})
    elif kamus.SUMBER[u["sumber"]]["posisi"]:
        t.append({"label": "Periode", "nilai": "semua dokumen yang belum lunas"})
    else:
        t.append({"label": "Periode", "nilai": f"data {_tgl(info['mulai'])} sampai {_tgl(info['akhir'])}"})
    return t


def _saran(p, u_kunci, nama_pemecah, perusahaan_dikenal):
    u = kamus.UKURAN[u_kunci]
    hasil = []
    if not nama_pemecah:
        for k in ("perusahaan", "supplier", "customer", "buyer", "bulan"):
            if _bisa(k, u_kunci) and len(hasil) < 3:
                hasil.append(f"per {kamus.PEMECAH[k]['label'].lower()}")
    else:
        if not p.get("n") and not kamus.PEMECAH[nama_pemecah].get("waktu"):
            hasil.append("10 terbesar")
        if nama_pemecah != "bulan" and _bisa("bulan", u_kunci) and not kamus.SUMBER[u["sumber"]]["posisi"]:
            hasil.append("per bulan")
    lain = [k for k in perusahaan_dikenal if k not in (p.get("perusahaan") or [])][:2]
    if lain:
        hasil.append(f"kalau {lain[0]}?")
    if p.get("perusahaan"):
        hasil.append("semua perusahaan")
    if p.get("maksud") != "daftar":
        hasil.append("daftar dokumennya")
    return hasil[:5]


def jawab_angka(p, ambil, perusahaan_dikenal):
    ukuran = p.get("ukuran")
    if not ukuran and p.get("status"):
        st = kamus.STATUS[p["status"][0]]
        ukuran = st.get("ukuran")
    if not ukuran:
        return None
    u = kamus.UKURAN[ukuran]
    sumber = u["sumber"]
    s = kamus.SUMBER[sumber]
    df, info = ambil(sumber)
    df = _siapkan(df, sumber)
    p = {**p, "ukuran": ukuran}

    nama_pemecah = p.get("pemecah")
    pesan_pemecah = None
    if nama_pemecah:
        ganti = _pemecah_untuk(nama_pemecah, ukuran)
        if ganti is None or not _bisa(ganti, ukuran):
            bisa = [kamus.PEMECAH[k]["label"].lower() for k in kamus.PEMECAH if _bisa(k, ukuran)]
            pesan_pemecah = f"{u['label']} tidak bisa dipecah per {kamus.PEMECAH[nama_pemecah]['label'].lower() if nama_pemecah in kamus.PEMECAH else nama_pemecah}. Bisa per: {', '.join(bisa)}."
            nama_pemecah = None
        else:
            nama_pemecah = ganti
    if nama_pemecah == "perusahaan" and len(p.get("perusahaan") or []) == 1:
        nama_pemecah = None   # satu perusahaan dipecah per perusahaan = satu angka
    p["pemecah"] = nama_pemecah

    periode = p.get("periode")
    if periode and not s["posisi"]:
        # data laporan hanya sejak awal periode bawaan; periode di luarnya disebut terus terang
        if pd.Timestamp(periode["dari"]) < pd.Timestamp(info["mulai"]):
            return {"teks": f"Data {NAMA_LAPORAN[s['laporan']]} yang dibaca Asisten mulai {_tgl(info['mulai'])}. "
                            f"Untuk {periode['label']}, buka laporan {NAMA_LAPORAN[s['laporan']]} dan ubah periodenya.",
                    "laporan": {"id": s["laporan"], "nama": NAMA_LAPORAN[s["laporan"]]}, "permintaan": p}
    banding = p.get("banding")
    if banding and not periode:
        h = date.today()
        periode = {"dari": date(h.year, h.month, 1).isoformat(), "sampai": h.isoformat(), "label": "bulan ini"}
        p["periode"] = periode

    d, ket = _saring(df, p, ukuran, periode)
    d, ket_cari = _saring_cari(d, p.get("cari"), sumber)
    catatan = []
    if pesan_pemecah:
        catatan.append(pesan_pemecah)
    if ket_cari is False and p.get("hanya_cari"):
        return None
    if ket_cari is False:
        catatan.append(f"Kata \"{p['cari']}\" tidak saya kenali dan tidak ditemukan di data, jadi tidak dipakai.")
        ket_cari = None
    if p.get("diwarisi"):
        catatan.append("Melanjutkan pertanyaan sebelumnya.")

    hasil = {"tafsiran": _tafsiran(p, u, nama_pemecah, periode, ket, info, ket_cari),
             "laporan": {"id": s["laporan"], "nama": NAMA_LAPORAN[s["laporan"]]}, "permintaan": p, "catatan": catatan,
             "saran": _saran(p, ukuran, nama_pemecah, perusahaan_dikenal), "arti": u["arti"]}
    lingkup = _lingkup(p, periode, s)

    if p.get("maksud") == "daftar":
        return {**hasil, **_daftar(d, p, u, sumber, lingkup)}

    if banding:
        pb = p.get("periode_banding")
        if not pb or (periode["label"] == "bulan ini" and pb["label"] == "bulan lalu"):
            pb = _periode_sebelum(periode)
        d2, _ = _saring(df, p, ukuran, pb)
        d2, _ = _saring_cari(d2, p.get("cari"), sumber)
        return {**hasil, **_banding(d, d2, p, u, sumber, nama_pemecah, periode, pb)}

    if not nama_pemecah:
        nilai = _hitung(d, u)
        tambahan, terbesar = [], ""
        if u["hitung"] != "dokumen" and len(d):
            tambahan.append(f"{_bil(d[['comp', u['nomor']]].drop_duplicates().shape[0])} dokumen")
        mitra = {"outstanding": "mitra", "po": "supplier_name", "pi": "supplier_name"}.get(sumber)
        if u["hitung"] == "jumlah" and mitra and len(d):
            per = d.groupby(mitra)[u["kolom"]].sum().sort_values(ascending=False)
            nama_mitra = "customer" if (u.get("saring") or {}).get("jenis") == ["piutang"] else "supplier"
            tambahan.append(f"{_bil((per > 0.5).sum())} {nama_mitra}")
            if len(per) and per.iloc[0] > 0:
                terbesar = f" Terbesar: {per.index[0]} ({rp(per.iloc[0])})."
        if not len(d):
            return {**hasil, "teks": f"Tidak ada {u['label'].lower()}{' ' + lingkup if lingkup else ''}."}
        status = ", ".join(v for k, v in ket if k == "Status")
        teks = f"{u['label']}{f' ({status})' if status else ''}{' ' + lingkup if lingkup else ''}: {fmt(nilai, u['satuan'])}"
        teks += f" ({', '.join(tambahan)})." if tambahan else "."
        teks += terbesar
        if u["hitung"] == "dokumen" and sumber in ("pr", "po") and p.get("status") and len(d):
            umur = d.groupby(["comp", u["nomor"]])["umur"].max()
            lewat = int((umur > 30).sum())
            teks += f" Paling lama {_bil(umur.max())} hari" + (f"; {_bil(lewat)} lebih dari 30 hari." if lewat else ".")
        return {**hasil, "teks": teks, "angka": {"nilai": nilai, "satuan": u["satuan"], "label": u["label"]}}

    seri = _kelompok(d, u, nama_pemecah, sumber)
    waktu = bool(kamus.PEMECAH[nama_pemecah].get("waktu"))
    jumlah_kelompok = len(seri)
    if waktu:
        seri = seri.sort_index()
    else:
        naik = p.get("urut") == "kecil"
        seri = seri.sort_values(ascending=naik)
    n = p.get("n") or (MAKS_BARIS if not waktu else 60)
    tampil = seri.iloc[:n] if not waktu else seri.iloc[-n:]
    label_p = kamus.PEMECAH[nama_pemecah]["label"]
    baris = [{"kelompok": _label_kelompok(k, nama_pemecah), "nilai": float(v) if u["hitung"] != "dokumen" else int(v)} for k, v in tampil.items()]
    total = _hitung(d, u)
    if jumlah_kelompok == 0:
        teks = f"Tidak ada data {u['label'].lower()} {lingkup}."
    elif waktu:
        puncak = seri.idxmax()
        if s["posisi"]:
            lingkup = (", ".join(p["perusahaan"]) + " " if p.get("perusahaan") else "") + "(yang belum lunas, menurut tanggal dokumen)"
        teks = f"{u['label']} per {label_p.lower()} {lingkup}: tertinggi {_label_kelompok(puncak, nama_pemecah)} ({fmt(seri.max(), u['satuan'])})"
        teks += "." if puncak == seri.index[-1] else f", terakhir {_label_kelompok(seri.index[-1], nama_pemecah)} ({fmt(seri.iloc[-1], u['satuan'])})."
    else:
        teks = f"{u['label']} {lingkup} per {label_p.lower()}: {_bil(jumlah_kelompok)} {label_p.lower()}"
        if u["hitung"] != "rata":
            teks += f", total {fmt(total, u['satuan'])}"
        atas = seri.index[0]
        porsi = f", {seri.iloc[0] / total * 100:.0f}%".replace(".", ",") if u["hitung"] != "rata" and total else ""
        teks += f". {'Terkecil' if p.get('urut') == 'kecil' else 'Terbesar'}: {atas} ({fmt(seri.iloc[0], u['satuan'])}{porsi})."
        if len(seri) > len(tampil):
            teks += f" Ditampilkan {len(tampil)} teratas."
    teks = re.sub(r"\s+", " ", teks).replace(" :", ":").replace(" .", ".")
    tipe = {"rp": "rp", "hari": "hari"}.get(u["satuan"], "angka")
    return {**hasil, "teks": teks,
            "tabel": {"kolom": [{"kunci": "kelompok", "judul": label_p, "tipe": "teks"}, {"kunci": "nilai", "judul": u["label"], "tipe": tipe}],
                      "baris": baris},
            "grafik": {"jenis": "garis" if waktu else "batang", "x": "kelompok", "seri": [{"kunci": "nilai", "nama": u["label"]}], "tipe": tipe}}


def _periode_sebelum(periode):
    dari, sampai = pd.Timestamp(periode["dari"]), pd.Timestamp(periode["sampai"])
    if dari.day == 1 and periode["label"] in ("bulan ini", "bulan lalu") or re.match(r"^[A-Z][a-z]+ \d{4}$", periode["label"]):
        awal = (dari - pd.offsets.MonthBegin(1))
        akhir = awal + pd.offsets.MonthEnd(0)
        label = f"{NAMA_BULAN[awal.month - 1]} {awal.year}"
        if periode["label"] == "bulan ini":   # bulan berjalan dibandingkan dengan tanggal yang sama bulan lalu
            akhir = min(akhir, awal + (sampai - dari))
            label = f"{awal.day}-{akhir.day} {NAMA_BULAN[awal.month - 1][:3]} {awal.year}"
        return {"dari": awal.date().isoformat(), "sampai": akhir.date().isoformat(), "label": label}
    lama = sampai - dari
    akhir = dari - pd.Timedelta(days=1)
    return {"dari": (akhir - lama).date().isoformat(), "sampai": akhir.date().isoformat(), "label": "periode sebelumnya"}


def _banding(d, d2, p, u, sumber, nama_pemecah, periode, pb):
    tipe = {"rp": "rp", "hari": "hari"}.get(u["satuan"], "angka")
    a, b = _hitung(d, u), _hitung(d2, u)
    la, lb = periode["label"], pb["label"]
    if a is not None and b:
        ubah = (a - b) / abs(b) * 100
        arah = "naik" if ubah > 0 else "turun" if ubah < 0 else "sama"
        teks = f"{u['label']} {la}: {fmt(a, u['satuan'])}, {arah} {abs(ubah):.0f}% dari {lb} ({fmt(b, u['satuan'])})." if arah != "sama" else \
            f"{u['label']} {la} sama dengan {lb}: {fmt(a, u['satuan'])}."
    else:
        teks = f"{u['label']} {la}: {fmt(a, u['satuan'])}. {lb}: {fmt(b, u['satuan'])}."
    if periode["label"] == "bulan ini":
        teks += " Bulan berjalan dibandingkan dengan tanggal yang sama di bulan lalu, supaya adil."
    if not nama_pemecah:
        baris = [{"kelompok": lb, "nilai": b}, {"kelompok": la, "nilai": a}]
        return {"teks": teks, "tabel": {"kolom": [{"kunci": "kelompok", "judul": "Periode", "tipe": "teks"},
                                                  {"kunci": "nilai", "judul": u["label"], "tipe": tipe}], "baris": baris},
                "grafik": {"jenis": "batang", "x": "kelompok", "seri": [{"kunci": "nilai", "nama": u["label"]}], "tipe": tipe}}
    s1, s2 = _kelompok(d, u, nama_pemecah, sumber), _kelompok(d2, u, nama_pemecah, sumber)
    g = pd.DataFrame({"a": s1, "b": s2}).fillna(0)
    g = g.reindex(g["a"].abs().add(g["b"].abs()).sort_values(ascending=False).index)[:p.get("n") or 10]
    baris = [{"kelompok": _label_kelompok(k, nama_pemecah), "b": float(r.b), "a": float(r.a), "selisih": float(r.a - r.b)} for k, r in g.iterrows()]
    return {"teks": teks,
            "tabel": {"kolom": [{"kunci": "kelompok", "judul": kamus.PEMECAH[nama_pemecah]["label"], "tipe": "teks"},
                                {"kunci": "b", "judul": lb, "tipe": tipe}, {"kunci": "a", "judul": la, "tipe": tipe},
                                {"kunci": "selisih", "judul": "Selisih", "tipe": tipe}], "baris": baris},
            "grafik": {"jenis": "batang", "x": "kelompok", "seri": [{"kunci": "b", "nama": lb}, {"kunci": "a", "nama": la}], "tipe": tipe}}


def _daftar(d, p, u, sumber, lingkup):
    kolom = kamus.DAFTAR[sumber]
    if isinstance(kolom, dict):
        kolom = kolom[(u.get("saring") or {}).get("jenis", ["hutang"])[0]]
    kol_nilai = u["kolom"] if u["hitung"] == "jumlah" else None
    if sumber == "outstanding":
        t = d
        urut = "umur" if p.get("urut") == "lama" else "tgl" if p.get("urut") == "baru" else kol_nilai or "sisa_rp"
    else:
        # satu baris per dokumen: barang digabung, umur terbesar
        nomor = u["nomor"]
        agg = {c: (c, "first") for c, _ in kolom if c not in (nomor, "comp", "itemname", "total_po", "line_total", "umur")}
        agg.update(umur=("umur", "max"))
        if "itemname" in dict(kolom):
            agg["itemname"] = ("itemname", lambda s: _ringkas_barang(s))
        if "total_po" in dict(kolom):
            agg["total_po"] = ("total_po", "sum")
        if "line_total" in dict(kolom):
            agg["line_total"] = ("line_total", "sum")
        t = d.groupby(["comp", nomor], as_index=False).agg(**agg) if len(d) else d
        urut = "umur" if p.get("urut") in ("lama", None) and sumber in ("pr", "po", "pi") and p.get("status") else \
            ({"po": "total_po", "pi": "line_total"}.get(sumber, kamus.SUMBER[sumber]["tanggal"]) if p.get("urut") in ("besar", "kecil")
             else kamus.SUMBER[sumber]["tanggal"])
        if p.get("urut") == "baru":
            urut = kamus.SUMBER[sumber]["tanggal"]
    naik = p.get("urut") == "kecil"
    if urut == kamus.SUMBER[sumber]["tanggal"] and p.get("urut") != "lama":
        naik = False
    t = t.sort_values(urut, ascending=naik, na_position="last") if len(t) else t
    n = p.get("n") or MAKS_DAFTAR
    total = len(t)
    t = t.head(n)
    tipe = {"tgl": "tanggal", "pr_date": "tanggal", "cd": "tanggal", "pi_date": "tanggal", "umur": "angka", "sisa_rp": "rp", "total_po": "rp",
            "line_total": "rp"}
    baris = []
    for r in t.to_dict("records"):
        b = {}
        for c, _ in kolom:
            v = r.get(c)
            if isinstance(v, pd.Timestamp):
                v = v.date().isoformat()
            elif v is not None and not isinstance(v, str) and pd.isna(v):
                v = None
            elif hasattr(v, "item"):
                v = v.item()
            b[c] = v
        baris.append(b)
    nama_dok = {"outstanding": f"dokumen {u['label'].lower()}", "pr": "PR", "po": "PO", "pi": "PI"}[sumber]
    urutan = {"umur": "paling lama", "tgl": "terbaru", "pr_date": "terbaru", "cd": "terbaru", "pi_date": "terbaru", "line_total": "nilai terbesar",
              "sisa_rp": "nilai terbesar",
              "total_po": "nilai terbesar", "dalam_pvr_rp": "nilai terbesar", "belum_diajukan_rp": "nilai terbesar"}.get(urut, "")
    if naik and urutan == "nilai terbesar":
        urutan = "nilai terkecil"
    status = ", ".join(kamus.STATUS[i].get("label") or ", ".join(kamus.STATUS[i]["nilai"]) for i in p.get("status") or [])
    ciri = ((f" berstatus {status}" if status else "") + (f" {lingkup}" if lingkup else "")).replace(" saat ini", " yang belum lunas")
    teks = f"Ada {_bil(total)} {nama_dok}{ciri}." if total else f"Tidak ada {nama_dok}{ciri}."
    if total > len(t):
        teks += f" Ditampilkan {len(t)} {urutan}."
    elif total:
        teks += f" Diurutkan dari yang {urutan}." if urutan else ""
    return {"teks": re.sub(r"\s+", " ", teks).replace(" .", "."),
            "tabel": {"kolom": [{"kunci": c, "judul": j, "tipe": tipe.get(c, "teks")} for c, j in kolom], "baris": baris, "nomor": u["nomor"]}}


def _ringkas_barang(s):
    nama = list(dict.fromkeys(x for x in s if x))
    return nama[0] if len(nama) == 1 else f"{nama[0]} +{len(nama) - 1} lainnya" if nama else ""


# ---------- dokumen ----------

def jawab_dokumen(nomor, ambil):
    n = nomor.casefold()
    urutan = (["pr", "po", "outstanding"] if "/PR/" in nomor else ["po", "outstanding", "pr"] if "/PO/" in nomor
              else ["pi", "outstanding", "po"] if "/PI/" in nomor else ["outstanding", "po", "pr"])
    for sumber in urutan:
        try:
            df, _ = ambil(sumber)
        except TanpaAkses:
            continue
        kol = {"pr": "prnumber", "po": "po_number", "outstanding": "no_dok", "pi": "pi_number"}[sumber]
        d = df[df[kol].astype(str).str.casefold() == n]
        if sumber == "po" and d.empty:
            d = df[df["pi_number"].astype(str).str.casefold().str.contains(re.escape(n))]
            if len(d):
                return _dok_pi(nomor, d)
        if d.empty:
            continue
        return {"pr": _dok_pr, "po": _dok_po, "outstanding": _dok_out, "pi": _dok_pi_pvr}[sumber](nomor, d)
    return {"teks": f"Dokumen {nomor} tidak ditemukan di data laporan PR (sejak awal tahun), PO (sejak awal tahun), dan Outstanding (yang belum lunas). "
                    "Mungkin sudah lunas, Void, atau di luar periode data.", "permintaan": {"maksud": "dokumen", "nomor": nomor}}


def _isi(r, kolom):
    hasil = {}
    for c in kolom:
        v = r.get(c)
        if isinstance(v, pd.Timestamp):
            v = v.date().isoformat()
        elif v is not None and not isinstance(v, str) and pd.isna(v):
            v = None
        elif hasattr(v, "item"):
            v = v.item()
        hasil[c] = v
    return hasil


def _dok_pr(nomor, d):
    r0 = d.iloc[0]
    status = ", ".join(f"{_bil(n)} {s}" for s, n in d["status"].value_counts().items())
    po = ", ".join(dict.fromkeys(x for v in d["po_number"] for x in str(v).split(", ") if x))
    teks = f"PR {nomor} ({r0['comp']}, {_tgl(r0['pr_date'])}): {len(d)} barang. Status barang: {status}."
    teks += f" PO: {po}." if po else f" Belum ada PO, umur {_bil(d['umur'].max())} hari."
    kol = [("itemname", "Barang", "teks"), ("qtyreq", "Qty PR", "angka"), ("qtyorder", "Qty PO", "angka"), ("qtyout", "Qty belum PO", "angka"),
           ("status", "Status", "teks"), ("po_number", "No. PO", "teks"), ("buyer", "Buyer", "teks")]
    return {"teks": teks, "tabel": {"kolom": [{"kunci": k, "judul": j, "tipe": t} for k, j, t in kol],
                                    "baris": [_isi(r, [k for k, _, _ in kol]) for r in d.to_dict("records")]},
            "laporan": {"id": "purchase_request", "nama": "Purchase Request", "cari": nomor}, "permintaan": {"maksud": "dokumen", "nomor": nomor}}


def _dok_po(nomor, d):
    r0 = d.iloc[0]
    status = ", ".join(f"{_bil(n)} {s}" for s, n in d["status"].value_counts().items())
    pi = ", ".join(dict.fromkeys(x for v in d["pi_number"] for x in str(v).split(", ") if x))
    teks = (f"PO {nomor} ({r0['comp']}, {_tgl(r0['cd'])}) ke {r0['supplier_name']}: {len(d)} barang, nilai "
            f"{rp(d['total_po'].sum()) if bool(d['rupiah'].all()) else 'dalam valas'}. Status barang: {status}.")
    if pi:
        jumlah_pi = len(pi.split(", "))
        teks += f" Sudah ditagih dengan {jumlah_pi} PI."
    kol = [("itemname", "Barang", "teks"), ("qtyordered", "Qty PO", "angka"), ("qtydelivered", "Qty diterima", "angka"),
           ("qtyout", "Qty belum diterima", "angka"), ("total_po", "Nilai", "rp"), ("status", "Status", "teks"), ("pi_number", "No. PI", "teks")]
    return {"teks": teks, "tabel": {"kolom": [{"kunci": k, "judul": j, "tipe": t} for k, j, t in kol],
                                    "baris": [_isi(r, [k for k, _, _ in kol]) for r in d.to_dict("records")]},
            "laporan": {"id": "purchase_order", "nama": "Purchase Order", "cari": nomor}, "permintaan": {"maksud": "dokumen", "nomor": nomor}}


def _dok_pi(nomor, d):
    po = ", ".join(sorted(set(d["po_number"])))
    return {"teks": f"{nomor} adalah PI untuk PO {po} ({d.iloc[0]['supplier_name']}). Rincian tagihannya ada di laporan Outstanding kalau belum lunas.",
            "laporan": {"id": "purchase_order", "nama": "Purchase Order", "cari": po.split(", ")[0]}, "permintaan": {"maksud": "dokumen", "nomor": nomor}}


def _dok_out(nomor, d):
    r = d.iloc[0]
    jenis = r["jenis"]
    if jenis in ("pr", "po"):
        return {"teks": f"{nomor} masih outstanding sebagai {jenis.upper()}.", "laporan": {"id": "outstanding", "nama": "Outstanding", "cari": nomor},
                "permintaan": {"maksud": "dokumen", "nomor": nomor}}
    teks = (f"{r['sumber']} {nomor} ({r['comp']}, {_tgl(r['tgl'])}) {'dari' if jenis == 'hutang' else 'ke'} {r['mitra']}: sisa {rp(d['sisa_rp'].sum())} "
            f"dari nilai {rp(d['nilai_rp'].sum())}. Status: {r['status']}, umur {_bil(r['umur'])} hari.")
    if r.get("no_pvr"):
        teks += f" PVR: {r['no_pvr']}."
    kol = [("sumber", "Sumber", "teks"), ("tgl", "Tanggal", "tanggal"), ("nilai_rp", "Nilai", "rp"), ("sudah_bayar_rp", "Sudah dibayar", "rp"),
           ("sisa_rp", "Sisa", "rp"), ("status", "Status", "teks"), ("no_pvr", "No. PVR", "teks")]
    return {"teks": teks, "tabel": {"kolom": [{"kunci": k, "judul": j, "tipe": t} for k, j, t in kol],
                                    "baris": [_isi(x, [k for k, _, _ in kol]) for x in d.to_dict("records")]},
            "laporan": {"id": "outstanding", "nama": "Outstanding", "cari": nomor}, "permintaan": {"maksud": "dokumen", "nomor": nomor}}


def _dok_pi_pvr(nomor, d):
    r0 = d.iloc[0]
    pvr = ", ".join(dict.fromkeys(x for v in d["pvr_number"] for x in str(v).split(", ") if x))
    pv = ", ".join(dict.fromkeys(x for v in d["pv_number"] for x in str(v).split(", ") if x))
    teks = (f"PI {nomor} ({r0['comp']}, {_tgl(r0['pi_date'])}) dari {r0['supplier_name']}: {len(d)} barang, nilai {rp(d['line_total'].sum())}. "
            f"Status: {r0['status']}.")
    teks += f" PVR: {pvr}." if pvr else f" Belum ada PVR, umur {_bil(r0['umur'])} hari."
    if pv:
        teks += f" PV: {pv}."
    kol = [("itemname", "Barang", "teks"), ("qty", "Qty", "angka"), ("line_total", "Nilai", "rp"), ("po_number", "No. PO", "teks"),
           ("pvr_number", "No. PVR", "teks"), ("pv_number", "No. PV", "teks")]
    return {"teks": teks, "tabel": {"kolom": [{"kunci": k, "judul": j, "tipe": t} for k, j, t in kol],
                                    "baris": [_isi(r, [k for k, _, _ in kol]) for r in d.to_dict("records")]},
            "laporan": {"id": "pi_pvr", "nama": "Purchase Invoice", "cari": nomor}, "permintaan": {"maksud": "dokumen", "nomor": nomor}}


# ---------- tidak paham ----------

def tebak(teks, n=3, menu=None):
    """Pertanyaan contoh yang paling mirip; rekomendasi menu yang dibuka didahulukan kalau sama mirip."""
    t = set(normal(teks).split())
    nilai = []
    utama = kamus.MENU.get(menu or "", {}).get("saran", [])
    for c in list(dict.fromkeys(utama + kamus.CONTOH)):
        kc = set(normal(c).split())
        skor = SequenceMatcher(None, normal(teks), normal(c)).ratio() + len(t & kc) * 0.3 + (0.15 if c in utama else 0)
        nilai.append((skor, c))
    return [c for _, c in sorted(nilai, reverse=True)[:n]]
