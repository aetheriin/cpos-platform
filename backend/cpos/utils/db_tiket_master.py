"""Referensi master yang dibaca dari database tiket Ascend."""
from decimal import Decimal

from utils.db_tiket_common import (
    koneksi_tiket as _koneksi,
    baris_hasil as _baris_hasil,
)

def daftar_supplier_master_tiket():
    """Daftar supplier Tiket beserta tipe supplier."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT
                s.SupplierID AS id_supplier,
                s.SupplierCode AS kode_supplier,
                s.SupplierName AS nama_supplier,
                s.AddressLine1 AS alamat1,
                s.AddressLine2 AS alamat2,
                s.SupplierTypeID AS id_jenis_supplier,
                st.SupplierTypeCode AS kode_jenis_supplier,
                st.SupplierTypeDescription AS jenis_supplier,
                s.Disabled AS disabled,
                s.IsTransport AS is_transport,
                s.IsExpedition AS is_expedition,
                s.PalmFFBSupplier AS supplier_tbs,
                s.DefaultTicketType AS default_ticket_type,
                s.CreateDate AS created_at
            FROM dbo.AP_Suppliers AS s
            LEFT JOIN dbo.AP_SupplierTypes AS st
                ON st.SupplierTypeID = s.SupplierTypeID
            ORDER BY
                CASE WHEN ISNULL(s.Disabled, 0) = 0 THEN 0 ELSE 1 END,
                s.SupplierName
            """
        )

        hasil = []
        for row in _baris_hasil(cursor):
            dibuat = row.get("created_at")

            hasil.append({
                "id_supplier": int(row["id_supplier"]),
                "kode_supplier": str(row.get("kode_supplier") or "").strip(),
                "nama_supplier": str(row.get("nama_supplier") or "").strip(),
                "alamat": " ".join(
                    str(bagian).strip()
                    for bagian in (row.get("alamat1"), row.get("alamat2"))
                    if bagian and str(bagian).strip()
                ),
                "id_jenis_supplier": row.get("id_jenis_supplier"),
                "kode_jenis_supplier": str(
                    row.get("kode_jenis_supplier") or ""
                ).strip(),
                "jenis_supplier": str(
                    row.get("jenis_supplier") or ""
                ).strip(),
                "is_active": not bool(row.get("disabled")),
                "is_transport": bool(row.get("is_transport")),
                "is_expedition": bool(row.get("is_expedition")),
                "supplier_tbs": bool(row.get("supplier_tbs")),
                "default_ticket_type": str(
                    row.get("default_ticket_type") or ""
                ).strip(),
                "created_at": dibuat.isoformat()[:10] if dibuat else None,
            })

        return hasil
    finally:
        koneksi.close()

def daftar_produk_master_tiket():
    """Daftar produk dari master Tiket."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute("EXEC dbo.USP_PALM_Products_QueryAll")

        hasil = []
        for row in _baris_hasil(cursor):
            hasil.append({
                "id_produk": int(row["ProductID"]),
                "nama_produk": str(row.get("ProductName") or "").strip(),
                "nama_tampil": str(row.get("VisibleName") or "").strip(),
                "state": str(row.get("State") or "").strip(),
                "deskripsi": str(
                    row.get("ProductDescription") or ""
                ).strip(),
                "req_do": bool(row.get("ReqDO")),
                "kode_awal": str(row.get("PInitialCode") or "").strip(),
                "prod_flags": str(row.get("ProdFlags") or "").strip(),
                "qe_ratio": (
                    float(row["QERatio"])
                    if row.get("QERatio") is not None else None
                ),
                "sales_account_id": int(row.get("SalesAccountID") or 0),
                "oa_account_id": int(row.get("OAAccountID") or 0),
                "inbound_extra": (
                    float(row["InboundExtra"])
                    if row.get("InboundExtra") is not None else None
                ),
                "outbound_extra": (
                    float(row["OutboundExtra"])
                    if row.get("OutboundExtra") is not None else None
                ),
                "inbound_extra_h": (
                    float(row["InboundExtraH"])
                    if row.get("InboundExtraH") is not None else None
                ),
            })

        return hasil
    finally:
        koneksi.close()

def daftar_produk_tbs_luar_tiket():
    """Nama produk yang pernah digunakan pada tiket TBS Luar Tiket."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT
                ProductName AS nama_produk,
                COUNT_BIG(*) AS jumlah_tiket,
                MAX([Date]) AS terakhir_dipakai
            FROM dbo.PALM_Tickets
            WHERE TicketType = 'TBSLuar'
              AND ISNULL(Void, 0) = 0
              AND NULLIF(LTRIM(RTRIM(ProductName)), '') IS NOT NULL
            GROUP BY ProductName
            ORDER BY ProductName
            """
        )

        hasil = []
        for row in _baris_hasil(cursor):
            terakhir = row.get("terakhir_dipakai")
            hasil.append({
                "nama_produk": str(row.get("nama_produk") or "").strip(),
                "jumlah_tiket": int(row.get("jumlah_tiket") or 0),
                "terakhir_dipakai": terakhir.isoformat()[:10] if terakhir else None,
            })

        return hasil
    finally:
        koneksi.close()

def simpan_produk_master_tiket(
    product_id,
    product_name,
    state,
    description,
    req_do,
    initial_code,
    prod_flags,
    qe_ratio,
):
    product_id = int(product_id or 0)
    koneksi = _koneksi()

    try:
        cursor = koneksi.cursor()

        if product_id:
            cursor.execute(
                """
                SELECT SalesAccountID, OAAccountID
                FROM dbo.PALM_Products
                WHERE ProductID = ?
                """,
                product_id,
            )
            akun = cursor.fetchone()
            if not akun:
                raise ValueError("Produk Tiket tidak ditemukan.")
            sales_account_id = int(akun[0] or 0)
            oa_account_id = int(akun[1] or 0)
        else:
            sales_account_id = 0
            oa_account_id = 0

        cursor.execute(
            """
            SELECT TOP (1) ProductID
            FROM dbo.PALM_Products
            WHERE ProductName = ?
              AND ProductID <> ?
            """,
            product_name,
            product_id,
        )
        if cursor.fetchone():
            raise ValueError(f"Produk {product_name} sudah ada di Tiket.")

        cursor.execute(
            """
            DECLARE @hasil INT;
            EXEC @hasil = dbo.USP_PALM_Products_Update
                @ProductID = ?,
                @ProductName = ?,
                @SalesAccountID = ?,
                @OAAccountID = ?,
                @State = ?,
                @ProductDescription = ?,
                @ReqDO = ?,
                @PInitialCode = ?,
                @ProdFlags = ?,
                @QERatio = ?;
            SELECT @hasil AS product_id;
            """,
            product_id,
            product_name,
            sales_account_id,
            oa_account_id,
            state,
            description,
            1 if req_do else 0,
            initial_code,
            prod_flags,
            Decimal(str(qe_ratio)),
        )

        hasil = _baris_hasil(cursor)
        if not hasil or int(hasil[0]["product_id"] or 0) <= 0:
            raise ValueError("Tiket tidak berhasil menyimpan produk.")

        koneksi.commit()
        return int(hasil[0]["product_id"])
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()

def daftar_associate(ticket_type):
    """Daftar Associate dari Tiket, beserta kode dan nama."""
    if ticket_type == "Produk":
        sql = """
            SELECT CustomerID, CustomerCode, CustomerName
            FROM dbo.AR_Customers
            ORDER BY CustomerName
        """
    elif ticket_type == "TBSLuar":
        sql = """
            SELECT SupplierID, SupplierCode, SupplierName
            FROM dbo.AP_Suppliers
            ORDER BY SupplierName
        """
    else:
        raise ValueError("Pilih jenis tiket Produk atau TBS Luar.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(sql)
        return [
            {
                "associate_id": int(row[0]),
                "associate_code": str(row[1] or "").strip(),
                "associate_name": str(row[2] or "").strip(),
            }
            for row in cursor.fetchall()
        ]
    finally:
        koneksi.close()

def daftar_mill():
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute("""
            SELECT MillID FROM dbo.PALM_DeliveryOrders
            WHERE MillID IS NOT NULL

            UNION

            SELECT MillID FROM dbo.PALM_ReceivingDeliveryOrders
            WHERE MillID IS NOT NULL

            ORDER BY MillID
        """)
        return [{"mill_id": int(row[0])} for row in cursor.fetchall()]
    finally:
        koneksi.close()

def daftar_shipper_kendaraan(ticket_type, id_do=None, associate_id=None):
    """Shipper dan kendaraan yang terkait dengan DO atau Supplier terpilih."""
    if ticket_type == "Produk":
        sql = """
            SELECT DISTINCT
                s.SupplierID,
                s.SupplierName,
                ev.VehicleID,
                ev.VehicleNo,
                ev.DriverName
            FROM dbo.PALM_DOTransport dot
            INNER JOIN dbo.AP_Suppliers s
                ON s.SupplierID = dot.ShipperID
            INNER JOIN dbo.PALM_ExternalVehicles ev
                ON ev.SupplierID = dot.ShipperID
            WHERE (? IS NULL OR dot.DeliveryOrderID = ?)
            ORDER BY s.SupplierName, ev.VehicleNo
        """
        parameter = int(id_do) if id_do else None
        parameters = (parameter, parameter)

    elif ticket_type == "TBSLuar":
        sql = """
            SELECT DISTINCT
                s.SupplierID,
                s.SupplierName,
                ev.VehicleID,
                ev.VehicleNo,
                ev.DriverName
            FROM dbo.AP_Suppliers AS s
            LEFT JOIN dbo.PALM_ExternalVehicles AS ev
                ON ev.SupplierID = s.SupplierID
            ORDER BY s.SupplierName, ev.VehicleNo
        """
        parameters = ()

    else:
        raise ValueError("Pilih jenis tiket Produk atau TBS Luar.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(sql, *parameters)

        hasil = {}
        for row in cursor.fetchall():
            shipper_id = int(row[0])
            shipper = hasil.setdefault(shipper_id, {
                "shipper_id": shipper_id,
                "shipper_name": str(row[1] or "").strip(),
                "vehicles": [],
            })

            if row[2] is not None and row[3]:
                no_kendaraan = str(row[3]).strip()
                if not any(v["vehicle_no"] == no_kendaraan for v in shipper["vehicles"]):
                    shipper["vehicles"].append({
                        "vehicle_id": int(row[2]),
                        "vehicle_no": no_kendaraan,
                        "driver_name": str(row[4] or "").strip(),
                    })

        return list(hasil.values())
    finally:
        koneksi.close()