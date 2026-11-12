"""RekapIn: data request operator & kategori (schema rekap), harga harian (dbo.DailyPrice), tiket timbang (Ascend / CPOS).

"Operator" = orang yang melakukan kesalahan: karyawan mana pun dalam cakupan data menu Request Operator (dbo.fn_UserMenuScope),
jadi aturan sama dengan halaman CPOS lain. Persetujuan request memakai Alur Persetujuan CPOS (jenis REKAP_*)."""
import json
from datetime import date, timedelta

from utils import harga_sumber
from utils.db_utils import get_connection, _rows_to_dicts

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
                             (SELECT COUNT(*) FROM dbo.OperatorRequest r WHERE r.CategoryID = c.CategoryID) AS jumlah_request
                      FROM dbo.RequestCategory c {'WHERE c.Active = 1' if aktif_saja else ''}
                      ORDER BY c.Active DESC, c.CategoryName""")


def simpan_kategori(id_kategori, nama, id_user):
    if any(k["nama"].casefold() == nama.casefold() and k["id"] != id_kategori for k in daftar_kategori()):
        raise ValueError("Kategori dengan nama itu sudah ada")
    if id_kategori is None:
        _ubah("INSERT INTO dbo.RequestCategory (CategoryName, CreateBy) VALUES (?, ?)", nama, id_user)
    elif not _ubah("UPDATE dbo.RequestCategory SET CategoryName = ? WHERE CategoryID = ?", nama, id_kategori):
        raise ValueError("Kategori tidak ditemukan")


def hapus_kategori(id_kategori):
    """Kategori yang sudah dipakai request tidak dihapus, hanya dinonaktifkan. Kembalikan 'hapus' / 'nonaktif'."""
    if _query("SELECT 1 AS x FROM dbo.OperatorRequest WHERE CategoryID = ?", id_kategori):
        _ubah("UPDATE dbo.RequestCategory SET Active = 0 WHERE CategoryID = ?", id_kategori)
        return "nonaktif"
    if not _ubah("DELETE FROM dbo.RequestCategory WHERE CategoryID = ?", id_kategori):
        raise ValueError("Kategori tidak ditemukan")
    return "hapus"


def set_aktif_kategori(id_kategori, aktif):
    if not _ubah("UPDATE dbo.RequestCategory SET Active = ? WHERE CategoryID = ?", 1 if aktif else 0, id_kategori):
        raise ValueError("Kategori tidak ditemukan")


# ===== Operator (karyawan siapa saja dalam cakupan user) =====
def daftar_operator(id_user):
    """Karyawan aktif dalam cakupan area user yang login: [{id_user, nama, nik, id_company, area}]"""
    return _query("""SELECT u.UserID AS id_user, u.Nama AS nama, u.NoKTP AS nik, a.CompID AS id_company,
                            a.CompID + ' · ' + a.AreaName AS area
                     FROM Users u JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
                     WHERE u.Active = 1 AND u.UserLevelID IS NOT NULL
                       AND u.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserMenuScope(?, 'RK_REQUEST'))
                     ORDER BY u.Nama""", id_user)


# ===== Tiket timbang 7 hari terakhir =====
def tiket_cpos(id_company, q=""):
    """Cadangan bila koneksi ERP belum diisi: tiket di database CPOS sendiri. Kolom sama dengan tiket_ascend()."""
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
                     WHERE a.CompID = ?
                       AND t.TicketDate >= ?
                       AND (t.TicketNumber LIKE ? OR v.NoVehicle LIKE ? OR p.ProductName LIKE ?)
                     ORDER BY t.TicketDate DESC""", id_company, date.today() - timedelta(days=7), q, q, q)
    for r in rows:
        r["Tanggal"] = r["Tanggal"].strftime("%Y-%m-%d %H:%M") if r["Tanggal"] else ""
        for k in ("Bruto", "Tara", "Netto"):
            r[k] = f"{r[k]:,.0f}".replace(",", ".") if r[k] is not None else ""
        for k in r:
            r[k] = "" if r[k] is None else str(r[k])
    return rows


KOLOM_TIKET = {"TicketNo": ("ticketno", "ticket_no", "ticketnumber"), "Tanggal": ("tanggal", "date"),
               "ProductName": ("productname",), "VehicleNo": ("vehicleno",), "NamaSupir": ("namasupir", "driversname", "drivername"),
               "Bruto": ("bruto",), "Tara": ("tara",), "Netto": ("netto",), "Operator": ("operator",)}


def tiket_ascend(id_company, q=""):
    """Tiket 7 hari terakhir dari Ascend: EXEC dbo.sp_GetTiketH7ByCompany <kode perusahaan> (sama dengan RekapIn lama).
    Kode perusahaan CPOS = CompName di Main.dbo.Company. Nama kolom dirapikan seperti RekapIn lama."""
    from modules.rekapin import erp
    hasil, ada, q = [], set(), q.strip().casefold()
    batas = date.today() - timedelta(days=7)
    for rows in erp.jalankan_prosedur("dbo.sp_GetTiketH7ByCompany", id_company):
        for row in rows:
            nilai = {str(k).replace("_", "").lower(): v for k, v in row.items()}
            t = {f: next((nilai[k] for k in alias if k in nilai), None) for f, alias in KOLOM_TIKET.items()}
            tgl = t["Tanggal"]
            tgl = tgl.date() if hasattr(tgl, "date") and callable(tgl.date) else tgl
            if not t["TicketNo"] or not tgl or str(t["TicketNo"]) in ada:
                continue
            try:
                tgl = tgl if isinstance(tgl, date) else date.fromisoformat(str(tgl)[:10])
            except ValueError:
                continue
            if not batas <= tgl <= date.today():
                continue
            t["Tanggal"] = tgl.isoformat()
            for k in ("Bruto", "Tara", "Netto"):
                if isinstance(t[k], (int, float)) or hasattr(t[k], "as_tuple"):
                    t[k] = f"{float(t[k]):,.0f}".replace(",", ".")
            t = {k: "" if v is None else str(v).strip() for k, v in t.items()}
            if q and not any(q in t[k].casefold() for k in ("TicketNo", "VehicleNo", "ProductName")):
                continue
            ada.add(t["TicketNo"])
            hasil.append(t)
    return hasil[:50]


# ===== Request operator =====
_SELECT_REQ = """SELECT r.RequestID AS id, r.OperatorID AS id_operator, o.Nama AS operator, a.CompID AS id_company,
                        r.CategoryID AS id_kategori, c.CategoryName AS kategori, r.TicketNumber AS tiket,
                        r.TicketDetails AS info_tiket, r.Remarks AS catatan, r.ActionRemarks AS catatan_aksi, r.Status AS status,
                        r.CreateDate AS dibuat, b.Nama AS dibuat_oleh, r.ActionDate AS tgl_aksi, x.Nama AS aksi_oleh,
                        r.DoneDate AS tgl_selesai
                 FROM dbo.OperatorRequest r
                 JOIN Users o ON o.UserID = r.OperatorID
                 LEFT JOIN CompanyArea a ON a.CompAreaID = o.CompAreaID
                 JOIN dbo.RequestCategory c ON c.CategoryID = r.CategoryID
                 LEFT JOIN Users b ON b.UserID = r.CreateBy
                 LEFT JOIN Users x ON x.UserID = r.ActionBy"""


def daftar_request(id_user, status=None, hanya_operator=None, juga_id=()):
    """Request dalam cakupan area user. hanya_operator = id user: hanya request tentang dia / yang dia buat
    (ditambah juga_id: request yang menunggu persetujuannya)."""
    syarat, args = ["o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserMenuScope(?, 'RK_REQUEST'))"], [id_user]
    if status:
        syarat.append("r.Status = ?")
        args.append(status)
    if hanya_operator:
        tambahan = f" OR r.RequestID IN ({', '.join(str(int(i)) for i in juga_id)})" if juga_id else ""
        syarat.append(f"(r.OperatorID = ? OR r.CreateBy = ?{tambahan})")
        args += [hanya_operator, hanya_operator]
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
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO dbo.OperatorRequest (OperatorID, CategoryID, TicketNumber, TicketDetails, Remarks, CreateBy)
                              OUTPUT INSERTED.RequestID VALUES (?, ?, ?, ?, ?, ?)""", id_operator, id_kategori, tiket, info, catatan, id_user)
            id_baru = cursor.fetchone()[0]
            conn.commit()
            return id_baru
        finally:
            conn.close()
    if not _ubah("""UPDATE dbo.OperatorRequest SET OperatorID = ?, CategoryID = ?, TicketNumber = ?, TicketDetails = ?, Remarks = ?
                      WHERE RequestID = ? AND Status NOT IN ('Rejected', 'Done')""",
                   id_operator, id_kategori, tiket, info, catatan, id_request):
        raise ValueError("Request yang sudah ditolak atau selesai tidak dapat diubah")
    return id_request


def hapus_request(id_request):
    if not _ubah("DELETE FROM dbo.OperatorRequest WHERE RequestID = ? AND Status NOT IN ('Rejected', 'Done')", id_request):
        raise ValueError("Request yang sudah ditolak atau selesai tidak dapat dihapus")


def ubah_status(id_request, status, catatan, id_user):
    """Approved / Rejected hanya dari Pending (dipanggil saat persetujuan selesai); Done hanya dari Approved."""
    if status in ("Approved", "Rejected"):
        return bool(_ubah("""UPDATE dbo.OperatorRequest SET Status = ?, ActionRemarks = ISNULL(CAST(? AS NVARCHAR(255)), ActionRemarks), ActionBy = ?,
                                    ActionDate = GETDATE()
                             WHERE RequestID = ? AND Status = 'Pending'""", status, (catatan or "")[:255] or None, id_user, id_request))
    if status == "Done":
        return bool(_ubah("""UPDATE dbo.OperatorRequest SET Status = 'Done', DoneBy = ?, DoneDate = GETDATE()
                             WHERE RequestID = ? AND Status = 'Approved'""", id_user, id_request))
    raise ValueError("Status tidak dikenal")


def ringkas_request(id_user, hanya_operator=None):
    hasil = dict.fromkeys(STATUS, 0)
    syarat = "o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserMenuScope(?, 'RK_REQUEST'))" + (" AND (r.OperatorID = ? OR r.CreateBy = ?)" if hanya_operator else "")
    for r in _query(f"""SELECT r.Status, COUNT(*) AS n FROM dbo.OperatorRequest r JOIN Users o ON o.UserID = r.OperatorID
                        WHERE {syarat} GROUP BY r.Status""", id_user, *([hanya_operator] * 2 if hanya_operator else [])):
        hasil[r["Status"]] = r["n"]
    return hasil


# ===== Harga harian (dbo.DailyPrice, atau Main.dbo.HARGA bila diatur di .env: utils/harga_sumber; sama dengan Dashboard CPOS) =====
def daftar_harga(companies, id_company="", tanggal="", batas=500):
    """companies: daftar CompID yang boleh dilihat (None = semua)."""
    if harga_sumber.aktif():
        return harga_sumber.daftar(companies, id_company, tanggal, batas=batas)
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
    if harga_sumber.aktif():
        return harga_sumber.ada(id_company, tanggal)
    return bool(_query("SELECT 1 AS x FROM DailyPrice WHERE CompID = ? AND PriceDate = ?", id_company, tanggal))


def hapus_harga(id_company, tanggal):
    if harga_sumber.aktif():
        return harga_sumber.hapus(id_company, tanggal)
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
    return bool(_query("""SELECT 1 AS x FROM dbo.OperatorRequest r JOIN Users o ON o.UserID = r.OperatorID
                          WHERE r.RequestID = ? AND o.CompAreaID IN (SELECT CompAreaID FROM dbo.fn_UserMenuScope(?, 'RK_REQUEST'))""",
                       id_request, id_user))


def catat_aksi(id_request, catatan):
    """Catatan penyetuju (tiap tahap) ke kolom Remarks Aksi."""
    if catatan:
        _ubah("UPDATE dbo.OperatorRequest SET ActionRemarks = ? WHERE RequestID = ?", catatan[:255], id_request)


def pengajuan_berjalan():
    """Persetujuan request yang masih menunggu: {id_request: {id_pengajuan, jenis, langkah, total, menunggu}}."""
    hasil = {}
    for r in _query("""SELECT p.RequestID AS id_pengajuan, p.RequestType AS jenis, p.Target AS target, p.CurrentStep AS langkah,
                              p.TotalSteps AS total, l.LevelDetName AS menunggu
                       FROM ApprovalRequest p
                       LEFT JOIN ApprovalRequestStep s ON s.RequestID = p.RequestID AND s.StepNo = p.CurrentStep
                       LEFT JOIN LevelDetails l ON l.LevelDetID = s.LevelDetID
                       WHERE p.RequestType LIKE 'REKAP[_]%' AND p.Status = 'MENUNGGU' AND p.Target LIKE 'RQ%'"""):
        nomor = r["target"][2:].split("-")[0]          # RQ12 (request baru), RQ12-U (koreksi), RQ12-H (hapus)
        if nomor.isdigit():
            hasil.setdefault(int(nomor), []).append(r)
    return hasil
