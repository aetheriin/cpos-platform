"""Pembacaan kontrak dan DO dari database Tiket."""

from decimal import Decimal

from utils.db_tiket_common import (
    koneksi_tiket as _koneksi,
    baris_hasil as _baris_hasil,
)

def daftar_do(ticket_type):
    """DO outstanding beserta nama Associate dari database Tiket."""
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
def daftar_kontrak_tiket(cari="", batas=500):
    """Daftar Kontrak Produk dan Kontrak Pembelian TBS Luar dari Tiket."""
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
        
def daftar_kontrak_do_tiket(cari="", batas=500):
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

def _baca_do_produk_tiket(no_do):
    """Baca DO Produk Tiket, termasuk DO yang outstanding-nya sudah nol."""
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

def cari_pasangan_do2_tiket(ticket_type, no_do1):
    """Cari DO2 outstanding untuk DO Produk yang kontraknya sama."""
    if ticket_type != "Produk":
        raise ValueError("Pemisahan DO hanya berlaku untuk tiket Produk.")

    do1 = _baca_do_produk_tiket(no_do1)
    if not do1:
        raise ValueError(
            "DO pertama tidak ditemukan di database Tiket."
        )
    if do1["void"]:
        raise ValueError(
            "DO pertama sudah dibatalkan di Tiket."
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
