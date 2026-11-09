"""Koneksi dan operasi tiket Ascend (database AS_WB_YBS)."""
import pyodbc

from config import DB_CONFIG


def _koneksi():
    """Gunakan server dan kredensial CPOS, tetapi arahkan ke database Ascend."""
    bagian = [
        f"DRIVER={DB_CONFIG['driver']}",
        f"SERVER={DB_CONFIG['server']}",
        "DATABASE=AS_WB_YBS",
    ]

    if DB_CONFIG["user"]:
        password = (DB_CONFIG["password"] or "").replace("}", "}}")
        bagian.extend([
            f"UID={DB_CONFIG['user']}",
            f"PWD={{{password}}}",
        ])
    else:
        bagian.append("Trusted_Connection=yes")

    bagian.extend([
        f"TrustServerCertificate={DB_CONFIG['trust_server_certificate']}",
        "APP=CPOS;",
    ])

    koneksi = pyodbc.connect(";".join(bagian), timeout=10)
    koneksi.timeout = 30
    return koneksi


def _baris_hasil(cursor):
    """Lewati result set tanpa kolom, lalu ubah result set pertama menjadi daftar dict."""
    while cursor.description is None:
        if not cursor.nextset():
            return []

    nama_kolom = [kolom[0] for kolom in cursor.description]
    return [dict(zip(nama_kolom, baris)) for baris in cursor.fetchall()]


def daftar_do(ticket_type):
    """DO outstanding beserta nama Associate dari database Ascend."""
    if ticket_type == "Produk":
        prosedur = "EXEC dbo.USP_PALM_DeliveryOrders_QueryOutstandingForWB"
        nama_do = "DeliveryOrderNumber"
        nama_associate = "CustomerID"
        tabel_associate = "AR_Customers"
        kolom_id = "CustomerID"
        kolom_nama = "CustomerName"
        nama_id_do = "DeliveryOrderID"
    elif ticket_type == "TBSLuar":
        prosedur = "EXEC dbo.USP_PALM_ReceivingDeliveryOrders_QueryOutstandingForWB"
        nama_do = "ReceivingDeliveryOrderNumber"
        nama_associate = "SupplierID"
        tabel_associate = "AP_Suppliers"
        kolom_id = "SupplierID"
        kolom_nama = "SupplierName"
        nama_id_do = "ReceivingDeliveryOrderID"
    else:
        raise ValueError("Pilih jenis tiket Produk atau TBS Luar.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(prosedur)
        sumber = _baris_hasil(cursor)
        id_do_list = sorted({
            int(row[nama_id_do])
            for row in sumber
            if row.get(nama_id_do) is not None
        })

        tabel_do = (
            "PALM_DeliveryOrders"
            if ticket_type == "Produk"
            else "PALM_ReceivingDeliveryOrders"
        )

        mill_by_do = {}
        if id_do_list:
            tanda_tanya_do = ", ".join("?" for _ in id_do_list)
            cursor.execute(
                f"""
                SELECT productname, MillID
                FROM dbo.{tabel_do}
                groupby productname, millid
                """,
                *id_do_list,
            )
            mill_by_do = {
                int(row[0]): int(row[1])
                for row in cursor.fetchall()
                if row[1] is not None
            }

        id_associate = sorted({
            int(row[nama_associate])
            for row in sumber
            if row.get(nama_associate) is not None
        })

        nama_by_id = {}
        if id_associate:
            tanda_tanya = ", ".join("?" for _ in id_associate)
            cursor.execute(
                f"""
                SELECT {kolom_id}, {kolom_nama}
                FROM dbo.{tabel_associate}
                WHERE {kolom_id} IN ({tanda_tanya})
                """,
                *id_associate,
            )
            nama_by_id = {
                int(row[0]): str(row[1]).strip()
                for row in cursor.fetchall()
            }

        hasil = []
        for row in sumber:
            no_do = row.get(nama_do)
            id_assoc = row.get(nama_associate)
            produk = row.get("ProductName")
            sisa = row.get("QtyOutstanding")
            if sisa is None:
                sisa = row.get("Outstanding")

            if not no_do or id_assoc is None or not produk:
                continue
            if sisa is not None and float(sisa) <= 0:
                continue

            associate_id = int(id_assoc)
            hasil.append({
                "no_do": str(no_do).strip(),
                "associate_id": associate_id,
                "associate_name": nama_by_id.get(associate_id, ""),
                "produk": str(produk).strip(),
                "id_do": row.get(nama_id_do),
                "mill_id": mill_by_do.get(int(row[nama_id_do]))
                    if row.get(nama_id_do) is not None else None,
                "sisa": float(sisa) if sisa is not None else None,
            })
        return hasil
    finally:
        koneksi.close()

def daftar_associate(ticket_type):
    """Daftar lengkap Associate beserta kode dan nama."""
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
        
def buat_tiket_kosong(ticket_type, produk, associate_id, vehicle_no,
                      date_time_in, sp_do, mill_id):
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            DECLARE @NewTicketID INT;
            EXEC @NewTicketID = dbo.USP_PALM_Tickets_CreateEx
                ?, ?, ?, ?, ?, ?, ?;
            SELECT @NewTicketID AS TicketID;
            """,
            ticket_type,
            produk,
            associate_id,
            vehicle_no,
            date_time_in.strftime("%Y%m%d"),
            sp_do,
            mill_id,
        )

        ticket_id = None

        while True:
            if cursor.description:
                nama_kolom = [kolom[0] for kolom in cursor.description]

                if "TicketID" in nama_kolom:
                    baris = cursor.fetchone()
                    if baris is not None:
                        ticket_id = int(baris[nama_kolom.index("TicketID")])
                    break

            if not cursor.nextset():
                break

        if ticket_id is None:
            raise RuntimeError(
                "Prosedur Ascend tidak mengembalikan nilai RETURN sebagai TicketID."
            )
        if ticket_id <= 0:
            raise ValueError(f"Ascend mengembalikan TicketID {ticket_id}.")

        cursor.execute(
            "SELECT TicketNo FROM dbo.PALM_Tickets WHERE TicketID = ?",
            ticket_id,
        )
        tiket = cursor.fetchone()
        if not tiket:
            raise RuntimeError(
                f"TicketID {ticket_id} dikembalikan, tetapi nomor tiket tidak ditemukan."
            )

        koneksi.commit()
        return {"ticket_id": ticket_id, "ticket_no": str(tiket[0])}
    except Exception:
        koneksi.rollback()
        raise
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