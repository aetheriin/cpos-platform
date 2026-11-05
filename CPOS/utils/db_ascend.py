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
                "sisa": float(sisa) if sisa is not None else None,
            })
        return hasil
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

        hasil = _baris_hasil(cursor)
        if not hasil:
            raise RuntimeError("Prosedur Ascend tidak mengembalikan TicketID.")

        ticket_id = int(hasil[0]["TicketID"])
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
            SELECT DISTINCT MillID
            FROM dbo.PALM_MillStation
            WHERE MillID IS NOT NULL
            ORDER BY MillID
        """)
        return [{"mill_id": int(row[0])} for row in cursor.fetchall()]
    finally:
        koneksi.close()