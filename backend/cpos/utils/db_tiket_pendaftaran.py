"""Pendaftaran tiket kosong pada database Tiket."""

from utils.db_tiket_common import koneksi_tiket as _koneksi

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

