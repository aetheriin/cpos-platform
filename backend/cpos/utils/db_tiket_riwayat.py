"""Antrean dan riwayat tiket Ascend."""
from datetime import date, datetime

from utils.db_tiket_common import (
    koneksi_tiket as _koneksi,
    baris_hasil as _baris_hasil,
)

def daftar_antrian_lab_tiket(ticket_ids):
    """Baca antrean Lab Tiket dan batasi hasil ke TicketID area CPOS."""
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

def riwayat_timbang_associate(
    ticket_ids, associate_id, ticket_type, mulai, sampai
):
    """Riwayat timbang Tiket dalam cakupan tiket CPOS."""
    if ticket_type not in ("Produk", "TBSLuar"):
        raise ValueError("Jenis tiket tidak valid.")

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
