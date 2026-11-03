"""Data Master › Kurs Mata Uang: pelengkap tabel referensi "kurs" (utils/db_referensi.py) - impor dari Excel / CSV,
saran kurs dari internet, dan peringatan bila kurs yang diinput jauh dari kurs sebelumnya (mis. salah ketik satu nol).
Kurs = rupiah per 1 unit mata uang, berlaku sejak tanggalnya sampai ada kurs berikutnya."""
import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree

import requests

from utils.db_utils import get_connection
from utils import db_referensi as ref

SELISIH_PERINGATAN = 0.10        # beda lebih dari 10% dari kurs sebelumnya -> peringatan
MAKS_BARIS_IMPOR = 2000
URL_INTERNET = "https://api.frankfurter.dev/v1/{dari}..{sampai}?base={kode}&symbols=IDR"   # kurs harian ECB
KOLOM_IMPOR = ("Tanggal", "Mata Uang", "Kurs", "Jenis", "Perusahaan", "Sumber", "Keterangan")


# ===== PERINGATAN =====
def kurs_sebelumnya(cursor, id_mata_uang, jenis, tanggal, id_company):
    """(tanggal, kurs) terakhir sebelum `tanggal` untuk mata uang + jenis + perusahaan yang sama, atau None."""
    cursor.execute("""SELECT TOP 1 RateDate, Rate FROM ExchangeRate
                      WHERE CurrencyID = ? AND RateType = ? AND RateDate < ? AND IsVoid = 0
                        AND (CompID = ? OR (CompID IS NULL AND ? IS NULL))
                      ORDER BY RateDate DESC""", id_mata_uang, jenis, tanggal, id_company, id_company)
    r = cursor.fetchone()
    return (r[0], float(r[1])) if r else None


def teks_peringatan(kurs, lama):
    if not lama or abs(kurs - lama[1]) / lama[1] <= SELISIH_PERINGATAN:
        return None
    return (f"beda {abs(kurs - lama[1]) / lama[1]:.0%} dari kurs {lama[0]:%d-%m-%Y} "
            f"(Rp {lama[1]:,.2f})".replace(",", "#").replace(".", ",").replace("#", "."))


def peringatan(form):
    """Peringatan untuk satu isian form kurs yang baru disimpan, atau None."""
    try:
        tanggal = date.fromisoformat((form.get("tanggal") or "").strip())
        kurs = float((form.get("kurs") or "").replace(",", "."))
    except ValueError:
        return None
    conn = get_connection()
    try:
        lama = kurs_sebelumnya(conn.cursor(), form.get("id_mata_uang"), form.get("jenis"), tanggal, form.get("id_company") or None)
    finally:
        conn.close()
    return teks_peringatan(kurs, lama)


# ===== SARAN DARI INTERNET =====
def kurs_internet(kode, tanggal):
    """(tanggal kurs, kurs) dari ECB untuk `tanggal` (hari libur: kurs hari kerja sebelumnya). ValueError bila gagal."""
    url = URL_INTERNET.format(dari=tanggal - timedelta(days=10), sampai=tanggal, kode=kode)
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "cpos"})
        r.raise_for_status()
        kurs = {date.fromisoformat(t): v["IDR"] for t, v in r.json().get("rates", {}).items() if v.get("IDR")}
    except Exception:
        raise ValueError("Kurs dari internet tidak bisa diambil. Periksa koneksi internet server, atau isi manual.")
    if not kurs:
        raise ValueError(f"Kurs {kode} ke IDR tidak tersedia di internet untuk tanggal itu")
    t = max(kurs)
    return t, float(kurs[t])


# ===== IMPOR =====
def _xlsx(isi):
    """Baris lembar pertama .xlsx sebagai list of list (tanpa library tambahan). Tanggal Excel tetap angka seri."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(isi)) as z:
        teks = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                teks.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        lembar = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not lembar:
            raise ValueError("Berkas Excel tidak berisi lembar kerja")
        akar = ElementTree.fromstring(z.read(lembar[0]))
    baris = []
    for row in akar.iter(f"{{{ns['m']}}}row"):
        isi_baris = {}
        for c in row.findall("m:c", ns):
            kolom = 0
            for ch in re.match(r"[A-Z]+", c.get("r", "A")).group():
                kolom = kolom * 26 + ord(ch) - 64
            v = c.find("m:v", ns)
            if c.get("t") == "s" and v is not None:
                nilai = teks[int(v.text)]
            elif c.get("t") == "inlineStr":
                nilai = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            else:
                nilai = v.text if v is not None else ""
            isi_baris[kolom - 1] = nilai
        if isi_baris:
            baris.append([isi_baris.get(i, "") for i in range(max(isi_baris) + 1)])
    return baris


def _csv(isi):
    teks = isi.decode("utf-8-sig", errors="replace")
    try:
        dialek = csv.Sniffer().sniff(teks[:2000], delimiters=",;\t")
    except csv.Error:
        dialek = csv.excel
    return [r for r in csv.reader(io.StringIO(teks), dialek)]


def baca_berkas(nama, isi):
    nama = (nama or "").lower()
    if nama.endswith(".xlsx"):
        try:
            return _xlsx(isi)
        except zipfile.BadZipFile:
            raise ValueError("Berkas .xlsx rusak atau bukan Excel")
    if nama.endswith((".csv", ".txt")):
        return _csv(isi)
    raise ValueError("Format berkas harus .xlsx atau .csv")


def _tanggal(v):
    v = str(v or "").strip()
    if re.fullmatch(r"\d+(\.0+)?", v) and 20000 < float(v) < 80000:       # angka seri tanggal Excel
        return date(1899, 12, 30) + timedelta(days=int(float(v)))
    for pola in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%y"):
        try:
            return datetime.strptime(v, pola).date()
        except ValueError:
            pass
    raise ValueError(f"tanggal '{v}' tidak dikenali (pakai format 31/12/2026)")


def _angka(v):
    v = str(v or "").strip().replace(" ", "").replace("Rp", "")
    if "." in v and "," in v:                                   # 16.250,50 atau 16,250.50
        v = v.replace(".", "").replace(",", ".") if v.rfind(",") > v.rfind(".") else v.replace(",", "")
    elif "," in v:
        v = v.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", v):                 # 16.250 = enam belas ribu
        v = v.replace(".", "")
    try:
        n = float(v)
    except ValueError:
        raise ValueError(f"kurs '{v}' bukan angka")
    if n <= 0:
        raise ValueError("kurs harus lebih dari 0")
    return n


def _cari_pilihan(opsi, teks, label):
    teks = str(teks or "").strip().upper()
    for o in opsi:
        if teks in (str(o["id"]).upper(), o["label"].upper(), o["label"].split(" · ")[0].upper()):
            return o["id"]
    raise ValueError(f"{label} '{teks}' tidak dikenal")


def periksa_impor(baris):
    """Baris berkas (baris pertama = judul kolom) -> [{baris, tanggal, mata_uang, ..., galat, peringatan}]."""
    if not baris:
        raise ValueError("Berkas kosong")
    judul = [str(j or "").strip().lower() for j in baris[0]]
    posisi = {k: judul.index(k.lower()) for k in KOLOM_IMPOR if k.lower() in judul}
    kurang = [k for k in KOLOM_IMPOR[:3] if k not in posisi]
    if kurang:
        raise ValueError(f"Kolom wajib tidak ada: {', '.join(kurang)}. Judul kolom: {', '.join(KOLOM_IMPOR)}")
    data = [b for b in baris[1:] if any(str(x or "").strip() for x in b)]
    if len(data) > MAKS_BARIS_IMPOR:
        raise ValueError(f"Maksimal {MAKS_BARIS_IMPOR} baris sekali impor")
    pilihan = ref.pilihan("kurs")
    ambil = lambda b, k: b[posisi[k]] if k in posisi and posisi[k] < len(b) else ""
    hasil, kunci_ada = [], set()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for i, b in enumerate(data, start=2):
            r = {"baris": i, "galat": None, "peringatan": None}
            try:
                r["tanggal"] = _tanggal(ambil(b, "Tanggal"))
                r["id_mata_uang"] = _cari_pilihan(pilihan["id_mata_uang"], ambil(b, "Mata Uang"), "Mata uang")
                r["kurs"] = _angka(ambil(b, "Kurs"))
                r["jenis"] = _cari_pilihan(pilihan["jenis"], ambil(b, "Jenis") or "TRANSAKSI", "Jenis")
                r["id_company"] = _cari_pilihan(pilihan["id_company"], ambil(b, "Perusahaan"), "Perusahaan") if str(ambil(b, "Perusahaan")).strip() else None
                r["sumber"] = _cari_pilihan(pilihan["sumber"], ambil(b, "Sumber"), "Sumber") if str(ambil(b, "Sumber")).strip() else None
                r["keterangan"] = str(ambil(b, "Keterangan")).strip()[:255] or None
                kunci = (r["id_mata_uang"], r["jenis"], r["tanggal"], r["id_company"])
                if kunci in kunci_ada:
                    raise ValueError("dobel dengan baris lain di berkas ini")
                kunci_ada.add(kunci)
                cursor.execute("""SELECT 1 FROM ExchangeRate WHERE CurrencyID = ? AND RateType = ? AND RateDate = ? AND IsVoid = 0
                                  AND (CompID = ? OR (CompID IS NULL AND ? IS NULL))""", *kunci, r["id_company"])
                if cursor.fetchone():
                    raise ValueError("kurs untuk tanggal ini sudah ada (batalkan yang lama bila ingin mengganti)")
                r["_lama"] = kurs_sebelumnya(cursor, *kunci)
            except ValueError as e:
                r["galat"] = str(e)
            hasil.append(r)
    finally:
        conn.close()
    # pembanding = kurs terdekat sebelumnya, dari database atau dari baris lain di berkas ini
    for r in hasil:
        lama = r.pop("_lama", None)
        if r["galat"]:
            continue
        for x in hasil:
            if (not x["galat"] and x["tanggal"] < r["tanggal"] and (not lama or x["tanggal"] > lama[0])
                    and (x["id_mata_uang"], x["jenis"], x["id_company"]) == (r["id_mata_uang"], r["jenis"], r["id_company"])):
                lama = (x["tanggal"], x["kurs"])
        r["peringatan"] = teks_peringatan(r["kurs"], lama)
    return hasil


def simpan_impor(hasil, user_id):
    """Simpan baris yang lolos pemeriksaan dalam satu transaksi. Kembalikan jumlahnya."""
    ok = [r for r in hasil if not r["galat"]]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for r in ok:
            cursor.execute("""INSERT INTO ExchangeRate (CurrencyID, RateType, RateDate, Rate, CompID, Source, Description, CreateBy)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", r["id_mata_uang"], r["jenis"], r["tanggal"], r["kurs"],
                           r["id_company"], r["sumber"], r["keterangan"], user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(ok)


def contoh_csv():
    """Templat impor (dibuka di Excel; pemisah titik koma sesuai pengaturan Indonesia)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(KOLOM_IMPOR)
    w.writerow(["02/01/2026", "USD", "16250", "TRANSAKSI", "", "JISDOR", "contoh, hapus baris ini"])
    w.writerow(["31/01/2026", "USD", "16310,5", "PENUTUPAN", "YBS", "JISDOR", ""])
    return "﻿" + buf.getvalue()
