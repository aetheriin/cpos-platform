"""Pencarian dan antrean tiket Ascend."""
from datetime import datetime

from utils.db_tiket_common import (
    koneksi_tiket as _koneksi,
    baris_hasil as _baris_hasil,
)

def cari_tiket_berdasarkan_plat(no_plat):
    """Cari tiket terbaru berdasarkan nomor plat."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1)
                TicketNo,
                TicketType,
                ProductName,
                AssociateID,
                VehicleNo,
                [Date],
                SPDO,
                MILLID
            FROM dbo.PALM_Tickets
            WHERE REPLACE(REPLACE(REPLACE(UPPER(LTRIM(RTRIM(VehicleNo))), ' ', ''), '-', ''), '.', '')
                = REPLACE(REPLACE(REPLACE(UPPER(?), ' ', ''), '-', ''), '.', '')
            AND ISNULL([Void], 0) = 0
            AND ISNULL([Splitted], 0) = 0
            AND (ISNULL([Step], 0) < 2 OR DateTimeOut IS NULL)
            ORDER BY TicketID ASC
            """,
            no_plat,
        )
        row = cursor.fetchone()

        if not row:
            return None

        kode_associate = ""
        nama_associate = ""

        if row[1] == "Produk":
            cursor.execute(
                """
                SELECT CustomerCode, CustomerName
                FROM dbo.AR_Customers
                WHERE CustomerID = ?
                """,
                row[3],
            )
        elif row[1] == "TBSLuar":
            cursor.execute(
                """
                SELECT SupplierCode, SupplierName
                FROM dbo.AP_Suppliers
                WHERE SupplierID = ?
                """,
                row[3],
            )

        associate = cursor.fetchone()
        if associate:
            kode_associate = str(associate[0] or "").strip()
            nama_associate = str(associate[1] or "").strip()

        return {
            "no_tiket": str(row[0] or "").strip(),
            "ticket_type": str(row[1] or "").strip(),
            "produk": str(row[2] or "").strip(),
            "associate_id": int(row[3]) if row[3] is not None else None,
            "associate_code": kode_associate,
            "associate_name": nama_associate,
            "no_plat": str(row[4] or "").strip(),
            "tanggal": row[5].isoformat() if row[5] else None,
            "no_do": str(row[6] or "").strip(),
            "mill_id": int(row[7]) if row[7] is not None else None,
        }
    finally:
        koneksi.close()

def cari_tiket_berdasarkan_no_tiket(no_tiket):
    """Cari tiket yang masih berjalan berdasarkan nomor tiket."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1)
                TicketNo, TicketType, ProductName, AssociateID,
                VehicleNo, [Date], SPDO, MILLID, TicketID, ParentTicketID
            FROM dbo.PALM_Tickets
            WHERE TicketNo = ?
              AND ISNULL([Void], 0) = 0
              AND ISNULL([Splitted], 0) = 0
              AND (ISNULL([Step], 0) < 2 OR DateTimeOut IS NULL)
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()
        if not row:
            return None

        associate_code = ""
        associate_name = ""

        if row[1] == "Produk":
            cursor.execute(
                """
                SELECT CustomerCode, CustomerName
                FROM dbo.AR_Customers
                WHERE CustomerID = ?
                """,
                row[3],
            )
        elif row[1] == "TBSLuar":
            cursor.execute(
                """
                SELECT SupplierCode, SupplierName
                FROM dbo.AP_Suppliers
                WHERE SupplierID = ?
                """,
                row[3],
            )

        associate = cursor.fetchone()
        if associate:
            associate_code = str(associate[0] or "").strip()
            associate_name = str(associate[1] or "").strip()

        return {
            "no_tiket": str(row[0] or "").strip(),
            "ticket_type": str(row[1] or "").strip(),
            "produk": str(row[2] or "").strip(),
            "associate_id": int(row[3]) if row[3] is not None else None,
            "associate": " · ".join(
                bagian for bagian in (associate_code, associate_name) if bagian
            ),
            "no_plat": str(row[4] or "").strip(),
            "tanggal": row[5].isoformat() if row[5] else None,
            "no_do": str(row[6] or "").strip(),
            "mill_id": int(row[7]) if row[7] is not None else None,
            "ticket_id": int(row[8]) if row[8] is not None else None,
            "parent_ticket_id": int(row[9]) if row[9] is not None else None,
            "jenis_transaksi": (
                "PENJUALAN" if row[1] == "Produk" else "PEMBELIAN"
            ),
        }
    finally:
        koneksi.close()

def daftar_tiket_aktif(ticket_ids):
    """Ambil tiket aktif yang ID-nya sudah dibatasi oleh cakupan area CPOS."""
    ticket_ids = sorted({int(ticket_id) for ticket_id in (ticket_ids or [])})
    if not ticket_ids:
        return []

    hasil = []
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        # Pecah agar jumlah parameter SQL tetap di bawah batas SQL Server.
        for awal in range(0, len(ticket_ids), 900):
            bagian = ticket_ids[awal:awal + 900]
            tanda_tanya = ", ".join("?" for _ in bagian)

            cursor.execute(
                f"""
                SELECT
                    t.TicketNo AS no_tiket,
                    t.VehicleNo AS no_plat,
                    t.TicketType AS ticket_type,
                    t.ProductName AS produk,
                    COALESCE(t.DateTimeIn, t.[Date]) AS created_at,
                    t.SPDO AS no_do,
                    t.[Step] AS step,
                    COALESCE(c.CustomerCode, s.SupplierCode) AS associate_code,
                    COALESCE(c.CustomerName, s.SupplierName) AS associate_name
                FROM dbo.PALM_Tickets t
                LEFT JOIN dbo.AR_Customers c
                    ON t.TicketType = 'Produk'
                   AND c.CustomerID = t.AssociateID
                LEFT JOIN dbo.AP_Suppliers s
                    ON t.TicketType = 'TBSLuar'
                   AND s.SupplierID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND ISNULL(t.Void, 0) = 0
                  AND ISNULL(t.[Splitted], 0) = 0
                  AND (ISNULL(t.[Step], 0) < 2 OR t.DateTimeOut IS NULL)
                """,
                *bagian,
            )

            for row in _baris_hasil(cursor):
                ticket_type = str(row["ticket_type"] or "").strip()
                step = int(row["step"] or 0)
                nama_associate = " · ".join(
                    bagian_nama for bagian_nama in (
                        str(row["associate_code"] or "").strip(),
                        str(row["associate_name"] or "").strip(),
                    ) if bagian_nama
                )

                hasil.append({
                    "no_tiket": str(row["no_tiket"] or "").strip(),
                    "no_plat": str(row["no_plat"] or "").strip(),
                    "supplier": nama_associate,
                    "status_alur": (
                        "SECURITY_REGISTER" if step == 0 else "TIMBANG_2"
                    ),
                    "jenis_transaksi": (
                        "PENJUALAN" if ticket_type == "Produk"
                        else "PEMBELIAN"
                    ),
                    "produk": str(row["produk"] or "").strip(),
                    "kategori_produk": None,
                    "created_at": row["created_at"],
                    "id_alur": None,
                    "no_do": str(row["no_do"] or "").strip(),
                    "supir": "",
                    "tahap_menunggu": None,
                    "tahap": [],
                })

        return hasil
    finally:
        koneksi.close()

def cari_tiket_global(kata, ticket_ids, batas=8):
    """Cari tiket yang TicketID-nya sudah dibatasi berdasarkan area CPOS."""
    kata = (kata or "").strip()
    ticket_ids = sorted({int(i) for i in (ticket_ids or [])})

    if not kata or not ticket_ids:
        return []

    batas = max(1, min(int(batas), 8))
    aman = kata.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    pola = f"%{aman}%"
    hasil = []

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        for awal in range(0, len(ticket_ids), 850):
            bagian = ticket_ids[awal:awal + 850]
            tanda_tanya = ", ".join("?" for _ in bagian)

            cursor.execute(
                f"""
                SELECT TOP ({batas})
                    t.TicketNo AS no_tiket,
                    t.VehicleNo AS no_plat,
                    t.SPDO AS no_do,
                    CASE
                        WHEN ISNULL(t.Void, 0) = 1 THEN 'VOID'
                        WHEN ISNULL(t.[Step], 0) >= 2
                             AND t.DateTimeOut IS NOT NULL THEN 'SELESAI'
                        WHEN ISNULL(t.[Step], 0) = 0 THEN 'SECURITY_REGISTER'
                        ELSE 'TIMBANG_2'
                    END AS status_alur,
                    COALESCE(t.DateTimeIn, CONVERT(DATETIME, t.[Date])) AS created_at,
                    COALESCE(c.CustomerName, s.SupplierName, '') AS customer,
                    t.ProductName AS produk,
                    CAST('' AS VARCHAR(100)) AS supir,
                    CASE
                        WHEN ISNULL(t.[Step], 0) >= 2
                             AND t.DateTimeOut IS NOT NULL THEN t.Netto
                        ELSE NULL
                    END AS netto
                FROM dbo.PALM_Tickets t
                LEFT JOIN dbo.AR_Customers c
                    ON t.TicketType = 'Produk'
                   AND c.CustomerID = t.AssociateID
                LEFT JOIN dbo.AP_Suppliers s
                    ON t.TicketType = 'TBSLuar'
                   AND s.SupplierID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND ISNULL(t.ParentTicketID, 0) = 0
                  AND (
                      t.TicketNo LIKE ?
                      OR REPLACE(UPPER(ISNULL(t.VehicleNo, '')), ' ', '')
                         LIKE REPLACE(UPPER(?), ' ', '')
                      OR ISNULL(t.SPDO, '') LIKE ?
                      OR COALESCE(c.CustomerName, s.SupplierName, '') LIKE ?
                      OR ISNULL(t.ProductName, '') LIKE ?
                  )
                ORDER BY
                    COALESCE(t.DateTimeIn, CONVERT(DATETIME, t.[Date])) DESC
                """,
                *bagian,
                pola,
                pola,
                pola,
                pola,
                pola,
            )

            hasil.extend(_baris_hasil(cursor))

        hasil.sort(
            key=lambda row: row.get("created_at") or datetime.min,
            reverse=True,
        )

        for row in hasil:
            row["netto"] = float(row["netto"]) if row["netto"] is not None else None

        return hasil[:batas]
    finally:
        koneksi.close()
