"""Pencarian global (header › Cari / Ctrl+K): tiket, DO / kontrak, personel, kendaraan; admin: akun."""
from utils.db_utils import _filter_area, query as _query

def _pola(kata):
    """'bk 8492' cocok dengan 'BK 8492 XA'; % dan _ dari user tidak dianggap wildcard."""
    aman = kata.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    return f"%{aman}%"


def cari_tiket(kata, id_area=None, batas=8):
    filter_area, param_area = _filter_area(id_area)
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} t.TicketNumber AS no_tiket, k.NoVehicle AS no_plat, t.DONumber AS no_do, t.StatusCode AS status_alur, t.TicketDate AS created_at,
               s.SupplierName AS customer, p.ProductName AS produk, d.Nama AS supir,
               COALESCE(tb.Netto, t.SplitWeight) AS netto
        FROM WeightBridge t
        JOIN DetailVehicle k ON k.IDVehicle = t.IDVehicle
        JOIN Supplier s ON s.SupplierID = t.SupplierID
        JOIN Product p ON p.ProductID = t.ProductID
        JOIN Users d ON d.UserID = t.DriverID
        LEFT JOIN WeighingSummary tb ON tb.TicketNumber = t.TicketNumber
        WHERE (t.TicketNumber LIKE ? OR REPLACE(k.NoVehicle, ' ', '') LIKE REPLACE(?, ' ', '') OR t.DONumber LIKE ?
               OR d.Nama LIKE ? OR s.SupplierName LIKE ?){filter_area}
        ORDER BY t.TicketDate DESC""", pola, pola, pola, pola, pola, *param_area)


def cari_do(kata, company=None, batas=5):
    """DO / kontrak: no. DO, no. kontrak, atau nama customer. Realisasi = total netto tiket DO (tanpa VOID).
    company: None = semua PT, atau kode PT yang boleh dilihat (kontrak milik PT itu)."""
    pola = _pola(kata)
    if company is not None and not company:
        return []
    f_pt = "" if company is None else f" AND k.CompID IN ({', '.join('?' * len(company))})"
    return _query(f"""
        SELECT TOP {int(batas)} o.DONumber AS no_do, k.ContractNumber AS no_kontrak, c.SupplierName AS customer, p.ProductName AS produk,
               k.ContractQty AS qty_kg, o.Active AS is_active, o.ExpiredDate AS berlaku_sampai,
               (SELECT SUM(COALESCE(tb.Netto, t.SplitWeight)) FROM WeightBridge t
                LEFT JOIN WeighingSummary tb ON tb.TicketNumber = t.TicketNumber
                WHERE t.DeliveryOrderID = o.DeliveryOrderID AND t.StatusCode <> 'VOID') AS realisasi_kg
        FROM DeliveryOrder o
        JOIN Contract k ON k.ContractID = o.ContractID
        JOIN Supplier c ON c.SupplierID = k.SupplierID
        JOIN Product p ON p.ProductID = k.ProductID
        WHERE (o.DONumber LIKE ? OR k.ContractNumber LIKE ? OR c.SupplierName LIKE ?){f_pt}
        ORDER BY o.Active DESC, o.CreateDate DESC""", pola, pola, pola, *sorted(company or ()))


NIK_MIN_ANGKA = 6     # NIK baru dicari bila yang diketik minimal sekian angka, supaya NIK tidak bisa ditelusuri dari 2 angka


def cari_personel(kata, batas=5):
    pola = _pola(kata)
    angka = kata.replace(" ", "")
    pakai_nik = angka.isdigit() and len(angka) >= NIK_MIN_ANGKA
    return _query(f"""
        SELECT TOP {int(batas)} UserID AS id_personel, Nama AS nama_personel, NoKTP AS nik, PersonType AS kategori, IsBlacklisted AS is_blacklisted
        FROM UserProfile
        WHERE Active = 1 AND (Nama LIKE ?{" OR NoKTP LIKE ?" if pakai_nik else ""})
        ORDER BY Nama""", pola, *([f"%{angka}%"] if pakai_nik else []))


def cari_kendaraan(kata, batas=5):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} IDVehicle AS id_kendaraan, NoVehicle AS no_plat, NoSTNK AS no_stnk, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted
        FROM DetailVehicle
        WHERE Active = 1 AND (REPLACE(NoVehicle, ' ', '') LIKE REPLACE(?, ' ', '') OR NoSTNK LIKE ?)
        ORDER BY NoVehicle""", pola, pola)


def cari_akun(kata, batas=8):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} u.UserID AS id_user, u.Nama AS nama, u.UserName AS username, u.Active AS is_active, l.LevelDetName AS nama_level, a.AreaName AS area
        FROM Users u JOIN LevelDetails l ON l.LevelDetID = u.UserLevelID JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
        WHERE u.Nama LIKE ? OR u.UserName LIKE ?
        ORDER BY u.Active DESC, u.Nama""", pola, pola)
