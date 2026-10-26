"""RekapIn: data request operator & kategori (schema rekap), harga harian (dbo.DailyPrice), tiket timbang (CPOS).

Operator = akun CPOS di departemen timbangan (OPERATOR_DEPT); cakupan perusahaan / area mengikuti user yang login
(utils.area.company_user / dbo.fn_UserScope), jadi aturan sama dengan halaman CPOS lain."""
import json
from datetime import date, timedelta

from utils.db_utils import get_connection, _rows_to_dicts

OPERATOR_DEPT = ("TBG",)          # Departemen yang dianggap operator timbangan
STATUS = ("Pending", "Approved", "Rejected", "Done")


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor) if cursor.description else []
    finally:
        conn.close()


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        n = cursor.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ===== Kategori kesalahan =====
def daftar_kategori(aktif_saja=False):
    return _query(f"""SELECT c.CategoryID AS id, c.CategoryName AS nama, c.Active AS is_active, c.CreateDate AS dibuat,
                             (SELECT COUNT(*) FROM rekap.OperatorRequest r WHERE r.CategoryID = c.CategoryID) AS jumlah_request
                      FROM rekap.RequestCategory c {'WHERE c.Active = 1' if aktif_saja else ''}
                      ORDER BY c.Active DESC, c.CategoryName""")


def simpan_kategori(id_kategori, nama, id_user):
    if any(k["nama"].casefold() == nama.casefold() and k["id"] != id_kategori for k in daftar_kategori()):
        raise ValueError("Kategori dengan nama itu sudah ada")
    if id_kategori is None:
        _ubah("INSERT INTO rekap.RequestCategory (CategoryName, CreateBy) VALUES (?, ?)", nama, id_user)
    elif not _ubah("UPDATE rekap.RequestCategory SET CategoryName = ? WHERE CategoryID = ?", nama, id_kategori):
        raise ValueError("Kategori tidak ditemukan")


def hapus_kategori(id_kategori):
    """Kategori yang sudah dipakai request tidak dihapus, hanya dinonaktifkan. Kembalikan 'hapus' / 'nonaktif'."""
    if _query("SELECT 1 AS x FROM rekap.OperatorRequest WHERE CategoryID = ?", id_kategori):
        _ubah("UPDATE rekap.RequestCategory SET Active = 0 WHERE CategoryID = ?", id_kategori)
        return "nonaktif"
    if not _ubah("DELETE FROM rekap.RequestCategory WHERE CategoryID = ?", id_kategori):
        raise ValueError("Kategori tidak ditemukan")
    return "hapus"


def set_aktif_kategori(id_kategori, aktif):
    if not _ubah("UPDATE rekap.RequestCategory SET Active = ? WHERE CategoryID = ?", 1 if aktif else 0, id_kategori):
        raise ValueError("Kategori tidak ditemukan")


# ===== Operator =====
def daftar_operator(id_user):
    """Operator timbangan aktif dalam cakupan area user yang login."""
    dept = ", ".join("?" * len(OPERATOR_DEPT))
    return _query(f"""SELECT u.UserID AS id_user, u.Nama AS nama, u.UserName AS username, a.CompID AS id_company,
                             a.CompID + ' · ' + a.AreaName AS area
                      FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID
                      JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
                      WHERE u.Active = 1 AND u.UserName IS NOT NULL AND ld.DeptID IN ({dept})
                        AND u.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserScope(?))
                      ORDER BY u.Nama""", *OPERATOR_DEPT, id_user)


def adalah_operator(id_user):
    dept = ", ".join("?" * len(OPERATOR_DEPT))
    return bool(_query(f"""SELECT 1 AS x FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID
                           WHERE u.UserID = ? AND ld.DeptID IN ({dept})""", id_user, *OPERATOR_DEPT))


# ===== Tiket timbang 7 hari terakhir (CPOS) =====
def tiket_operator(id_operator, q=""):
    """Tiket di perusahaan operator, 7 hari terakhir. [{TicketNo, Tanggal, ProductName, VehicleNo, NamaSupir, Bruto,
    Tara, Netto, Operator}] - nama kolom sama dengan RekapIn lama supaya info tiket tersimpan dengan format yang sama."""
    q = f"%{q.strip()}%"
    rows = _query("""SELECT TOP 50 t.TicketNumber AS TicketNo, t.TicketDate AS Tanggal, p.ProductName, v.NoVehicle AS VehicleNo,
                            d.Nama AS NamaSupir, s.Bruto, s.Tara, s.Netto, o.Nama AS Operator
                     FROM WeightBridge t
                     JOIN CompanyArea a ON a.CompAreaID = t.CompAreaID
                     JOIN Product p ON p.ProductID = t.ProductID
                     JOIN DetailVehicle v ON v.IDVehicle = t.IDVehicle
                     JOIN Users d ON d.UserID = t.DriverID
                     LEFT JOIN WeighingSummary s ON s.TicketNumber = t.TicketNumber
                     LEFT JOIN Users o ON o.UserID = s.OperatorID
                     WHERE a.CompID = (SELECT a2.CompID FROM Users u JOIN CompanyArea a2 ON a2.CompAreaID = u.CompAreaID WHERE u.UserID = ?)
                       AND t.TicketDate >= ?
                       AND (t.TicketNumber LIKE ? OR v.NoVehicle LIKE ? OR p.ProductName LIKE ?)
                     ORDER BY t.TicketDate DESC""", id_operator, date.today() - timedelta(days=7), q, q, q)
    for r in rows:
        r["Tanggal"] = r["Tanggal"].strftime("%Y-%m-%d %H:%M") if r["Tanggal"] else ""
        for k in ("Bruto", "Tara", "Netto"):
            r[k] = f"{r[k]:,.0f}".replace(",", ".") if r[k] is not None else ""
        for k in r:
            r[k] = "" if r[k] is None else str(r[k])
    return rows


# ===== Request operator =====
_SELECT_REQ = """SELECT r.RequestID AS id, r.OperatorID AS id_operator, o.Nama AS operator, a.CompID AS id_company,
                        r.CategoryID AS id_kategori, c.CategoryName AS kategori, r.TicketNumber AS tiket,
                        r.TicketDetails AS info_tiket, r.Remarks AS catatan, r.ActionRemarks AS catatan_aksi, r.Status AS status,
                        r.CreateDate AS dibuat, b.Nama AS dibuat_oleh, r.ActionDate AS tgl_aksi, x.Nama AS aksi_oleh,
                        r.DoneDate AS tgl_selesai
                 FROM rekap.OperatorRequest r
                 JOIN Users o ON o.UserID = r.OperatorID
                 LEFT JOIN CompanyArea a ON a.CompAreaID = o.CompAreaID
                 JOIN rekap.RequestCategory c ON c.CategoryID = r.CategoryID
                 LEFT JOIN Users b ON b.UserID = r.CreateBy
                 LEFT JOIN Users x ON x.UserID = r.ActionBy"""


def daftar_request(id_user, status=None, hanya_operator=None):
    """Request operator dalam cakupan area user (operator: hanya miliknya sendiri)."""
    syarat, args = ["o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserScope(?))"], [id_user]
    if status:
        syarat.append("r.Status = ?")
        args.append(status)
    if hanya_operator:
        syarat.append("r.OperatorID = ?")
        args.append(hanya_operator)
    rows = _query(_SELECT_REQ + " WHERE " + " AND ".join(syarat) + " ORDER BY r.CreateDate DESC", *args)
    for r in rows:
        try:
            r["info_tiket"] = json.loads(r["info_tiket"] or "{}")
        except ValueError:
            r["info_tiket"] = {}
    return rows


def get_request(id_request):
    rows = _query(_SELECT_REQ + " WHERE r.RequestID = ?", id_request)
    return rows[0] if rows else None


def simpan_request(id_request, id_operator, id_kategori, tiket, info_tiket, catatan, id_user):
    """Tambah / ubah. Request yang sudah ditolak atau selesai tidak bisa diubah."""
    info = json.dumps(info_tiket or {}, ensure_ascii=False, default=str)
    if id_request is None:
        _ubah("""INSERT INTO rekap.OperatorRequest (OperatorID, CategoryID, TicketNumber, TicketDetails, Remarks, CreateBy)
                 VALUES (?, ?, ?, ?, ?, ?)""", id_operator, id_kategori, tiket, info, catatan, id_user)
    elif not _ubah("""UPDATE rekap.OperatorRequest SET OperatorID = ?, CategoryID = ?, TicketNumber = ?, TicketDetails = ?, Remarks = ?
                      WHERE RequestID = ? AND Status NOT IN ('Rejected', 'Done')""",
                   id_operator, id_kategori, tiket, info, catatan, id_request):
        raise ValueError("Request yang sudah ditolak atau selesai tidak dapat diubah")


def hapus_request(id_request):
    if not _ubah("DELETE FROM rekap.OperatorRequest WHERE RequestID = ? AND Status NOT IN ('Rejected', 'Done')", id_request):
        raise ValueError("Request yang sudah ditolak atau selesai tidak dapat dihapus")


def ubah_status(id_request, status, catatan, id_user):
    """Approved / Rejected hanya dari Pending; Done dari Pending / Approved. Kembalikan True bila berubah."""
    if status in ("Approved", "Rejected"):
        return bool(_ubah("""UPDATE rekap.OperatorRequest SET Status = ?, ActionRemarks = ?, ActionBy = ?, ActionDate = GETDATE()
                             WHERE RequestID = ? AND Status = 'Pending'""", status, (catatan or "")[:255], id_user, id_request))
    if status == "Done":
        return bool(_ubah("""UPDATE rekap.OperatorRequest SET Status = 'Done', DoneBy = ?, DoneDate = GETDATE()
                             WHERE RequestID = ? AND Status IN ('Pending', 'Approved')""", id_user, id_request))
    raise ValueError("Status tidak dikenal")


def ringkas_request(id_user, hanya_operator=None):
    hasil = dict.fromkeys(STATUS, 0)
    syarat = "o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserScope(?))" + (" AND r.OperatorID = ?" if hanya_operator else "")
    for r in _query(f"""SELECT r.Status, COUNT(*) AS n FROM rekap.OperatorRequest r JOIN Users o ON o.UserID = r.OperatorID
                        WHERE {syarat} GROUP BY r.Status""", id_user, *([hanya_operator] if hanya_operator else [])):
        hasil[r["Status"]] = r["n"]
    return hasil


# ===== Harga harian (dbo.DailyPrice, sama dengan Isi Harga di Dashboard CPOS) =====
def daftar_harga(companies, id_company="", tanggal="", batas=500):
    """companies: daftar CompID yang boleh dilihat (None = semua)."""
    syarat, args = [], []
    if companies is not None:
        if not companies:
            return []
        syarat.append(f"h.CompID IN ({', '.join('?' * len(companies))})")
        args += sorted(companies)
    if id_company:
        syarat.append("h.CompID = ?")
        args.append(id_company)
    if tanggal:
        syarat.append("h.PriceDate = ?")
        args.append(tanggal)
    return _query(f"""SELECT TOP {int(batas)} h.CompID AS id_company, c.CompName AS perusahaan, h.PriceDate AS tanggal,
                             h.CPOPrice AS harga_cpo, h.KernelPrice AS harga_kernel, h.OERCPO AS oer_cpo,
                             h.ProcessingCost AS biaya_olah, h.RSIQty AS qty_rsi, u.Nama AS oleh, h.UpdateDate AS diubah
                      FROM DailyPrice h JOIN Company c ON c.CompID = h.CompID LEFT JOIN Users u ON u.UserID = h.UpdateBy
                      {('WHERE ' + ' AND '.join(syarat)) if syarat else ''}
                      ORDER BY h.PriceDate DESC, h.CompID""", *args)


def harga_ada(id_company, tanggal):
    return bool(_query("SELECT 1 AS x FROM DailyPrice WHERE CompID = ? AND PriceDate = ?", id_company, tanggal))


def hapus_harga(id_company, tanggal):
    if not _ubah("DELETE FROM DailyPrice WHERE CompID = ? AND PriceDate = ?", id_company, tanggal):
        raise ValueError("Data harga tidak ditemukan")


def tren_harga(companies, hari=7):
    """Harga CPO & kernel per perusahaan, hari terakhir: {id_company: {tanggal: (cpo, kernel)}}"""
    rows = daftar_harga(companies, batas=1000)
    batas = date.today() - timedelta(days=hari - 1)
    hasil = {}
    for r in rows:
        if r["tanggal"] >= batas:
            hasil.setdefault(r["id_company"], {})[r["tanggal"]] = (float(r["harga_cpo"]), float(r["harga_kernel"]))
    return hasil


def request_dalam_cakupan(id_request, id_user):
    """Request ada dan operatornya di area yang boleh diurus user."""
    return bool(_query("""SELECT 1 AS x FROM rekap.OperatorRequest r JOIN Users o ON o.UserID = r.OperatorID
                          WHERE r.RequestID = ? AND o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserScope(?))""",
                       id_request, id_user))
