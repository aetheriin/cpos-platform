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


_JAM = re.compile(r"\s+\d{1,2}:\d{2}(:\d{2})?(\s*[AP]M)?$", re.I)      # "12:00:00 AM" di belakang tanggal


def urutan_tanggal(nilai):
    """'bulan_dulu' bila tanggal teks di berkas berformat bulan/tanggal (mis. unduhan JISDOR Bank Indonesia: 10/15/2026 12:00:00 AM),
    selain itu 'tanggal_dulu' (31/12/2026). Dilihat dari angka yang lebih dari 12; tanda AM/PM berarti format Amerika."""
    bulan_dulu = False
    for v in nilai:
        v = str(v or "").strip()
        m = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}", v)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            return "tanggal_dulu"
        if b > 12 or re.search(r"[AP]M\s*$", v, re.I):
            bulan_dulu = True
    return "bulan_dulu" if bulan_dulu else "tanggal_dulu"


def _tanggal(v, urutan="tanggal_dulu"):
    v = _JAM.sub("", str(v or "").strip())
    if re.fullmatch(r"\d+(\.\d+)?", v) and 20000 < float(v) < 80000:      # angka seri tanggal Excel
        return date(1899, 12, 30) + timedelta(days=int(float(v)))
    hari_bulan = ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y") if urutan == "bulan_dulu" else ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y")
    for pola in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", *hari_bulan):
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


def periksa_impor(baris, bawaan=None, timpa=False):
    """Baris berkas (baris pertama = judul kolom) -> [{baris, tanggal, ..., aksi, galat, peringatan}].
    Wajib kolom Tanggal dan Kurs; kolom lain boleh tidak ada: nilainya dari bawaan {id_mata_uang, jenis, id_company, sumber}
    (pilihan di layar impor). Tanggal yang kursnya sudah ada: kurs sama -> dilewati; beda -> diganti bila timpa, selain itu dilewati.
    aksi: baru | ganti | lewati (baris dengan galat tidak disimpan)."""
    bawaan = bawaan or {}
    if not baris:
        raise ValueError("Berkas kosong")
    # Baris judul kolom = baris pertama (dari 10 teratas) yang memuat Tanggal dan Kurs; baris di atasnya judul laporan (mis. unduhan BI)
    awal = next((i for i, b in enumerate(baris[:10]) if {"tanggal", "kurs"} <= {str(j or "").strip().lower() for j in b}), None)
    if awal is None:
        raise ValueError("Judul kolom Tanggal dan Kurs tidak ditemukan di 10 baris teratas berkas")
    judul = [str(j or "").strip().lower() for j in baris[awal]]
    posisi = {k: judul.index(k.lower()) for k in KOLOM_IMPOR if k.lower() in judul}
    baris = baris[awal:]
    if "Mata Uang" not in posisi and not bawaan.get("id_mata_uang"):
        raise ValueError("Berkas tidak punya kolom Mata Uang: pilih mata uangnya di layar impor")
    data = [b for b in baris[1:] if any(str(x or "").strip() for x in b)]
    if not data:
        raise ValueError("Berkas tidak berisi baris data")
    if len(data) > MAKS_BARIS_IMPOR:
        raise ValueError(f"Maksimal {MAKS_BARIS_IMPOR} baris sekali impor")
    pilihan = ref.pilihan("kurs")
    ambil = lambda b, k: str(b[posisi[k]] if k in posisi and posisi[k] < len(b) else "").strip()
    urutan = urutan_tanggal(ambil(b, "Tanggal") for b in data)
    hasil, kunci_ada = [], set()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for i, b in enumerate(data, start=awal + 2):
            r = {"baris": i, "galat": None, "peringatan": None, "aksi": None, "kurs_lama": None}
            try:
                r["tanggal"] = _tanggal(ambil(b, "Tanggal"), urutan)
                kode = ambil(b, "Mata Uang")
                if kode:
                    try:
                        r["id_mata_uang"] = _cari_pilihan(pilihan["id_mata_uang"], kode, "Mata uang")
                    except ValueError:
                        raise ValueError(f"mata uang '{kode.upper()}' belum terdaftar. Tambahkan di Data Master › Mata Uang & Bank, lalu impor ulang")
                elif bawaan.get("id_mata_uang"):
                    r["id_mata_uang"] = bawaan["id_mata_uang"]
                else:
                    raise ValueError("mata uang kosong")
                r["kurs"] = _angka(ambil(b, "Kurs"))
                r["jenis"] = _cari_pilihan(pilihan["jenis"], ambil(b, "Jenis"), "Jenis") if ambil(b, "Jenis") else (bawaan.get("jenis") or "TRANSAKSI")
                r["id_company"] = (_cari_pilihan(pilihan["id_company"], ambil(b, "Perusahaan"), "Perusahaan") if ambil(b, "Perusahaan")
                                   else bawaan.get("id_company") or None)
                r["sumber"] = _cari_pilihan(pilihan["sumber"], ambil(b, "Sumber"), "Sumber") if ambil(b, "Sumber") else bawaan.get("sumber") or None
                r["keterangan"] = ambil(b, "Keterangan")[:255] or None
                kunci = (r["id_mata_uang"], r["jenis"], r["tanggal"], r["id_company"])
                if kunci in kunci_ada:
                    raise ValueError("tanggal ini muncul lebih dari sekali di berkas")
                kunci_ada.add(kunci)
                cursor.execute("""SELECT ExchangeRateID, Rate FROM ExchangeRate WHERE CurrencyID = ? AND RateType = ? AND RateDate = ? AND IsVoid = 0
                                  AND (CompID = ? OR (CompID IS NULL AND ? IS NULL))""", *kunci, r["id_company"])
                ada = cursor.fetchone()
                if ada is None:
                    r["aksi"] = "baru"
                else:
                    r["id_lama"], r["kurs_lama"] = ada[0], float(ada[1])
                    r["aksi"] = "lewati" if abs(r["kurs_lama"] - r["kurs"]) < 1e-6 or not timpa else "ganti"
                r["_lama"] = kurs_sebelumnya(cursor, *kunci)
            except ValueError as e:
                r["galat"] = str(e)
            hasil.append(r)
    finally:
        conn.close()
    # pembanding = kurs terdekat sebelumnya, dari database atau dari baris lain di berkas ini
    for r in hasil:
        lama = r.pop("_lama", None)
        if r["galat"] or r["aksi"] == "lewati":
            continue
        for x in hasil:
            if (not x["galat"] and x["tanggal"] < r["tanggal"] and (not lama or x["tanggal"] > lama[0])
                    and (x["id_mata_uang"], x["jenis"], x["id_company"]) == (r["id_mata_uang"], r["jenis"], r["id_company"])):
                lama = (x["tanggal"], x["kurs"])
        r["peringatan"] = teks_peringatan(r["kurs"], lama)
    return hasil


def simpan_impor(hasil, user_id):
    """Simpan baris baru dan ganti (kurs lama dibatalkan, riwayatnya tetap) dalam satu transaksi. Kembalikan (baru, diganti)."""
    simpan = [r for r in hasil if not r["galat"] and r["aksi"] in ("baru", "ganti")]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for r in simpan:
            if r["aksi"] == "ganti":
                cursor.execute("UPDATE ExchangeRate SET IsVoid = 1, VoidDate = GETDATE(), VoidBy = ? WHERE ExchangeRateID = ? AND IsVoid = 0",
                               user_id, r["id_lama"])
            cursor.execute("""INSERT INTO ExchangeRate (CurrencyID, RateType, RateDate, Rate, CompID, Source, Description, CreateBy)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", r["id_mata_uang"], r["jenis"], r["tanggal"], r["kurs"],
                           r["id_company"], r["sumber"], r["keterangan"], user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return sum(r["aksi"] == "baru" for r in simpan), sum(r["aksi"] == "ganti" for r in simpan)


def _sel_xlsx(baris, kolom, nilai):
    ref_sel = f"{chr(65 + kolom)}{baris}"
    if isinstance(nilai, (int, float)):
        return f'<c r="{ref_sel}"><v>{nilai}</v></c>'
    teks = str(nilai).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    gaya = ' s="1"' if baris == 1 else ""
    return f'<c r="{ref_sel}" t="inlineStr"{gaya}><is><t>{teks}</t></is></c>'


_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_NS = "http://schemas.openxmlformats.org"


def contoh_xlsx():
    """Templat impor .xlsx (dibuat tanpa library tambahan). Hanya Tanggal dan Kurs yang wajib; kolom lain boleh dihapus."""
    baris = [list(KOLOM_IMPOR),
             ["02/01/2026", "USD", 16250, "TRANSAKSI", "", "JISDOR", "contoh, hapus baris ini"],
             ["31/01/2026", "USD", 16310.5, "PENUTUPAN", "YBS", "JISDOR", ""]]
    isi_baris = "".join(f'<row r="{r}">' + "".join(_sel_xlsx(r, c, v) for c, v in enumerate(b) if v != "") + "</row>"
                        for r, b in enumerate(baris, start=1))
    berkas = {
        "[Content_Types].xml": _XML + f'<Types xmlns="{_NS}/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": _XML + f'<Relationships xmlns="{_NS}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_NS}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": _XML + f'<workbook xmlns="{_NS}/spreadsheetml/2006/main" xmlns:r="{_NS}/officeDocument/2006/relationships">'
            '<sheets><sheet name="Kurs" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": _XML + f'<Relationships xmlns="{_NS}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_NS}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{_NS}/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": _XML + f'<styleSheet xmlns="{_NS}/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": _XML + f'<worksheet xmlns="{_NS}/spreadsheetml/2006/main">'
            '<cols><col min="1" max="6" width="14" customWidth="1"/><col min="7" max="7" width="30" customWidth="1"/></cols>'
            f'<sheetData>{isi_baris}</sheetData></worksheet>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nama, isi in berkas.items():
            z.writestr(nama, isi)
    return buf.getvalue()
