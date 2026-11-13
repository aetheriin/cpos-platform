"""Metadata sementara pasangan DO2 untuk tiket Ascend."""
from utils.db_utils import get_connection


def simpan_pasangan_do2(ticket_id, ticket_no, no_do2, created_by=None):
    """Simpan DO2 pasangan untuk TicketID Ascend."""
    ticket_id = int(ticket_id)
    ticket_no = (ticket_no or "").strip()
    no_do2 = (no_do2 or "").strip().upper()

    if not ticket_no:
        raise ValueError("Nomor tiket Ascend wajib diisi.")
    if not no_do2:
        raise ValueError("DO kedua wajib dipilih.")
    if len(no_do2) > 50:
        raise ValueError("Nomor DO kedua maksimal 50 karakter.")

    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.AscendTicketSplitPlan
                (TicketID, TicketNo, NoDO2, CreatedBy)
            VALUES (?, ?, ?, ?)
            """,
            ticket_id,
            ticket_no,
            no_do2,
            int(created_by) if created_by is not None else None,
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def ambil_pasangan_do2(ticket_id):
    """Ambil DO2 yang dipasangkan ke tiket Ascend."""
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT NoDO2
            FROM dbo.AscendTicketSplitPlan
            WHERE TicketID = ?
            """,
            int(ticket_id),
        )
        row = cursor.fetchone()
        return str(row[0]).strip() if row and row[0] else None
    finally:
        koneksi.close()


def hapus_pasangan_do2(ticket_id):
    """Hapus metadata pasangan setelah Ascend menyelesaikan split."""
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            DELETE FROM dbo.AscendTicketSplitPlan
            WHERE TicketID = ?
            """,
            int(ticket_id),
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()

def simpan_timbang_akhir_pending(
    ticket_id,
    berat_akhir,
    waktu_timbang,
    operator_id,
    alasan,
):
    """Simpan satu kali berat akhir sambil menunggu DO2 tersedia."""
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT PendingFinalScaleKg, PendingFinalAt, PendingFinalBy, PendingStatus
            FROM dbo.AscendTicketSplitPlan WITH (UPDLOCK, HOLDLOCK)
            WHERE TicketID = ?
            """,
            int(ticket_id),
        )
        baris = cursor.fetchone()

        if not baris:
            raise RuntimeError(
                f"Rencana split TicketID {ticket_id} tidak ditemukan di Main."
            )

        if baris[0] is not None:
            if str(baris[3] or "").strip().upper() == "MENUNGGU_DO2":
                koneksi.commit()
                return {
                    "berat_akhir": float(baris[0]),
                    "waktu_timbang": baris[1],
                    "operator_id": int(baris[2]) if baris[2] is not None else None,
                    "status": "MENUNGGU_DO2",
                }
            raise ValueError(
                "Berat akhir tiket ini sudah pernah dicatat; "
                "jangan menimbang atau menyimpan ulang."
            )

        cursor.execute(
            """
            UPDATE dbo.AscendTicketSplitPlan
            SET PendingFinalScaleKg = ?,
                PendingFinalAt = ?,
                PendingFinalBy = ?,
                PendingStatus = 'MENUNGGU_DO2',
                PendingAttempts = 0,
                PendingLastError = ?,
                PendingCompletedAt = NULL
            WHERE TicketID = ?
              AND PendingFinalScaleKg IS NULL
            """,
            float(berat_akhir),
            waktu_timbang,
            int(operator_id),
            str(alasan or "")[:1000],
            int(ticket_id),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Berat akhir tertunda tidak tersimpan tepat satu kali."
            )

        koneksi.commit()
        return {
            "berat_akhir": float(berat_akhir),
            "waktu_timbang": waktu_timbang,
            "operator_id": int(operator_id),
            "status": "MENUNGGU_DO2",
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()