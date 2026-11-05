"""Tabel detail ke Excel: lembar data dan lembar Info (filter, periode, waktu ekspor). openpyxl write-only supaya hemat memori.

Teks berawalan "=" disimpan sebagai teks, bukan rumus, supaya isi database seperti "=HYPERLINK(...)" tidak dijalankan Excel.
openpyxl diimpor saat dipakai, jadi server tetap menyala walau pustakanya belum terpasang.
"""
import re
from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace

from . import konfigurasi

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAKS_BARIS = konfigurasi.MAKS_BARIS_EKSPOR
FORMAT_TANGGAL = "dd/mm/yyyy"
FORMAT_WAKTU = "dd/mm/yyyy hh:mm"
FORMAT_DESIMAL = "#,##0.00"
LEBAR_MAKS, LEBAR_MIN, CONTOH_BARIS = 50, 8, 200

_ILEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_NAMA_SHEET_ILEGAL = re.compile(r"[\[\]:*?/\\]")
_BERKAS_ILEGAL = re.compile(r"[^A-Za-z0-9._-]+")
PESAN_PUSTAKA_HILANG = "Export Excel butuh pustaka openpyxl yang belum terpasang di server. Jalankan: pip install -r requirements.txt, lalu mulai ulang server."


class PustakaHilang(RuntimeError):
    pass


def _openpyxl():
    try:
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise PustakaHilang(PESAN_PUSTAKA_HILANG) from e
    return SimpleNamespace(Workbook=Workbook, WriteOnlyCell=WriteOnlyCell, Alignment=Alignment, Border=Border, Font=Font, PatternFill=PatternFill, Side=Side,
                           get_column_letter=get_column_letter)


def tersedia():
    try:
        _openpyxl()
    except PustakaHilang:
        return False
    return True


def bersihkan_teks(v):
    """Karakter kontrol membuat berkas Excel rusak."""
    return _ILEGAL.sub("", v)


def nama_sheet(teks, cadangan="Data"):
    """Nama lembar Excel: maksimal 31 karakter, tanpa [ ] : * ? / \\, dan tidak boleh kosong."""
    hasil = _NAMA_SHEET_ILEGAL.sub(" ", bersihkan_teks(str(teks or ""))).strip().strip("'")[:31].strip()
    return hasil or cadangan


def nama_berkas(*bagian):
    """Aman di semua sistem dan di header HTTP."""
    teks = "_".join(str(b) for b in bagian if b not in (None, ""))
    teks = _BERKAS_ILEGAL.sub("_", teks).strip("._")
    return (teks[:120] or "laporan") + ".xlsx"


def _sel(xl, ws, nilai, tipe):
    """Hanya nilai yang butuh format atau pengamanan yang dibungkus WriteOnlyCell (lebih lambat)."""
    if nilai is None:
        return None
    if tipe == "tanggal" and isinstance(nilai, str):
        try:
            c = xl.WriteOnlyCell(ws, value=date.fromisoformat(nilai[:10]))
            c.number_format = FORMAT_TANGGAL
            return c
        except ValueError:
            pass                                    # tanggal tidak sah ditulis sebagai teks
    if tipe == "waktu" and isinstance(nilai, str):
        try:
            c = xl.WriteOnlyCell(ws, value=datetime.fromisoformat(nilai))
            c.number_format = FORMAT_WAKTU
            return c
        except ValueError:
            pass
    if isinstance(nilai, bool):
        return "Ya" if nilai else "Tidak"
    if isinstance(nilai, float):
        c = xl.WriteOnlyCell(ws, value=nilai)
        c.number_format = FORMAT_DESIMAL
        return c
    if isinstance(nilai, (int, date, datetime)):
        return nilai
    teks = bersihkan_teks(str(nilai))
    if teks.startswith("="):
        c = xl.WriteOnlyCell(ws, value=teks)
        c.data_type = "s"                           # teks, bukan rumus
        return c
    return teks


def _lebar(kolom, baris):
    """Menurut judul dan CONTOH_BARIS baris pertama."""
    lebar = []
    for k in kolom:
        panjang = len(str(k["judul"])) + 2
        for r in baris[:CONTOH_BARIS]:
            v = r.get(k["kunci"])
            if v is not None:
                panjang = max(panjang, len(str(v)) + 2)
        lebar.append(max(LEBAR_MIN, min(LEBAR_MAKS, panjang)))
    return lebar


def buat_xlsx(judul, kolom, baris, info):
    """kolom dan baris seperti di respons tabel detail. info: [(label, nilai)] untuk lembar Info; nilai None dilewati."""
    xl = _openpyxl()
    gaya = {"font": xl.Font(bold=True, color="FFFFFF"), "fill": xl.PatternFill("solid", start_color="0369A1"),
            "alignment": xl.Alignment(vertical="center", wrap_text=True)}
    wb = xl.Workbook(write_only=True)

    ws = wb.create_sheet(nama_sheet(judul))
    for i, lebar in enumerate(_lebar(kolom, baris), start=1):
        ws.column_dimensions[xl.get_column_letter(i)].width = lebar
    ws.freeze_panes = "A2"
    kepala = []
    for k in kolom:
        c = xl.WriteOnlyCell(ws, value=bersihkan_teks(str(k["judul"])))
        c.font, c.fill, c.alignment = gaya["font"], gaya["fill"], gaya["alignment"]
        kepala.append(c)
    ws.append(kepala)
    for r in baris:
        ws.append([_sel(xl, ws, r.get(k["kunci"]), k["tipe"]) for k in kolom])
    if kolom:
        ws.auto_filter.ref = f"A1:{xl.get_column_letter(len(kolom))}{len(baris) + 1}"

    wi = wb.create_sheet("Info")
    wi.column_dimensions["A"].width = 26
    wi.column_dimensions["B"].width = 80
    for label, nilai in info:
        if nilai is None:
            continue
        a = xl.WriteOnlyCell(wi, value=bersihkan_teks(str(label)))
        a.font = xl.Font(bold=True)
        wi.append([a, _sel(xl, wi, nilai if isinstance(nilai, (int, float)) else str(nilai), "teks")])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def buat_xlsx_giro(judul, baris, label_periode, info):
    """Jasa giro seperti pivot Excel BANK GIRO: perusahaan sebagai judul kelompok, rekeningnya di bawah, lalu Grand Total."""
    xl = _openpyxl()
    biru = xl.PatternFill("solid", start_color="BDE3F2")
    garis = xl.Side(style="thin", color="7FB7CE")
    tebal = xl.Font(bold=True)
    kanan = xl.Alignment(horizontal="right")
    wb = xl.Workbook()
    ws = wb.active
    ws.title = nama_sheet(judul)
    ws.sheet_view.showGridLines = False
    for kol, lebar in zip("ABCD", (42, 20, 22, 11)):
        ws.column_dimensions[kol].width = lebar
    kepala = [["", "Column Labels", "", ""], ["", "GIRO", "AVG BALANCE", "% GIRO"], ["Row Labels", label_periode, label_periode, label_periode]]
    for r, isi in enumerate(kepala, start=1):
        for c, v in enumerate(isi, start=1):
            sel = ws.cell(r, c, v or None)
            sel.fill, sel.font = biru, tebal
            if c > 1 and r > 1:
                sel.alignment = kanan
    ws.cell(3, 1).alignment = xl.Alignment(horizontal="center")
    ws.freeze_panes = "B4"

    def angka(r, b, huruf_tebal=False):
        for c, kunci, fmt in ((2, "nilai", "#,##0.00"), (3, "rata_saldo", "#,##0.00"), (4, "persen", "0.00%")):
            v = b.get(kunci)
            sel = ws.cell(r, c, None if v is None else (v / 100 if kunci == "persen" else v))
            sel.number_format = fmt
            sel.font = xl.Font(bold=huruf_tebal)

    grup, total = {}, None
    for b in baris:
        if b["perusahaan"] == "Grand total":
            total = b
        elif b["rekening"] != "Total":
            grup.setdefault(b["perusahaan"], []).append(b)
    r = 4
    for nama in sorted(grup):
        for c in range(1, 5):
            ws.cell(r, c).border = xl.Border(bottom=garis)
        ws.cell(r, 1, bersihkan_teks(nama)).font = tebal
        r += 1
        for b in sorted(grup[nama], key=lambda x: x["rekening"]):
            ws.cell(r, 1, bersihkan_teks(b["rekening"])).alignment = xl.Alignment(indent=1)
            angka(r, b)
            r += 1
    if total:
        ws.cell(r, 1, "Grand Total")
        angka(r, total, True)
        for c in range(1, 5):
            sel = ws.cell(r, c)
            sel.fill, sel.font, sel.border = biru, tebal, xl.Border(top=garis)

    wi = wb.create_sheet("Info")
    wi.column_dimensions["A"].width = 26
    wi.column_dimensions["B"].width = 80
    for label, nilai in info:
        if nilai is not None:
            wi.append([bersihkan_teks(str(label)), bersihkan_teks(str(nilai))])
            wi.cell(wi.max_row, 1).font = tebal
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
