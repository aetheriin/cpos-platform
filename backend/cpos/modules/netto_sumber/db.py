"""Data form Netto Sumber: tiket penjualan dari dbo.TIKET_PENJUALAN per perusahaan, isian di dbo.NettoSumberIsian."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pyodbc

from utils.db_utils import get_connection, query as _query

SP = "dbo.TIKET_PENJUALAN"
JENIS = "JUAL"
# Produk penjualan yang memakai netto sumber. Tiket produk lain hanya ikut bila pecahan split.
PRODUK = ("CPO", "PFAD", "R.POME", "RUCO")
_PRODUK = {p.casefold() for p in PRODUK}
_NONAKTIF = {"0", "false", "n", "no", "off", "inactive", "nonaktif", "non-aktif", "tidak aktif", "disabled"}
_PECAHAN = re.compile(r"-\d+$")


class TabelBelumAda(RuntimeError):
    """dbo.NettoSumberIsian belum ada: jalankan database/perubahan/029_netto_sumber.sql di database Main."""


PESAN_TABEL = "Isian netto sumber belum bisa dipakai. Hubungi IT."


class SudahBerubah(ValueError):
    pass


def _tabel_belum_ada(e):
    return "nettosumberisian" in str(e).casefold() and ("invalid object" in str(e).casefold() or "42s02" in str(e).casefold())


def perusahaan_ascend():
    """Perusahaan ERP aktif yang tiketnya bisa dibaca SP (sama dengan daftar perusahaan laporan Analytics): [{kode, nama}]."""
    rows = _query("""SELECT RTRIM(CompID) AS kode, CompName AS nama, Status AS status FROM dbo.Company
                     WHERE CompType = 'CLOUD' AND ISNULL(LTRIM(RTRIM(CompAddr)), '') <> ''
                       AND ISNULL(LTRIM(RTRIM(CompDataBase)), '') <> '' ORDER BY CompID""")
    return [{"kode": r["kode"], "nama": r["nama"] or r["kode"]} for r in rows
            if r["status"] is None or str(r["status"]).strip().casefold() not in _NONAKTIF]


def _angka(v):
    return 0.0 if v is None else float(v)


def _tanggal(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _tiket_sp(kode, mulai, akhir):
    conn = get_connection()
    conn.timeout = 120          # SP membaca server Ascend lewat server tertaut
    try:
        cur = conn.cursor()
        cur.execute(f"EXEC {SP} ?, ?, ?", kode, mulai, akhir)
        while cur.description is None:
            if not cur.nextset():
                return []
        kolom = [c[0] for c in cur.description]
        baris = [dict(zip(kolom, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    hasil = []
    for r in baris:
        tiket = str(r.get("No. Tiket") or "").strip()
        if not tiket or r.get("Tanggal") is None:
            continue
        split = str(r.get("Split") or "").strip() == "Ya"
        hasil.append({
            "comp": kode, "tanggal": _tanggal(r["Tanggal"]), "tiket": tiket, "split": split,
            "induk": _PECAHAN.sub("", tiket) if split else None,
            "produk": str(r.get("Produk") or "").strip(), "pembeli": str(r.get("Nama Pembeli") or "").strip(),
            "no_do": str(r.get("Nomor DO") or "").strip(), "kendaraan": str(r.get("No. Kendaraan") or "").strip(),
            "netto": _angka(r.get("Netto")), "sumber_ascend": _angka(r.get("Netto Sumber")),
        })
    return hasil


def tiket(kode_pt, mulai, akhir):
    """Tiket penjualan yang memakai netto sumber (produk PRODUK atau pecahan split), semua perusahaan sekaligus.
    Kembalikan (tiket, {kode PT yang gagal dibaca: galat}); satu PT gagal tidak menggagalkan yang lain."""
    def satu(kode):
        try:
            return kode, _tiket_sp(kode, mulai, akhir), None
        except pyodbc.Error as e:
            return kode, [], e

    with ThreadPoolExecutor(max_workers=min(len(kode_pt), 4) or 1) as pool:
        hasil = list(pool.map(satu, kode_pt))
    semua = [t for _, daftar, _ in hasil for t in daftar]
    return [t for t in semua if t["split"] or t["produk"].casefold() in _PRODUK], {k: e for k, _, e in hasil if e}


def satu_tiket(kode, no_tiket, tgl):
    """Tiket dibaca ulang dari Ascend saat simpan, supaya angka pembanding tidak berasal dari browser."""
    return next((t for t in _tiket_sp(kode, tgl, tgl) if t["tiket"] == no_tiket), None)


_KOLOM_ISIAN = """i.EntryID AS id, RTRIM(i.CompID) AS comp, i.TicketNo AS tiket, i.NettoSumber AS netto_sumber,
                  i.RefNo AS referensi, i.Notes AS catatan, i.NettoAscend AS netto_ascend,
                  i.NettoSumberAscend AS sumber_ascend, i.CreateDate AS pada, u.Nama AS oleh"""


def isian_terakhir(mulai, akhir):
    """{(comp, tiket): baris isian terakhir} untuk tiket bertanggal di sekitar rentang. Baris terakhir bisa pembatalan
    (netto_sumber None). TabelBelumAda bila 029_netto_sumber.sql belum dijalankan."""
    try:
        rows = _query(f"""SELECT {_KOLOM_ISIAN}
                          FROM dbo.NettoSumberIsian i LEFT JOIN dbo.Users u ON u.UserID = i.CreateBy
                          WHERE i.TicketType = ? AND i.TicketDate BETWEEN ? AND ?
                            AND i.EntryID = (SELECT MAX(x.EntryID) FROM dbo.NettoSumberIsian x
                                             WHERE x.CompID = i.CompID AND x.TicketType = i.TicketType AND x.TicketNo = i.TicketNo)""",
                      JENIS, mulai - timedelta(days=7), akhir + timedelta(days=7))
    except pyodbc.Error as e:
        if _tabel_belum_ada(e):
            raise TabelBelumAda(PESAN_TABEL) from e
        raise
    return {(r["comp"], r["tiket"]): r for r in rows}


def riwayat(kode, no_tiket):
    try:
        return _query(f"""SELECT {_KOLOM_ISIAN}
                          FROM dbo.NettoSumberIsian i LEFT JOIN dbo.Users u ON u.UserID = i.CreateBy
                          WHERE i.CompID = ? AND i.TicketType = ? AND i.TicketNo = ? ORDER BY i.EntryID DESC""",
                      kode, JENIS, no_tiket)
    except pyodbc.Error as e:
        if _tabel_belum_ada(e):
            return []
        raise


def simpan(kode, t, netto_sumber, referensi, catatan, id_terakhir, id_user):
    """Tambah satu baris isian (netto_sumber None = batalkan isian). id_terakhir = EntryID terakhir yang dilihat pengguna
    (0 bila belum ada): bila sudah ada yang lebih baru, SudahBerubah supaya isian orang lain tidak tertimpa diam-diam."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT ISNULL(MAX(EntryID), 0) FROM dbo.NettoSumberIsian WITH (UPDLOCK, HOLDLOCK)
                       WHERE CompID = ? AND TicketType = ? AND TicketNo = ?""", kode, JENIS, t["tiket"])
        if int(cur.fetchone()[0]) != int(id_terakhir or 0):
            raise SudahBerubah("Isian tiket ini baru saja diubah orang lain. Tutup lalu buka lagi tiketnya untuk melihat angka terbaru.")
        cur.execute("""INSERT INTO dbo.NettoSumberIsian (CompID, TicketType, TicketNo, TicketDate, NettoSumber, RefNo, Notes,
                                                         NettoAscend, NettoSumberAscend, CreateBy)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    kode, JENIS, t["tiket"], t["tanggal"], netto_sumber, referensi or None, catatan or None,
                    t["netto"], t["sumber_ascend"], id_user)
        conn.commit()
    except pyodbc.Error as e:
        conn.rollback()
        if _tabel_belum_ada(e):
            raise TabelBelumAda(PESAN_TABEL) from e
        raise
    except SudahBerubah:
        conn.rollback()
        raise
    finally:
        conn.close()
