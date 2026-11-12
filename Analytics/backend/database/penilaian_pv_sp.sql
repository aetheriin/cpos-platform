-- Stored procedure laporan Penilaian PV, dibuat di database Main.
-- @CompID (opsional, mis. 'YBS'): satu perusahaan saja; kosong = semua perusahaan aktif bertipe CLOUD di dbo.company.
-- @Mulai, @Akhir: tanggal PV (VoucherDate), @Akhir ikut dihitung.
-- Satu baris per item PV hutang (IsAR = 0, tidak void), dengan kolom Bagian:
--   'ITEM' = item dokumen (FI_ARAPItems), 'LAIN' = item lain-lain (FI_ARAPExtraItems), 'PPH' = potongan PPh di header PV.
-- Urut = ID baris item (VoucherItemID / VoucherExtraItemID); item pertama per PV dipilih di Python: ITEM, lalu LAIN, lalu PPH, lalu Urut.
-- Data mentah saja: nomor dokumen (ItemRef), label dan tanda potongan PPh, nama supplier, Check Number dari histori, kategori, dan bobot
-- dikerjakan di Python (laporan/penilaian_pv/sumber.py).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.PENILAIAN_PV 'YBS', '2026-10-01', '2026-10-31';
CREATE OR ALTER PROCEDURE dbo.PENILAIAN_PV
    @CompID varchar(10) = NULL,
    @Mulai date,
    @Akhir date
AS
BEGIN
    SET NOCOUNT ON;

    CREATE TABLE #hasil (VoucherDate datetime, VoucherNo nvarchar(100), CreatedBy nvarchar(100), CheckNo nvarchar(200),
        SupplierName nvarchar(300), AssociateName nvarchar(300), AnonymName nvarchar(300),
        Bagian varchar(10), Urut int, ItemType varchar(10), PurchaseNumber nvarchar(100), NoteNumber nvarchar(100), TicketNo nvarchar(100),
        Keterangan nvarchar(1000), Jumlah decimal(28, 6),
        CompID varchar(10) NULL);

    DECLARE @b nvarchar(max) = N'
SELECT v.VoucherDate, v.VoucherNo, v.CreatedBy, v.CheckNo, s.SupplierName, v.AssociateName, v.AnonymName,
       d.Bagian, d.Urut, d.ItemType, d.PurchaseNumber, d.NoteNumber, d.TicketNo, d.Keterangan, d.Jumlah
FROM {DB}.dbo.FI_ARAP v
JOIN (
    SELECT i.VoucherID, ''ITEM'' AS Bagian, i.VoucherItemID AS Urut, i.ItemType, p.PurchaseNumber, n.Number AS NoteNumber, t.TicketNo,
           i.Remarks AS Keterangan, i.AmountPaid AS Jumlah
    FROM {DB}.dbo.FI_ARAPItems i
    LEFT JOIN {DB}.dbo.AP_Purchases p ON p.PurchaseID = i.ItemID AND i.ItemType IN (''PI'', ''PO'')
    LEFT JOIN {DB}.dbo.FI_ARAPNotes n ON n.ARAPNoteID = i.ItemID AND i.ItemType IN (''PN'', ''PD'', ''PUK'')
    LEFT JOIN {DB}.dbo.PALM_Tickets t ON t.TicketID = i.ItemID AND i.ItemType IN (''TV'', ''BT'', ''BTP'')
    UNION ALL
    SELECT e.VoucherID, ''LAIN'', e.VoucherExtraItemID, NULL, NULL, NULL, NULL, e.Description, e.Amount
    FROM {DB}.dbo.FI_ARAPExtraItems e
    UNION ALL
    SELECT x.VoucherID, ''PPH'', 0, NULL, NULL, NULL, NULL, pt.PPHTypeDescription, x.DeductedPPh
    FROM {DB}.dbo.FI_ARAP x
    LEFT JOIN {DB}.dbo.FI_PPhTypes pt ON pt.PPHTypeID = x.PPhTypeID
    WHERE ISNULL(x.DeductedPPh, 0) <> 0
) d ON d.VoucherID = v.VoucherID
LEFT JOIN {DB}.dbo.AP_Suppliers s ON s.SupplierID = v.AssociateID
WHERE v.IsAR = 0
  AND ISNULL(v.Void, 0) = 0
  AND v.VoucherDate >= ? AND v.VoucherDate < ?;';

    DECLARE @Comp varchar(10), @Server sysname, @DB sysname, @q nvarchar(max), @x nvarchar(max);
    DECLARE @Sampai date = DATEADD(day, 1, @Akhir);
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
        SET @q = REPLACE(@b, '{DB}', QUOTENAME(@DB));
        SET @x = N'INSERT INTO #hasil (VoucherDate, VoucherNo, CreatedBy, CheckNo, SupplierName, AssociateName, AnonymName,
                   Bagian, Urut, ItemType, PurchaseNumber, NoteNumber, TicketNo, Keterangan, Jumlah)
                   EXEC (@q, @Mulai, @Sampai) AT ' + QUOTENAME(@Server) + N';';
        EXEC sp_executesql @x, N'@q nvarchar(max), @Mulai date, @Sampai date', @q, @Mulai, @Sampai;
        UPDATE #hasil SET CompID = @Comp WHERE CompID IS NULL;
        FETCH c INTO @Comp, @Server, @DB;
    END
    CLOSE c; DEALLOCATE c;

    SELECT CompID, VoucherDate, VoucherNo, CreatedBy, CheckNo, SupplierName, AssociateName, AnonymName,
           Bagian, Urut, ItemType, PurchaseNumber, NoteNumber, TicketNo, Keterangan, Jumlah
    FROM #hasil;
END
