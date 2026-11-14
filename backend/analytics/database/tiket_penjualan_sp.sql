-- Stored procedure laporan Tiket Timbangan Penjualan, dibuat di database Main.
-- Tiket penjualan (produk keluar) yang sudah selesai timbang, kolom sama dengan ekspor Excel Ascend.
--   @CompID         perusahaan, mis. 'YBS' (server dan database Ascend dibaca dari dbo.company, CompType CLOUD)
--   @Mulai, @Akhir  tanggal tiket, @Akhir ikut dihitung (harian: sama; mingguan: Senin..Minggu; bulanan: tgl 1..akhir bulan)
-- Nama Pengangkutan diambil dari Contractor (isian "Nama Pengangkutan" di layar timbangan Ascend tersimpan di sana).
-- Tiket split: Ascend mem-void tiket induk dan membuat pecahan (-1, -2, ...). Yang dipakai tiket induknya,
-- pecahannya tidak diikutkan, dan kolom Split diisi "Ya". Tiket void biasa tetap tidak diikutkan.
-- Hanya MEMBACA database Ascend; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.TIKET_PENJUALAN 'YBS', '2026-11-01', '2026-11-14';
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
    DECLARE @P nvarchar(500) = QUOTENAME(@Server) + '.' + QUOTENAME(@DB) + '.dbo.';
    DECLARE @Dari date = @Mulai, @Sampai date = @Akhir;

    DECLARE @s nvarchar(max) = N'
    /* Tiket penjualan diambil sekali; induk split dan pecahan ditentukan dari data yang sama */
    SELECT t.*
      INTO #T
      FROM {P}PALM_Tickets t
     WHERE t.TicketType = ''Produk'' AND t.[Date] >= @Dari AND t.[Date] < DATEADD(day, 1, @Sampai);

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
        CASE WHEN t.Splitted = 1 THEN ''Ya'' ELSE '''' END        AS Split
    FROM #T t
    LEFT JOIN {P}AR_Customers cu ON cu.CustomerID = t.AssociateID
    WHERE t.TicketType = ''Produk''                           -- hanya penjualan
      AND (ISNULL(t.Void, 0) = 0 OR t.Splitted = 1)             -- induk split tetap dipakai walau di-void Ascend
      AND ISNULL(t.ParentTicketID, 0) = 0                       -- pecahan split tidak diikutkan
      AND (NOT (t.TicketNo LIKE ''%-[0-9]'' OR t.TicketNo LIKE ''%-[0-9][0-9]'')
           OR NOT EXISTS (SELECT 1 FROM #T p     -- di cloud ParentTicketID sering 0: kenali pecahan dari nomornya (induk + "-1", "-2")
                         WHERE p.Splitted = 1
                           AND p.TicketNo = LEFT(t.TicketNo, LEN(t.TicketNo) - CHARINDEX(''-'', REVERSE(t.TicketNo)))))
      AND t.Step >= 2 AND t.DateTimeOut IS NOT NULL          -- hanya tiket yang sudah selesai timbang, sama dengan ekspor Ascend
      AND t.[Date] >= @Dari AND t.[Date] < DATEADD(day, 1, @Sampai)
    ORDER BY t.[Date], t.TicketNo;';

    SET @s = REPLACE(@s, N'{P}', @P);
    EXEC sp_executesql @s, N'@Dari date, @Sampai date', @Dari = @Dari, @Sampai = @Sampai;
END;
GO
GRANT EXECUTE ON dbo.TIKET_PENJUALAN TO pythonReport;
