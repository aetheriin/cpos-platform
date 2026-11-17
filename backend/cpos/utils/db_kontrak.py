from utils.db_utils import get_connection, get_semua_supplier, query as _query

def daftar_mitra():
    """Customer dan pengangkutan aktif untuk Pos Security dan Blacklist."""
    return _query(
        """
        SELECT
            s.SupplierID AS id_supplier,
            s.SupplierName AS nama_supplier,
            p.TypeCode AS peran
        FROM Supplier s
        JOIN SupplierTypeDetails p
            ON p.SupplierID = s.SupplierID
        WHERE s.Active = 1
        ORDER BY s.SupplierName
        """
    )

def id_pengangkutan_dari_nama(nama):
    """Cari atau buat pengangkut lokal untuk Pos Security."""
    nama = " ".join(nama.split())[:100]
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT SupplierID AS id_supplier
            FROM Supplier
            WHERE LOWER(SupplierName) = LOWER(?)
            """,
            nama,
        )
        row = cursor.fetchone()

        if row:
            id_mitra = row.id_supplier
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM Supplier WHERE SupplierCode LIKE 'ANG-%'"
            )
            kode = f"ANG-{cursor.fetchone()[0] + 1:03d}"
            cursor.execute(
                """
                SET NOCOUNT ON;
                INSERT INTO Supplier (SupplierCode, SupplierName)
                VALUES (?, ?);
                SELECT CAST(SCOPE_IDENTITY() AS INT)
                """,
                kode,
                nama,
            )
            id_mitra = cursor.fetchone()[0]

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM SupplierTypeDetails
                WHERE SupplierID = ?
                  AND TypeCode = 'PENGANGKUTAN'
            )
                INSERT INTO SupplierTypeDetails (SupplierID, TypeCode)
                VALUES (?, 'PENGANGKUTAN')
            """,
            id_mitra,
            id_mitra,
        )
        conn.commit()
    finally:
        conn.close()

    get_semua_supplier.hapus()
    return id_mitra