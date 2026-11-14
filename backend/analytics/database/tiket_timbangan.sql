/* Tiket Timbangan Penjualan (tiket produk keluar): kolom sama dengan ekspor Excel Ascend.
   Nama Pengangkutan diambil dari kolom Contractor, karena isian "Nama Pengangkutan" di layar timbangan Ascend tersimpan di sana.
   Hanya tiket penjualan (TicketType Produk) yang sudah selesai timbang.
   Tiket split: Ascend mem-void tiket induk dan membuat pecahan (-1, -2, ...). Di sini yang dipakai tiket induknya,
   pecahannya tidak diikutkan, dan kolom Split diisi "Ya". Tiket void biasa (bukan karena split) tetap tidak diikutkan.
   Jalankan di database Main. Isi @Company (YBS, SUN, SJN, ORI, RCM) dan tanggal; database Ascend-nya dicari di dbo.Company
   (CompType CLOUD) dan dibaca lewat linked server. */
DECLARE @Company nvarchar(10) = 'YBS', @Dari date = '2026-11-13', @Sampai date = '2026-11-13';

DECLARE @P nvarchar(500);
SELECT TOP 1 @P = QUOTENAME(RTRIM(LTRIM(CompAddr))) + '.' + QUOTENAME(RTRIM(LTRIM(CompDataBase))) + '.dbo.'
FROM dbo.Company WHERE RTRIM(LTRIM(CompID)) = @Company AND RTRIM(LTRIM(CompType)) = 'CLOUD';
IF @P IS NULL THROW 50001, 'Company tidak ditemukan pada dbo.Company.', 1;

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
