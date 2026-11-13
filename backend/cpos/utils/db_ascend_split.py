"""Metadata sementara pasangan DO2 untuk tiket Ascend."""
from utils.db_utils import get_connection


def simpan_pasangan_do2(ticket_id, ticket_no, no_do2, created_by=None):
    """Buat atau perbarui rencana pasangan DO2; DO2 boleh belum tersedia."""
    ticket_id = int(ticket_id)
    ticket_no = (ticket_no or "").strip()
    no_do2 = (no_do2 or "").strip().upper()

    if not ticket_no:
        raise ValueError("Nomor tiket Ascend wajib diisi.")
    if len(no_do2) > 50:
        raise ValueError("Nomor DO kedua maksimal 50 karakter.")

    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            UPDATE dbo.AscendTicketSplitPlan
            SET TicketNo = ?,
                NoDO2 = ?,
                CreatedBy = COALESCE(?, CreatedBy)
            WHERE TicketID = ?
            """,
            ticket_no,
            no_do2,
            int(created_by) if created_by is not None else None,
            ticket_id,
        )

        if cursor.rowcount == 0:
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

def baca_status_timbang_pending(ticket_no):
    """Ambil status timbang tertunda dari rencana split di Main."""
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TicketID, NoDO2, PendingFinalScaleKg,
                   PendingStatus, PendingLastError
            FROM dbo.AscendTicketSplitPlan
            WHERE TicketNo = ?
            """,
            (ticket_no or "").strip(),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "ticket_id": int(row[0]),
            "no_do2": str(row[1] or "").strip(),
            "berat_akhir_pending": (
                float(row[2]) if row[2] is not None else None
            ),
            "status": str(row[3] or "").strip().upper(),
            "error": str(row[4] or "").strip() or None,
        }
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

def daftar_timbang_akhir_pending():
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (100)
                TicketID AS ticket_id,
                TicketNo AS ticket_no,
                PendingFinalScaleKg AS berat_akhir,
                PendingFinalAt AS waktu_timbang,
                PendingFinalBy AS operator_id
            FROM dbo.AscendTicketSplitPlan
            WHERE PendingStatus = 'MENUNGGU_DO2'
              AND PendingFinalScaleKg IS NOT NULL
            ORDER BY PendingFinalAt, TicketID
            """
        )
        kolom = [item[0] for item in cursor.description]
        return [dict(zip(kolom, row)) for row in cursor.fetchall()]
    finally:
        koneksi.close()


def catat_percobaan_timbang_pending(ticket_id, alasan):
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            UPDATE dbo.AscendTicketSplitPlan
            SET PendingAttempts = ISNULL(PendingAttempts, 0) + 1,
                PendingLastError = ?
            WHERE TicketID = ?
              AND PendingStatus = 'MENUNGGU_DO2'
            """,
            str(alasan or "")[:1000],
            int(ticket_id),
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def selesaikan_timbang_pending(ticket_id, no_do2=None):
    no_do2 = (no_do2 or "").strip().upper()
    status = "SELESAI_SPLIT" if no_do2 else "SELESAI_TANPA_SPLIT"

    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            UPDATE dbo.AscendTicketSplitPlan
            SET NoDO2 = CASE WHEN ? <> '' THEN ? ELSE NoDO2 END,
                PendingStatus = ?,
                PendingLastError = NULL,
                PendingCompletedAt = SYSDATETIME()
            WHERE TicketID = ?
              AND PendingFinalScaleKg IS NOT NULL
            """,
            no_do2,
            no_do2,
            status,
            int(ticket_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                f"Status timbang tertunda TicketID {ticket_id} tidak berhasil diperbarui."
            )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()

def daftar_monitor_split():
    """Daftar timbang pending/split untuk pemantauan tim DO/kontrak."""
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT
                TicketID AS ticket_id,
                TicketNo AS ticket_no,
                NoDO2 AS no_do2,
                PendingFinalScaleKg AS berat_akhir,
                PendingFinalAt AS waktu_timbang,
                PendingStatus AS status,
                PendingAttempts AS jumlah_percobaan,
                PendingLastError AS pesan_error,
                PendingCompletedAt AS waktu_selesai
            FROM dbo.AscendTicketSplitPlan
            WHERE PendingStatus IN (
                'MENUNGGU_DO2',
                'SELESAI_SPLIT',
                'SELESAI_TANPA_SPLIT'
            )
            ORDER BY
                COALESCE(PendingFinalAt, PendingCompletedAt) DESC,
                TicketID DESC
            """
        )
        kolom = [item[0] for item in cursor.description]
        return [dict(zip(kolom, row)) for row in cursor.fetchall()]
    finally:
        koneksi.close()