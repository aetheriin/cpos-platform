"""Koneksi dan operasi tiket (database AS_WB_YBS)."""
from datetime import datetime
from decimal import Decimal
from utils import db_tiket_pisah
from utils.db_tiket_common import (koneksi_tiket as _koneksi, baris_hasil as _baris_hasil,)
from utils.db_tiket_master import (daftar_supplier_master_tiket, daftar_produk_master_tiket, daftar_produk_tbs_luar_tiket, 
                                   simpan_produk_master_tiket, daftar_associate, daftar_mill, daftar_shipper_kendaraan,)
from utils.db_tiket_pencarian import (cari_tiket_berdasarkan_plat, cari_tiket_berdasarkan_no_tiket, daftar_tiket_aktif, cari_tiket_global,)
from utils.db_tiket_riwayat import (daftar_antrian_lab_tiket, daftar_riwayat_lab_tiket, daftar_riwayat_sortasi_tiket, daftar_riwayat_tiket,
                                     riwayat_timbang_associate,)
from utils.db_tiket_kontrak_do import (daftar_do, daftar_kontrak_tiket, daftar_kontrak_do_tiket, _baca_do_produk_tiket, 
                                       cari_pasangan_do2_tiket,)
from utils.db_tiket_timbang import (baca_berat_tiket, baca_hasil_pisah_tiket, simpan_berat_tiket,)
from utils.db_tiket_lab import simpan_hasil_lab_tiket
from utils.db_tiket_sortasi import simpan_hasil_sortasi_tiket

def _kunci_dan_cari_tiket_aktif(cursor, vehicle_no):
    """Kunci proses per plat, lalu cari tiket yang belum selesai."""
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
          AND ISNULL([Pemisahanted], 0) = 0
          AND (ISNULL([Step], 0) < 2 OR DateTimeOut IS NULL)
        ORDER BY TicketID ASC
        """,
        plat_normal,
    )
    return cursor.fetchone()

def daftar_riwayat_lab_tiket(ticket_ids, batas=100):
    """Baca hasil Lab tersimpan dari tiket induk Tiket yang boleh dilihat area."""
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
                    t.Ulage,
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
                    "ulage": angka(row.get("Ulage")),
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

def daftar_riwayat_sortasi_tiket(ticket_ids, batas=100):
    """Baca riwayat Sortasi dari tiket sesuai cakupan TicketID."""
    ticket_ids = sorted({int(i) for i in (ticket_ids or [])})
    if not ticket_ids:
        return []

    batas = max(1, min(int(batas), 200))
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
                    t.TicketID AS ticket_id,
                    t.TicketNo AS no_tiket,
                    t.SortasiDateTime AS sortasi_datetime,
                    t.VehicleNo AS no_plat,
                    t.ProductName AS nama_produk,
                    s.SupplierName AS nama_supplier,
                    t.Deduction AS deduction_kg,
                    t.SortasiBy AS sortasi_by
                FROM dbo.PALM_Tickets t
                LEFT JOIN dbo.AP_Suppliers s
                    ON s.SupplierID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND t.TicketType = 'TBSLuar'
                  AND t.ProductName = 'TBS'
                  AND t.SortasiDateTime IS NOT NULL
                ORDER BY t.SortasiDateTime DESC, t.TicketID DESC
                """,
                *bagian,
            )

            for row in cursor.fetchall():
                hasil.append({
                    "ticket_id": int(row[0]),
                    "no_tiket": str(row[1] or "").strip(),
                    "sortasi_datetime": (
                        row[2].isoformat() if row[2] else None
                    ),
                    "no_plat": str(row[3] or "").strip(),
                    "nama_produk": str(row[4] or "").strip(),
                    "nama_supplier": str(row[5] or "").strip(),
                    "deduction_kg": (
                        float(row[6]) if row[6] is not None else None
                    ),
                    "sortasi_by": str(row[7] or "").strip(),
                })

        hasil.sort(
            key=lambda r: (r["sortasi_datetime"] or "", r["ticket_id"]),
            reverse=True,
        )
        return hasil[:batas]
    finally:
        koneksi.close()

def daftar_riwayat_tiket(ticket_ids, nama_produk=None, hari=7, batas=500):
    """Riwayat tiket induk Tiket yang termasuk area CPOS."""
    ticket_ids = sorted({int(i) for i in (ticket_ids or [])})
    if not ticket_ids:
        return []

    nama_produk = (nama_produk or "").strip() or None
    hari = max(1, int(hari))
    batas = max(1, int(batas))
    hasil = []

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        for awal in range(0, len(ticket_ids), 900):
            bagian = ticket_ids[awal:awal + 900]
            tanda_tanya = ", ".join("?" for _ in bagian)
            filter_produk = "AND t.ProductName = ?" if nama_produk else ""

            parameter = [*bagian, -hari]
            if nama_produk:
                parameter.append(nama_produk)

            cursor.execute(
                f"""
                SELECT
                    t.TicketID AS ticket_id,
                    COALESCE(
                        t.DateTimeIn,
                        CONVERT(DATETIME, t.[Date])
                    ) AS created_at,
                    t.DateTimeIn AS datetime_in,
                    t.DateTimeOut AS datetime_out,
                    t.TicketNo AS no_tiket,
                    t.VehicleNo AS no_plat,
                    COALESCE(c.CustomerName, s.SupplierName, '') AS supplier,
                    t.ProductName AS produk,
                    t.TicketType AS ticket_type,
                    t.Bruto AS berat_bruto,
                    t.Tara AS berat_tara,
                    t.Netto AS berat_netto,
                    t.[Step] AS step,
                    t.SPDO AS no_do,
                    t.Void AS void,
                    CASE
                        WHEN t.DateTimeIn IS NOT NULL
                         AND t.DateTimeOut IS NOT NULL
                        THEN DATEDIFF(MINUTE, t.DateTimeIn, t.DateTimeOut)
                        ELSE NULL
                    END AS lama_menit
                FROM dbo.PALM_Tickets t
                LEFT JOIN dbo.AR_Customers c
                    ON t.TicketType = 'Produk'
                   AND c.CustomerID = t.AssociateID
                LEFT JOIN dbo.AP_Suppliers s
                    ON t.TicketType = 'TBSLuar'
                   AND s.SupplierID = t.AssociateID
                WHERE t.TicketID IN ({tanda_tanya})
                  AND ISNULL(t.ParentTicketID, 0) = 0
                  AND COALESCE(
                      t.DateTimeIn,
                      CONVERT(DATETIME, t.[Date])
                  ) >= DATEADD(day, ?, CONVERT(date, GETDATE()))
                  {filter_produk}
                ORDER BY created_at DESC, t.TicketID DESC
                """,
                *parameter,
            )

            for row in _baris_hasil(cursor):
                step = int(row.get("step") or 0)
                void = bool(row.get("void"))

                if void:
                    status = "VOID"
                elif step >= 2 and row.get("datetime_out") is not None:
                    status = "SELESAI"
                elif step <= 0:
                    status = "SECURITY_REGISTER"
                else:
                    status = "TIMBANG_2"

                hasil.append({
                    "created_at": row.get("created_at"),
                    "no_tiket": str(row.get("no_tiket") or "").strip(),
                    "no_plat": str(row.get("no_plat") or "").strip(),
                    "supir": "",
                    "supplier": str(row.get("supplier") or "").strip(),
                    "produk": str(row.get("produk") or "").strip(),
                    "jenis_transaksi": (
                        "PENJUALAN"
                        if str(row.get("ticket_type") or "").strip() == "Produk"
                        else "PEMBELIAN"
                    ),
                    "berat_bruto": (
                        float(row["berat_bruto"])
                        if row.get("berat_bruto") is not None else None
                    ),
                    "berat_tara": (
                        float(row["berat_tara"])
                        if row.get("berat_tara") is not None else None
                    ),
                    "berat_netto": (
                        float(row["berat_netto"])
                        if row.get("berat_netto") is not None else None
                    ),
                    "status_alur": status,
                    "no_do": str(row.get("no_do") or "").strip(),
                    "lama_menit": (
                        int(row["lama_menit"])
                        if row.get("lama_menit") is not None else None
                    ),
                })

        hasil.sort(
            key=lambda row: row.get("created_at") or datetime.min,
            reverse=True,
        )
        return hasil[:batas]
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
                f"Truk {vehicle_no} masih memiliki tiket "
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
                "Prosedur Tiket tidak mengembalikan nilai RETURN sebagai TicketID."
            )
        if ticket_id <= 0:
            raise ValueError(f"Tiket mengembalikan TicketID {ticket_id}.")

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
                f"DateTimeIn tiket {tiket[0]} belum tersimpan di Tiket."
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

