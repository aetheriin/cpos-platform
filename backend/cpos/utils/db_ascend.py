"""Koneksi dan operasi tiket Ascend (database AS_WB_YBS)."""
import pyodbc

from datetime import datetime
from decimal import Decimal
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
                VehicleNo, [Date], SPDO, MILLID
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
            "jenis_transaksi": (
                "PENJUALAN" if row[1] == "Produk" else "PEMBELIAN"
            ),
        }
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

        tiket["bruto"] = bruto
        tiket["tara"] = tara
        tiket["step"] = step_baru
        tiket["datetimeout"] = date_time_out

        if step_baru == 2 and ticket_type == "Produk":
            no_do1 = str(nilai("SPDO", "") or "").strip()
            daftar = daftar_do("Produk")

            do1 = next(
                (
                    d for d in daftar
                    if d["no_do"].strip().casefold() == no_do1.casefold()
                ),
                None,
            )
            if not do1:
                raise ValueError(
                    "DO pertama tidak lagi tersedia sebagai DO outstanding Ascend."
                )

            netto_final = Decimal(str(tiket["netto"]))
            sisa_do1 = Decimal(str(do1.get("sisa") or 0))

            if netto_final > sisa_do1:
                do2 = cari_pasangan_do2_ascend("Produk", no_do1)
                if not do2:
                    pending = db_ascend_split.simpan_timbang_akhir_pending(
                        int(nilai("TicketID")),
                        berat,
                        now,
                        int(operator),
                        "Netto melewati sisa DO1; menunggu DO2 yang cocok.",
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
                spdo2 = do2["no_do"]

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

def cari_pasangan_do2_ascend(ticket_type, no_do1):
    """Cari satu DO outstanding lain dengan kontrak dan atribut yang sama."""
    no_do1 = (no_do1 or "").strip().casefold()
    daftar = daftar_do(ticket_type)

    do1 = next(
        (d for d in daftar if d["no_do"].strip().casefold() == no_do1),
        None,
    )
    if not do1:
        raise ValueError(
            "DO pertama tidak ditemukan di daftar outstanding Ascend."
        )

    kontrak1 = do1.get("contract_no", "").strip().casefold()
    if not kontrak1:
        raise ValueError(
            "Nomor referensi kontrak DO pertama kosong; pasangan DO belum bisa ditentukan."
        )

    kandidat = [
        d for d in daftar
        if d["no_do"].strip().casefold() != no_do1
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