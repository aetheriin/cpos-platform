-- Stored procedure Outstanding (hutang dan piutang belum lunas), dibuat di database Main.
-- Tanpa parameter: semua perusahaan aktif bertipe CLOUD di dbo.company, semua riwayat dokumen.
-- @CompID (opsional, mis. 'YBS'): satu perusahaan saja. Web Analytics memanggil per perusahaan secara bersamaan supaya lebih cepat.
-- Satu baris per dokumen yang belum lunas. Perhitungan lanjutan (tanda potongan, status, kurs, rekap) dikerjakan di Python (laporan Outstanding).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main untuk membuat/memperbarui SP-nya, lalu cek: EXEC dbo.R_OUTSTANDING_ARAP;  atau  EXEC dbo.R_OUTSTANDING_ARAP 'YBS';
CREATE OR ALTER PROCEDURE dbo.R_OUTSTANDING_ARAP
    @CompID varchar(10) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    CREATE TABLE #hasil (IsAR bit, Kode varchar(10), Sumber varchar(100), NoDok varchar(200), Tgl date, Mitra nvarchar(300), Mata varchar(20), KursDok decimal(18, 4),
        Arah int, Nilai money, SudahPV money, Sisa money, DalamPVR money, PVBelumJatuhTempo money, NoPVBelumJatuhTempo nvarchar(max),
        TglPVBelumJatuhTempo date, NoPV nvarchar(max), NoPVR nvarchar(max), TglPVR date, ApprovePVR varchar(20), TagihanPVR money, PotonganPVR money,
        NoDO nvarchar(200), NoKontrak nvarchar(200), NoTC nvarchar(200), Keterangan nvarchar(400),
        CompID varchar(10) NULL);

    DECLARE @b nvarchar(max) = N'USE {DB};
SET NOCOUNT ON;
DECLARE @Dari date = ''19000101'', @Sampai date = ''99991230'';   -- semua riwayat

-- Semua sumber hutang dan piutang yang dipakai ERP saat membuat PV/RV (tabel SH_ARAPCalculations)
CREATE TABLE #I (IsAR bit, Kode varchar(10), Sumber varchar(100), ItemID int, NoDok varchar(200), Tgl date,
                 Nilai money, Positif bit, MitraID int, CurrencyID int, Kurs decimal(18, 4));
DECLARE @sql nvarchar(max), @kode varchar(10);
DECLARE k CURSOR LOCAL FAST_FORWARD FOR
SELECT CompCode,
       N''INSERT #I SELECT '' + CAST(IsAR AS varchar(1)) + '', '''''' + CompCode + '''''', '''''' + ISNULL(SummarizedAs, CompCode) + '''''', ''
       + KeyField + '', '' + NumberField + '', '' + DateField + '', '' + CalcField + '', '' + CAST(IsPositive AS varchar(1)) + '', ''
       + ISNULL(NULLIF(AssociateField, ''''), CASE WHEN IsAR = 1 THEN ''CustomerID'' ELSE ''SupplierID'' END) + '', '' + CurrencyField
       + '', '' + CASE WHEN COL_LENGTH(SourceTable, ''ExchangeRate'') IS NOT NULL THEN ''M.ExchangeRate'' ELSE ''NULL'' END  -- kurs yang tercatat di dokumen
       + '' FROM '' + SourceTable + '' M '' + ISNULL(ExtraJoin, '''')
       + '' WHERE '' + ISNULL(NULLIF(VoidField, ''''), ''0'') + '' != 1'' + ISNULL('' AND ('' + NULLIF(ExtraFilter, '''') + '')'', '''')
       + '' AND '' + DateField + '' >= @Dari AND '' + DateField + '' < DATEADD(day, 1, @Sampai)''
FROM SH_ARAPCalculations
WHERE ARAPCalc = 1 AND CompCode NOT IN (''EXR'', ''EXM'')
  AND SourceTable <> ''VIEW_FI_PPhAP'';  -- PPh potong dan setor ke kas negara saling menutup, tidak dihitung sebagai hutang supplier
OPEN k; FETCH k INTO @kode, @sql;
WHILE @@FETCH_STATUS = 0 BEGIN
    -- Sumber yang gagal (mis. timeout saat server sibuk) dicoba sekali lagi; kalau masih gagal, pemuatan berhenti dengan pesan,
    -- supaya angka yang kurang tidak pernah tampil diam-diam.
    BEGIN TRY EXEC sp_executesql @sql, N''@Dari date, @Sampai date'', @Dari, @Sampai; END TRY
    BEGIN CATCH
        BEGIN TRY EXEC sp_executesql @sql, N''@Dari date, @Sampai date'', @Dari, @Sampai; END TRY
        BEGIN CATCH
            DECLARE @pesan nvarchar(2048) = N''Sumber '' + @kode + N'' gagal dibaca: '' + ERROR_MESSAGE();
            THROW 50001, @pesan, 1;
        END CATCH
    END CATCH
    FETCH k INTO @kode, @sql;
END
CLOSE k; DEALLOCATE k;
CREATE INDEX ix ON #I (Kode, ItemID);

-- Nama sumber (dipasang di hasil akhir saja) mengikuti nama yang tampil di ERP (SH_ARAPCalculations.DisplayTitle), mis. AP Discount Notes, AP Notes.
SELECT c.IsAR, c.CompCode AS Kode, COALESCE(NULLIF(c.DisplayTitle, ''''), c.SummarizedAs, c.CompCode) AS Label
INTO #L
FROM SH_ARAPCalculations c
WHERE c.ARAPCalc = 1;

-- PVR yang sudah dibuatkan PV (aturan ERP)
SELECT DISTINCT SourceVoucherID AS ID INTO #PVRSelesai FROM FI_ARAP WHERE (VoidCheck = 1 OR Void = 0) AND SourceVoucherID > 0 AND IsAR = 0
UNION SELECT PVRVoucherID FROM FI_ARAPSources;

-- Baris pembayaran PV/RV untuk dokumen di #I, sekali baca; Depan = 1 untuk PV bertanggal setelah hari ini (belum dibayar)
SELECT i.ItemType AS Kode, i.ItemID, v.VoucherNo, CAST(v.VoucherDate AS date) AS Tgl, i.AmountPaid AS Bayar, i.AmountDebit - i.AmountCredit AS DK,
       CASE WHEN v.VoucherDate >= DATEADD(day, 1, CAST(GETDATE() AS date)) THEN 1 ELSE 0 END AS Depan
INTO #BB
FROM FI_ARAPItems i JOIN FI_ARAP v ON v.VoucherID = i.VoucherID JOIN #I x ON x.Kode = i.ItemType AND x.ItemID = i.ItemID
WHERE v.Void != 1 OR v.VoidCheck = 1;
CREATE INDEX ix ON #BB (Kode, ItemID, Depan);

-- Pembayaran yang sudah lewat tanggalnya
SELECT b.Kode, b.ItemID, SUM(b.Bayar) AS Bayar, SUM(b.DK) AS DK
INTO #Bayar
FROM #BB b WHERE b.Depan = 0
GROUP BY b.Kode, b.ItemID;

-- PV bertanggal ke depan (setelah hari ini): sudah dibuat tapi belum dibayar, jadi masih hutang
SELECT b.Kode, b.ItemID, SUM(b.Bayar + b.DK) AS Nilai, MIN(b.Tgl) AS TglPV
INTO #PVDepan
FROM #BB b WHERE b.Depan = 1
GROUP BY b.Kode, b.ItemID;

-- Item PVR yang belum dibuatkan PV, sekali baca
SELECT i.ItemType AS Kode, i.ItemID, r.VoucherID, r.VoucherNo, i.AmountPaid + i.AmountDebit - i.AmountCredit AS Nilai
INTO #RR
FROM FI_APRequestItems i JOIN FI_APRequest r ON r.VoucherID = i.VoucherID JOIN #I x ON x.Kode = i.ItemType AND x.ItemID = i.ItemID
WHERE r.Void != 1 AND r.VoucherID NOT IN (SELECT ID FROM #PVRSelesai);
CREATE INDEX ix ON #RR (Kode, ItemID);

SELECT r.Kode, r.ItemID, SUM(r.Nilai) AS Nilai
INTO #PVR
FROM #RR r
GROUP BY r.Kode, r.ItemID;

SELECT x.IsAR, x.Kode, x.ItemID, x.Sumber, x.NoDok, x.Tgl, COALESCE(s.SupplierName, c.CustomerName,
                ''(Transportir belum diisi'' + ISNULL('', tiket ke '' + tc.CustomerName, '''') + '')'') AS Mitra, cu.Currency AS Mata, x.Kurs AS KursDok,
       CASE WHEN x.Positif = 1 THEN 1 ELSE -1 END AS Arah, x.Nilai,
       ISNULL(b.Bayar, 0) + CASE WHEN x.IsAR = 1 THEN -1 ELSE 1 END * ISNULL(b.DK, 0) AS SudahPV,
       x.Nilai - ISNULL(b.Bayar, 0) - CASE WHEN x.IsAR = 1 THEN -1 ELSE 1 END * ISNULL(b.DK, 0) AS Sisa,
       ISNULL(p.Nilai, 0) AS DalamPVR, ISNULL(f.Nilai, 0) AS PVBelumJatuhTempo, f.TglPV AS TglPVBelumJatuhTempo
INTO #Sisa
FROM #I x
LEFT JOIN #Bayar b ON b.Kode = x.Kode AND b.ItemID = x.ItemID
LEFT JOIN #PVR p ON p.Kode = x.Kode AND p.ItemID = x.ItemID
LEFT JOIN #PVDepan f ON f.Kode = x.Kode AND f.ItemID = x.ItemID
LEFT JOIN AP_Suppliers s ON s.SupplierID = x.MitraID AND x.IsAR = 0
LEFT JOIN AR_Customers c ON c.CustomerID = x.MitraID AND x.IsAR = 1
-- Ongkos angkut tiket tanpa transportir: tampilkan customer tiketnya sebagai petunjuk
LEFT JOIN PALM_Tickets tk ON tk.TicketID = x.ItemID AND x.Kode IN (''TV'', ''TV2'') AND s.SupplierID IS NULL
LEFT JOIN AR_Customers tc ON tc.CustomerID = tk.AssociateID
LEFT JOIN CO_Currency cu ON cu.CurrencyID = x.CurrencyID
WHERE x.Nilai - ISNULL(b.Bayar, 0) - CASE WHEN x.IsAR = 1 THEN -1 ELSE 1 END * ISNULL(b.DK, 0) > 0.5;

-- Nilai tiap PVR pending: tagihan dikurangi potongan (AP Discount Notes dll) yang ikut dimasukkan ke PVR itu
SELECT r.VoucherID, r.VoucherNo AS NoPVR,
       SUM(CASE WHEN ISNULL(c.IsPositive, 1) = 1 THEN i.AmountPaid + i.AmountDebit - i.AmountCredit ELSE 0 END) AS Tagihan,
       SUM(CASE WHEN c.IsPositive = 0 THEN i.AmountPaid + i.AmountDebit - i.AmountCredit ELSE 0 END) AS Potongan,
       COUNT(*) AS JumlahDokumen, CAST(r.VoucherDate AS date) AS TglPVR,
       CASE WHEN ISNULL(r.Approved, 0) = 0 THEN ''Belum approve'' ELSE ''Sudah approve'' END AS Approve
INTO #PVRNilai
FROM FI_APRequest r JOIN FI_APRequestItems i ON i.VoucherID = r.VoucherID
LEFT JOIN SH_ARAPCalculations c ON c.CompCode = i.ItemType AND c.IsAR = 0 AND c.ARAPCalc = 1
WHERE r.Void != 1 AND r.VoucherID NOT IN (SELECT ID FROM #PVRSelesai)
GROUP BY r.VoucherID, r.VoucherNo, r.VoucherDate, r.Approved;

-- Satu baris per dokumen yang belum lunas (hutang dan piutang); tanda (Arah) diterapkan di Python.
-- Daftar nomor PV/PVR hanya disusun untuk dokumen yang belum lunas.
SELECT x.IsAR, x.Kode, COALESCE(l.Label, x.Sumber) AS Sumber, x.NoDok, x.Tgl, x.Mitra, x.Mata, x.KursDok, x.Arah, x.Nilai, x.SudahPV, x.Sisa, x.DalamPVR,
       x.PVBelumJatuhTempo,
       STUFF((SELECT DISTINCT '', '' + b2.VoucherNo FROM #BB b2 WHERE b2.Kode = x.Kode AND b2.ItemID = x.ItemID AND b2.Depan = 1 FOR XML PATH('''')), 1, 2, '''') AS NoPVBelumJatuhTempo,
       x.TglPVBelumJatuhTempo,
       STUFF((SELECT DISTINCT '', '' + b2.VoucherNo FROM #BB b2 WHERE b2.Kode = x.Kode AND b2.ItemID = x.ItemID AND b2.Depan = 0 FOR XML PATH('''')), 1, 2, '''') AS NoPV,
       STUFF((SELECT DISTINCT '', '' + r2.VoucherNo FROM #RR r2 WHERE r2.Kode = x.Kode AND r2.ItemID = x.ItemID FOR XML PATH('''')), 1, 2, '''') AS NoPVR,
       pv.TglPVR, pv.Approve AS ApprovePVR, pv.Tagihan AS TagihanPVR, pv.Potongan AS PotonganPVR,
       d.DeliveryOrderNumber AS NoDO, k.ContractNumber AS NoKontrak, d.TCNo AS NoTC, LEFT(iv.Remarks, 200) AS Keterangan
FROM #Sisa x
LEFT JOIN #L l ON l.Kode = x.Kode AND l.IsAR = x.IsAR
OUTER APPLY (SELECT SUM(n.Tagihan) AS Tagihan, SUM(n.Potongan) AS Potongan, MIN(n.TglPVR) AS TglPVR, MIN(n.Approve) AS Approve FROM #PVRNilai n
             WHERE x.IsAR = 0 AND n.VoucherID IN (SELECT r.VoucherID FROM #RR r WHERE r.Kode = x.Kode AND r.ItemID = x.ItemID)) pv
LEFT JOIN PALM_Invoices iv ON iv.InvoiceID = x.ItemID AND x.IsAR = 1 AND x.Kode IN (''PS'', ''PB'')
LEFT JOIN PALM_DeliveryOrders d ON d.DeliveryOrderID = iv.DeliveryOrderID
LEFT JOIN PALM_Contracts k ON k.ContractID = COALESCE(d.ContractID, iv.ContractID);
';

    DECLARE @Comp varchar(10), @Server sysname, @DB sysname, @q nvarchar(max), @x nvarchar(max);
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
        SET @x = N'INSERT INTO #hasil (IsAR, Kode, Sumber, NoDok, Tgl, Mitra, Mata, KursDok, Arah, Nilai, SudahPV, Sisa, DalamPVR, PVBelumJatuhTempo, NoPVBelumJatuhTempo, TglPVBelumJatuhTempo, NoPV, NoPVR, TglPVR, ApprovePVR, TagihanPVR, PotonganPVR, NoDO, NoKontrak, NoTC, Keterangan) EXEC (@q) AT ' + QUOTENAME(@Server) + N';';
        EXEC sp_executesql @x, N'@q nvarchar(max)', @q;
        UPDATE #hasil SET CompID = @Comp WHERE CompID IS NULL;
        FETCH c INTO @Comp, @Server, @DB;
    END
    CLOSE c; DEALLOCATE c;

    SELECT CompID, IsAR, Kode, Sumber, NoDok, Tgl, Mitra, Mata, KursDok, Arah, Nilai, SudahPV, Sisa, DalamPVR, PVBelumJatuhTempo, NoPVBelumJatuhTempo, TglPVBelumJatuhTempo, NoPV, NoPVR, TglPVR, ApprovePVR, TagihanPVR, PotonganPVR, NoDO, NoKontrak, NoTC, Keterangan FROM #hasil;
END
