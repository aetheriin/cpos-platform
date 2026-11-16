-- Stored procedure laporan Tiket Timbangan Penjualan, dibuat di database Main.
-- Tiket penjualan (produk keluar) yang sudah selesai timbang, kolom sama dengan ekspor Excel Ascend.
--   @CompID         perusahaan, mis. 'YBS' (server dan database Ascend dibaca dari dbo.company, CompType CLOUD)
--   @Mulai, @Akhir  tanggal tiket, @Akhir ikut dihitung (harian: sama; mingguan: Senin..Minggu; bulanan: tgl 1..akhir bulan)
-- Nama Pengangkutan diambil dari Contractor (isian "Nama Pengangkutan" di layar timbangan Ascend tersimpan di sana).
-- Tiket split: Ascend mem-void tiket induk dan membuat pecahan (-1, -2, ...). Yang dipakai pecahannya, karena
-- Nomor DO dan kontrak hanya ada di pecahan; kolom Split pecahan diisi "Ya". Induk dan tiket void lain tidak diikutkan.
-- Query dijalankan di server Ascend (EXEC ... AT), bukan ditarik lewat server tertaut: 93 hari YBS turun dari 23 detik ke 3 detik.
-- Hanya MEMBACA database Ascend; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main (utuh, F5), lalu cek: EXEC dbo.TIKET_PENJUALAN 'YBS', '2026-11-01', '2026-11-14';
CREATE OR ALTER PROCEDURE dbo.TIKET_PENJUALAN
    @CompID varchar(10),
    @Mulai date,
    @Akhir date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @Server sysname, @DB sysname;
    SELECT TOP 1 @Server = RTRIM(CompAddr), @DB = RTRIM(CompDataBase)
      FROM dbo.company
     WHERE RTRIM(CompID) = RTRIM(@CompID) AND RTRIM(CompType) = 'CLOUD' AND Status = 1
       AND NULLIF(RTRIM(CompAddr), '') IS NOT NULL AND NULLIF(RTRIM(CompDataBase), '') IS NOT NULL;
    IF @Server IS NULL
    BEGIN
        RAISERROR('Perusahaan %s tidak ada di dbo.company (CLOUD, aktif).', 16, 1, @CompID);
        RETURN;
    END;

    DECLARE @q nvarchar(max) = N'USE {DB};
DECLARE @Dari date = ?, @Sampai date = ?;
/* Induk split ikut diambil hanya untuk menandai pecahannya */
SELECT TicketNo, Splitted INTO #T FROM PALM_Tickets
 WHERE TicketType = ''Produk'' AND [Date] >= @Dari AND [Date] < DATEADD(day, 1, @Sampai);

SELECT
    CAST(t.[Date] AS date)                                   AS Tanggal,
    CONVERT(varchar(8), t.DateTimeIn, 108)                   AS [Jam Masuk],
    CONVERT(varchar(8), t.DateTimeOut, 108)                  AS [Jam Keluar],
    ISNULL(cu.CustomerName, '''')                             AS [Nama Pembeli],
    NULLIF(LTRIM(RTRIM(t.SPDO)), '''')                       AS [Nomor DO],
    t.ProductName                                            AS Produk,
    LTRIM(RTRIM(ISNULL(t.Contractor, '''')))                AS [Nama Pengangkutan],
    t.TicketNo                                               AS [No. Tiket],
    t.VehicleNo                                              AS [No. Kendaraan],
    t.NamaSupir                                              AS [Nama Supir],
    NULLIF(LTRIM(RTRIM(t.SPDO)), '''')                       AS [Nomor Kontrak],
    t.Bruto, t.Tara,
    ISNULL(t.Deduction, 0)                                   AS Potongan,
    t.Netto,
    ISNULL(t.FirstWeight, 0)                                 AS [Netto Sumber],
    ISNULL(t.FFA, 0)                                         AS FFA,
    ISNULL(t.PctAir, 0)                                      AS [Kadar Air],
    ISNULL(t.PctKotoran, 0)                                  AS [Kadar Kotoran],
    ISNULL(t.Dobi, 0)                                        AS Dobi,
    CASE WHEN ISNULL(t.ParentTicketID, 0) <> 0
           OR EXISTS (SELECT 1 FROM #T p     -- di cloud ParentTicketID sering 0: kenali pecahan dari nomornya (induk + "-1", "-2")
                      WHERE p.Splitted = 1 AND t.TicketNo LIKE ''%-[0-9]%''
                        AND p.TicketNo = LEFT(t.TicketNo, LEN(t.TicketNo) - CHARINDEX(''-'', REVERSE(t.TicketNo))))
         THEN ''Ya'' ELSE '''' END                           AS Split
FROM PALM_Tickets t
LEFT JOIN AR_Customers cu ON cu.CustomerID = t.AssociateID
WHERE t.TicketType = ''Produk''                               -- hanya penjualan
  AND ISNULL(t.Void, 0) = 0                                   -- induk split dan tiket void lain tidak diikutkan
  AND t.Step >= 2 AND t.DateTimeOut IS NOT NULL               -- hanya tiket yang sudah selesai timbang, sama dengan ekspor Ascend
  AND t.[Date] >= @Dari AND t.[Date] < DATEADD(day, 1, @Sampai)
ORDER BY t.[Date], t.TicketNo;';

    SET @q = REPLACE(@q, N'{DB}', QUOTENAME(@DB));
    DECLARE @x nvarchar(max) = N'EXEC (@q, @Mulai, @Akhir) AT ' + QUOTENAME(@Server) + N';';
    EXEC sp_executesql @x, N'@q nvarchar(max), @Mulai date, @Akhir date', @q, @Mulai, @Akhir;
END;
GO
GRANT EXECUTE ON dbo.TIKET_PENJUALAN TO pythonReport;
