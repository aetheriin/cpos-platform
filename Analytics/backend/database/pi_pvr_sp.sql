-- Stored procedure laporan PI & PVR, dibuat di database Main.
-- @CompID (opsional, mis. 'YBS'): satu perusahaan saja; kosong = semua perusahaan aktif bertipe CLOUD di dbo.company.
-- @Mulai, @Akhir: tanggal PI (PurchaseDate), @Akhir ikut dihitung.
-- Satu baris per baris PI x PVR x PV yang terkait, data mentah saja. PVR dan PV dicocokkan lewat ID item (FI_APRequestItems / FI_ARAPItems
-- bertipe PI atau PO), bukan teks. Kurs, status void PVR, penggabungan nomor, status, dan umur dikerjakan di Python (laporan/pi_pvr/sumber.py).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.PI_PVR 'YBS', '2026-10-01', '2026-10-31';
CREATE OR ALTER PROCEDURE dbo.PI_PVR
    @CompID varchar(10) = NULL,
    @Mulai date,
    @Akhir date
AS
BEGIN
    SET NOCOUNT ON;

    CREATE TABLE #hasil (DetailID int, PONumber nvarchar(400), SupplierCode nvarchar(100), SupplierName nvarchar(300), PurchaseNumber nvarchar(100),
        PIDate datetime, PICreateDate datetime, PICreateBy nvarchar(100), QtyPI decimal(28, 6), ItemCode nvarchar(100), ItemName nvarchar(400),
        LineTotal decimal(28, 6), ExchangeRate decimal(28, 6),
        PVRNumber nvarchar(100), PVRDate datetime, PVRCreateDate datetime, PVRCreateBy nvarchar(100), PVRVoid bit, PVRSource nvarchar(100),
        PVNumber nvarchar(100), PVDate datetime, PVCreateBy nvarchar(100),
        CompID varchar(10) NULL);

    DECLARE @b nvarchar(max) = N'
SELECT pid.PurchaseDetailID, pi.PONumbers, s.SupplierCode, s.SupplierName, pi.PurchaseNumber,
       pi.PurchaseDate, pi.CreateDate, pi.CreatedBy, pid.Quantity, it.ItemCode, it.ItemName,
       pid.LineTotal, pi.ExchangeRate,
       pvr.VoucherNo, pvr.VoucherDate, pvr.CreateDate, pvr.CreatedBy, pvr.Void, pvr.PVRSource,
       pv.VoucherNo, pv.VoucherDate, pv.CreatedBy
FROM {DB}.dbo.AP_Purchases pi
JOIN {DB}.dbo.AP_PurchaseDetails pid ON pid.PurchaseID = pi.PurchaseID
LEFT JOIN {DB}.dbo.IC_Items it ON it.ItemID = pid.ItemID
LEFT JOIN {DB}.dbo.AP_Suppliers s ON s.SupplierID = pi.SupplierID
LEFT JOIN (
    SELECT DISTINCT i.ItemID, r.VoucherNo, r.VoucherDate, r.CreateDate, r.CreatedBy, r.Void, r.PVRSource
    FROM {DB}.dbo.FI_APRequestItems i
    JOIN {DB}.dbo.FI_APRequest r ON r.VoucherID = i.VoucherID
    WHERE i.ItemType IN (''PI'', ''PO'')
) pvr ON pvr.ItemID = pi.PurchaseID
LEFT JOIN (
    SELECT DISTINCT i.ItemID, v.VoucherNo, v.VoucherDate, v.CreatedBy
    FROM {DB}.dbo.FI_ARAPItems i
    JOIN {DB}.dbo.FI_ARAP v ON v.VoucherID = i.VoucherID
    WHERE i.ItemType IN (''PI'', ''PO'') AND v.IsAR = 0 AND ISNULL(v.Void, 0) = 0
) pv ON pv.ItemID = pi.PurchaseID
WHERE pi.PurchaseDate >= ? AND pi.PurchaseDate < ?
  AND ISNULL(pi.Void, 0) = 0
  AND pi.PurchaseNumber LIKE ''%/PI/%'';';

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
        SET @x = N'INSERT INTO #hasil (DetailID, PONumber, SupplierCode, SupplierName, PurchaseNumber, PIDate, PICreateDate, PICreateBy, QtyPI, ItemCode, ItemName,
                   LineTotal, ExchangeRate, PVRNumber, PVRDate, PVRCreateDate, PVRCreateBy, PVRVoid, PVRSource, PVNumber, PVDate, PVCreateBy)
                   EXEC (@q, @Mulai, @Sampai) AT ' + QUOTENAME(@Server) + N';';
        EXEC sp_executesql @x, N'@q nvarchar(max), @Mulai date, @Sampai date', @q, @Mulai, @Sampai;
        UPDATE #hasil SET CompID = @Comp WHERE CompID IS NULL;
        FETCH c INTO @Comp, @Server, @DB;
    END
    CLOSE c; DEALLOCATE c;

    SELECT CompID, DetailID, PONumber, SupplierCode, SupplierName, PurchaseNumber, PIDate, PICreateDate, PICreateBy, QtyPI, ItemCode, ItemName,
           LineTotal, ExchangeRate, PVRNumber, PVRDate, PVRCreateDate, PVRCreateBy, PVRVoid, PVRSource, PVNumber, PVDate, PVCreateBy
    FROM #hasil;
END
