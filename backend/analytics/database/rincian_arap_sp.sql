-- Stored procedure rincian satu dokumen untuk jendela rincian laporan Outstanding, Purchase Request, Purchase Orders, dan Purchase Invoice,
-- dibuat di database Main.
-- @CompID: perusahaan (mis. 'YBS'). @NoDok: nomor dokumen.
-- @Kode: kode sumber hutang/piutang di SH_ARAPCalculations (mis. 'PI', 'PN'), '#PO' untuk satu PO (asal PR tiap barisnya),
--        '#SUP' untuk semua PO terbuka satu supplier sekaligus (@NoDok = nama supplier persis seperti di ERP),
--        atau '#PR' untuk satu PR (barang beserta PO dan PI lanjutannya).
-- Hasil satu tabel, kolom Bagian membedakan isinya:
--   'info'  : keterangan tambahan dokumen (Nama = label, Ket = isi): lengkap untuk PI, Keterangan saja untuk sumber lain yang punya kolom Remarks
--   'item'  : baris barang PI atau PO (No = kode barang, Nama = nama barang, Qty, Harga, Nilai, Ket = catatan baris),
--             dengan asal dokumennya: NoPO, NoPR, TglPR, PembuatPR, serta KetPO (keterangan PO), KetPR (keterangan PR), PerluPR (keperluan PR),
--             dan NoPI (PI lanjutan baris PO/PR, dipisah koma)
--   'bayar' : PVR, PV, dan RV yang memuat dokumen ini (No, Tgl, Nama = PVR/PV/RV, Nilai, Status, Ket = keterangan voucher)
-- Rantai baris: PI (AP_PurchaseDetails.SourceID) -> PO (AP_PurchaseOrderDetails.SourceID) -> PR (AP_PRDetails).
-- Hanya MEMBACA database ERP. Jalankan sekali di database Main.
-- Cek: EXEC dbo.RINCIAN_ARAP 'YBS', 'PI', 'YBS/PI/HO/2611/083';  EXEC dbo.RINCIAN_ARAP 'YBS', '#PO', 'YBS/PO/HO/2611/3476';
--      EXEC dbo.RINCIAN_ARAP 'YBS', '#SUP', 'PT ANPA MAJU BERSAMA';  EXEC dbo.RINCIAN_ARAP 'YBS', '#PR', 'YBS/PR/HO/2611/010';
CREATE OR ALTER PROCEDURE dbo.RINCIAN_ARAP
    @CompID varchar(10),
    @Kode varchar(10),
    @NoDok varchar(200)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @b nvarchar(max) = N'USE {DB};
SET NOCOUNT ON;
DECLARE @Kode varchar(10) = ?, @NoDok varchar(200) = ?;
DECLARE @tabel sysname, @kunci nvarchar(200), @nomor nvarchar(200), @sql nvarchar(max), @ID int;

CREATE TABLE #R (Bagian varchar(10), Urut int, No nvarchar(200), Tgl date, Nama nvarchar(300), Qty decimal(18, 4), Harga money, Nilai money,
                 Status nvarchar(50), Ket nvarchar(400), NoPO nvarchar(200), NoPR nvarchar(200), TglPR date, PembuatPR nvarchar(100),
                 KetPO nvarchar(400), KetPR nvarchar(400), PerluPR nvarchar(400), NoPI nvarchar(400));

IF @Kode = ''#PR''
BEGIN
    INSERT #R (Bagian, Urut, Nama, Ket)
    SELECT ''info'', n.Urut, n.Label, n.Isi
    FROM AP_PR pr
    CROSS APPLY (VALUES (1, ''Tanggal PR'', CONVERT(varchar(10), pr.Date, 103)), (2, ''Dibuat oleh'', pr.CreatedBy),
                        (3, ''Disetujui oleh'', pr.ApprovedBy), (4, ''Dibutuhkan'', CONVERT(varchar(10), pr.RequiredDate, 103)),
                        (5, ''Keperluan'', LEFT(pr.Purpose, 400)), (6, ''Keterangan'', LEFT(pr.Remarks, 400))) n(Urut, Label, Isi)
    WHERE pr.PRNumber = @NoDok AND NULLIF(LTRIM(n.Isi), '''') IS NOT NULL;

    INSERT #R (Bagian, Urut, No, Nama, Qty, Ket, NoPR, PerluPR, NoPO, NoPI)
    SELECT ''item'', pd.DisplayIndex, it.ItemCode, COALESCE(NULLIF(LTRIM(pd.ItemDescription), ''''), it.ItemName), pd.Quantity, LEFT(pd.Remarks, 400),
           pr.PRNumber, pd.Purpose,
           STUFF((SELECT DISTINCT '', '' + o.PONumber FROM AP_PurchaseOrderDetails od JOIN AP_PurchaseOrders o ON o.POID = od.POID
                  WHERE od.SourceID = pd.PRDetailID AND o.Void = 0 FOR XML PATH('''')), 1, 2, ''''),
           STUFF((SELECT DISTINCT '', '' + p.PurchaseNumber FROM AP_PurchaseOrderDetails od JOIN AP_PurchaseOrders o ON o.POID = od.POID
                  JOIN AP_PurchaseDetails d ON d.SourceID = od.PODetailID AND d.SourceType = ''PO'' JOIN AP_Purchases p ON p.PurchaseID = d.PurchaseID
                  WHERE od.SourceID = pd.PRDetailID AND o.Void = 0 AND p.Void = 0 FOR XML PATH('''')), 1, 2, '''')
    FROM AP_PR pr JOIN AP_PRDetails pd ON pd.PRID = pr.PRID
    LEFT JOIN IC_Items it ON it.ItemID = pd.ItemID
    WHERE pr.PRNumber = @NoDok;
    SELECT Bagian, Urut, No, Tgl, Nama, Qty, Harga, Nilai, Status, Ket, NoPO, NoPR, TglPR, PembuatPR, KetPO, KetPR, PerluPR, NoPI FROM #R;
    RETURN;
END

IF @Kode IN (''#PO'', ''#SUP'')
BEGIN
    IF @Kode = ''#PO''
        INSERT #R (Bagian, Urut, Nama, Ket)
        SELECT ''info'', n.Urut, n.Label, n.Isi
        FROM AP_PurchaseOrders o LEFT JOIN AP_Suppliers sp ON sp.SupplierID = o.SupplierID
        CROSS APPLY (VALUES (1, ''Tanggal PO'', CONVERT(varchar(10), o.PODate, 103)), (2, ''Supplier'', sp.SupplierName),
                            (3, ''Dibuat oleh'', o.CreatedBy), (4, ''Disetujui oleh'', o.ApprovedBy),
                            (5, ''Perkiraan kirim'', CONVERT(varchar(10), o.ExpectedDeliveryDate, 103)), (6, ''Keterangan'', LEFT(o.Remarks, 400))) n(Urut, Label, Isi)
        WHERE o.PONumber = @NoDok AND NULLIF(LTRIM(n.Isi), '''') IS NOT NULL;

    INSERT #R
    SELECT ''item'', od.DisplayIndex, it.ItemCode, NULL, it.ItemName, od.QtyOrdered, od.UnitCost, od.LineTotal, NULL, LEFT(CAST(od.Remarks AS nvarchar(max)), 400),
           o.PONumber, pr.PRNumber, CAST(pr.Date AS date), pr.CreatedBy,
           NULLIF(LTRIM(LEFT(o.Remarks, 400)), ''''), COALESCE(NULLIF(LTRIM(pd.Remarks), ''''), NULLIF(LTRIM(LEFT(pr.Remarks, 400)), '''')),
           COALESCE(NULLIF(LTRIM(pd.Purpose), ''''), NULLIF(LTRIM(pr.Purpose), '''')),
           STUFF((SELECT DISTINCT '', '' + p.PurchaseNumber FROM AP_PurchaseDetails d JOIN AP_Purchases p ON p.PurchaseID = d.PurchaseID
                  WHERE d.SourceID = od.PODetailID AND d.SourceType = ''PO'' AND p.Void = 0 FOR XML PATH('''')), 1, 2, '''')
    FROM AP_PurchaseOrders o JOIN AP_PurchaseOrderDetails od ON od.POID = o.POID
    LEFT JOIN IC_Items it ON it.ItemID = od.ItemID
    LEFT JOIN AP_PRDetails pd ON pd.PRDetailID = od.SourceID
    LEFT JOIN AP_PR pr ON pr.PRID = pd.PRID
    LEFT JOIN AP_Suppliers sp ON sp.SupplierID = o.SupplierID
    WHERE (@Kode = ''#PO'' AND o.PONumber = @NoDok)
       OR (@Kode = ''#SUP'' AND sp.SupplierName = @NoDok AND o.Void = 0 AND ISNULL(o.Closed, 0) = 0);
    SELECT Bagian, Urut, No, Tgl, Nama, Qty, Harga, Nilai, Status, Ket, NoPO, NoPR, TglPR, PembuatPR, KetPO, KetPR, PerluPR, NoPI FROM #R;
    RETURN;
END

SELECT TOP 1 @tabel = SourceTable, @kunci = KeyField, @nomor = NumberField
FROM SH_ARAPCalculations WHERE CompCode = @Kode AND ARAPCalc = 1;
IF @tabel IS NULL RETURN;

SET @sql = N''SELECT TOP 1 @ID = '' + @kunci + N'' FROM '' + @tabel + N'' M WHERE '' + @nomor + N'' = @NoDok'';
EXEC sp_executesql @sql, N''@NoDok varchar(200), @ID int OUTPUT'', @NoDok, @ID OUTPUT;
IF @ID IS NULL RETURN;

-- Keterangan dokumen untuk sumber selain PI (nota, tiket, dll), kalau tabelnya punya kolom Remarks
IF @tabel <> ''AP_Purchases'' AND COL_LENGTH(@tabel, ''Remarks'') IS NOT NULL
BEGIN
    SET @sql = N''INSERT #R (Bagian, Urut, Nama, Ket) SELECT ''''info'''', 6, ''''Keterangan'''', LEFT(CAST(M.Remarks AS nvarchar(max)), 400) FROM ''
             + @tabel + N'' M WHERE '' + @kunci + N'' = @ID AND NULLIF(LTRIM(CAST(M.Remarks AS nvarchar(max))), '''''''') IS NOT NULL'';
    EXEC sp_executesql @sql, N''@ID int'', @ID;
END

-- PVR yang sudah dibuatkan PV (aturan ERP, sama dengan SP Outstanding)
SELECT DISTINCT SourceVoucherID AS ID INTO #PVRSelesai FROM FI_ARAP WHERE (VoidCheck = 1 OR Void = 0) AND SourceVoucherID > 0 AND IsAR = 0
UNION SELECT PVRVoucherID FROM FI_ARAPSources;

INSERT #R (Bagian, Urut, No, Tgl, Nama, Nilai, Status, Ket)
SELECT ''bayar'', 1, r.VoucherNo, CAST(r.VoucherDate AS date), ''PVR'', i.AmountPaid + i.AmountDebit - i.AmountCredit,
       CASE WHEN r.Void = 1 THEN ''Void'' WHEN r.VoucherID IN (SELECT ID FROM #PVRSelesai) THEN ''Sudah jadi PV''
            WHEN ISNULL(r.Approved, 0) = 0 THEN ''Belum approve'' ELSE ''Sudah approve'' END,
       LEFT(r.Remarks, 400)
FROM FI_APRequestItems i JOIN FI_APRequest r ON r.VoucherID = i.VoucherID
WHERE i.ItemType = @Kode AND i.ItemID = @ID;

INSERT #R (Bagian, Urut, No, Tgl, Nama, Nilai, Status, Ket)
SELECT ''bayar'', 2, v.VoucherNo, CAST(v.VoucherDate AS date), CASE WHEN v.IsAR = 1 THEN ''RV'' ELSE ''PV'' END,
       i.AmountPaid + i.AmountDebit - i.AmountCredit,
       CASE WHEN v.Void = 1 AND ISNULL(v.VoidCheck, 0) = 0 THEN ''Void''
            WHEN v.VoucherDate >= DATEADD(day, 1, CAST(GETDATE() AS date)) THEN ''Belum jatuh tempo'' ELSE ''Sudah dibayar'' END,
       LEFT(v.Remarks, 400)
FROM FI_ARAPItems i JOIN FI_ARAP v ON v.VoucherID = i.VoucherID
WHERE i.ItemType = @Kode AND i.ItemID = @ID;

IF @tabel = ''AP_Purchases''
BEGIN
    INSERT #R (Bagian, Urut, Nama, Ket)
    SELECT ''info'', n.Urut, n.Label, n.Isi
    FROM AP_Purchases p
    CROSS APPLY (VALUES (1, ''No. PO'', LEFT(p.PONumbers, 400)), (2, ''No. referensi'', p.ReferenceNo),
                        (3, ''Jatuh tempo'', CONVERT(varchar(10), p.DueDate, 103)), (4, ''No. faktur pajak'', p.FPNo),
                        (5, ''Dibuat oleh'', p.CreatedBy), (6, ''Keterangan'', LEFT(p.Remarks, 400))) n(Urut, Label, Isi)
    WHERE p.PurchaseID = @ID AND NULLIF(LTRIM(n.Isi), '''') IS NOT NULL;

    INSERT #R
    SELECT ''item'', d.DisplayIndex, it.ItemCode, NULL, it.ItemName, d.Quantity, d.Cost, d.LineTotal, NULL, LEFT(d.Remarks, 400),
           o.PONumber, pr.PRNumber, CAST(pr.Date AS date), pr.CreatedBy,
           NULLIF(LTRIM(LEFT(o.Remarks, 400)), ''''), COALESCE(NULLIF(LTRIM(pd.Remarks), ''''), NULLIF(LTRIM(LEFT(pr.Remarks, 400)), '''')),
           COALESCE(NULLIF(LTRIM(pd.Purpose), ''''), NULLIF(LTRIM(pr.Purpose), '''')), NULL
    FROM AP_PurchaseDetails d LEFT JOIN IC_Items it ON it.ItemID = d.ItemID
    LEFT JOIN AP_PurchaseOrderDetails od ON od.PODetailID = d.SourceID AND d.SourceType = ''PO''
    LEFT JOIN AP_PurchaseOrders o ON o.POID = od.POID
    LEFT JOIN AP_PRDetails pd ON pd.PRDetailID = od.SourceID
    LEFT JOIN AP_PR pr ON pr.PRID = pd.PRID
    WHERE d.PurchaseID = @ID;
END

SELECT Bagian, Urut, No, Tgl, Nama, Qty, Harga, Nilai, Status, Ket, NoPO, NoPR, TglPR, PembuatPR, KetPO, KetPR, PerluPR, NoPI FROM #R;
';

    DECLARE @Server sysname, @DB sysname, @q nvarchar(max);
    SELECT TOP 1 @Server = RTRIM(CompAddr), @DB = RTRIM(CompDataBase)
    FROM dbo.company
    WHERE RTRIM(CompType) = 'CLOUD' AND Status = 1 AND RTRIM(CompID) = RTRIM(@CompID);
    IF @Server IS NULL OR @DB IS NULL
        THROW 50002, N'Perusahaan tidak ditemukan atau belum punya server dan database.', 1;

    SET @q = REPLACE(@b, '{DB}', QUOTENAME(@DB));
    DECLARE @x nvarchar(max) = N'EXEC (@q, @Kode, @NoDok) AT ' + QUOTENAME(@Server) + N';';
    EXEC sp_executesql @x, N'@q nvarchar(max), @Kode varchar(10), @NoDok varchar(200)', @q, @Kode, @NoDok;
END
GO
GRANT EXECUTE ON dbo.RINCIAN_ARAP TO pythonReport;
