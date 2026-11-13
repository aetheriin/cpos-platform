/* Tiket Timbangan: kolom sama dengan ekspor Excel Ascend, ditambah Nama Pengangkutan yang dilengkapi.
   Nama Pengangkutan diambil berurutan, yang pertama terisi dipakai:
     1. Contractor di tiket (sama dengan ekspor Ascend)
     2. Transportir ongkos angkut di tiket (ShipperID)
     3. Transportir di DO (DOShipperSupplierID)
     4. Transportir di kontrak (ShipperSupplierID, lalu ShipperSupplierID2)
     5. Daftar transportir DO (PALM_DOTransport); kalau DO punya beberapa transportir, semuanya ditulis dipisah " / "
   Tiket TBS tidak punya DO atau kontrak; isi Contractor-nya hanya "TBS LUAR" / "TBS INTI", jadi pengangkutnya ditulis kosong.
   Nomor DO dan Nomor Kontrak hanya untuk tiket produk keluar, sama dengan ekspor Ascend. Hanya tiket yang sudah selesai timbang.
   Jalankan di database Main. Isi @Company (YBS, SUN, SJN, ORI, RCM) dan tanggal; database Ascend-nya dicari di dbo.Company
   (CompType CLOUD) dan dibaca lewat linked server, sama dengan prosedur laporan TBS. */
DECLARE @Company nvarchar(10) = 'YBS', @Dari date = '2026-11-13', @Sampai date = '2026-11-13';

DECLARE @P nvarchar(500);
SELECT TOP 1 @P = QUOTENAME(RTRIM(LTRIM(CompAddr))) + '.' + QUOTENAME(RTRIM(LTRIM(CompDataBase))) + '.dbo.'
FROM dbo.Company WHERE RTRIM(LTRIM(CompID)) = @Company AND RTRIM(LTRIM(CompType)) = 'CLOUD';
IF @P IS NULL THROW 50001, 'Company tidak ditemukan pada dbo.Company.', 1;

DECLARE @s nvarchar(max) = N'
SELECT
    CAST(t.[Date] AS date)                                   AS Tanggal,
    CONVERT(varchar(8), t.DateTimeIn, 108)                   AS [Jam Masuk],
    CONVERT(varchar(8), t.DateTimeOut, 108)                  AS [Jam Keluar],
    COALESCE(cu.CustomerName, su.SupplierName, '''')          AS [Nama Rekanan],
    CASE WHEN t.TicketType = ''Produk'' THEN NULLIF(LTRIM(RTRIM(t.SPDO)), '''') END AS [Nomor DO],
    t.ProductName                                            AS Produk,
    CASE
        WHEN LTRIM(RTRIM(ISNULL(t.Contractor, ''''))) NOT IN ('''', ''TBS LUAR'', ''TBS INTI'') THEN LTRIM(RTRIM(t.Contractor))
        ELSE COALESCE(s1.SupplierName, s2.SupplierName, s3.SupplierName, s4.SupplierName, dt.Nama)
    END                                                      AS [Nama Pengangkutan],
    CASE
        WHEN LTRIM(RTRIM(ISNULL(t.Contractor, ''''))) NOT IN ('''', ''TBS LUAR'', ''TBS INTI'') THEN ''Tiket''
        WHEN s1.SupplierName IS NOT NULL THEN ''Ongkos angkut tiket''
        WHEN s2.SupplierName IS NOT NULL THEN ''DO''
        WHEN s3.SupplierName IS NOT NULL OR s4.SupplierName IS NOT NULL THEN ''Kontrak''
        WHEN dt.Nama IS NOT NULL THEN CASE WHEN dt.Nama LIKE ''% / %'' THEN ''Daftar transportir DO (lebih dari satu)'' ELSE ''Daftar transportir DO'' END
        ELSE ''Kosong''
    END                                                      AS [Sumber Pengangkutan],
    t.TicketNo                                               AS [No. Tiket],
    t.VehicleNo                                              AS [No. Kendaraan],
    t.NamaSupir                                              AS [Nama Supir],
    CASE WHEN t.TicketType = ''Produk'' THEN NULLIF(LTRIM(RTRIM(t.SPDO)), '''') END AS [Nomor Kontrak],
    t.Bruto, t.Tara,
    ISNULL(t.Deduction, 0)                                   AS Potongan,
    t.Netto,
    ISNULL(t.FirstWeight, 0)                                 AS [Netto Sumber],
    ISNULL(t.FFA, 0)                                         AS FFA,
    ISNULL(t.PctAir, 0)                                      AS [Kadar Air],
    ISNULL(t.PctKotoran, 0)                                  AS [Kadar Kotoran],
    ISNULL(t.Dobi, 0)                                        AS Dobi
FROM {P}PALM_Tickets t
LEFT JOIN {P}AR_Customers cu ON t.TicketType = ''Produk'' AND cu.CustomerID = t.AssociateID
LEFT JOIN {P}AP_Suppliers su ON t.TicketType <> ''Produk'' AND su.SupplierID = t.AssociateID
LEFT JOIN {P}PALM_DeliveryOrders d ON d.DeliveryOrderID = t.DeliveryOrderID
LEFT JOIN {P}PALM_Contracts k ON k.ContractID = d.ContractID
LEFT JOIN {P}AP_Suppliers s1 ON s1.SupplierID = NULLIF(t.ShipperID, 0)
LEFT JOIN {P}AP_Suppliers s2 ON s2.SupplierID = NULLIF(d.DOShipperSupplierID, 0)
LEFT JOIN {P}AP_Suppliers s3 ON s3.SupplierID = NULLIF(k.ShipperSupplierID, 0)
LEFT JOIN {P}AP_Suppliers s4 ON s4.SupplierID = NULLIF(k.ShipperSupplierID2, 0)
OUTER APPLY (SELECT NULLIF(STUFF((SELECT DISTINCT '' / '' + RTRIM(sx.SupplierName)
                                  FROM {P}PALM_DOTransport x JOIN {P}AP_Suppliers sx ON sx.SupplierID = x.ShipperID
                                  WHERE x.DeliveryOrderID = t.DeliveryOrderID AND t.DeliveryOrderID > 0
                                  FOR XML PATH(''''), TYPE).value(''.'', ''nvarchar(max)''), 1, 3, ''''), '''') AS Nama) dt
WHERE ISNULL(t.Void, 0) = 0
  AND t.Step >= 2 AND t.DateTimeOut IS NOT NULL          -- hanya tiket yang sudah selesai timbang, sama dengan ekspor Ascend
  AND t.[Date] >= @Dari AND t.[Date] < DATEADD(day, 1, @Sampai)
ORDER BY t.[Date], t.TicketNo;';

SET @s = REPLACE(@s, N'{P}', @P);
EXEC sp_executesql @s, N'@Dari date, @Sampai date', @Dari = @Dari, @Sampai = @Sampai;
