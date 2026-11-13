/* Laporan Pembelian TBS lebih cepat: data Ascend diambil sekali lewat linked server ke tabel sementara #P,
   lalu semua perhitungan membaca #P. Sebelumnya bagian itu dijalankan 2-3 kali per prosedur. Rumus dan hasil tidak berubah.
   Jalankan di database Main. */
USE Main;
GO

ALTER PROCEDURE [dbo].[tbsdetailybs2]
    @Company NVARCHAR(10) = 'YBS',
    @Tanggal DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    /* ============================================
       1. DEFAULT TANGGAL
       ============================================ */

    IF @Tanggal IS NULL
        SET @Tanggal = CAST(GETDATE() AS DATE);


    /* ============================================
       2. VARIABLE DATABASE COMPANY
       ============================================ */

    DECLARE @LoopIP NVARCHAR(100);
    DECLARE @LoopDBID NVARCHAR(100);
    DECLARE @FullDatabasePath NVARCHAR(500);
    DECLARE @DynamicSQL NVARCHAR(MAX);


    /* ============================================
       3. AMBIL DATABASE BERDASARKAN COMPANY
       ============================================ */

    SELECT TOP 1
        @LoopIP = RTRIM(LTRIM(CompAddr)),
        @LoopDBID = RTRIM(LTRIM(CompDataBase))
    FROM dbo.Company
    WHERE RTRIM(LTRIM(CompID)) = RTRIM(LTRIM(@Company))
      AND RTRIM(LTRIM(CompType)) = 'CLOUD';

    IF @LoopIP IS NULL OR @LoopDBID IS NULL
    BEGIN
        THROW 50001,
              'Company tidak ditemukan pada dbo.Company.',
              1;
    END;

    SET @FullDatabasePath =
        QUOTENAME(@LoopIP) + '.' + QUOTENAME(@LoopDBID);


    /* ============================================
       4. QUERY UTAMA
       ============================================ */

    SET @DynamicSQL = N'

    
    /* Data Ascend diambil sekali lewat linked server; semua perhitungan di bawah membaca #P */
    SELECT p.PURCHASEID, p.PURCHASEDATE, pd.DETAILID, pd.LINETOTAL, pd.NETTO, pd.PRICEPERKG,
           sup.SupplierName, st.SUPPLIERTYPECODE, bg.BUSINESSGROUPNAME
      INTO #P
    FROM ' + @FullDatabasePath + N'.dbo.palm_ffbpurchases p

        INNER JOIN ' + @FullDatabasePath + N'.dbo.palm_ffbpurchasedetails pd
            ON p.PURCHASEID = pd.PURCHASEID

        INNER JOIN ' + @FullDatabasePath + N'.dbo.ap_suppliers sup
            ON p.SUPPLIERID = sup.SUPPLIERID

        LEFT JOIN ' + @FullDatabasePath + N'.dbo.ap_suppliertypes st
            ON sup.SUPPLIERTYPEID = st.SUPPLIERTYPEID

        LEFT JOIN ' + @FullDatabasePath + N'.dbo.ar_businessgroups bg
            ON sup.BUSINESSGROUPID = bg.BUSINESSGROUPID
     WHERE p.PURCHASEDATE >= @ParamTanggal AND p.PURCHASEDATE < DATEADD(DAY, 1, @ParamTanggal);

/* =====================================================
       HARGA
       ===================================================== */

    WITH HARGA_DATA AS
    (
        SELECT TOP 1
            h.harga_cpo AS HARGA_CPO_ASLI,
            h.harga_cpo - 450 AS HARGA_CPO_FINAL,
            h.harga_kernel AS HARGA_KERNEL,
            h.oer_cpo AS OER_CPO,
            h.biaya_olah AS BIAYA_OLAH,
            h.qty_rsi AS QTY_RSI
        FROM dbo.HARGA h
        WHERE UPPER(LTRIM(RTRIM(h.company))) =
              UPPER(LTRIM(RTRIM(@ParamComp)))
          AND h.tanggal = @ParamTanggal
        ORDER BY h.id DESC
    ),


    /* =====================================================
       RAW DATA
       ===================================================== */

    RAW AS
    (
        SELECT
            p.PURCHASEID,
            p.DETAILID,
            CAST(p.PURCHASEDATE AS DATE) AS TANGGAL,
            p.LINETOTAL,
            p.NETTO,
            p.PRICEPERKG,
            p.SupplierName,
            p.BUSINESSGROUPNAME,
            p.SUPPLIERTYPECODE,

            ''PT. '' + @ParamComp AS MAP_COMPANY,

            ISNULL(ms.Category, '''') AS Category,

            h.HARGA_CPO_ASLI,
            h.HARGA_CPO_FINAL,
            h.HARGA_KERNEL,
            h.OER_CPO,
            h.BIAYA_OLAH,
            h.QTY_RSI

        FROM #P p

        LEFT JOIN dbo.MappingSupplier ms
            ON p.SUPPLIERTYPECODE = ms.Supplier
           AND ms.Company = ''PT. '' + @ParamComp

        CROSS JOIN HARGA_DATA h

        WHERE p.PURCHASEDATE >= @ParamTanggal
          AND p.PURCHASEDATE < DATEADD(DAY, 1, @ParamTanggal)
    ),


    /* =====================================================
       HARGA TRANSAKSI SUPPLIER BINAAN
       Hanya supplier BINAAN di kategori KEBUN BINAAN.
       Supplier DSS dan lainnya tidak ikut dihitung.
       ===================================================== */

    BINAAN_PRICING AS
    (
        SELECT
            ISNULL(MAX(
                CASE
                    WHEN UPPER(LTRIM(RTRIM(SUPPLIERTYPECODE))) = ''BINAAN''
                    THEN PRICEPERKG
                END
            ), 0) AS HARGA_BINAAN_TRANSAKSI
        FROM RAW
        WHERE UPPER(LTRIM(RTRIM(Category))) = ''KEBUN BINAAN''
    ),


    /* =====================================================
       SEMUA KATEGORI DARI MAPPING DAN TRANSAKSI
       ===================================================== */

    ALL_CATEGORIES AS
    (
        SELECT DISTINCT Category
        FROM dbo.MappingSupplier
        WHERE Company = ''PT. '' + @ParamComp

        UNION

        SELECT DISTINCT Category
        FROM RAW

        UNION

        SELECT ''AGEN BINAAN''
    ),


    /* =====================================================
       GROUP PER CATEGORY
       ===================================================== */

    GROUPED AS
    (
        SELECT
            ''PT. '' + @ParamComp AS MAP_COMPANY,

            ac.Category,

            SUM(ISNULL(r.NETTO, 0)) AS TONASE,

            SUM(ISNULL(r.LINETOTAL, 0)) AS TOTAL_LINETOTAL,

            CASE
                WHEN SUM(ISNULL(r.NETTO, 0)) = 0
                    THEN 0
                ELSE
                    SUM(ISNULL(r.LINETOTAL, 0))
                    / SUM(ISNULL(r.NETTO, 0))
            END AS HARGA_BELI_RATA2,

            ISNULL(MAX(r.PRICEPERKG), 0)
                AS HARGA_TBS_TERTINGGI,

            ISNULL(
                MAX(r.HARGA_CPO_ASLI),
                (SELECT HARGA_CPO_ASLI FROM HARGA_DATA)
            ) AS HARGA_CPO_ASLI,

            ISNULL(
                MAX(r.HARGA_CPO_FINAL),
                (SELECT HARGA_CPO_FINAL FROM HARGA_DATA)
            ) AS HARGA_CPO,

            ISNULL(
                MAX(r.HARGA_KERNEL),
                (SELECT HARGA_KERNEL FROM HARGA_DATA)
            ) AS HARGA_KERNEL,

            ISNULL(
                MAX(r.OER_CPO),
                (SELECT OER_CPO FROM HARGA_DATA)
            ) AS OER_CPO,

            ISNULL(
                MAX(r.BIAYA_OLAH),
                (SELECT BIAYA_OLAH FROM HARGA_DATA)
            ) AS BIAYA_OLAH,

            ISNULL(
                MAX(r.QTY_RSI),
                (SELECT QTY_RSI FROM HARGA_DATA)
            ) AS QTY_RSI

        FROM ALL_CATEGORIES ac
        LEFT JOIN RAW r
            ON ac.Category = r.Category

        GROUP BY ac.Category
    ),


    /* =====================================================
       PERHITUNGAN KATEGORI
       Logika harga dasar dan SPSI dipusatkan di CROSS APPLY (x)
       ===================================================== */

    CALCULATED AS
    (
        SELECT
            g.MAP_COMPANY,
            g.Category,
            g.HARGA_BELI_RATA2,

            x.HARGA_DASAR AS HARGA_TBS_TERTINGGI,

            CASE
                WHEN x.HARGA_DASAR = 0 OR g.TONASE = 0
                    THEN 0
                ELSE ROUND(x.HARGA_DASAR + x.SPSI, 0)
            END AS HARGA_TBS_SPSI,

            ROUND(g.HARGA_CPO_ASLI, 0) AS HARGA_CPO_ASLI,
            ROUND(g.HARGA_CPO, 0)      AS HARGA_CPO,
            g.HARGA_KERNEL,

            CASE
                WHEN g.HARGA_CPO = 0 OR x.HARGA_DASAR = 0 OR g.TONASE = 0
                    THEN 0
                ELSE (x.HARGA_DASAR + x.SPSI) / g.HARGA_CPO
            END AS PERSENTASE,

            g.TONASE,

            CASE
                WHEN g.HARGA_CPO = 0 OR x.HARGA_DASAR = 0 OR g.TONASE = 0
                    THEN 0
                ELSE g.TONASE * ((x.HARGA_DASAR + x.SPSI) / g.HARGA_CPO)
            END AS TONASE_CPO,

            g.OER_CPO,
            g.BIAYA_OLAH,
            g.QTY_RSI

        FROM GROUPED g
        CROSS JOIN BINAAN_PRICING bp
        CROSS APPLY
        (
            SELECT
                /* Khusus SJN + KEBUN BINAAN: pakai harga supplier BINAAN jika ada.
                   Jika tidak ada transaksi BINAAN, tetap harga tertinggi kategori. */
                CASE
                    WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''SJN''
                     AND UPPER(LTRIM(RTRIM(g.Category))) = ''KEBUN BINAAN''
                     AND bp.HARGA_BINAAN_TRANSAKSI > 0
                    THEN bp.HARGA_BINAAN_TRANSAKSI
                    ELSE g.HARGA_TBS_TERTINGGI
                END AS HARGA_DASAR,

                CASE
                    WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''YBS'' THEN 15
                    WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''SUN'' THEN 14
                    WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''SJN'' THEN 15
                    ELSE 0
                END AS SPSI
        ) x
    ),


    /* =====================================================
       FINAL DATA
       KATEGORI NORMAL + PT.RSI
       ===================================================== */

    FINAL_DATA AS
    (
        /* -----------------------------------------------
           A. SEMUA KATEGORI NORMAL
           ----------------------------------------------- */

        SELECT
            MAP_COMPANY,
            Category,
            HARGA_TBS_SPSI,
            HARGA_CPO_ASLI,
            HARGA_CPO,
            HARGA_KERNEL,
            PERSENTASE,
            TONASE,
            TONASE_CPO,
            OER_CPO,
            BIAYA_OLAH,
            QTY_RSI
        FROM CALCULATED

        UNION ALL

        /* -----------------------------------------------
           B. BARIS KHUSUS PT.RSI
           KHUSUS COMPANY YBS
           ----------------------------------------------- */

        SELECT
            ''PT. '' + @ParamComp AS MAP_COMPANY,

            ''PT.RSI'' AS Category,

            ROUND(h.HARGA_CPO_FINAL * 0.27, 0)
                AS HARGA_TBS_SPSI,

            ROUND(h.HARGA_CPO_ASLI, 0)
                AS HARGA_CPO_ASLI,

            ROUND(h.HARGA_CPO_FINAL, 0)
                AS HARGA_CPO,

            h.HARGA_KERNEL,

            CAST(0.27 AS DECIMAL(18,8))
                AS PERSENTASE,

            h.QTY_RSI AS TONASE,

            h.QTY_RSI * 0.27 AS TONASE_CPO,

            h.OER_CPO,
            h.BIAYA_OLAH,
            h.QTY_RSI

        FROM HARGA_DATA h

        WHERE UPPER(LTRIM(RTRIM(@ParamComp))) = ''YBS''
          AND ISNULL(h.QTY_RSI, 0) > 0
    )


    /* =====================================================
       HASIL AKHIR
       TOTAL DIHITUNG SETELAH PT.RSI DITAMBAHKAN
       ===================================================== */

    SELECT
        @ParamComp AS COMPANY,

        @ParamTanggal AS TANGGAL,

        MAP_COMPANY,
        Category,
        HARGA_TBS_SPSI,
        HARGA_CPO_ASLI,
        HARGA_CPO,
        HARGA_KERNEL,
        PERSENTASE,
        TONASE,
        TONASE_CPO,
        OER_CPO,
        BIAYA_OLAH,
        QTY_RSI,

        /* TOTAL TONASE SELURUH KATEGORI + PT.RSI */
        SUM(ISNULL(TONASE, 0)) OVER ()
            AS TOTAL_TONASE,

        /* TOTAL TONASE CPO SELURUH KATEGORI + PT.RSI */
        SUM(ISNULL(TONASE_CPO, 0)) OVER ()
            AS TOTAL_TONASE_CPO,

        CASE
            WHEN SUM(ISNULL(TONASE, 0)) OVER () = 0
                THEN 0
            ELSE
                SUM(ISNULL(TONASE_CPO, 0)) OVER ()
                /
                SUM(ISNULL(TONASE, 0)) OVER ()
        END AS PERSENTASE_TOTAL,

        CASE
            WHEN HARGA_CPO = 0
                THEN 0
            ELSE
                (
                    CAST(HARGA_KERNEL - 450 AS DECIMAL(18,8))
                    /
                    CAST(HARGA_CPO AS DECIMAL(18,8))
                ) * 0.05
        END AS PERSENTASE_KERNEL,

        CASE
            WHEN HARGA_CPO = 0
                THEN 0
            ELSE
                CAST(BIAYA_OLAH AS DECIMAL(18,8))
                /
                CAST(HARGA_CPO / 100.0 AS DECIMAL(18,8))
        END AS BIAYA_OLAH_TBS,

        OER_CPO

        +

        CASE
            WHEN HARGA_CPO = 0
                THEN 0
            ELSE
                (
                    CAST(HARGA_KERNEL - 450 AS DECIMAL(18,8))
                    /
                    CAST(HARGA_CPO AS DECIMAL(18,8))
                ) * 0.05
        END

        -

        CASE
            WHEN SUM(ISNULL(TONASE, 0)) OVER () = 0
                THEN 0
            ELSE
                SUM(ISNULL(TONASE_CPO, 0)) OVER ()
                /
                SUM(ISNULL(TONASE, 0)) OVER ()
        END

        -

        CASE
            WHEN HARGA_CPO = 0
                THEN 0
            ELSE
                CAST(BIAYA_OLAH AS DECIMAL(18,8))
                /
                CAST(HARGA_CPO / 100.0 AS DECIMAL(18,8))
        END AS SELISIH

    FROM FINAL_DATA

    ORDER BY
        CASE
            WHEN Category = ''AGEN BINAAN'' THEN 1
            WHEN Category = ''PT.RSI'' THEN 999
            WHEN Category = '''' THEN 998
            ELSE 2
        END,
        Category;
    ';


    /* ============================================
       5. EXECUTE
       ============================================ */

    EXEC sp_executesql
        @DynamicSQL,
        N'@ParamTanggal DATE,
          @ParamComp NVARCHAR(10)',
        @ParamTanggal = @Tanggal,
        @ParamComp = @Company;

END;
GO

ALTER PROCEDURE [dbo].[tbsdetailybsweekly]
    @Company NVARCHAR(10) = 'YBS',
    @TanggalAwal DATE = NULL,
    @TanggalAkhir DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    /* =========================================================
       1. DEFAULT TANGGAL
       ========================================================= */

    IF @TanggalAwal IS NULL
        SET @TanggalAwal = CAST(GETDATE() AS DATE);

    IF @TanggalAkhir IS NULL
        SET @TanggalAkhir = @TanggalAwal;

    IF @TanggalAwal > @TanggalAkhir
    BEGIN
        THROW 50001,
              'Tanggal Awal tidak boleh lebih besar dari Tanggal Akhir.',
              1;
    END;


    /* =========================================================
       2. VARIABLE DATABASE COMPANY
       ========================================================= */

    DECLARE @LoopIP NVARCHAR(100);
    DECLARE @LoopDBID NVARCHAR(100);
    DECLARE @FullDatabasePath NVARCHAR(500);
    DECLARE @DynamicSQL NVARCHAR(MAX);


    /* =========================================================
       3. AMBIL DATABASE BERDASARKAN COMPANY
       ========================================================= */

    SELECT TOP 1
        @LoopIP = RTRIM(LTRIM(CompAddr)),
        @LoopDBID = RTRIM(LTRIM(CompDataBase))
    FROM dbo.Company
    WHERE RTRIM(LTRIM(CompID)) = RTRIM(LTRIM(@Company))
      AND RTRIM(LTRIM(CompType)) = 'CLOUD';


    IF @LoopIP IS NULL OR @LoopDBID IS NULL
    BEGIN
        THROW 50002,
              'Company tidak ditemukan pada dbo.Company.',
              1;
    END;

    SET @FullDatabasePath =
        QUOTENAME(@LoopIP)
        + '.'
        + QUOTENAME(@LoopDBID)
        + '.dbo';


    /* =========================================================
       4. QUERY UTAMA
       ========================================================= */

    SET @DynamicSQL = N'

    
    /* Data Ascend diambil sekali lewat linked server; semua perhitungan di bawah membaca #P */
    SELECT p.PURCHASEID, p.PURCHASEDATE, pd.DETAILID, pd.LINETOTAL, pd.NETTO, pd.PRICEPERKG,
           sup.SupplierName, st.SUPPLIERTYPECODE, bg.BUSINESSGROUPNAME
      INTO #P
    FROM ' + @FullDatabasePath + N'.palm_ffbpurchases p
        INNER JOIN ' + @FullDatabasePath + N'.palm_ffbpurchasedetails pd ON p.PURCHASEID = pd.PURCHASEID
        INNER JOIN ' + @FullDatabasePath + N'.ap_suppliers sup ON p.SUPPLIERID = sup.SUPPLIERID
        LEFT JOIN ' + @FullDatabasePath + N'.ap_suppliertypes st ON sup.SUPPLIERTYPEID = st.SUPPLIERTYPEID
        LEFT JOIN ' + @FullDatabasePath + N'.ar_businessgroups bg ON sup.BUSINESSGROUPID = bg.BUSINESSGROUPID
     WHERE p.PURCHASEDATE >= @ParamTanggalAwal AND p.PURCHASEDATE < DATEADD(DAY, 1, @ParamTanggalAkhir);

;WITH WEEK_PERIOD AS
    (
        SELECT
            @ParamTanggalAwal AS WEEK_START,
            CASE
                WHEN DATEADD(DAY, 6 - (DATEDIFF(DAY, ''19000101'', @ParamTanggalAwal) % 7), @ParamTanggalAwal) > @ParamTanggalAkhir
                THEN @ParamTanggalAkhir
                ELSE DATEADD(DAY, 6 - (DATEDIFF(DAY, ''19000101'', @ParamTanggalAwal) % 7), @ParamTanggalAwal)
            END AS WEEK_END

        UNION ALL

        SELECT
            DATEADD(DAY, 1, WEEK_END) AS WEEK_START,
            CASE
                WHEN DATEADD(DAY, 7, WEEK_END) > @ParamTanggalAkhir
                THEN @ParamTanggalAkhir
                ELSE DATEADD(DAY, 7, WEEK_END)
            END AS WEEK_END
        FROM WEEK_PERIOD
        WHERE WEEK_END < @ParamTanggalAkhir
    ),

    PERIODS AS
    (
        SELECT
            WEEK_START,
            WEEK_END,
            CONCAT(
                ''Minggu '',
                ROW_NUMBER() OVER (ORDER BY WEEK_START),
                '' ('',
                CONVERT(VARCHAR(10), WEEK_START, 103),
                '' - '',
                CONVERT(VARCHAR(10), WEEK_END, 103),
                '')''
            ) AS PERIOD_LABEL
        FROM WEEK_PERIOD
    ),

    RAW AS
    (
        SELECT
            p.PURCHASEID,
            p.DETAILID,
            CAST(p.PURCHASEDATE AS DATE) AS TANGGAL,
            p.LINETOTAL,
            p.NETTO,
            p.PRICEPERKG,
            p.SupplierName,
            p.BUSINESSGROUPNAME,
            p.SUPPLIERTYPECODE,
            ms.Company AS MAP_COMPANY,
            ms.Category AS MAP_CATEGORY,

            CASE
                WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''YBS''
                     AND UPPER(LTRIM(RTRIM(p.SUPPLIERTYPECODE))) = ''GHS BRD''
                THEN ''Brondolan''

                WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''YBS''
                     AND UPPER(LTRIM(RTRIM(p.SUPPLIERTYPECODE))) IN (''MITRA C'', ''AGEN BINAA'')
                THEN ''Agen''

                WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''SUN''
                     AND UPPER(LTRIM(RTRIM(p.SUPPLIERTYPECODE))) = ''BRD''
                THEN ''Brondolan''

                WHEN UPPER(LTRIM(RTRIM(@ParamComp))) = ''SUN''
                     AND UPPER(LTRIM(RTRIM(p.SUPPLIERTYPECODE))) IN (''UMUM'', ''TBS AGEN'')
                THEN ''Agen''

                ELSE ''Kebun''
            END AS KATEGORI

        FROM #P p
        LEFT JOIN dbo.MappingSupplier ms ON p.SUPPLIERTYPECODE = ms.Supplier AND ms.Company = ''PT. '' + @ParamComp
        WHERE CAST(p.PURCHASEDATE AS DATE) BETWEEN @ParamTanggalAwal AND @ParamTanggalAkhir
          AND NOT (
              UPPER(LTRIM(RTRIM(@ParamComp))) = ''YBS''
              AND UPPER(LTRIM(RTRIM(p.SUPPLIERTYPECODE))) = ''AGEN BINAA''
              AND UPPER(LTRIM(RTRIM(p.BUSINESSGROUPNAME))) = ''PT. RIAU SAWIT INDAH''
          )
    ),

    DATA_PERIOD AS
    (
        SELECT
            r.*,
            p.PERIOD_LABEL,
            p.WEEK_START,
            p.WEEK_END
        FROM RAW r
        INNER JOIN PERIODS p ON r.TANGGAL BETWEEN p.WEEK_START AND p.WEEK_END
    ),

    GROUPED AS
    (
        SELECT
            MAP_COMPANY,
            SUPPLIERTYPECODE,
            BUSINESSGROUPNAME,
            KATEGORI,
            PERIOD_LABEL,
            WEEK_START,
            WEEK_END,

            SUM(ISNULL(NETTO, 0)) AS TONASE_KG,
            SUM(ISNULL(NETTO, 0)) / 1000.0 AS TONASE,
            SUM(ISNULL(LINETOTAL, 0)) AS TOTAL_LINETOTAL,

            CASE
                WHEN SUM(ISNULL(NETTO, 0)) = 0 THEN 0
                ELSE SUM(ISNULL(LINETOTAL, 0)) / SUM(ISNULL(NETTO, 0))
            END AS HARGA_BELI_RATA2,

            CASE
                WHEN SUM(ISNULL(NETTO, 0)) = 0 THEN 0
                ELSE SUM(ISNULL(NETTO, 0) * ISNULL(PRICEPERKG, 0)) / SUM(ISNULL(NETTO, 0))
            END AS PRICE_PER_KG_RATA2

        FROM DATA_PERIOD
        GROUP BY
            MAP_COMPANY,
            SUPPLIERTYPECODE,
            BUSINESSGROUPNAME,
            KATEGORI,
            PERIOD_LABEL,
            WEEK_START,
            WEEK_END
    ),

    /* =========================================================
       PERHITUNGAN ATENSI (STATISTIK WINDOWS)
       ========================================================= */
    GROUPED_WITH_STATS AS
    (
        SELECT
            G.*,
            
            -- Mean & StdDev dari minggu-minggu sebelumnya
            AVG(G.TONASE_KG) OVER (
                PARTITION BY G.SUPPLIERTYPECODE, G.BUSINESSGROUPNAME, G.KATEGORI
                ORDER BY G.WEEK_START
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS MEAN,

            STDEV(G.TONASE_KG) OVER (
                PARTITION BY G.SUPPLIERTYPECODE, G.BUSINESSGROUPNAME, G.KATEGORI
                ORDER BY G.WEEK_START
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS STD_DEV
        FROM GROUPED G
    ),

    CALCULATED_ATTENSI AS
    (
        SELECT
            S.*,
            
            (S.TONASE_KG - S.MEAN) AS DIFFERENCE,

            CASE
                WHEN S.STD_DEV IS NOT NULL AND S.STD_DEV > 0 THEN
                    CASE
                        WHEN (S.TONASE_KG - S.MEAN) > (1.5 * S.STD_DEV) THEN ''NAIK''
                        WHEN (S.TONASE_KG - S.MEAN) < (-1.5 * S.STD_DEV) THEN ''TURUN''
                        ELSE NULL
                    END
                ELSE NULL
            END AS ATTENSI
        FROM GROUPED_WITH_STATS S
    ),

    WEEK_TOTAL AS
    (
        SELECT
            PERIOD_LABEL,
            WEEK_START,
            WEEK_END,
            SUM(TONASE_KG) AS TOTAL_TONASE_KG,
            SUM(TONASE) AS TOTAL_TONASE,
            SUM(CASE WHEN KATEGORI = ''Agen'' THEN TONASE ELSE 0 END) AS AGEN_TOTAL_TON,
            SUM(CASE WHEN KATEGORI = ''Kebun'' THEN TONASE ELSE 0 END) AS KEBUN_TOTAL_TON,
            SUM(CASE WHEN KATEGORI = ''Brondolan'' THEN TONASE ELSE 0 END) AS BRONDOLAN_TOTAL_TON
        FROM CALCULATED_ATTENSI
        GROUP BY
            PERIOD_LABEL,
            WEEK_START,
            WEEK_END
    )

    /* =========================================================
       HASIL AKHIR (Sama persis dengan urutanDataSet2)
       ========================================================= */
    SELECT
        @ParamComp AS COMPANY,
        G.WEEK_START AS TANGGAL_AWAL,
        G.WEEK_END AS TANGGAL_AKHIR,
        G.PERIOD_LABEL AS PERIODE,
        G.SUPPLIERTYPECODE AS JENIS_KEBUN,
        G.BUSINESSGROUPNAME AS [GROUP],
        G.KATEGORI,
        G.TONASE_KG,
        G.TONASE,
        G.STD_DEV,
        G.TOTAL_LINETOTAL,
        G.HARGA_BELI_RATA2,
        G.MEAN,
        G.DIFFERENCE,
        G.PRICE_PER_KG_RATA2,
        WT.TOTAL_TONASE AS TOTAL_TONASE_MINGGU,
        G.ATTENSI,
        WT.AGEN_TOTAL_TON,
        WT.KEBUN_TOTAL_TON,
        WT.BRONDOLAN_TOTAL_TON,
        CASE
            WHEN WT.TOTAL_TONASE = 0 THEN 0
            ELSE G.TONASE / WT.TOTAL_TONASE
        END AS PERSENTASE_TOTAL

    FROM CALCULATED_ATTENSI G
    INNER JOIN WEEK_TOTAL WT
        ON G.PERIOD_LABEL = WT.PERIOD_LABEL
       AND G.WEEK_START = WT.WEEK_START
       AND G.WEEK_END = WT.WEEK_END

    ORDER BY
        G.WEEK_START,
        CASE
            WHEN G.KATEGORI = ''Kebun'' THEN 0
            WHEN G.KATEGORI = ''Agen'' THEN 1
            WHEN G.KATEGORI = ''Brondolan'' THEN 2
            ELSE 3
        END,
        G.SUPPLIERTYPECODE,
        G.BUSINESSGROUPNAME

    OPTION (MAXRECURSION 0);
    ';

    /* =========================================================
       5. EXECUTE DYNAMIC SQL
       ========================================================= */
    EXEC sp_executesql
        @DynamicSQL,
        N'@ParamTanggalAwal DATE,
          @ParamTanggalAkhir DATE,
          @ParamComp NVARCHAR(10)',
        @ParamTanggalAwal = @TanggalAwal,
        @ParamTanggalAkhir = @TanggalAkhir,
        @ParamComp = @Company;

END;
GO

ALTER PROCEDURE [dbo].[tbsdetailmonthly]
    @Company NVARCHAR(10) = 'YBS',
    @TanggalAwal DATE = NULL,
    @TanggalAkhir DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    /* =========================================================
       1. DEFAULT TANGGAL
       ========================================================= */

    IF @TanggalAwal IS NULL
        SET @TanggalAwal = CAST(GETDATE() AS DATE);

    IF @TanggalAkhir IS NULL
        SET @TanggalAkhir = @TanggalAwal;

    IF @TanggalAwal > @TanggalAkhir
    BEGIN
        THROW 50001,
              'Tanggal Awal tidak boleh lebih besar dari Tanggal Akhir.',
              1;
    END;


    /* =========================================================
       2. VARIABLE DATABASE COMPANY
       ========================================================= */

    DECLARE @LoopIP NVARCHAR(100);
    DECLARE @LoopDBID NVARCHAR(100);

    DECLARE @FullDatabasePath NVARCHAR(500);
    DECLARE @DynamicSQL NVARCHAR(MAX);


    /* =========================================================
       3. AMBIL DATABASE BERDASARKAN COMPANY
       ========================================================= */

    SELECT TOP 1
        @LoopIP = RTRIM(LTRIM(CompAddr)),
        @LoopDBID = RTRIM(LTRIM(CompDataBase))
    FROM dbo.Company
    WHERE RTRIM(LTRIM(CompID)) = RTRIM(LTRIM(@Company))
      AND RTRIM(LTRIM(CompType)) = 'CLOUD';


    IF @LoopIP IS NULL OR @LoopDBID IS NULL
    BEGIN
        THROW 50002,
              'Company tidak ditemukan pada dbo.Company.',
              1;
    END;


    /* =========================================================
       4. DATABASE PATH
       ========================================================= */

    SET @FullDatabasePath =
        QUOTENAME(@LoopIP)
        + '.'
        + QUOTENAME(@LoopDBID)
        + '.dbo';


    /* =========================================================
       5. QUERY MONTHLY
       ========================================================= */

    SET @DynamicSQL = N'

    
    /* Data Ascend diambil sekali lewat linked server; semua perhitungan di bawah membaca #P */
    SELECT p.PURCHASEID, p.PURCHASEDATE, pd.DETAILID, pd.LINETOTAL, pd.NETTO, pd.PRICEPERKG,
           sup.SupplierName, st.SUPPLIERTYPECODE, bg.BUSINESSGROUPNAME
      INTO #P
    FROM ' + @FullDatabasePath + N'.palm_ffbpurchases p


        INNER JOIN ' + @FullDatabasePath + N'.palm_ffbpurchasedetails pd

            ON p.PURCHASEID = pd.PURCHASEID


        INNER JOIN ' + @FullDatabasePath + N'.ap_suppliers sup

            ON p.SUPPLIERID = sup.SUPPLIERID


        LEFT JOIN ' + @FullDatabasePath + N'.ap_suppliertypes st

            ON sup.SUPPLIERTYPEID = st.SUPPLIERTYPEID


        LEFT JOIN ' + @FullDatabasePath + N'.ar_businessgroups bg

            ON sup.BUSINESSGROUPID = bg.BUSINESSGROUPID
     WHERE p.PURCHASEDATE >= @ParamTanggalAwal AND p.PURCHASEDATE < DATEADD(DAY, 1, @ParamTanggalAkhir);

/* =========================================================
       MONTH PERIOD
       ========================================================= */

    ;WITH MONTH_PERIOD AS
    (
        /* =====================================================
           BULAN PERTAMA
           ===================================================== */

        SELECT

            @ParamTanggalAwal AS MONTH_START,

            CASE

                WHEN EOMONTH(
                        @ParamTanggalAwal
                     ) > @ParamTanggalAkhir

                THEN @ParamTanggalAkhir

                ELSE EOMONTH(
                        @ParamTanggalAwal
                     )

            END AS MONTH_END


        UNION ALL


        /* =====================================================
           BULAN BERIKUTNYA
           ===================================================== */

        SELECT

            DATEADD(
                DAY,
                1,
                MONTH_END
            ) AS MONTH_START,

            CASE

                WHEN EOMONTH(
                        DATEADD(
                            DAY,
                            1,
                            MONTH_END
                        )
                     ) > @ParamTanggalAkhir

                THEN @ParamTanggalAkhir

                ELSE EOMONTH(
                        DATEADD(
                            DAY,
                            1,
                            MONTH_END
                        )
                     )

            END AS MONTH_END

        FROM MONTH_PERIOD

        WHERE MONTH_END < @ParamTanggalAkhir
    ),


    /* =========================================================
       6. PERIODS
       ========================================================= */

    PERIODS AS
    (
        SELECT

            MONTH_START,

            MONTH_END,

            CONCAT(

                CASE MONTH(MONTH_START)

                    WHEN 1 THEN ''Jan''
                    WHEN 2 THEN ''Feb''
                    WHEN 3 THEN ''Mar''
                    WHEN 4 THEN ''Apr''
                    WHEN 5 THEN ''May''
                    WHEN 6 THEN ''Jun''
                    WHEN 7 THEN ''Jul''
                    WHEN 8 THEN ''Aug''
                    WHEN 9 THEN ''Sep''
                    WHEN 10 THEN ''Oct''
                    WHEN 11 THEN ''Nov''
                    WHEN 12 THEN ''Dec''

                END,

                ''-'',

                YEAR(MONTH_START)

            ) AS PERIOD_LABEL

        FROM MONTH_PERIOD
    ),


    /* =========================================================
       7. RAW DATA
       ========================================================= */

    RAW AS
    (
        SELECT

            p.PURCHASEID,

            p.DETAILID,

            CAST(
                p.PURCHASEDATE AS DATE
            ) AS TANGGAL,

            p.LINETOTAL,

            p.NETTO,

            p.PRICEPERKG,

            p.SupplierName,

            p.BUSINESSGROUPNAME,

            p.SUPPLIERTYPECODE,

            ms.Company AS MAP_COMPANY,

            ms.Category AS MAP_CATEGORY,


            /* =================================================
               KATEGORI
               ================================================= */

            CASE

                /* =========================
                   YBS
                   ========================= */

                WHEN UPPER(
                        LTRIM(
                            RTRIM(@ParamComp)
                        )
                     ) = ''YBS''

                     AND UPPER(
                            LTRIM(
                                RTRIM(
                                    p.SUPPLIERTYPECODE
                                )
                            )
                         ) = ''GHS BRD''

                THEN ''Brondolan''


                WHEN UPPER(
                        LTRIM(
                            RTRIM(@ParamComp)
                        )
                     ) = ''YBS''

                     AND UPPER(
                            LTRIM(
                                RTRIM(
                                    p.SUPPLIERTYPECODE
                                )
                            )
                         ) IN
                         (
                            ''MITRA C'',
                            ''AGEN BINAA''
                         )

                THEN ''Agen''


                /* =========================
                   SUN
                   ========================= */

                WHEN UPPER(
                        LTRIM(
                            RTRIM(@ParamComp)
                        )
                     ) = ''SUN''

                     AND UPPER(
                            LTRIM(
                                RTRIM(
                                    p.SUPPLIERTYPECODE
                                )
                            )
                         ) = ''BRD''

                THEN ''Brondolan''


                WHEN UPPER(
                        LTRIM(
                            RTRIM(@ParamComp)
                        )
                     ) = ''SUN''

                     AND UPPER(
                            LTRIM(
                                RTRIM(
                                    p.SUPPLIERTYPECODE
                                )
                            )
                         ) IN
                         (
                            ''UMUM'',
                            ''TBS AGEN''
                         )

                THEN ''Agen''


                /* =========================
                   DEFAULT
                   ========================= */

                ELSE ''Kebun''

            END AS KATEGORI


        FROM #P p


        LEFT JOIN dbo.MappingSupplier ms

            ON p.SUPPLIERTYPECODE = ms.Supplier

           AND ms.Company =
               ''PT. '' + @ParamComp


        WHERE CAST(
                  p.PURCHASEDATE AS DATE
              )
              BETWEEN @ParamTanggalAwal
                  AND @ParamTanggalAkhir


        /* =================================================
           KHUSUS YBS

           AGEN BINAA
           PT. RIAU SAWIT INDAH
           TIDAK DIHITUNG
           ================================================= */

        AND NOT
        (
            UPPER(
                LTRIM(
                    RTRIM(@ParamComp)
                )
            ) = ''YBS''

            AND UPPER(
                    LTRIM(
                        RTRIM(
                            p.SUPPLIERTYPECODE
                        )
                    )
                ) = ''AGEN BINAA''

            AND UPPER(
                    LTRIM(
                        RTRIM(
                            p.BUSINESSGROUPNAME
                        )
                    )
                ) = ''PT. RIAU SAWIT INDAH''
        )
    ),


    /* =========================================================
       8. DATA PERIOD
       ========================================================= */

    DATA_PERIOD AS
    (
        SELECT

            r.*,

            p.PERIOD_LABEL,

            p.MONTH_START,

            p.MONTH_END

        FROM RAW r

        INNER JOIN PERIODS p

            ON r.TANGGAL
               BETWEEN p.MONTH_START
                   AND p.MONTH_END
    ),


    /* =========================================================
       9. GROUPED PER BULAN
       ========================================================= */

    GROUPED AS
    (
        SELECT

            MAP_COMPANY,

            SUPPLIERTYPECODE,

            BUSINESSGROUPNAME,

            KATEGORI,

            PERIOD_LABEL,

            MONTH_START,

            MONTH_END,


            /* =========================
               TONASE KG
               ========================= */

            SUM(
                ISNULL(
                    NETTO,
                    0
                )
            ) AS TONASE_KG,


            /* =========================
               TONASE TON
               ========================= */

            SUM(
                ISNULL(
                    NETTO,
                    0
                )
            ) / 1000.0 AS TONASE,


            /* =========================
               TOTAL NILAI
               ========================= */

            SUM(
                ISNULL(
                    LINETOTAL,
                    0
                )
            ) AS TOTAL_LINETOTAL,


            /* =========================
               HARGA BELI RATA-RATA
               ========================= */

            CASE

                WHEN SUM(
                        ISNULL(
                            NETTO,
                            0
                        )
                     ) = 0

                THEN 0

                ELSE

                    SUM(
                        ISNULL(
                            LINETOTAL,
                            0
                        )
                    )
                    /
                    SUM(
                        ISNULL(
                            NETTO,
                            0
                        )
                    )

            END AS HARGA_BELI_RATA2,


            /* =========================
               PRICE PER KG RATA-RATA
               ========================= */

            CASE

                WHEN SUM(
                        ISNULL(
                            NETTO,
                            0
                        )
                     ) = 0

                THEN 0

                ELSE

                    SUM(
                        ISNULL(NETTO, 0)
                        *
                        ISNULL(PRICEPERKG, 0)
                    )
                    /
                    SUM(
                        ISNULL(
                            NETTO,
                            0
                        )
                    )

            END AS PRICE_PER_KG_RATA2


        FROM DATA_PERIOD

        GROUP BY

            MAP_COMPANY,

            SUPPLIERTYPECODE,

            BUSINESSGROUPNAME,

            KATEGORI,

            PERIOD_LABEL,

            MONTH_START,

            MONTH_END
    ),


    /* =========================================================
       10. TOTAL BULANAN
       ========================================================= */

    MONTH_TOTAL AS
    (
        SELECT

            PERIOD_LABEL,

            MONTH_START,

            MONTH_END,


            /* =========================
               GRAND TOTAL
               ========================= */

            SUM(
                TONASE_KG
            ) AS TOTAL_TONASE_KG,


            SUM(
                TONASE
            ) AS TOTAL_TONASE,


            /* =========================
               AGEN
               ========================= */

            SUM(
                CASE

                    WHEN KATEGORI = ''Agen''

                    THEN TONASE

                    ELSE 0

                END
            ) AS AGEN_TOTAL_TON,


            /* =========================
               KEBUN
               ========================= */

            SUM(
                CASE

                    WHEN KATEGORI = ''Kebun''

                    THEN TONASE

                    ELSE 0

                END
            ) AS KEBUN_TOTAL_TON,


            /* =========================
               BRONDOLAN
               ========================= */

            SUM(
                CASE

                    WHEN KATEGORI = ''Brondolan''

                    THEN TONASE

                    ELSE 0

                END
            ) AS BRONDOLAN_TOTAL_TON


        FROM GROUPED

        GROUP BY

            PERIOD_LABEL,

            MONTH_START,

            MONTH_END
    )


    /* =========================================================
       11. HASIL AKHIR
       ========================================================= */

    SELECT

        @ParamComp AS COMPANY,


        G.MONTH_START AS TANGGAL_AWAL,

        G.MONTH_END AS TANGGAL_AKHIR,

        G.PERIOD_LABEL AS PERIODE,


        /* =========================
           SUPPLIER
           ========================= */

        G.SUPPLIERTYPECODE AS JENIS_KEBUN,

        G.BUSINESSGROUPNAME AS [GROUP],

        G.KATEGORI,


        /* =========================
           TONASE
           ========================= */

        G.TONASE_KG,

        G.TONASE,


        /* =========================
           NILAI
           ========================= */

        G.TOTAL_LINETOTAL,


        /* =========================
           HARGA
           ========================= */

        G.HARGA_BELI_RATA2,

        G.PRICE_PER_KG_RATA2,


        /* =========================
           TOTAL BULAN
           ========================= */

        WT.TOTAL_TONASE AS TOTAL_TONASE_BULAN,

        WT.AGEN_TOTAL_TON,

        WT.KEBUN_TOTAL_TON,

        WT.BRONDOLAN_TOTAL_TON,


        /* =========================
           PERSENTASE TOTAL
           ========================= */

        CASE

            WHEN WT.TOTAL_TONASE = 0

            THEN 0

            ELSE

                G.TONASE
                /
                WT.TOTAL_TONASE

        END AS PERSENTASE_TOTAL


    FROM GROUPED G

    INNER JOIN MONTH_TOTAL WT

        ON G.PERIOD_LABEL = WT.PERIOD_LABEL

       AND G.MONTH_START = WT.MONTH_START

       AND G.MONTH_END = WT.MONTH_END


    /* =========================
       URUTAN KATEGORI
       ========================= */

    ORDER BY

        G.MONTH_START,

        CASE

            WHEN G.KATEGORI = ''Kebun''
                THEN 0

            WHEN G.KATEGORI = ''Agen''
                THEN 1

            WHEN G.KATEGORI = ''Brondolan''
                THEN 2

            ELSE 3

        END,

        G.SUPPLIERTYPECODE,

        G.BUSINESSGROUPNAME


    OPTION (MAXRECURSION 0);

    ';


    /* =========================================================
       12. EXECUTE
       ========================================================= */

    EXEC sp_executesql

        @DynamicSQL,

        N'@ParamTanggalAwal DATE,
          @ParamTanggalAkhir DATE,
          @ParamComp NVARCHAR(10)',

        @ParamTanggalAwal = @TanggalAwal,

        @ParamTanggalAkhir = @TanggalAkhir,

        @ParamComp = @Company;

END;
GO
