-- Stored procedure laporan Penilaian PVR, dibuat di database Main.
-- @CompID (opsional, mis. 'YBS'): satu perusahaan saja; kosong = semua perusahaan aktif bertipe CLOUD di dbo.company.
-- @Mulai, @Akhir: tanggal PVR (VoucherDate), @Akhir ikut dihitung.
-- @Bagian: 'ITEM' = item PVR pada periode itu (bawaan); 'CEK' = riwayat Check Number per supplier dari semua PVR yang tidak void
--          (jumlah pemakaian dan tanggal terakhir), dipakai Python untuk mengisi Check Number yang kosong.
-- VoucherItemID = urutan item saat diinput; item pertama per PVR (kategori selain Angkutan) adalah yang terkecil.
-- Data mentah saja: pemilihan nomor dokumen (ItemRef), nama supplier, Check Number dari histori, kategori, dan bobot dikerjakan di Python
-- (laporan/penilaian_pvr/sumber.py).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.PENILAIAN_PVR 'YBS', '2026-10-01', '2026-10-31';  dan  EXEC dbo.PENILAIAN_PVR 'YBS', NULL, NULL, 'CEK';
CREATE OR ALTER PROCEDURE dbo.PENILAIAN_PVR
    @CompID varchar(10) = NULL,
    @Mulai date = NULL,
    @Akhir date = NULL,
    @Bagian varchar(10) = 'ITEM'
AS
BEGIN
    SET NOCOUNT ON;

    CREATE TABLE #item (VoucherDate datetime, VoucherNo nvarchar(100), VoucherItemID int, AssociateID int, CheckNo nvarchar(200), CreatedBy nvarchar(100),
        SupplierName nvarchar(300), AssociateName nvarchar(300), ItemType varchar(10), OBNumber nvarchar(200), PurchaseNumber nvarchar(100),
        NoteNumber nvarchar(100), TicketNo nvarchar(100), Remarks nvarchar(1000), AmountPaid decimal(28, 6),
        CompID varchar(10) NULL);
    CREATE TABLE #cek (AssociateID int, CheckNo nvarchar(200), Jumlah int, Terakhir datetime, CompID varchar(10) NULL);

    DECLARE @item nvarchar(max) = N'
SELECT v.VoucherDate, v.VoucherNo, i.VoucherItemID, v.AssociateID, v.CheckNo, v.CreatedBy, s.SupplierName, v.AssociateName,
       i.ItemType, i.OBNumber, p.PurchaseNumber, n.Number, t.TicketNo, i.Remarks, i.AmountPaid
FROM {DB}.dbo.FI_APRequest v
JOIN {DB}.dbo.FI_APRequestItems i ON i.VoucherID = v.VoucherID
LEFT JOIN {DB}.dbo.AP_Purchases p ON p.PurchaseID = i.ItemID AND i.ItemType IN (''PI'', ''PO'', ''PR'')   -- PR = Purchase Return
LEFT JOIN {DB}.dbo.FI_ARAPNotes n ON n.ARAPNoteID = i.ItemID AND i.ItemType IN (''PN'', ''PD'', ''PUK'')
LEFT JOIN {DB}.dbo.PALM_Tickets t ON t.TicketID = i.ItemID AND i.ItemType IN (''TV'', ''BT'', ''BTP'')
LEFT JOIN {DB}.dbo.AP_Suppliers s ON s.SupplierID = v.AssociateID
WHERE v.VoucherDate >= ? AND v.VoucherDate < ?
  AND ISNULL(v.Void, 0) = 0;';

    DECLARE @cek nvarchar(max) = N'
SELECT AssociateID, LTRIM(RTRIM(CheckNo)), COUNT(*), MAX(VoucherDate)
FROM {DB}.dbo.FI_APRequest
WHERE NULLIF(LTRIM(RTRIM(CheckNo)), '''') IS NOT NULL
  AND ISNULL(Void, 0) = 0
GROUP BY AssociateID, LTRIM(RTRIM(CheckNo));';

    DECLARE @Comp varchar(10), @Server sysname, @DB sysname, @q nvarchar(max), @x nvarchar(max);
    DECLARE @Dari date = ISNULL(@Mulai, '19000101'), @Sampai date = DATEADD(day, 1, ISNULL(@Akhir, '99991230'));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT RTRIM(CompID), RTRIM(CompAddr), RTRIM(CompDataBase)
        FROM dbo.company
        WHERE RTRIM(CompType) = 'CLOUD' AND Status = 1
          AND NULLIF(RTRIM(CompAddr), '') IS NOT NULL AND NULLIF(RTRIM(CompDataBase), '') IS NOT NULL
          AND (@CompID IS NULL OR RTRIM(CompID) = RTRIM(@CompID))
        ORDER BY CompID;
    OPEN c; FETCH c INTO @Comp, @Server, @DB;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @Bagian = 'CEK'
        BEGIN
            SET @q = REPLACE(@cek, '{DB}', QUOTENAME(@DB));
            SET @x = N'INSERT INTO #cek (AssociateID, CheckNo, Jumlah, Terakhir) EXEC (@q) AT ' + QUOTENAME(@Server) + N';';
            EXEC sp_executesql @x, N'@q nvarchar(max)', @q;
            UPDATE #cek SET CompID = @Comp WHERE CompID IS NULL;
        END
        ELSE
        BEGIN
            SET @q = REPLACE(@item, '{DB}', QUOTENAME(@DB));
            SET @x = N'INSERT INTO #item (VoucherDate, VoucherNo, VoucherItemID, AssociateID, CheckNo, CreatedBy, SupplierName, AssociateName, ItemType, OBNumber,
                       PurchaseNumber, NoteNumber, TicketNo, Remarks, AmountPaid) EXEC (@q, @Dari, @Sampai) AT ' + QUOTENAME(@Server) + N';';
            EXEC sp_executesql @x, N'@q nvarchar(max), @Dari date, @Sampai date', @q, @Dari, @Sampai;
            UPDATE #item SET CompID = @Comp WHERE CompID IS NULL;
        END
        FETCH c INTO @Comp, @Server, @DB;
    END
    CLOSE c; DEALLOCATE c;

    IF @Bagian = 'CEK'
        SELECT CompID, AssociateID, CheckNo, Jumlah, Terakhir FROM #cek;
    ELSE
        SELECT CompID, VoucherDate, VoucherNo, VoucherItemID, AssociateID, CheckNo, CreatedBy, SupplierName, AssociateName, ItemType, OBNumber,
               PurchaseNumber, NoteNumber, TicketNo, Remarks, AmountPaid
        FROM #item;
END
