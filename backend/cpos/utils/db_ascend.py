"""Koneksi dan operasi tiket Ascend (database AS_WB_YBS)."""
import pyodbc

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from utils import db_ascend_split
from utils.koneksi_lain import connection_string


def _koneksi():
    """Server dan kredensial CPOS (DB_*), database AS_WB_YBS. ASCEND_SERVER / _DB / _USER / _PASSWORD di .env bila berbeda."""
    koneksi = pyodbc.connect(connection_string("ASCEND", "CPOS", db_bawaan="AS_WB_YBS"), timeout=10)
    koneksi.timeout = 30
    return koneksi

def _kunci_dan_cari_tiket_aktif(cursor, vehicle_no):
    """Kunci proses per plat, lalu cari tiket Ascend yang belum selesai."""
    plat_normal = "".join(
        karakter
        for karakter in vehicle_no.upper().strip()
        if karakter not in " .-"
    )
    if not plat_normal:
        raise ValueError("Nomor kendaraan wajib diisi.")

    resource = f"CPOS_TIKET_ASCEND:{plat_normal}"

    cursor.execute(
        """
        DECLARE @hasil INT;
        EXEC @hasil = sys.sp_getapplock
            @Resource = ?,
            @LockMode = 'Exclusive',
            @LockOwner = 'Transaction',
            @LockTimeout = 10000;
        SELECT @hasil;
        """,
        resource,
    )
    hasil_kunci = cursor.fetchone()[0]

    if hasil_kunci < 0:
        raise RuntimeError(
            "Tidak bisa mengunci pemeriksaan tiket untuk kendaraan ini. Coba lagi."
        )

    cursor.execute(
        """
        SELECT TOP (1) TicketNo
        FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
        WHERE REPLACE(REPLACE(REPLACE(UPPER(LTRIM(RTRIM(VehicleNo))), ' ', ''), '-', ''), '.', '')
            = ?
          AND ISNULL([Void], 0) = 0
          AND ISNULL([Splitted], 0) = 0
          AND (ISNULL([Step], 0) < 2 OR DateTimeOut IS NULL)
        ORDER BY TicketID ASC
        """,
        plat_normal,
    )
    return cursor.fetchone()

def _baris_hasil(cursor):
    """Lewati result set tanpa kolom, lalu ubah result set pertama menjadi daftar dict."""
    while cursor.description is None:
        if not cursor.nextset():
            return []

    nama_kolom = [kolom[0] for kolom in cursor.description]
    return [dict(zip(nama_kolom, baris)) for baris in cursor.fetchall()]

def daftar_supplier_master_ascend():
    """Daftar supplier Ascend beserta tipe supplier."""
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

def daftar_produk_master_ascend():
    """Daftar produk dari master Ascend."""
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

def daftar_produk_tbs_luar_ascend():
    """Nama produk yang pernah digunakan pada tiket TBS Luar Ascend."""
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

def simpan_produk_master_ascend(
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
                raise ValueError("Produk Ascend tidak ditemukan.")
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
            raise ValueError(f"Produk {product_name} sudah ada di Ascend.")

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
            raise ValueError("Ascend tidak berhasil menyimpan produk.")

        koneksi.commit()
        return int(hasil[0]["product_id"])
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()

def cari_tiket_ascend_berdasarkan_plat(no_plat):
    """Cari tiket Ascend terbaru berdasarkan nomor plat."""
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

def cari_tiket_ascend_berdasarkan_no_tiket(no_tiket):
    """Cari tiket Ascend yang masih berjalan berdasarkan nomor tiket."""
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

def daftar_antrian_lab_ascend(ticket_ids):
    """Baca antrean Lab Ascend dan batasi hasil ke TicketID area CPOS."""
    ticket_ids = {int(ticket_id) for ticket_id in (ticket_ids or [])}
    if not ticket_ids:
        return []

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute("EXEC dbo.USP_PALM_Tickets_QueryForLabInput")

        kolom = [item[0] for item in cursor.description]
        hasil = []

        for row in cursor.fetchall():
            data = dict(zip(kolom, row))
            ticket_id = int(data.get("TicketID") or 0)

            if ticket_id not in ticket_ids:
                continue

            def tanggal(nilai):
                return nilai.isoformat() if nilai else None

            def angka(nilai):
                return float(nilai) if nilai is not None else None

            hasil.append({
                "ticket_id": ticket_id,
                "tanggal": tanggal(data.get("Date")),
                "datetime_in": tanggal(data.get("DateTimeIn")),
                "no_tiket": str(data.get("TicketNo") or "").strip(),
                "no_plat": str(data.get("VehicleNo") or "").strip(),
                "customer": str(data.get("CustomerName") or "").strip(),
                "produk": str(data.get("ProductName") or "").strip(),
                "bruto": angka(data.get("Bruto")),
                "tara": angka(data.get("Tara")),
                "netto": angka(data.get("Netto")),
            })

        return hasil
    finally:
        koneksi.close()

def daftar_riwayat_lab_ascend(ticket_ids, batas=100):
    """Baca hasil Lab tersimpan dari tiket induk Ascend yang boleh dilihat area."""
    ticket_ids = sorted({int(ticket_id) for ticket_id in (ticket_ids or [])})
    if not ticket_ids:
        return []

    batas = max(1, min(int(batas), 200))
    hasil = []
    koneksi = _koneksi()

    try:
        cursor = koneksi.cursor()

        # Kelompok 850 menjaga jumlah parameter SQL Server tetap aman.
        for awal in range(0, len(ticket_ids), 850):
            bagian = ticket_ids[awal:awal + 850]
            tanda_tanya = ", ".join("?" for _ in bagian)

            cursor.execute(
                f"""
                SELECT TOP ({batas})
                    t.TicketID,
                    t.TicketNo,
                    t.[Date],
                    t.DateTimeIn,
                    t.VehicleNo,
                    t.ProductName,
                    t.FFA,
                    t.Suhu,
                    t.PctAir,
                    t.PctKotoran,
                    t.KColor,
                    t.LabBy,
                    t.LabDateTime,
                    c.CustomerName
                FROM dbo.PALM_Tickets t
                LEFT JOIN dbo.AR_Customers c
                    ON c.CustomerID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND t.TicketType = 'Produk'
                  AND t.ProductName IN ('CPO', 'PK', 'Kernel')
                  AND t.LabDateTime IS NOT NULL
                ORDER BY t.LabDateTime DESC, t.TicketID DESC
                """,
                *bagian,
            )

            kolom = [item[0] for item in cursor.description]
            for baris in cursor.fetchall():
                row = dict(zip(kolom, baris))

                def tanggal(nilai):
                    return nilai.isoformat() if nilai else None

                def angka(nilai):
                    return float(nilai) if nilai is not None else None

                hasil.append({
                    "ticket_id": int(row["TicketID"]),
                    "no_tiket": str(row.get("TicketNo") or "").strip(),
                    "tanggal": tanggal(row.get("Date")),
                    "datetime_in": tanggal(row.get("DateTimeIn")),
                    "no_plat": str(row.get("VehicleNo") or "").strip(),
                    "customer": str(row.get("CustomerName") or "").strip(),
                    "produk": str(row.get("ProductName") or "").strip(),
                    "ffa": angka(row.get("FFA")),
                    "suhu": angka(row.get("Suhu")),
                    "pct_air": angka(row.get("PctAir")),
                    "pct_kotoran": angka(row.get("PctKotoran")),
                    "kcolor": str(row.get("KColor") or "").strip(),
                    "lab_by": str(row.get("LabBy") or "").strip(),
                    "lab_datetime": tanggal(row.get("LabDateTime")),
                })

        hasil.sort(
            key=lambda row: (row.get("lab_datetime") or "", row["ticket_id"]),
            reverse=True,
        )
        return hasil[:batas]
    finally:
        koneksi.close()

def daftar_tiket_ascend_aktif(ticket_ids):
    """Ambil tiket Ascend aktif yang ID-nya sudah dibatasi oleh cakupan area CPOS."""
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
                  AND ISNULL(t.Splitted, 0) = 0
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

def cari_tiket_ascend_global(kata, ticket_ids, batas=8):
    """Cari tiket Ascend yang TicketID-nya sudah dibatasi berdasarkan area CPOS."""
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

def baca_berat_tiket_ascend(no_tiket):
    """Baca berat Ascend sesuai tahap timbang tiket."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1) Bruto, Tara, Netto, TicketType, [Step]
            FROM dbo.PALM_Tickets
            WHERE TicketNo = ?
              AND ISNULL([Void], 0) = 0
              AND ISNULL([Splitted], 0) = 0
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()

        if not row:
            return None

        bruto, tara, netto, ticket_type, step = row
        step = int(step or 0)

        # Tiket kosong: nilai 0 di database belum berarti sudah timbang.
        if step <= 0:
            bruto = tara = netto = None
        elif step == 1:
            # Produk/penjualan: timbang pertama adalah Tara.
            if ticket_type == "Produk":
                bruto = None
                netto = None
            # TBS Luar/penerimaan: timbang pertama adalah Bruto.
            else:
                tara = None
                netto = None

        return {
            "berat_bruto": float(bruto) if bruto is not None else None,
            "berat_tara": float(tara) if tara is not None else None,
            "berat_netto": float(netto) if netto is not None else None,
        }
    finally:
        koneksi.close()

def simpan_hasil_lab_tiket_ascend(
    no_tiket,
    ffa=None,
    suhu=None,
    pct_air=None,
    pct_kotoran=None,
    kcolor=None,
    operator=None,
):
    """Simpan pengukuran Lab pada tiket induk Ascend lewat USP_PALM_Tickets_Update."""
    no_tiket = (no_tiket or "").strip()
    if not no_tiket:
        raise ValueError("Nomor tiket wajib diisi.")

    def angka_opsional(nilai, nama, batas_persen=False):
        if nilai is None or str(nilai).strip() == "":
            return None
        try:
            hasil = Decimal(str(nilai))
        except Exception as exc:
            raise ValueError(f"Nilai {nama} harus berupa angka.") from exc
        if not hasil.is_finite() or hasil < 0:
            raise ValueError(f"Nilai {nama} tidak valid.")
        if batas_persen and hasil > 100:
            raise ValueError(f"Nilai {nama} harus antara 0 dan 100.")
        return hasil

    ffa = angka_opsional(ffa, "FFA", batas_persen=True)
    suhu = angka_opsional(suhu, "suhu")
    pct_air = angka_opsional(pct_air, "kadar air", batas_persen=True)
    pct_kotoran = angka_opsional(pct_kotoran, "kadar kotoran", batas_persen=True)

    warna = (kcolor or "").strip()[:30] or None
    operator_login = str(operator or "").strip()[:30]
    if not operator_login:
        raise ValueError("Petugas Lab wajib diisi.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        cursor.execute(
            """
            SELECT TOP (1) *
            FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
            WHERE TicketNo = ?
              AND ISNULL(Void, 0) = 0
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tiket Ascend tidak ditemukan atau sudah dibatalkan.")

        kolom = [item[0] for item in cursor.description]
        tiket = {nama.casefold(): row[i] for i, nama in enumerate(kolom)}

        # Hasil satu muatan split disimpan sekali pada tiket induk.
        parent_id = int(tiket.get("parentticketid") or 0)
        if parent_id:
            cursor.execute(
                """
                SELECT *
                FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
                WHERE TicketID = ?
                  AND ISNULL(Void, 0) = 0
                """,
                parent_id,
            )
            row_induk = cursor.fetchone()
            if not row_induk:
                raise ValueError("Tiket induk Ascend untuk hasil Lab tidak ditemukan.")
            kolom = [item[0] for item in cursor.description]
            tiket = {nama.casefold(): row_induk[i] for i, nama in enumerate(kolom)}

        jenis = str(tiket.get("tickettype") or "").strip()
        produk = str(tiket.get("productname") or "").strip().upper()

        if jenis != "Produk" or produk not in {"CPO", "PK", "KERNEL"}:
            raise ValueError("Lab Ascend saat ini hanya menerima produk CPO, PK, dan Kernel.")

        if produk == "CPO" and (ffa is None or suhu is None):
            raise ValueError("Untuk CPO, FFA dan suhu wajib diisi.")
        if produk in {"PK", "KERNEL"} and (pct_air is None or pct_kotoran is None):
            raise ValueError("Untuk PK dan Kernel, kadar air dan kadar kotoran wajib diisi.")

        # Ubah hanya hasil Lab yang dikirim; nilai timbang, DO, dan field tiket lain dipertahankan.
        for kunci, nilai in (
            ("ffa", ffa),
            ("suhu", suhu),
            ("pctair", pct_air),
            ("pctkotoran", pct_kotoran),
            ("kcolor", warna),
        ):
            if nilai is not None:
                tiket[kunci] = nilai

        tiket["savelab"] = 1

        cursor.execute(
            """
            SELECT name
            FROM sys.parameters
            WHERE object_id = OBJECT_ID('dbo.USP_PALM_Tickets_Update')
              AND parameter_id > 0
            ORDER BY parameter_id
            """
        )
        nama_parameter = [row[0] for row in cursor.fetchall()]

        wajib = {
            "ticketid", "ticketno", "tickettype", "date", "datetimein",
            "estateid", "vehicleno", "referenceno", "associateid",
            "productname", "bruto", "tara", "deduction", "netto",
            "checkedby", "operator", "printcount", "step",
            "owncar", "allocated", "external",
        }

        parameter_terisi = []
        nilai_parameter = []
        tidak_tersedia = []

        for nama in nama_parameter:
            kunci = nama.lstrip("@").casefold()

            if kunci == "loginname":
                nilai = operator_login
            elif kunci == "operator":
                # Pertahankan operator tiket yang sudah tercatat.
                nilai = tiket.get("operator") or operator_login
            elif kunci == "savelab":
                nilai = 1
            elif kunci == "spdo2":
                nilai = ""
            elif kunci in {"linktodo", "force", "checkmaxdolimit"}:
                nilai = 0
            elif kunci in tiket:
                nilai = tiket[kunci]
            else:
                if kunci in wajib:
                    tidak_tersedia.append(nama)
                continue

            parameter_terisi.append(nama)
            nilai_parameter.append(nilai)

        if tidak_tersedia:
            raise RuntimeError(
                "Data tiket Ascend tidak cukup untuk menyimpan hasil Lab: "
                + ", ".join(tidak_tersedia)
            )

        sql = (
            "EXEC dbo.USP_PALM_Tickets_Update "
            + ", ".join(f"{nama} = ?" for nama in parameter_terisi)
        )
        cursor.execute(sql, *nilai_parameter)

        ticket_id = int(tiket["ticketid"])
        cursor.execute(
            """
            SELECT FFA, Suhu, PctAir, PctKotoran, KColor, LabBy, LabDateTime
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            ticket_id,
        )
        tersimpan = cursor.fetchone()
        if not tersimpan:
            raise RuntimeError("Hasil Lab tidak ditemukan saat membaca balik tiket Ascend.")

        ffa_db, suhu_db, air_db, kotoran_db, warna_db, lab_by_db, lab_at_db = tersimpan

        for nama, nilai_db, harapan in (
            ("FFA", ffa_db, ffa),
            ("suhu", suhu_db, suhu),
            ("kadar air", air_db, pct_air),
            ("kadar kotoran", kotoran_db, pct_kotoran),
        ):
            if harapan is not None and (
                nilai_db is None
                or abs(Decimal(str(nilai_db)) - harapan) > Decimal("0.01")
            ):
                raise RuntimeError(f"Nilai {nama} yang tersimpan di Ascend tidak sesuai.")

        if warna is not None and str(warna_db or "").strip() != warna:
            raise RuntimeError("Warna yang tersimpan di Ascend tidak sesuai.")
        if not lab_by_db or lab_at_db is None:
            raise RuntimeError("Audit petugas/waktu Lab belum tersimpan di Ascend.")

        koneksi.commit()
        return {
            "ticket_id": ticket_id,
            "ticket_no": str(tiket.get("ticketno") or "").strip(),
            "ticket_type": jenis,
            "product": produk,
            "lab_by": str(lab_by_db).strip(),
            "lab_datetime": lab_at_db,
            "ffa": float(ffa_db) if ffa_db is not None else None,
            "suhu": float(suhu_db) if suhu_db is not None else None,
            "pct_air": float(air_db) if air_db is not None else None,
            "pct_kotoran": float(kotoran_db) if kotoran_db is not None else None,
            "kcolor": str(warna_db or "").strip(),
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()
        
def riwayat_timbang_associate(
    ticket_ids, associate_id, ticket_type, mulai, sampai
):
    """Riwayat timbang Ascend dalam cakupan tiket CPOS."""
    if ticket_type not in ("Produk", "TBSLuar"):
        raise ValueError("Jenis tiket Ascend tidak valid.")

    ticket_ids = sorted({int(i) for i in (ticket_ids or [])})
    if not ticket_ids:
        return []

    rows = []
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        for awal in range(0, len(ticket_ids), 900):
            bagian = ticket_ids[awal:awal + 900]
            tanda_tanya = ", ".join("?" for _ in bagian)

            cursor.execute(
                f"""
                SELECT
                    w.WeighAt AS created_at,
                    t.VehicleNo AS no_plat,
                    COALESCE(c.CustomerName, s.SupplierName) AS nama_supplier,
                    t.Bruto AS berat_bruto,
                    t.Tara AS berat_tara,
                    t.Netto AS berat_netto
                FROM dbo.PALM_Tickets t
                CROSS APPLY (
                    SELECT COALESCE(
                        t.DateTimeOut,
                        t.DateTimeIn,
                        CONVERT(DATETIME, t.[Date])
                    ) AS WeighAt
                ) w
                LEFT JOIN dbo.AR_Customers c
                    ON t.TicketType = 'Produk'
                   AND c.CustomerID = t.AssociateID
                LEFT JOIN dbo.AP_Suppliers s
                    ON t.TicketType = 'TBSLuar'
                   AND s.SupplierID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND t.AssociateID = ?
                  AND t.TicketType = ?
                  AND ISNULL(t.Void, 0) = 0
                  AND ISNULL(t.ParentTicketID, 0) = 0
                  AND ISNULL(t.[Step], 0) >= 2
                  AND w.WeighAt >= ?
                  AND w.WeighAt < ?
                """,
                *bagian,
                int(associate_id),
                ticket_type,
                mulai,
                sampai,
            )

            for row in _baris_hasil(cursor):
                rows.append({
                    **row,
                    "berat_bruto": (
                        float(row["berat_bruto"])
                        if row["berat_bruto"] is not None else None
                    ),
                    "berat_tara": (
                        float(row["berat_tara"])
                        if row["berat_tara"] is not None else None
                    ),
                    "berat_netto": (
                        float(row["berat_netto"])
                        if row["berat_netto"] is not None else None
                    ),
                })

        rows.sort(key=lambda r: r["created_at"] or datetime.min, reverse=True)
        return rows[:500]
    finally:
        koneksi.close()
        
def baca_hasil_split_ascend(ticket_id):
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT SPDO, [Step], DateTimeOut, Splitted, Void
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            int(ticket_id),
        )
        induk = cursor.fetchone()
        if not induk:
            return None

        cursor.execute(
            """
            SELECT TicketID, TicketNo, SPDO, Netto, [Step]
            FROM dbo.PALM_Tickets
            WHERE ParentTicketID = ?
              AND ISNULL([Void], 0) = 0
            ORDER BY TicketID
            """,
            int(ticket_id),
        )
        anak = [
            {
                "ticket_id": int(row[0]),
                "no_tiket": str(row[1] or "").strip(),
                "no_do": str(row[2] or "").strip(),
                "berat_netto": float(row[3] or 0),
                "step": int(row[4] or 0),
            }
            for row in cursor.fetchall()
        ]

        return {
            "no_do1": str(induk[0] or "").strip(),
            "step": int(induk[1] or 0),
            "datetimeout": induk[2],
            "splitted": bool(induk[3]),
            "void": bool(induk[4]),
            "anak": anak,
        }
    finally:
        koneksi.close()

def simpan_berat_tiket_ascend(no_tiket, berat_kg, operator, waktu_timbang=None):
    """Simpan timbang ke Ascend melalui USP_PALM_Tickets_Update."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        # Kunci baris sampai transaksi selesai agar timbang tidak tersimpan ganda.
        cursor.execute(
            """
            SELECT TOP (1) *
            FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
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
            raise ValueError("Tiket Ascend tidak ditemukan atau sudah selesai.")

        kolom = [item[0] for item in cursor.description]
        tiket = {nama.casefold(): row[i] for i, nama in enumerate(kolom)}

        def nilai(nama, default=None):
            return tiket.get(nama.casefold(), default)

        step = int(nilai("Step", 0) or 0)
        ticket_type = str(nilai("TicketType", "") or "").strip()
        berat = Decimal(str(berat_kg))

        if berat <= 0:
            raise ValueError("Berat timbang harus lebih dari 0 kg.")
        if step not in (0, 1):
            raise ValueError("Tiket ini tidak berada pada tahap timbang yang bisa disimpan.")

        bruto = Decimal(str(nilai("Bruto", 0) or 0))
        tara = Decimal(str(nilai("Tara", 0) or 0))
        now = waktu_timbang or datetime.now()
        spdo2 = ""
        deduction_harapan = None

        if step == 0:
            if ticket_type == "Produk":
                tara = berat
                tiket["taradatetime"] = now
                tiket["taraby"] = str(operator)[:50]
            elif ticket_type == "TBSLuar":
                bruto = berat
                tiket["brutoby"] = str(operator)[:50]
            else:
                raise ValueError(f"Jenis tiket {ticket_type!r} belum didukung.")

            step_baru = 1
            date_time_out = nilai("DateTimeOut")

        else:  # Step 1: simpan timbang terakhir
            if ticket_type == "Produk":
                bruto = berat
                tiket["brutoby"] = str(operator)[:50]
            elif ticket_type == "TBSLuar":
                tara = berat
                tiket["taradatetime"] = now
                tiket["taraby"] = str(operator)[:50]
            else:
                raise ValueError(f"Jenis tiket {ticket_type!r} belum didukung.")

            if bruto <= tara:
                raise ValueError("Bruto harus lebih besar daripada Tara.")

            step_baru = 2
            date_time_out = now
            tiket["netto"] = bruto - tara

            nama_produk = str(nilai("ProductName", "") or "").strip().casefold()
            if ticket_type == "TBSLuar" and nama_produk == "tbs":
                deduction_lama = Decimal(
                    str(nilai("Deduction", 0) or 0)
                )
                deduction_sortasi = Decimal("0")

                sortasi = db_ascend_split.ambil_sortasi_tiket_ascend(
                    int(nilai("TicketID"))
                )

                if sortasi:
                    total_persen = (
                        Decimal(str(sortasi["mentah"] or 0))
                        + Decimal(str(sortasi["tangkai"] or 0))
                        + Decimal(str(sortasi["sampah"] or 0))
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )

                    # Sama dengan rumus CPOS: potongan dihitung dari Bruto - Tara.
                    netto_sebelum_potongan = bruto - tara
                    deduction_sortasi = (
                        netto_sebelum_potongan
                        * total_persen
                        / Decimal("100")
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )

                if deduction_sortasi > 0:
                    cursor.execute(
                        """
                        SELECT dbo.UDF_SH_Settings_GetAsBit(
                            'PALM_Tickets.FixDeduction.LBPI_ES', 0
                        )
                        """
                    )
                    if bool(cursor.fetchone()[0]):
                        raise ValueError(
                            "Setting khusus Ascend mengubah Deduction setelah "
                            "simpan. Potongan sortasi CPOS belum bisa diterapkan "
                            "dengan aman pada konfigurasi ini."
                        )

                cursor.execute(
                    """
                    SELECT dbo.UDF_SH_Settings_GetAsBit(
                        'PALM_Tickets.IncludeKgRejectInNetto', 0
                    )
                    """
                )
                include_kg_reject = bool(cursor.fetchone()[0])
                kg_reject = (
                    Decimal(str(nilai("KgReject", 0) or 0))
                    if include_kg_reject else Decimal("0")
                )

                timbang3 = Decimal(str(nilai("Timbang3", 0) or 0))
                tara_untuk_netto = timbang3 if timbang3 > 0 else tara

                deduction_harapan = deduction_lama + deduction_sortasi
                tiket["deduction"] = deduction_harapan
                tiket["netto"] = (
                    bruto - tara_untuk_netto
                    - deduction_harapan + kg_reject
                )

        tiket["bruto"] = bruto
        tiket["tara"] = tara
        tiket["step"] = step_baru
        tiket["datetimeout"] = date_time_out

        if step_baru == 2 and ticket_type == "Produk":
            no_do1 = str(nilai("SPDO", "") or "").strip()
            alasan_pending = None

            try:
                do1 = _baca_do_produk_ascend(no_do1)
            except Exception as e:
                do1 = None
                alasan_pending = (
                    f"Data DO pertama Ascend belum dapat dibaca: {e}"
                )

            if not alasan_pending:
                if not do1:
                    alasan_pending = (
                        "DO pertama tidak ditemukan di Ascend; "
                        "menunggu data DO dapat dipastikan."
                    )
                elif do1["void"]:
                    raise ValueError(
                        "DO pertama sudah dibatalkan di Ascend. "
                        "Tiket perlu diperiksa sebelum timbang akhir disimpan."
                    )
                else:
                    netto_final = Decimal(str(tiket["netto"]))
                    sisa_do1 = Decimal(str(do1["sisa"] or 0))

                    # DO yang ditutup tidak menerima alokasi baru.
                    if do1["closed"]:
                        sisa_do1 = Decimal("0")

                    if netto_final > sisa_do1:
                        try:
                            do2 = cari_pasangan_do2_ascend(
                                "Produk",
                                no_do1,
                            )
                        except Exception as e:
                            do2 = None
                            alasan_pending = (
                                f"Pasangan DO2 belum dapat dipastikan: {e}"
                            )

                        if not alasan_pending:
                            if not do2:
                                alasan_pending = (
                                    "Netto melewati sisa DO1; "
                                    "menunggu DO2 yang cocok."
                                )
                            elif sisa_do1 > 0:
                                # Masih ada bagian untuk DO1: minta Ascend split.
                                spdo2 = do2["no_do"]
                            else:
                                # DO1 habis: seluruh tiket diarahkan ke DO2.
                                # Tidak meminta Ascend membuat anak dengan netto 0.
                                tiket["spdo"] = do2["no_do"]
                                tiket["deliveryorderid"] = int(do2["id_do"])

            if alasan_pending:
                pending = db_ascend_split.simpan_timbang_akhir_pending(
                    int(nilai("TicketID")),
                    berat,
                    now,
                    int(operator),
                    alasan_pending,
                )

                koneksi.rollback()
                return {
                    "step": 2,
                    "ticket_type": ticket_type,
                    "ticket_id": int(nilai("TicketID")),
                    "ticket_no": no_tiket,
                    "pending_do2": True,
                    "pending_status": pending["status"],
                    "no_do2": None,
                    "tiket_split": [],
                    "berat_bruto": float(bruto),
                    "berat_tara": float(tara),
                    "berat_netto": float(bruto - tara),
                }

        # Ambil parameter prosedur Ascend; kirim nilai yang tersedia di baris tiket.
        cursor.execute(
            """
            SELECT name
            FROM sys.parameters
            WHERE object_id = OBJECT_ID('dbo.USP_PALM_Tickets_Update')
              AND parameter_id > 0
            ORDER BY parameter_id
            """
        )
        nama_parameter = [row[0] for row in cursor.fetchall()]

        wajib = {
            "ticketid", "ticketno", "tickettype", "date", "datetimein",
            "estateid", "vehicleno", "referenceno", "associateid",
            "productname", "bruto", "tara", "deduction", "netto",
            "checkedby", "operator", "printcount", "step",
            "owncar", "allocated", "external",
        }

        parameter_terisi = []
        nilai_parameter = []
        tidak_tersedia = []

        for nama in nama_parameter:
            kunci = nama.lstrip("@").casefold()

            if kunci == "operator":
                isi = str(operator)[:50]
            elif kunci == "spdo2":
                isi = spdo2
            elif kunci == "loginname":
                isi = str(operator)[:30]
            elif kunci in tiket:
                isi = tiket[kunci]
            else:
                if kunci in wajib:
                    tidak_tersedia.append(nama)
                continue

            parameter_terisi.append(nama)
            nilai_parameter.append(isi)

        if tidak_tersedia:
            raise RuntimeError(
                "Kolom tiket tidak cukup untuk mengisi parameter wajib Ascend: "
                + ", ".join(tidak_tersedia)
            )

        sql = (
            "EXEC dbo.USP_PALM_Tickets_Update "
            + ", ".join(f"{nama} = ?" for nama in parameter_terisi)
        )
        cursor.execute(sql, *nilai_parameter)
        ticket_id_induk = int(nilai("TicketID"))
        tiket_split = []

        # Untuk timbang biasa, pastikan nilai benar-benar sudah tertulis
        # di PALM_Tickets sebelum transaksi di-commit.
        # Kasus split diperiksa lewat validasi dua tiket pecahan di bawah.
        if not spdo2:
            cursor.execute(
                """
                SELECT Bruto, Tara, Netto, [Step], DateTimeOut, SPDO, Deduction
                FROM dbo.PALM_Tickets
                WHERE TicketID = ?
                """,
                ticket_id_induk,
            )
            tersimpan = cursor.fetchone()

            if not tersimpan:
                raise RuntimeError(
                    "Tiket tidak ditemukan saat memeriksa hasil simpan timbang."
                )

            (
                bruto_db,
                tara_db,
                netto_db,
                step_db,
                datetime_out_db,
                spdo_db,
                deduction_db,
            ) = tersimpan
            toleransi_kg = Decimal("0.01")

            def berat_sesuai(nilai_db, nilai_harapan):
                if nilai_db is None:
                    return False
                return (
                    abs(Decimal(str(nilai_db)) - Decimal(str(nilai_harapan)))
                    <= toleransi_kg
                )

            if int(step_db or 0) != step_baru:
                raise RuntimeError(
                    "Step tiket Ascend tidak sama dengan tahap timbang yang dikirim."
                )

            if not berat_sesuai(bruto_db, bruto):
                raise RuntimeError(
                    "Nilai Bruto yang tersimpan di Ascend tidak sesuai."
                )

            if not berat_sesuai(tara_db, tara):
                raise RuntimeError(
                    "Nilai Tara yang tersimpan di Ascend tidak sesuai."
                )

            if step_baru == 2:
                netto_harapan = Decimal(str(tiket["netto"] or 0))

                if not berat_sesuai(netto_db, netto_harapan):
                    raise RuntimeError(
                        "Nilai Netto yang tersimpan di Ascend tidak sesuai."
                    )

                if deduction_harapan is not None:
                    if not berat_sesuai(deduction_db, deduction_harapan):
                        raise RuntimeError(
                            "Nilai Deduction yang tersimpan di Ascend tidak sesuai."
                        )

                if datetime_out_db is None:
                    raise RuntimeError(
                        "DateTimeOut belum tersimpan pada timbang terakhir."
                    )

            if ticket_type == "Produk" and step_baru == 2 and not spdo2:
                spdo_harapan = str(tiket.get("spdo") or "").strip()
                spdo_tersimpan = str(spdo_db or "").strip()

                if spdo_tersimpan.casefold() != spdo_harapan.casefold():
                    raise RuntimeError(
                        "Nomor DO tiket yang tersimpan di Ascend tidak sesuai."
                    )

        if spdo2:
            cursor.execute(
                """
                SELECT TicketID, TicketNo, SPDO, Netto, [Step]
                FROM dbo.PALM_Tickets
                WHERE ParentTicketID = ?
                  AND ISNULL([Void], 0) = 0
                ORDER BY TicketID
                """,
                ticket_id_induk,
            )

            tiket_split = [
                {
                    "ticket_id": int(row[0]),
                    "no_tiket": str(row[1] or "").strip(),
                    "no_do": str(row[2] or "").strip(),
                    "berat_netto": float(row[3] or 0),
                    "step": int(row[4] or 0),
                }
                for row in cursor.fetchall()
            ]

            if len(tiket_split) != 2:
                raise RuntimeError(
                    "Ascend menerima permintaan split, tetapi tidak "
                    "mengembalikan tepat dua tiket pecahan."
                )

            do_pecahan = {
                baris["no_do"].casefold()
                for baris in tiket_split
            }
            if do_pecahan != {
                str(nilai("SPDO", "") or "").strip().casefold(),
                spdo2.strip().casefold(),
            }:
                raise RuntimeError(
                    "DO pada tiket pecahan Ascend tidak cocok dengan DO1 dan DO2."
                )

            netto_pecahan = sum(
                Decimal(str(baris["berat_netto"]))
                for baris in tiket_split
            )
            netto_awal = Decimal(str(tiket["netto"] or 0))

            if abs(netto_pecahan - netto_awal) > Decimal("0.01"):
                raise RuntimeError(
                    "Jumlah netto tiket pecahan tidak sama dengan netto truk."
                )
        koneksi.commit()

        return {
            "step": step_baru,
            "ticket_type": ticket_type,
            "ticket_id": int(nilai("TicketID")),
            "ticket_no": no_tiket,
            "no_do2": spdo2 or None,
            "tiket_split": tiket_split,
            "berat_bruto": float(bruto) if step_baru == 2 or ticket_type == "TBSLuar" else None,
            "berat_tara": float(tara) if step_baru == 2 or ticket_type == "Produk" else None,
            "berat_netto": float(tiket["netto"]) if step_baru == 2 else None,
        }

    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()

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
                SELECT {nama_id_do}, MillID
                FROM dbo.{tabel_do}
                WHERE {nama_id_do} IN ({tanda_tanya_do})
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
                "contract_no": str(row.get("ContractNoEx") or "").strip(),
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
def daftar_kontrak_ascend(cari="", batas=500):
    """Daftar Kontrak Produk dan Kontrak Pembelian TBS Luar dari Ascend."""
    cari = (cari or "").strip()
    pola = f"%{cari}%"
    batas = max(1, min(int(batas), 1000))

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            f"""
            SELECT TOP ({batas}) *
            FROM (
                SELECT
                    CAST('PRODUK' AS varchar(10)) AS source_kind,
                    c.ContractID AS source_id,
                    c.ContractNumber AS no_kontrak,
                    c.ReferenceNo AS no_referensi,
                    CAST('PENJUALAN' AS varchar(20)) AS jenis_transaksi,
                    c.CustomerID AS associate_id,
                    a.CustomerName AS nama_associate,
                    c.ProductName AS nama_produk,
                    c.ContractDate AS tanggal_kontrak,
                    c.Quantity AS qty_kg,
                    c.PricePerKg AS harga_per_kg,
                    c.TaxPercent AS tax_percent,
                    c.InclusiveTax AS inclusive_tax,
                    c.MillID AS mill_id,
                    c.CreateDate AS created_at,
                    c.Void AS is_void,
                    CAST(0 AS bit) AS is_closed,
                    c.ManagerApproved AS manager_approved,
                    c.DirectorApproved AS director_approved,
                    c.Verified AS verified,
                    (
                        SELECT COUNT_BIG(*)
                        FROM dbo.PALM_DeliveryOrders d
                        WHERE d.ContractID = c.ContractID
                          AND ISNULL(d.Void, 0) = 0
                    ) AS jumlah_do
                FROM dbo.PALM_Contracts c
                LEFT JOIN dbo.AR_Customers a
                    ON a.CustomerID = c.CustomerID

                UNION ALL

                SELECT
                    CAST('TBSLUAR' AS varchar(10)) AS source_kind,
                    pc.PurchaseContractID AS source_id,
                    pc.PurchaseContractNumber AS no_kontrak,
                    pc.ReferenceNo AS no_referensi,
                    CAST('PEMBELIAN' AS varchar(20)) AS jenis_transaksi,
                    pc.SupplierID AS associate_id,
                    s.SupplierName AS nama_associate,
                    pc.ProductName AS nama_produk,
                    pc.PurchaseContractDate AS tanggal_kontrak,
                    pc.Quantity AS qty_kg,
                    pc.PricePerKg AS harga_per_kg,
                    pc.TaxPercent AS tax_percent,
                    pc.InclusiveTax AS inclusive_tax,
                    pc.MillID AS mill_id,
                    pc.CreateDate AS created_at,
                    pc.Void AS is_void,
                    pc.Closed AS is_closed,
                    pc.ManagerApproved AS manager_approved,
                    pc.DirectorApproved AS director_approved,
                    pc.Verified AS verified,
                    (
                        SELECT COUNT_BIG(*)
                        FROM dbo.PALM_ReceivingDeliveryOrders r
                        WHERE r.ContractID = pc.PurchaseContractID
                          AND ISNULL(r.Void, 0) = 0
                    ) AS jumlah_do
                FROM dbo.PALM_PurchaseContracts pc
                LEFT JOIN dbo.AP_Suppliers s
                    ON s.SupplierID = pc.SupplierID
            ) AS daftar
            WHERE no_kontrak LIKE ?
               OR no_referensi LIKE ?
               OR nama_associate LIKE ?
               OR nama_produk LIKE ?
            ORDER BY
                CASE WHEN is_void = 0 AND is_closed = 0 THEN 0 ELSE 1 END,
                created_at DESC
            """,
            pola,
            pola,
            pola,
            pola,
        )

        hasil = []
        for row in _baris_hasil(cursor):
            hasil.append({
                "id_kontrak": (
                    f"{row['source_kind']}:{int(row['source_id'])}"
                ),
                "jenis_dokumen": str(row["source_kind"]).strip(),
                "no_kontrak": str(row.get("no_kontrak") or "").strip(),
                "no_referensi": str(
                    row.get("no_referensi") or ""
                ).strip(),
                "jenis_transaksi": str(
                    row.get("jenis_transaksi") or ""
                ).strip(),
                "id_associate": (
                    int(row["associate_id"])
                    if row.get("associate_id") is not None else None
                ),
                "nama_associate": str(
                    row.get("nama_associate") or ""
                ).strip(),
                "nama_produk": str(row.get("nama_produk") or "").strip(),
                "tanggal_kontrak": row.get("tanggal_kontrak"),
                "qty_kg": (
                    float(row["qty_kg"])
                    if row.get("qty_kg") is not None else None
                ),
                "harga_per_kg": (
                    float(row["harga_per_kg"])
                    if row.get("harga_per_kg") is not None else None
                ),
                "tax_percent": (
                    float(row["tax_percent"])
                    if row.get("tax_percent") is not None else 0
                ),
                "inclusive_tax": bool(row.get("inclusive_tax")),
                "mill_id": (
                    int(row["mill_id"])
                    if row.get("mill_id") is not None else None
                ),
                "created_at": row.get("created_at"),
                "is_void": bool(row.get("is_void")),
                "is_closed": bool(row.get("is_closed")),
                "is_active": not bool(
                    row.get("is_void") or row.get("is_closed")
                ),
                "manager_approved": bool(row.get("manager_approved")),
                "director_approved": bool(row.get("director_approved")),
                "verified": bool(row.get("verified")),
                "jumlah_do": int(row.get("jumlah_do") or 0),
            })

        return hasil
    finally:
        koneksi.close()
        
def daftar_kontrak_do_ascend(cari="", batas=500):
    """Daftar DO Produk dan TBS Luar untuk halaman Kontrak & DO."""
    cari = (cari or "").strip()
    pola = f"%{cari}%"
    batas = max(1, min(int(batas), 1000))

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            f"""
            SELECT TOP ({batas}) *
            FROM (
                SELECT
                    CAST('PRODUK' AS varchar(10)) AS source_kind,
                    d.DeliveryOrderID AS source_id,
                    d.DeliveryOrderNumber AS no_do,
                    d.ContractID AS id_kontrak,
                    COALESCE(
                        NULLIF(d.ContractNoEx, ''),
                        NULLIF(c.ContractNumber, ''),
                        c.ReferenceNo,
                        ''
                    ) AS no_kontrak,
                    CAST('PENJUALAN' AS varchar(20)) AS jenis_transaksi,
                    d.CustomerID AS id_customer,
                    a.CustomerName AS nama_customer,
                    d.ProductName AS nama_produk,
                    COALESCE(c.ContractDate, d.DeliveryOrderDate) AS tanggal_kontrak,
                    d.Quantity AS qty_kg,
                    c.PricePerKg AS harga_per_kg,
                    COALESCE(
                        NULLIF(d.Remarks, ''),
                        NULLIF(c.Remarks, ''),
                        ''
                    ) AS keterangan,
                    CASE
                        WHEN ISNULL(c.TaxPercent, 0) > 0 THEN 1
                        ELSE 0
                    END AS ppn,
                    ISNULL(c.InclusiveTax, 0) AS harga_termasuk_ppn,
                    d.MillID AS id_company,
                    d.MillID AS mill_id,
                    CONCAT('Mill ', d.MillID) AS kode_company,
                    d.DeliveryOrderDate AS tanggal_do,
                    d.DeliveryOrderDateUntil AS berlaku_sampai,
                    CASE
                        WHEN ISNULL(d.Void, 0) = 0
                         AND ISNULL(d.Closed, 0) = 0
                         AND ISNULL(c.Void, 0) = 0 THEN 1
                        ELSE 0
                    END AS is_active,
                    d.CreateDate AS created_at,
                    d.QuantityShipped AS realisasi_kg
                FROM dbo.PALM_DeliveryOrders d
                LEFT JOIN dbo.PALM_Contracts c
                    ON c.ContractID = d.ContractID
                LEFT JOIN dbo.AR_Customers a
                    ON a.CustomerID = d.CustomerID

                UNION ALL

                SELECT
                    CAST('TBSLUAR' AS varchar(10)) AS source_kind,
                    r.ReceivingDeliveryOrderID AS source_id,
                    r.ReceivingDeliveryOrderNumber AS no_do,
                    r.ContractID AS id_kontrak,
                    COALESCE(
                        NULLIF(pc.PurchaseContractNumber, ''),
                        pc.ReferenceNo,
                        ''
                    ) AS no_kontrak,
                    CAST('PEMBELIAN' AS varchar(20)) AS jenis_transaksi,
                    r.SupplierID AS id_customer,
                    s.SupplierName AS nama_customer,
                    r.ProductName AS nama_produk,
                    COALESCE(
                        pc.PurchaseContractDate,
                        r.ReceivingDeliveryOrderDate
                    ) AS tanggal_kontrak,
                    r.Quantity AS qty_kg,
                    pc.PricePerKg AS harga_per_kg,
                    COALESCE(
                        NULLIF(r.Remarks, ''),
                        NULLIF(pc.Remarks, ''),
                        ''
                    ) AS keterangan,
                    CASE
                        WHEN ISNULL(pc.TaxPercent, 0) > 0 THEN 1
                        ELSE 0
                    END AS ppn,
                    ISNULL(pc.InclusiveTax, 0) AS harga_termasuk_ppn,
                    r.MillID AS id_company,
                    r.MillID AS mill_id,
                    CONCAT('Mill ', r.MillID) AS kode_company,
                    r.ReceivingDeliveryOrderDate AS tanggal_do,
                    CAST(NULL AS datetime) AS berlaku_sampai,
                    CASE
                        WHEN ISNULL(r.Void, 0) = 0
                         AND ISNULL(r.Closed, 0) = 0
                         AND ISNULL(pc.Void, 0) = 0
                         AND ISNULL(pc.Closed, 0) = 0 THEN 1
                        ELSE 0
                    END AS is_active,
                    r.CreateDate AS created_at,
                    r.QuantityShipped AS realisasi_kg
                FROM dbo.PALM_ReceivingDeliveryOrders r
                LEFT JOIN dbo.PALM_PurchaseContracts pc
                    ON pc.PurchaseContractID = r.ContractID
                LEFT JOIN dbo.AP_Suppliers s
                    ON s.SupplierID = r.SupplierID
            ) AS daftar
            WHERE no_do LIKE ?
               OR no_kontrak LIKE ?
               OR nama_customer LIKE ?
               OR nama_produk LIKE ?
            ORDER BY is_active DESC, created_at DESC
            """,
            pola,
            pola,
            pola,
            pola,
        )
        rows = _baris_hasil(cursor)

        id_do_produk = [
            int(row["source_id"])
            for row in rows
            if row["source_kind"] == "PRODUK"
        ]
        angkutan_per_do = {}

        for awal in range(0, len(id_do_produk), 900):
            bagian = id_do_produk[awal:awal + 900]
            tanda_tanya = ", ".join("?" for _ in bagian)

            cursor.execute(
                f"""
                SELECT
                    t.DeliveryOrderID AS id_do,
                    t.ShipperID AS shipper_id,
                    s.SupplierName AS nama_pengangkutan,
                    t.MaxKg AS max_kg,
                    t.CostPerKg AS ongkos_per_kg
                FROM dbo.PALM_DOTransport t
                LEFT JOIN dbo.AP_Suppliers s
                    ON s.SupplierID = t.ShipperID
                WHERE t.DeliveryOrderID IN ({tanda_tanya})
                ORDER BY t.DetailID
                """,
                *bagian,
            )

            for row in _baris_hasil(cursor):
                id_do = int(row["id_do"])
                nama = str(row.get("nama_pengangkutan") or "").strip()

                if not nama:
                    nama = f"Shipper {row['shipper_id']}"

                angkutan_per_do.setdefault(id_do, []).append({
                    "cara_angkut": "ASCEND",
                    "nama_pengangkutan": nama,
                    "qty_kg": (
                        float(row["max_kg"])
                        if row.get("max_kg") is not None else None
                    ),
                    "ongkos_per_kg": (
                        float(row["ongkos_per_kg"])
                        if row.get("ongkos_per_kg") is not None else None
                    ),
                    "label": nama,
                })

        hasil = []

        for row in rows:
            source_kind = str(row["source_kind"]).strip()
            source_id = int(row["source_id"])
            mill_id = row.get("mill_id")

            hasil.append({
                "id_do": f"{source_kind}:{source_id}",
                "no_do": str(row.get("no_do") or "").strip(),
                "id_kontrak": (
                    int(row["id_kontrak"])
                    if row.get("id_kontrak") is not None else None
                ),
                "no_kontrak": str(row.get("no_kontrak") or "").strip(),
                "jenis_transaksi": str(
                    row.get("jenis_transaksi") or ""
                ).strip(),
                "id_customer": (
                    int(row["id_customer"])
                    if row.get("id_customer") is not None else None
                ),
                "nama_customer": str(
                    row.get("nama_customer") or ""
                ).strip(),
                "id_produk": None,
                "nama_produk": str(row.get("nama_produk") or "").strip(),
                "tanggal_kontrak": row.get("tanggal_kontrak"),
                "qty_kg": (
                    float(row["qty_kg"])
                    if row.get("qty_kg") is not None else None
                ),
                "harga_per_kg": (
                    float(row["harga_per_kg"])
                    if row.get("harga_per_kg") is not None else None
                ),
                "keterangan": str(row.get("keterangan") or "").strip(),
                "ppn": bool(row.get("ppn")),
                "harga_termasuk_ppn": bool(
                    row.get("harga_termasuk_ppn")
                ),
                "id_company": (
                    int(mill_id) if mill_id is not None else None
                ),
                "kode_company": str(
                    row.get("kode_company") or ""
                ).strip(),
                "tanggal_do": row.get("tanggal_do"),
                "berlaku_sampai": row.get("berlaku_sampai"),
                "is_active": bool(row.get("is_active")),
                "created_at": row.get("created_at"),
                "realisasi_kg": (
                    float(row["realisasi_kg"])
                    if row.get("realisasi_kg") is not None else None
                ),
                "angkutan": (
                    angkutan_per_do.get(source_id, [])
                    if source_kind == "PRODUK" else []
                ),
            })

        return hasil
    finally:
        koneksi.close()

def _baca_do_produk_ascend(no_do):
    """Baca DO Produk Ascend, termasuk DO yang outstanding-nya sudah nol."""
    no_do = (no_do or "").strip()
    if not no_do:
        return None

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1)
                DeliveryOrderID,
                DeliveryOrderNumber,
                ContractNoEx,
                ContractID,
                CustomerID,
                ProductName,
                MillID,
                Quantity,
                QuantityShipped,
                Void,
                Closed
            FROM dbo.PALM_DeliveryOrders
            WHERE DeliveryOrderNumber = ?
            """,
            no_do,
        )
        row = cursor.fetchone()
    finally:
        koneksi.close()

    if not row:
        return None

    quantity = Decimal(str(row[7] or 0))
    quantity_shipped = Decimal(str(row[8] or 0))
    sisa = max(Decimal("0"), quantity - quantity_shipped)

    return {
        "id_do": int(row[0]),
        "no_do": str(row[1] or "").strip(),
        "contract_no": str(row[2] or "").strip(),
        "contract_id": int(row[3]) if row[3] is not None else None,
        "associate_id": int(row[4]) if row[4] is not None else None,
        "produk": str(row[5] or "").strip(),
        "mill_id": int(row[6]) if row[6] is not None else None,
        "sisa": sisa,
        "void": bool(row[9]),
        "closed": bool(row[10]),
    }

def cari_pasangan_do2_ascend(ticket_type, no_do1):
    """Cari DO2 outstanding untuk DO Produk yang kontraknya sama."""
    if ticket_type != "Produk":
        raise ValueError("Split DO hanya berlaku untuk tiket Produk.")

    do1 = _baca_do_produk_ascend(no_do1)
    if not do1:
        raise ValueError(
            "DO pertama tidak ditemukan di database Ascend."
        )
    if do1["void"]:
        raise ValueError(
            "DO pertama sudah dibatalkan di Ascend."
        )

    kontrak1 = do1["contract_no"].strip().casefold()
    if not kontrak1:
        raise ValueError(
            "Nomor referensi kontrak DO pertama kosong; "
            "pasangan DO belum bisa ditentukan."
        )

    daftar = daftar_do("Produk")
    kandidat = [
        d for d in daftar
        if d["no_do"].strip().casefold() != do1["no_do"].casefold()
        and d.get("contract_no", "").strip().casefold() == kontrak1
        and int(d["associate_id"]) == int(do1["associate_id"])
        and d["produk"].strip().casefold() == do1["produk"].strip().casefold()
        and d.get("mill_id") is not None
        and do1.get("mill_id") is not None
        and int(d["mill_id"]) == int(do1["mill_id"])
        and float(d.get("sisa") or 0) > 0
    ]

    if not kandidat:
        return None

    if len(kandidat) > 1:
        raise ValueError(
            "Ada lebih dari satu DO outstanding yang cocok. "
            "Pasangan belum dipilih agar alokasi tidak salah."
        )

    return kandidat[0]

def daftar_associate(ticket_type):
    """Daftar Associate dari Ascend, beserta kode dan nama."""
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
        tiket_aktif = _kunci_dan_cari_tiket_aktif(cursor, vehicle_no)
        if tiket_aktif:
            raise ValueError(
                f"Truk {vehicle_no} masih memiliki tiket Ascend "
                f"{str(tiket_aktif[0]).strip()} yang belum selesai."
            )
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
            date_time_in,
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
            """
            SELECT TicketNo, DateTimeIn
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            ticket_id,
        )
        tiket = cursor.fetchone()

        if not tiket:
            raise RuntimeError(
                f"TicketID {ticket_id} dikembalikan, tetapi tiket tidak ditemukan."
            )

        waktu_tersimpan = tiket[1]
        if waktu_tersimpan is None:
            raise RuntimeError(
                f"DateTimeIn tiket {tiket[0]} belum tersimpan di Ascend."
            )

        selisih_detik = abs(
            (waktu_tersimpan - date_time_in).total_seconds()
        )
        if selisih_detik > 1:
            raise RuntimeError(
                f"DateTimeIn tiket {tiket[0]} tidak cocok dengan waktu yang dikirim."
            )

        koneksi.commit()
        return {
            "ticket_id": ticket_id,
            "ticket_no": str(tiket[0]),
        }
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