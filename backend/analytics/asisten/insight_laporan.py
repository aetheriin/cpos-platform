"""Insight menu yang dihitung dari ringkasan dashboard laporan (hasil lap.bangun, sama dengan yang tampil di halaman), jadi ikut data terbaru.

Tiap cek menerima `dasbor(laporan_id, **filter)` dan mengembalikan poin dengan bentuk yang sama dengan insight.py:
kode, tingkat, skor, data, tanya. Kalimat dan saran tindakannya disusun terpisah di KALIMAT dan TINDAKAN."""
import logging
import re
from statistics import median

from .pengolah import _bil, rp
from .insight import TINGKAT

log = logging.getLogger(__name__)


def _poin(kode, tingkat, skor, data, tanya=None):
    return {"kode": kode, "tingkat": tingkat, "skor": TINGKAT[tingkat] * 1000 + skor, "data": data, "tanya": tanya}


def _pct(x):
    p = x * 100
    return (f"{p:.1f}".replace(".", ",").removesuffix(",0") if 0 < abs(p) < 10 else f"{p:.0f}") + "%"


def _des(x, n=1):
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


def _ton(kg):
    return f"{_bil(round(kg / 1000))} ton"


def _ubah(a, b):
    return (a - b) / b if b else None


def _arah(x):
    return f"naik {_pct(abs(x))}" if x > 0 else f"turun {_pct(abs(x))}"


# ---------- PR & PO Outstanding / PO & PI Outstanding (tambahan dari dashboard) ----------

def _alur(d, kode_naik, kode_lambat, kode_kat, dok, masuk, keluar):
    """Outstanding naik, tahap berikutnya melambat di minggu-minggu terakhir, dan kategori yang outstanding-nya melonjak."""
    hasil = []
    k, b = d["kpi"], d.get("banding", {}).get("kpi", {})
    awal, akhir = k["outstanding_awal"], k["outstanding_akhir"]
    ubah = _ubah(akhir, awal)
    if ubah is not None and ubah >= 0.2 and akhir - awal >= 30:
        hasil.append(_poin(kode_naik, "tinggi" if ubah >= 0.35 else "sedang", 80 + ubah * 50,
                           {"awal": awal, "akhir": akhir, "ubah": ubah, "selesai": k.get("completion_rate"), "selesai_lalu": b.get("completion_rate"),
                            "dok": dok}))
    minggu = [w for w in d.get("mingguan", []) if w.get(masuk)]
    if len(minggu) >= 3:
        terakhir = minggu[-2] if len(minggu) >= 2 else minggu[-1]       # minggu terakhir lengkap
        if terakhir[keluar] < 0.7 * terakhir[masuk] and terakhir[masuk] >= 50:
            hasil.append(_poin(kode_lambat, "sedang", 40, {"label": terakhir["label"], "masuk": terakhir[masuk], "keluar": terakhir[keluar], "dok": dok}))
    naik = [x for x in d.get("kategori_outstanding", []) if x["outstanding_akhir"] - x["outstanding_awal"] >= 30
            and x["outstanding_akhir"] >= 1.5 * max(x["outstanding_awal"], 1)]
    if naik:
        x = max(naik, key=lambda x: x["outstanding_akhir"] - x["outstanding_awal"])
        hasil.append(_poin(kode_kat, "sedang" if x["kategori"] != "(kosong)" else "info", 30,
                           {"kategori": x["kategori"], "awal": x["outstanding_awal"], "akhir": x["outstanding_akhir"], "dok": dok}))
    return hasil


def _pr_po(dasbor, p):
    return _alur(dasbor("pr_po", **p), "alur_pr_naik", "alur_pr_lambat", "alur_pr_kategori", "PR", "new_pr", "new_po")


def _po_pi(dasbor, p):
    return _alur(dasbor("po_pi", **p), "alur_po_naik", "alur_po_lambat", "alur_po_kategori", "PO", "new_po", "new_pi")


# ---------- PO Spend Analysis ----------

def _po_amt(dasbor, p):
    d = dasbor("po_amt", **p)
    hasil = []
    kat = {x["nama"]: x for x in d.get("kategori", [])}
    besar = kat.get("> 500JT")
    if besar and besar["pct_nilai"] >= 0.5:
        hasil.append(_poin("spend_besar", "sedang", 60, {"po": besar["po"], "pct_po": besar["pct_po"], "pct_nilai": besar["pct_nilai"]},
                           "10 supplier dengan nilai PO terbesar"))
    kecil = [kat[k] for k in ("<= 1JT", "1JT - 5JT") if k in kat]
    if kecil:
        pct_po, nilai = sum(x["pct_po"] for x in kecil), sum(x["nilai"] for x in kecil)
        if pct_po >= 0.4:
            hasil.append(_poin("spend_kecil", "sedang", 50, {"po": sum(x["po"] for x in kecil), "pct_po": pct_po, "nilai": nilai,
                                                             "pct_nilai": sum(x["pct_nilai"] for x in kecil)}))
    seri = [x for x in d.get("seri_bulan", []) if x.get("nilai")]
    if len(seri) >= 4:
        tengah = median(x["nilai"] for x in seri)
        puncak = max(seri, key=lambda x: x["nilai"])
        if tengah and puncak["nilai"] >= 2 * tengah:
            hasil.append(_poin("spend_lonjak", "info", 30, {"bulan": puncak["label"], "nilai": puncak["nilai"], "kali": puncak["nilai"] / tengah},
                               "Nilai PO per bulan"))
    bt = d.get("banding_tahun") or {}
    tahun = bt.get("tahun") or []
    if len(tahun) >= 2:
        kini, lalu = tahun[-1], tahun[-2]
        baris = [r for r in bt.get("baris", []) if r.get(f"po_{kini}")]
        a, b = sum(r[f"po_{kini}"] for r in baris), sum(r.get(f"po_{lalu}") or 0 for r in baris)
        if b and a >= 1.5 * b:
            hasil.append(_poin("spend_tahun", "info", 20, {"kini": kini, "lalu": lalu, "a": a, "b": b, "kali": a / b}))
    return hasil


# ---------- PI & GT ----------

def _pi_gt(dasbor, p):
    d = dasbor("pi_gt", **p)
    hasil = []
    bulan = d.get("bulanan", [])
    if len(bulan) >= 3:
        awal, akhir = bulan[0]["outstanding_awal"], bulan[-1]["outstanding_akhir"]
        lebih = sum(1 for b in bulan if b["new_pi"] > b["new_gt"])
        if akhir >= 100 and akhir >= 2 * max(awal, 1) and lebih >= len(bulan) / 2:
            hasil.append(_poin("gt_tumpuk", "tinggi", 80, {"awal": awal, "akhir": akhir, "bulan_awal": bulan[0]["label"], "lebih": lebih, "bulan": len(bulan),
                                                          "ambang": d.get("ambang")}))
    pembuat = d.get("gt_per_pembuat", [])
    total = sum(sum(x["nilai"]) for x in pembuat)
    if total >= 50:
        x = max(pembuat, key=lambda x: sum(x["nilai"]))
        porsi = sum(x["nilai"]) / total
        if porsi >= 0.5:
            hasil.append(_poin("gt_pembuat", "sedang", 40, {"nama": x["nama"], "jumlah": sum(x["nilai"]), "total": total, "porsi": porsi}))
    rute = [r for r in d.get("durasi_rute", []) if r.get("gt", 0) >= 10]
    if len(rute) >= 3:
        r = max(rute, key=lambda r: r["rata"])
        lain = median(x["rata"] for x in rute if x is not r)
        if r["rata"] >= 7 and r["rata"] >= 3 * max(lain, 1):
            hasil.append(_poin("gt_rute", "sedang", 35, {"rute": r["nama"], "rata": r["rata"], "median": r["median"], "gt": r["gt"], "lain": lain}))
    for t in d.get("temuan", []):
        if t.get("jenis") == "belum_diterima":
            hasil.append(_poin("gt_belum_diterima", "sedang", 30, {"teks": t["teks"]}))
    return hasil


# ---------- PVR KPI / PV KPI ----------

def _kpi(laporan, awalan):
    def cek(dasbor, p):
        d = dasbor(laporan, **p)
        hasil = []
        kat = [k for k in d.get("kategori", []) if k.get("pvr")]
        total_skor = sum(k["skor"] for k in kat)
        total_dok = sum(k["pvr"] for k in kat)
        if total_skor and total_dok:
            k = max(kat, key=lambda k: (k["skor"] / total_skor) / (k["pvr"] / total_dok))
            porsi_skor, porsi_dok = k["skor"] / total_skor, k["pvr"] / total_dok
            rendah = min(kat, key=lambda k: k["bobot"] or 0)
            if porsi_skor >= 0.2 and porsi_skor >= 1.5 * porsi_dok:
                hasil.append(_poin(f"{awalan}_bobot", "sedang", 50, {"kategori": k["nama"], "bobot": k["bobot"], "porsi_skor": porsi_skor,
                                                                    "porsi_dok": porsi_dok, "rendah": rendah["nama"], "bobot_rendah": rendah["bobot"]}))
        r = d.get("rekap") or {}
        orang, nilai, bulan = r.get("pembuat", []), r.get("nilai", []), r.get("bulan", [])
        total = sum(r.get("total_pembuat", []) or [0])
        if orang and total:
            atas = max(range(len(orang)), key=lambda i: r["total_pembuat"][i])
            porsi = r["total_pembuat"][atas] / total
            if porsi >= 0.3:
                hasil.append(_poin(f"{awalan}_satu_orang", "info", 30, {"nama": orang[atas], "skor": r["total_pembuat"][atas], "porsi": porsi}))
        if len(bulan) >= 6 and orang:
            def rata(i, sl):
                xs = [baris[i] for baris in nilai[sl]]
                return sum(xs) / len(xs) if xs else 0
            ubah = [(orang[i], rata(i, slice(0, 3)), rata(i, slice(-3, None))) for i in range(len(orang))]
            naik = max(ubah, key=lambda x: x[2] - x[1])
            turun = min(ubah, key=lambda x: x[2] - x[1])
            if naik[2] - naik[1] >= 200 and turun[1] - turun[2] >= 200:
                hasil.append(_poin(f"{awalan}_pindah", "info", 25, {"naik": naik[0], "naik_dari": naik[1], "naik_ke": naik[2], "turun": turun[0],
                                                                   "turun_dari": turun[1], "turun_ke": turun[2]}))
        tanpa = (d.get("kpi") or {}).get("tanpa_kategori") or 0
        if tanpa:
            hasil.append(_poin(f"{awalan}_tanpa_kategori", "info", 10, {"jumlah": tanpa}))
        return hasil
    return cek


# ---------- Weighbridge ----------

def _weighbridge(dasbor, p):
    hasil = []
    for jenis, mitra in (("Pembelian", "supplier"), ("Penjualan", "customer")):
        d = dasbor("palm_weighbridge", transaksi=[jenis], **p)
        k = d.get("kpi") or {}
        n, risiko = k.get("transaksi") or 0, k.get("berisiko") or 0
        if n >= 100 and risiko / n >= 0.5:
            hasil.append(_poin("wb_banyak", "tinggi", 70 + risiko / n * 20, {"jenis": jenis.lower(), "berisiko": risiko, "transaksi": n, "porsi": risiko / n,
                                                                             "selisih": k.get("rata_selisih_tara")}))
        tara_total = next((x["jumlah"] for x in d.get("risiko", []) if x["kunci"] == "tara"), 0)
        pel = (d.get("pelanggar") or {}).get(mitra) or []
        if tara_total >= 50 and pel:
            x = max(pel, key=lambda x: x["tara"])
            if x["tara"] / tara_total >= 0.3:
                hasil.append(_poin("wb_satu_mitra", "sedang", 45, {"jenis": jenis.lower(), "nama": x["nama"], "tara": x["tara"], "tara_total": tara_total,
                                                                   "persen": x["persen"]}))
        ekstrem = [x for x in d.get("tara_kendaraan", []) if abs(x["rata"]) >= 3000]
        if ekstrem:
            x = max(ekstrem, key=lambda x: x["jumlah"])
            hasil.append(_poin("wb_kendaraan", "sedang", 35, {"jenis": jenis.lower(), "kendaraan": x["kendaraan"], "jumlah": x["jumlah"], "rata": x["rata"],
                                                              "banyak": len(ekstrem)}))
        lama = [x for x in pel if x.get("durasi", 0) >= 10]
        if lama:
            x = max(lama, key=lambda x: x["durasi"])
            hasil.append(_poin("wb_durasi", "info", 15, {"jenis": jenis.lower(), "nama": x["nama"], "durasi": x["durasi"]}))
    # Poin yang sama untuk pembelian dan penjualan: hanya yang paling penting dari tiap kode
    terbaik = {}
    for x in hasil:
        if x["kode"] not in terbaik or x["skor"] > terbaik[x["kode"]]["skor"]:
            terbaik[x["kode"]] = x
    return list(terbaik.values())


# ---------- Tiket Penjualan ----------

def _tiket(dasbor, p):
    d = dasbor("tiket_penjualan", **p)
    hasil = []
    k, b = d.get("kpi") or {}, (d.get("banding") or {}).get("kpi") or {}
    angkut = (d.get("per_pengangkut") or {}).get("data") or []
    if angkut and angkut[0]["persen"] >= 0.35:
        hasil.append(_poin("tk_pengangkut", "sedang", 50, {"nama": angkut[0]["nama"], "netto": angkut[0]["netto"], "rit": angkut[0]["rit"],
                                                           "persen": angkut[0]["persen"]}))
    ubah = _ubah(k.get("netto") or 0, b.get("netto") or 0)
    if ubah is not None and abs(ubah) >= 0.1:
        hasil.append(_poin("tk_netto", "info", 30, {"netto": k["netto"], "ubah": ubah}))
    produk = (d.get("per_produk") or {}).get("data") or []
    rit_total, per_rit = k.get("rit") or 0, k.get("per_rit") or 0
    kecil = [x for x in produk if x["rit"] >= 0.2 * rit_total and x["netto"] / x["rit"] < per_rit / 2]
    if kecil and rit_total:
        x = max(kecil, key=lambda x: x["rit"])
        hasil.append(_poin("tk_rit_kecil", "info", 20, {"nama": x["nama"], "rit": x["rit"], "per_rit": x["netto"] / x["rit"], "umum": per_rit}))
    beli = (d.get("per_pembeli") or {}).get("data") or []
    porsi = sum(x["persen"] for x in beli[:3])
    if len(beli) >= 3 and porsi >= 0.5:
        hasil.append(_poin("tk_pembeli", "info", 15, {"nama": [x["nama"] for x in beli[:3]], "porsi": porsi}))
    return hasil


# ---------- Pembelian TBS Mingguan ----------

def _tbs_mingguan(dasbor, p):
    d = dasbor("tbs_mingguan", **p)
    hasil = []
    r = d.get("ringkasan") or {}
    minggu = [w["netto"] for w in d.get("minggu", [])]
    if r.get("rata") and r.get("nilai"):
        ubah = _ubah(r["nilai"], r["rata"])
        naik_beruntun = 0
        for a, b in zip(minggu[::-1], minggu[-2::-1]):
            if a > b:
                naik_beruntun += 1
            else:
                break
        if abs(ubah) >= 0.1 or naik_beruntun >= 3:
            hasil.append(_poin("tbs_arah", "sedang", 50, {"nilai": r["nilai"], "rata": r["rata"], "ubah": ubah, "beruntun": naik_beruntun,
                                                          "tertinggi": bool(minggu) and r["nilai"] >= max(minggu), "minggu": len(minggu)}))
    grup = d.get("grup", [])
    henti = sorted([g for g in grup if not g["nilai"] and g["rata"] >= 30000], key=lambda g: -g["rata"])
    if henti:
        hasil.append(_poin("tbs_berhenti", "sedang", 45, {"grup": [(g["nama"], g["rata"]) for g in henti[:3]], "jumlah": len(henti)}))
    turun = sorted([g for g in grup if g.get("status") == "TURUN"], key=lambda g: g["nilai"] - g["rata"])
    if turun:
        hasil.append(_poin("tbs_turun", "info", 25, {"grup": [(g["nama"], g["persen"]) for g in turun[:3]], "jumlah": len(turun)}))
    naik = [g for g in grup if g.get("status") == "NAIK"]
    if naik:
        g = max(naik, key=lambda g: g["nilai"] - g["rata"])
        hasil.append(_poin("tbs_penyumbang", "info", 20, {"nama": g["nama"], "comp": g["comp"], "nilai": g["nilai"], "persen": g["persen"]}))
    return hasil


# ---------- Forecast Penerimaan TBS ----------

def _penerimaan(dasbor, p):
    d = dasbor("penerimaan_tbs", **p)
    hasil = []
    k, b = d.get("kpi") or {}, (d.get("banding") or {}).get("kpi") or {}
    uh, un = _ubah(k.get("harga") or 0, b.get("harga") or 0), _ubah(k.get("netto") or 0, b.get("netto") or 0)
    if uh is not None and un is not None and (abs(uh) >= 0.03 or abs(un) >= 0.05):
        hasil.append(_poin("tbs_harga_volume", "info", 40, {"netto": k["netto"], "un": un, "harga": k["harga"], "uh": uh, "nilai": k.get("nilai")}))
    tipe = (d.get("per_tipe") or {}).get("data") or []
    umum = next((t for t in tipe if t["nama"] == "UMUM"), None)
    total = sum(t["netto"] for t in tipe)
    if umum and total:
        mahal = [t for t in tipe if t["netto"] >= 0.02 * total and t["harga"] >= 1.15 * umum["harga"]]
        if mahal:
            t = max(mahal, key=lambda t: t["harga"])
            hasil.append(_poin("tbs_premi", "sedang", 45, {"nama": t["nama"], "harga": t["harga"], "umum": umum["harga"], "lebih": t["harga"] / umum["harga"] - 1}))
    f = d.get("forecast") or {}
    hari = f.get("hari") or []
    if hari:
        uji, iv = f.get("uji") or {}, f.get("interval") or {}
        hasil.append(_poin("tbs_forecast", "info", 35, {"total": sum(h["netto"] for h in hari), "mulai": hari[0]["hari"], "akhir": hari[-1]["hari"],
                                                        "bawah": iv.get("total_bawah"), "atas": iv.get("total_atas"), "selisih": uji.get("selisih"),
                                                        "harian": uji.get("meleset_harian")}))
    return hasil


# ---------- Bank Statement ----------

_BADAN = re.compile(r"\b(PT|CV|UD|BANK|LTD|CO|INC|TBK|S\.?L\.?U?|KUD|KOPERASI|BUMDES|ESCROW|OCBC|MANDIRI|BNI|BRI|CIMB|BCA|BEA|PAJAK|KPP|KANTOR|DINAS)\b", re.I)


def _kas(dasbor, p):
    d = dasbor("cash_flow", **p)
    hasil = []
    g = d.get("giro") or {}
    if (g.get("rata_saldo") or 0) >= 10e9 and not g.get("imbal"):
        hasil.append(_poin("kas_giro", "sedang", 50, {"rata": g["rata_saldo"]}))
    hari = [h for h in ((d.get("deret") or {}).get("hari") or []) if h.get("saldo") is not None]
    k = d.get("kpi") or {}
    if hari:
        x = min(hari, key=lambda h: h["saldo"])
        hasil.append(_poin("kas_saldo", "info", 30, {"awal": k.get("saldo_awal"), "akhir": k.get("saldo_akhir"), "terendah": x["saldo"], "hari": x["hari"]}))
    masuk = ((d.get("mitra") or {}).get("masuk")) or []
    rv = next((x["debit"] for x in d.get("dokumen", []) if x["jenis"] == "Receipt Voucher"), 0)
    bukan_bank = [x for x in masuk if not re.search(r"\b(BANK|ESCROW|OCBC|MANDIRI|BNI|BRI|CIMB|BCA)\b", x["nama"], re.I)]
    if rv and len(bukan_bank) >= 3:
        porsi = sum(x["nilai"] for x in bukan_bank[:3]) / rv
        if porsi >= 0.4:
            hasil.append(_poin("kas_konsentrasi", "info", 25, {"nama": [x["nama"] for x in bukan_bank[:3]], "porsi": min(porsi, 1)}))
    orang = [x for x in masuk if x["nilai"] >= 1e9 and not _BADAN.search(x["nama"])]
    if orang:
        x = orang[0]
        hasil.append(_poin("kas_perorangan", "sedang", 40, {"nama": x["nama"], "nilai": x["nilai"], "jumlah": x["jumlah"]}))
    return hasil


# Menu -> (cek, juga pakai cek data baris dari insight.py)
CEK = {
    "pr_po": (_pr_po, True), "po_pi": (_po_pi, True), "po_amt": (_po_amt, False), "pi_gt": (_pi_gt, False),
    "penilaian_pvr": (_kpi("penilaian_pvr", "pvr"), False), "penilaian_pv": (_kpi("penilaian_pv", "pv"), False),
    "palm_weighbridge": (_weighbridge, False), "tiket_penjualan": (_tiket, False), "tbs_mingguan": (_tbs_mingguan, False),
    "penerimaan_tbs": (_penerimaan, False), "cash_flow": (_kas, False),
}


_BULAN = {"Jan": "Januari", "Feb": "Februari", "Mar": "Maret", "Apr": "April", "Mei": "Mei", "May": "Mei", "Jun": "Juni", "Jul": "Juli",
          "Agu": "Agustus", "Agt": "Agustus", "Aug": "Agustus", "Sep": "September", "Okt": "Oktober", "Oct": "Oktober", "Nov": "November",
          "Des": "Desember", "Dec": "Desember"}


def _bulan(label):
    """'Apr 26' -> 'April 2026'; label lain dibiarkan."""
    b, _, t = str(label).partition(" ")
    return f"{_BULAN.get(b, b)} {'20' + t if len(t) == 2 else t}".strip()


def _minggu(label):
    """'13-11 sd 19-11' -> '13 sampai 19 November'."""
    import re
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2}) sd (\d{1,2})-(\d{1,2})", str(label).strip())
    if not m:
        return str(label).replace(" sd ", " sampai ")
    a, ba, b, bb = m.groups()
    bln = lambda x: ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
                     "November", "Desember"][int(x) - 1]
    return f"{int(a)} sampai {int(b)} {bln(bb)}" if ba == bb else f"{int(a)} {bln(ba)} sampai {int(b)} {bln(bb)}"


def _ringan(x):
    return "lebih ringan" if x < 0 else "lebih berat"


def _setara(d, dok):
    if not d.get("bobot_rendah") or d["rendah"] == d["kategori"] or d["bobot"] < 2 * d["bobot_rendah"]:
        return ""
    return f" Satu {dok} {d['kategori']} bernilai sama dengan {_des(d['bobot'] / d['bobot_rendah'], 0)} {dok} {d['rendah']}."


def _daftar(xs):
    return ", ".join(xs[:-1]) + f", dan {xs[-1]}" if len(xs) > 2 else " dan ".join(xs)


KALIMAT = {
    "alur_pr_naik": lambda d: f"PR outstanding naik {_pct(d['ubah'])} dalam periode ini ({_bil(d['awal'])} jadi {_bil(d['akhir'])}). "
                              f"PR yang selesai {_pct(d['selesai'])}" + (f", bulan lalu {_pct(d['selesai_lalu'])}." if d.get("selesai_lalu") else "."),
    "alur_po_naik": lambda d: f"PO outstanding naik {_pct(d['ubah'])} dalam periode ini ({_bil(d['awal'])} jadi {_bil(d['akhir'])}). "
                              f"PO yang selesai {_pct(d['selesai'])}" + (f", bulan lalu {_pct(d['selesai_lalu'])}." if d.get("selesai_lalu") else "."),
    "alur_pr_lambat": lambda d: f"Minggu {_minggu(d['label'])} ada {_bil(d['masuk'])} PR baru tapi hanya {_bil(d['keluar'])} PO dibuat.",
    "alur_po_lambat": lambda d: f"Minggu {_minggu(d['label'])} ada {_bil(d['masuk'])} PO baru tapi hanya {_bil(d['keluar'])} PI dibuat.",
    "alur_pr_kategori": lambda d: (f"PR outstanding tanpa kategori naik dari {_bil(d['awal'])} ke {_bil(d['akhir'])} barang." if d["kategori"] == "(kosong)" else
                                   f"Outstanding kategori {d['kategori']} naik dari {_bil(d['awal'])} ke {_bil(d['akhir'])} barang."),
    "alur_po_kategori": lambda d: (f"PO outstanding tanpa kategori naik dari {_bil(d['awal'])} ke {_bil(d['akhir'])} barang." if d["kategori"] == "(kosong)" else
                                   f"Outstanding kategori {d['kategori']} naik dari {_bil(d['awal'])} ke {_bil(d['akhir'])} barang."),
    "spend_besar": lambda d: f"{_bil(d['po'])} PO di atas Rp 500 juta ({_pct(d['pct_po'])} dari jumlah PO) memegang {_pct(d['pct_nilai'])} nilai belanja.",
    "spend_kecil": lambda d: f"{_bil(d['po'])} PO ({_pct(d['pct_po'])}) bernilai di bawah Rp 5 juta, totalnya hanya {rp(d['nilai'])} "
                             f"({_pct(d['pct_nilai'])} dari nilai belanja).",
    "spend_lonjak": lambda d: f"Nilai PO {_bulan(d['bulan'])} {rp(d['nilai'])}, {_des(d['kali'])} kali bulan biasa.",
    "spend_tahun": lambda d: f"Jumlah PO {d['kini']} sampai bulan ini {_bil(d['a'])}, {_des(d['kali'])} kali periode yang sama {d['lalu']} ({_bil(d['b'])}).",
    "gt_tumpuk": lambda d: f"Barang yang sudah di-PI lebih dari {d['ambang']} hari tapi belum di-GT naik dari {_bil(d['awal'])} ({_bulan(d['bulan_awal'])}) "
                           f"ke {_bil(d['akhir'])}. " + ("Setiap bulan" if d['lebih'] == d['bulan'] else f"Di {d['lebih']} dari {d['bulan']} bulan")
                           + ", jumlah PI lebih banyak daripada GT, jadi tumpukannya terus naik.",
    "gt_pembuat": lambda d: f"{d['nama']} membuat {_pct(d['porsi'])} GT ({_bil(d['jumlah'])} dari {_bil(d['total'])}).",
    "gt_rute": lambda d: f"Rute {d['rute'].replace(' → ', ' ke ')} rata-rata {_des(d['rata'])} hari dari GT sampai diterima (separuhnya lebih dari {_des(d['median'])} hari, "
                         f"{_bil(d['gt'])} GT). Rute lain umumnya {_des(d['lain'])} hari.",
    "gt_belum_diterima": lambda d: d["teks"],
    "pvr_bobot": lambda d: f"Kategori {d['kategori']} (bobot {_des(d['bobot'])}) menyumbang {_pct(d['porsi_skor'])} skor dari hanya {_pct(d['porsi_dok'])} PVR. "
                           f"Skor lebih ditentukan kategori daripada banyaknya kerja." + _setara(d, "PVR"),
    "pv_bobot": lambda d: f"Kategori {d['kategori']} (bobot {_des(d['bobot'])}) menyumbang {_pct(d['porsi_skor'])} skor dari hanya {_pct(d['porsi_dok'])} PV. "
                          f"Skor lebih ditentukan kategori daripada banyaknya kerja." + _setara(d, "PV"),
    "pvr_satu_orang": lambda d: f"{d['nama']} memegang {_pct(d['porsi'])} dari total skor ({_des(d['skor'], 0)} poin).",
    "pv_satu_orang": lambda d: f"{d['nama']} memegang {_pct(d['porsi'])} dari total skor ({_des(d['skor'], 0)} poin).",
    "pvr_pindah": lambda d: f"Beban kerja berpindah: rata-rata skor bulanan {d['naik']} naik dari {_des(d['naik_dari'], 0)} ke {_des(d['naik_ke'], 0)}, "
                            f"{d['turun']} turun dari {_des(d['turun_dari'], 0)} ke {_des(d['turun_ke'], 0)} (3 bulan pertama dibanding 3 bulan terakhir).",
    "pv_pindah": lambda d: f"Beban kerja berpindah: rata-rata skor bulanan {d['naik']} naik dari {_des(d['naik_dari'], 0)} ke {_des(d['naik_ke'], 0)}, "
                           f"{d['turun']} turun dari {_des(d['turun_dari'], 0)} ke {_des(d['turun_ke'], 0)} (3 bulan pertama dibanding 3 bulan terakhir).",
    "pvr_tanpa_kategori": lambda d: f"{_bil(d['jumlah'])} PVR tanpa kategori tidak ikut dinilai.",
    "pv_tanpa_kategori": lambda d: f"{_bil(d['jumlah'])} PV tanpa kategori tidak ikut dinilai.",
    "wb_banyak": lambda d: f"{_pct(d['porsi'])} timbangan {d['jenis']} ditandai berisiko ({_bil(d['berisiko'])} dari {_bil(d['transaksi'])}), "
                           f"rata-rata taranya {_bil(abs(d['selisih']))} kg {_ringan(d['selisih'])} dari pembandingnya. Tanda sebanyak ini sulit ditindaklanjuti satu per satu.",
    "wb_satu_mitra": lambda d: f"Di {d['jenis']}, {d['nama']} menyumbang {_pct(d['tara'] / d['tara_total'])} peringatan tara "
                               f"({_bil(d['tara'])} dari {_bil(d['tara_total'])}). {_pct(d['persen'])} transaksinya ditandai.",
    "wb_kendaraan": lambda d: f"Kendaraan {d['kendaraan']} rata-rata taranya {_bil(abs(d['rata']))} kg {_ringan(d['rata'])} dari pembandingnya dalam {_bil(d['jumlah'])} timbangan {d['jenis']}. "
                              f"Ada {_bil(d['banyak'])} kendaraan dengan selisih lebih dari 3 ton.",
    "wb_durasi": lambda d: f"{d['nama']} paling sering timbang lebih dari 3 jam di {d['jenis']} ({_bil(d['durasi'])} kali).",
    "tk_pengangkut": lambda d: f"{d['nama']} mengangkut {_pct(d['persen'])} netto ({_ton(d['netto'])} dalam {_bil(d['rit'])} rit).",
    "tk_netto": lambda d: f"Netto periode ini {_ton(d['netto'])}, {_arah(d['ubah'])} dari periode yang sama bulan lalu.",
    "tk_rit_kecil": lambda d: f"{d['nama']} punya {_bil(d['rit'])} rit tapi muatannya hanya {_des(d['per_rit'] / 1000)} ton per rit, "
                              f"rata-rata semua produk {_des(d['umum'] / 1000)} ton.",
    "tk_pembeli": lambda d: f"Tiga pembeli terbesar ({_daftar(d['nama'])}) mengambil {_pct(d['porsi'])} netto.",
    "tbs_arah": lambda d: (f"Minggu terakhir {_ton(d['nilai'])}, {_arah(d['ubah'])} dari rata-rata {_ton(d['rata'])}"
                           + (f", tertinggi dalam {d['minggu']} minggu" if d["tertinggi"] else "")
                           + (f", dan sudah naik {d['beruntun']} minggu berturut-turut." if d["beruntun"] >= 3 else ".")),
    "tbs_berhenti": lambda d: f"{_bil(d['jumlah'])} grup yang biasanya rutin tidak mengirim sama sekali minggu ini, antara lain "
                              + _daftar([f"{n} (biasanya {_ton(r)})" for n, r in d["grup"]]) + ".",
    "tbs_turun": lambda d: f"{_bil(d['jumlah'])} grup turun di luar kebiasaan, antara lain " + _daftar([f"{n} (turun {_des(abs(x), 0)}%)" for n, x in d["grup"]]) + ".",
    "tbs_penyumbang": lambda d: f"Kenaikan terbesar dari {d['nama']} ({d['comp']}): {_ton(d['nilai'])}, naik {_des(d['persen'], 0)}% dari biasanya.",
    "tbs_harga_volume": lambda d: f"Tonase {_ton(d['netto'])} ({_arah(d['un'])}), harga rata-rata Rp {_bil(d['harga'])}/kg ({_arah(d['uh'])}), "
                                  f"dibanding 30 hari sebelumnya.",
    "tbs_premi": lambda d: f"Tipe {d['nama']} dibayar Rp {_bil(d['harga'])}/kg, {_pct(d['lebih'])} di atas tipe UMUM (Rp {_bil(d['umum'])}/kg).",
    "tbs_forecast": lambda d: (f"Perkiraan penerimaan {d['mulai'][8:10]}/{d['mulai'][5:7]} sampai {d['akhir'][8:10]}/{d['akhir'][5:7]} sekitar {_ton(d['total'])}"
                               + (f" (rentang {_ton(d['bawah'])} sampai {_ton(d['atas'])})" if d.get("bawah") else "") + "."
                               + (f" Minggu lalu perkiraannya meleset {_pct(abs(d['selisih']))} untuk total seminggu, per hari sekitar {_pct(d['harian'])}."
                                  if d.get("selisih") is not None and d.get("harian") is not None else "")),
    "kas_giro": lambda d: f"Rata-rata saldo {rp(d['rata'])}, tapi jasa giro yang tercatat Rp 0.",
    "kas_saldo": lambda d: f"Saldo {rp(d['awal'])} jadi {rp(d['akhir'])}. Terendah {rp(d['terendah'])} pada {d['hari'][8:10]}/{d['hari'][5:7]}.",
    "kas_konsentrasi": lambda d: f"{_pct(d['porsi'])} penerimaan dari penjualan berasal dari 3 pembeli: {_daftar(d['nama'])}.",
    "kas_perorangan": lambda d: f"Ada uang masuk {rp(d['nilai'])} dari {d['nama']} ({_bil(d['jumlah'])} transaksi), yang tampak seperti nama perorangan.",
}

# Saran tindakan per kode (ditampilkan di bawah kalimatnya). Kode yang tidak ada di sini tidak punya saran khusus.
TINDAKAN = {
    "alur_pr_naik": "Cek PR lama yang mungkin sudah tidak dibutuhkan dan tutup di ERP.",
    "alur_po_naik": "Cek tumpukan tagihan atau berita acara yang belum diinput menjadi PI.",
    "alur_pr_lambat": "Cek apakah ada PR yang menunggu penawaran atau persetujuan.",
    "alur_po_lambat": "Tanyakan ke bagian yang menginput PI apakah ada tagihan yang menumpuk.",
    "alur_pr_kategori": "Lengkapi kategori di master barang.",
    "alur_po_kategori": "Cek apakah tagihan atau berita acara untuk kategori ini tertahan.",
    "spend_besar": "Pastikan PO besar lewat negosiasi atau tender, dan jadwalnya diketahui bagian keuangan.",
    "spend_kecil": "Untuk barang kecil yang rutin, pertimbangkan kontrak harga tetap atau kas kecil.",
    "spend_lonjak": "Informasikan jadwal PO besar ke bagian keuangan lebih awal.",
    "spend_tahun": "Pastikan dulu apakah ada perusahaan yang baru memakai ERP sebelum membandingkan antar tahun.",
    "gt_tumpuk": "Buat target bulanan supaya GT minimal sama dengan PI, lalu kurangi tumpukannya.",
    "gt_pembuat": "Siapkan petugas cadangan untuk membuat GT.",
    "gt_rute": "Minta gudang tujuan mengonfirmasi penerimaan di sistem.",
    "gt_belum_diterima": "Minta gudang tujuan mengonfirmasi penerimaan GT yang tertunda.",
    "pvr_bobot": "Tinjau ulang bobot kategori sebelum skor dipakai untuk menilai orang.",
    "pv_bobot": "Tinjau ulang bobot kategori sebelum skor dipakai untuk menilai orang.",
    "pvr_pindah": "Bandingkan rata-rata per bulan aktif, bukan skor setahun, untuk orang yang baru masuk atau pindah tugas.",
    "pv_pindah": "Bandingkan rata-rata per bulan aktif, bukan skor setahun, untuk orang yang baru masuk atau pindah tugas.",
    "pvr_satu_orang": "Lihat juga jumlah dokumen dan bulan aktifnya, karena skor tinggi bisa datang dari kategori berbobot besar.",
    "pv_satu_orang": "Lihat juga jumlah dokumen dan bulan aktifnya, karena skor tinggi bisa datang dari kategori berbobot besar.",
    "tk_pembeli": "Cari pembeli tambahan supaya tidak bergantung pada sedikit pembeli.",
    "kas_konsentrasi": "Pantau jadwal pembayaran dari pembeli ini karena penerimaan sangat bergantung padanya.",
    "tbs_penyumbang": "Pastikan mutu buah dari grup ini tetap terjaga saat kirimannya naik.",
    "kas_saldo": "Sesuaikan jadwal pembayaran besar dengan hari saldo rendah.",
    "pvr_tanpa_kategori": "Lengkapi kategorinya supaya ikut dinilai.",
    "pv_tanpa_kategori": "Lengkapi kategorinya supaya ikut dinilai.",
    "wb_banyak": "Tinjau cara pembanding tara (misalnya tara yang umum per kendaraan dalam 90 hari) supaya yang ditandai tinggal daftar pendek.",
    "wb_satu_mitra": "Kalau ini timbang sementara atau kebun sendiri, pisahkan dari indikator kecurangan.",
    "wb_kendaraan": "Cek data master kendaraan: kemungkinan satu plat dipakai beberapa truk atau taranya salah.",
    "wb_durasi": "Cek antrean dan prosedur di jembatan timbang.",
    "tk_pengangkut": "Siapkan angkutan cadangan.",
    "tk_rit_kecil": "Kalau ongkos angkut dibayar per rit, cek ongkos per tonnya.",
    "tbs_arah": "Siapkan kapasitas olah dan dana untuk minggu berikutnya.",
    "tbs_berhenti": "Hubungi grup ini dan cek apakah pindah ke pembeli lain.",
    "tbs_turun": "Hubungi grup yang turun untuk mengetahui sebabnya.",
    "tbs_premi": "Pastikan premi ini sesuai mutu buahnya.",
    "tbs_forecast": "Pakai untuk rencana dana mingguan, bukan harian.",
    "kas_giro": "Cek apakah jasa giro belum dicatat, dan pertimbangkan deposito jangka pendek untuk dana yang mengendap.",
    "kas_perorangan": "Pastikan pencatatannya benar, misalnya sebagai pinjaman atau setoran modal.",
    # Kode dari insight.py (dihitung dari baris data)
    "pi_tanpa_pvr": "Tetapkan kapan pembayaran boleh tanpa PVR, lalu periksa sampelnya.",
    "piutang_satu": "Pantau jatuh tempo customer ini lebih ketat.",
    "piutang_lama_mitra": "Prioritaskan penagihan customer ini.",
    "hutang_tua": "Urutkan pembayaran dari yang paling lama, dan cek dokumen yang mungkin sudah dibayar tapi belum dicatat.",
    "hutang_setahun": "Rekonsiliasi atau bersihkan saldo lama ini.",
    "mitra_dua_arah": "Pertimbangkan kompensasi hutang dan piutang dengan persetujuan kedua pihak.",
    "hutang_tua_belum_pvr": "Ajukan PVR untuk hutang lama ini atau pastikan memang ditahan.",
    "pvr_tertahan": "Cek kenapa PVR yang sudah disetujui belum dibayar.",
    "po_out_pembuat": "Alihkan PO lama ini ke buyer yang aktif, atau tutup yang sudah tidak berlaku.",
    "po_supplier_lambat": "Bahas jadwal pengiriman dengan supplier ini, atau evaluasi suppliernya.",
    "pr_out_belum_setuju": "Kirim pengingat ke pemberi persetujuan.",
    "pr_out_basi": "Tinjau bersama Purchasing dan peminta, lalu tutup PR yang sudah tidak dibutuhkan.",
    "po_out_basi": "Tanyakan ke supplier apakah barang masih akan dikirim, kalau tidak tutup PO-nya.",
    "pr_out_pt": "Cek bersama perusahaan ini PR mana yang masih dibutuhkan.",
    "po_out_supplier": "Pantau jadwal pengiriman dari supplier ini.",
    "pi_belum_pvr": "Ajukan PVR untuk PI yang sudah lama.",
    "pi_pvr_tertahan": "Cek kenapa PVR yang sudah ada belum dibayar.",
}


def hitung(menu, dasbor, perusahaan=None):
    """-> daftar poin dari dashboard menu ini (belum diurutkan, belum dipotong). Memuat / TanpaAkses diteruskan ke pemanggil."""
    cek, _ = CEK[menu]
    p = {"perusahaan": list(perusahaan)} if perusahaan else {}
    try:
        hasil = [x for x in cek(dasbor, p) if x]
    except (KeyError, TypeError, IndexError, ValueError, ZeroDivisionError):
        log.exception("Insight dashboard %s gagal dihitung", menu)
        return []
    for x in hasil:
        x["teks"] = KALIMAT[x["kode"]](x["data"])
        x["tindakan"] = TINDAKAN.get(x["kode"])
    return hasil
