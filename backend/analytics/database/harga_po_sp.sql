-- Stored procedure harga PO per baris, dibuat di database Main. Dipakai tabel detail PR & PO, PO & PI, dan PO outstanding di laporan Outstanding.
-- @CompID (opsional, mis. 'YBS'): satu perusahaan saja; kosong = semua perusahaan aktif bertipe CLOUD di dbo.company.
-- @Mulai (opsional): PO bertanggal mulai tanggal ini; kosong = semua PO.
-- Hanya mengambil data mentah; pencocokan ke baris PR/PO dan perhitungan nilai dikerjakan di Python (laporan/harga_po.py).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.R_HARGA_PO 'YBS', '2026-01-01';
CREATE OR ALTER PROCEDURE dbo.R_HARGA_PO
    @CompID varchar(10) = NULL,
    @Mulai date = NULL
AS
BEGIN
    SET NOCOUNT ON;

    CREATE TABLE #hasil (PODetailID int, SourceID int, PONumber varchar(100), UnitCost money, LineTotal money, Currency varchar(20),
                         CompID varchar(10) NULL);

    DECLARE @b nvarchar(max) = N'
SELECT d.PODetailID, d.SourceID, o.PONumber, d.UnitCost, d.LineTotal, c.Currency
FROM {DB}.dbo.AP_PurchaseOrderDetails d
JOIN {DB}.dbo.AP_PurchaseOrders o ON o.POID = d.POID
LEFT JOIN {DB}.dbo.CO_Currency c ON c.CurrencyID = o.CurrencyID
WHERE o.PODate >= ?;';

    DECLARE @Comp varchar(10), @Server sysname, @DB sysname, @q nvarchar(max), @x nvarchar(max);
    DECLARE @Dari date = ISNULL(@Mulai, '19000101');
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
        SET @x = N'INSERT INTO #hasil (PODetailID, SourceID, PONumber, UnitCost, LineTotal, Currency) EXEC (@q, @Dari) AT ' + QUOTENAME(@Server) + N';';
        EXEC sp_executesql @x, N'@q nvarchar(max), @Dari date', @q, @Dari;
        UPDATE #hasil SET CompID = @Comp WHERE CompID IS NULL;
        FETCH c INTO @Comp, @Server, @DB;
    END
    CLOSE c; DEALLOCATE c;

    SELECT CompID, PODetailID, SourceID, PONumber, UnitCost, LineTotal, Currency FROM #hasil;
END
