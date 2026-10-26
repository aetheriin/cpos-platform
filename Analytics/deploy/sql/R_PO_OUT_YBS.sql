USE [Main]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

-- PO & PI, mengikuti pola R_PR_OUT_YBS_2: setiap baris PI ditautkan langsung ke baris PO lewat
-- AP_PURCHASEDETAILS.SOURCEID = AP_PURCHASEORDERDETAILS.PODETAILID, lalu qty PI dikonversi ke UOM baris PO.
-- Kolom hasil sama dengan versi sebelumnya, jadi dashboard tidak perlu diubah.
ALTER PROCEDURE [dbo].[R_PO_OUT_YBS]
    @COMP NVARCHAR(MAX),   -- daftar nama company dipisah koma
    @TYPE NVARCHAR(10),
    @DTFR NVARCHAR(12),    -- yyyymmdd (berdasarkan PO CREATEDATE)
    @DTTO NVARCHAR(8),     -- yyyymmdd
    @ST   INT
AS
BEGIN
    SET NOCOUNT ON;
    SET FMTONLY OFF;

    DECLARE @PO_ST NVARCHAR(25);

    -- 0 = VOID, 1 = COMPLETED, 2 = CLOSED, 3 = OUTSTANDING, 4 = ALL
    SELECT @PO_ST = IIF(@ST = 0, 'VOID', IIF(@ST = 1, 'COMPLETED', IIF(@ST = 2, '%CLOSED%', IIF(@ST = 3, '%[0123456789]%', '%'))));

    DECLARE @StartDT DATETIME = CONVERT(DATETIME, LEFT(@DTFR, 8), 112);
    DECLARE @EndDT   DATETIME = DATEADD(DAY, 1, CONVERT(DATETIME, LEFT(@DTTO, 8), 112));  -- eksklusif

    IF OBJECT_ID('tempdb..#TAB_PO')  IS NOT NULL DROP TABLE #TAB_PO;
    IF OBJECT_ID('tempdb..#PO_BASE') IS NOT NULL DROP TABLE #PO_BASE;
    IF OBJECT_ID('tempdb..#PI')      IS NOT NULL DROP TABLE #PI;

    CREATE TABLE #TAB_PO (
        COMPID            NVARCHAR(50),
        POID              NVARCHAR(50),
        PODETAILID        NVARCHAR(50),
        PONUMBER          NVARCHAR(100),
        PODATE            NVARCHAR(20),
        CREATEDDATE       NVARCHAR(20),
        CREATEDBY         NVARCHAR(50),
        ITEMID            NVARCHAR(50),
        ITEMCODE          NVARCHAR(50),
        ITEMNAME          NVARCHAR(MAX),
        CATEGORY          NVARCHAR(200),
        ITEMTYPE          NVARCHAR(200),
        UOMLEVEL          NVARCHAR(50),
        UOMNAME           NVARCHAR(50),
        QTYORDERED        DECIMAL(20, 6),
        QTYDELIVERED      DECIMAL(20, 6),    -- total qty PI, sudah dalam UOM baris PO
        QTYOUT            DECIMAL(20, 6),
        SUPPLIERCODE      NVARCHAR(MAX),
        SUPPLIERNAME      NVARCHAR(MAX),
        PURCHASEID        NVARCHAR(MAX),
        PURCHASENUMBER    NVARCHAR(MAX),
        PURCHASEDATE      NVARCHAR(MAX),     -- yyyymmdd, dipisah koma, urut tanggal
        ISCOMPLETE        BIT,
        ISVOID            BIT,
        POISCLOSE         BIT,
        ISCLOSE           BIT,
        ISOPEN            BIT,
        VOIDDT            NVARCHAR(20),
        CLOSEDT           NVARCHAR(20),
        AGING             NVARCHAR(60)
    );

    CREATE TABLE #PO_BASE (
        POID         NVARCHAR(50),
        PODETAILID   INT NOT NULL PRIMARY KEY,
        PONUMBER     NVARCHAR(100),
        PODATE       NVARCHAR(20),
        CREATEDDATE  NVARCHAR(20),
        CREATEDBY    NVARCHAR(50),
        SUPPLIERCODE NVARCHAR(MAX),
        SUPPLIERNAME NVARCHAR(MAX),
        ITEMID       NVARCHAR(50),
        ITEMCODE     NVARCHAR(50),
        ITEMNAME     NVARCHAR(MAX),
        CATEGORY     NVARCHAR(200),
        ITEMTYPE     NVARCHAR(200),
        UOMLEVEL     NVARCHAR(50),
        UOMNAME      NVARCHAR(50),
        CONVERTION   DECIMAL(20, 6),         -- IC_ITEMS.PACKING2, sama seperti PR & PO
        QTYORDERED   DECIMAL(20, 6),
        ISVOID       BIT,
        POISCLOSE    BIT,
        ISCLOSE      BIT,
        VOIDDT       NVARCHAR(20),
        CLOSEDT      NVARCHAR(20)
    );

    -- Satu baris per baris PI yang menunjuk baris PO di #PO_BASE
    CREATE TABLE #PI (
        PODETAILID     INT NOT NULL,
        PURCHASEID     INT NOT NULL,
        PURCHASENUMBER NVARCHAR(100),
        PURCHASEDATE   DATETIME,
        UOMLEVEL       NVARCHAR(50),
        QTY            DECIMAL(20, 6)
    );

    DECLARE @LoopCompany NVARCHAR(50);
    DECLARE @LoopIP      NVARCHAR(100);
    DECLARE @LoopDBID    NVARCHAR(100);
    DECLARE @FullDatabasePath NVARCHAR(MAX);
    DECLARE @SQL     NVARCHAR(MAX);
    DECLARE @MinDate DATETIME;

    DECLARE CompanyCursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT
        RTRIM(LTRIM(REPLACE(c.CompName, CHAR(160), ''))),
        RTRIM(LTRIM(c.CompAddr)),
        RTRIM(LTRIM(c.CompDataBase))
    FROM dbo.company c
    INNER JOIN STRING_SPLIT(@COMP, ',') s
        ON RTRIM(LTRIM(REPLACE(c.CompName, CHAR(160), ''))) = RTRIM(LTRIM(s.value))
    WHERE RTRIM(LTRIM(c.CompType)) = @TYPE
      AND c.Status = 1;

    OPEN CompanyCursor;
    FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @FullDatabasePath = QUOTENAME(@LoopIP) + '.' + QUOTENAME(@LoopDBID) + '.dbo.';

        TRUNCATE TABLE #PO_BASE;
        TRUNCATE TABLE #PI;

        ------------------------------------------------------------------
        -- 1) Baris PO yang dibuat dalam periode
        ------------------------------------------------------------------
        SET @SQL = N'
            INSERT INTO #PO_BASE (
                POID, PODETAILID, PONUMBER, PODATE, CREATEDDATE, CREATEDBY,
                SUPPLIERCODE, SUPPLIERNAME, ITEMID, ITEMCODE, ITEMNAME, CATEGORY, ITEMTYPE,
                UOMLEVEL, UOMNAME, CONVERTION, QTYORDERED, ISVOID, POISCLOSE, ISCLOSE, VOIDDT, CLOSEDT
            )
            SELECT
                hPO.POID, dPO.PODETAILID, hPO.PONUMBER,
                CONVERT(NVARCHAR(20), hPO.PODATE, 112),
                CONVERT(NVARCHAR(20), hPO.CREATEDATE, 112),
                hPO.CREATEDBY,
                supp.SUPPLIERCODE, supp.SUPPLIERNAME,
                dPO.ITEMID, ISNULL(item.ITEMCODE, ''''), item.ITEMNAME,
                cat.STOCKCATEGORYNAME, cat.ITEMTYPES,
                dPO.UOMLEVEL, uom.UOMCODE, item.PACKING2, dPO.QTYORDERED,
                CASE WHEN hPO.VOID = 1 THEN 1 ELSE 0 END,
                CASE WHEN hPO.CLOSED = 1 THEN 1 ELSE 0 END,
                CASE WHEN hPO.CLOSEDDATETIME IS NOT NULL THEN 1 ELSE 0 END,
                CONVERT(NVARCHAR(20), hPO.VOIDDATETIME, 112),
                CONVERT(NVARCHAR(20), hPO.CLOSEDDATETIME, 112)
            FROM ' + @FullDatabasePath + N'AP_PURCHASEORDERS hPO
            INNER JOIN ' + @FullDatabasePath + N'AP_PURCHASEORDERDETAILS dPO ON dPO.POID = hPO.POID
            LEFT JOIN ' + @FullDatabasePath + N'IC_ITEMS item ON item.ITEMID = dPO.ITEMID
            LEFT JOIN ' + @FullDatabasePath + N'IC_UOM uom
                   ON uom.UOMID = CASE WHEN dPO.UOMLEVEL = ''2'' THEN item.UOMID2 ELSE item.UOMID1 END
            LEFT JOIN ' + @FullDatabasePath + N'AP_SUPPLIERS supp ON supp.SUPPLIERID = hPO.SUPPLIERID
            LEFT JOIN ' + @FullDatabasePath + N'IC_STOCKCATEGORIES cat ON cat.STOCKCATEGORYID = item.CATEGORYID
            WHERE hPO.CREATEDATE >= @StartDT AND hPO.CREATEDATE < @EndDT;
        ';

        EXECUTE sp_executesql @SQL,
            N'@StartDT DATETIME, @EndDT DATETIME',
            @StartDT = @StartDT, @EndDT = @EndDT;

        IF EXISTS (SELECT 1 FROM #PO_BASE)
        BEGIN
            -- PI tidak mungkin lebih awal dari PO tertua
            SELECT @MinDate = MIN(CONVERT(DATETIME, PODATE, 112)) FROM #PO_BASE;

            ------------------------------------------------------------------
            -- 2) Baris PI yang bersumber dari PO, ditautkan lewat SOURCEID (bukan teks PONUMBERS + ITEMID).
            --    PI yang di-void tidak diambil sama sekali: qty, nomor, dan tanggalnya tidak ikut.
            --    AP_PURCHASES juga berisi dokumen lain (mis. PRT); tidak ada kolom jenisnya, jadi yang diambil hanya nomor /PI/.
            ------------------------------------------------------------------
            SET @SQL = N'
                INSERT INTO #PI (PODETAILID, PURCHASEID, PURCHASENUMBER, PURCHASEDATE, UOMLEVEL, QTY)
                SELECT dPI.SOURCEID, hPI.PURCHASEID, hPI.PURCHASENUMBER, hPI.PURCHASEDATE, dPI.UOMLEVEL, dPI.QUANTITY
                FROM ' + @FullDatabasePath + N'AP_PURCHASES hPI
                INNER JOIN ' + @FullDatabasePath + N'AP_PURCHASEDETAILS dPI ON dPI.PURCHASEID = hPI.PURCHASEID
                WHERE hPI.PURCHASEDATE >= @MinDate
                  AND ISNULL(hPI.VOID, 0) = 0
                  AND hPI.PURCHASENUMBER LIKE ''%/PI/%''
                  AND dPI.SOURCETYPE = ''PO''
                  AND dPI.SOURCEID IS NOT NULL;
            ';

            EXECUTE sp_executesql @SQL,
                N'@MinDate DATETIME', @MinDate = @MinDate;

            DELETE pi FROM #PI pi WHERE NOT EXISTS (SELECT 1 FROM #PO_BASE b WHERE b.PODETAILID = pi.PODETAILID);

            ------------------------------------------------------------------
            -- 3) Qty PI dalam UOM baris PO (konversi sama seperti PR & PO), lalu dijumlah per baris PO.
            --    Satu PI dengan beberapa baris ke baris PO yang sama dihitung satu nomor.
            ------------------------------------------------------------------
            ;WITH konversi AS (
                SELECT
                    pi.PODETAILID, pi.PURCHASEID, pi.PURCHASENUMBER, pi.PURCHASEDATE,
                    CASE
                        WHEN pi.UOMLEVEL = b.UOMLEVEL THEN pi.QTY
                        WHEN b.UOMLEVEL = '1' AND pi.UOMLEVEL = '2' THEN pi.QTY / ISNULL(NULLIF(b.CONVERTION, 0), 1)
                        WHEN b.UOMLEVEL = '2' AND pi.UOMLEVEL = '1' THEN pi.QTY * ISNULL(NULLIF(b.CONVERTION, 0), 1)
                        ELSE pi.QTY
                    END AS QTY
                FROM #PI pi
                INNER JOIN #PO_BASE b ON b.PODETAILID = pi.PODETAILID
            ),
            per_pi AS (
                SELECT PODETAILID, PURCHASEID, PURCHASENUMBER, PURCHASEDATE, SUM(QTY) AS QTY
                FROM konversi
                GROUP BY PODETAILID, PURCHASEID, PURCHASENUMBER, PURCHASEDATE
            ),
            per_po AS (
                SELECT
                    PODETAILID,
                    SUM(QTY) AS QTY,
                    STRING_AGG(CAST(PURCHASEID AS NVARCHAR(MAX)), ', ') WITHIN GROUP (ORDER BY PURCHASEDATE, PURCHASEID) AS PURCHASEID,
                    STRING_AGG(CAST(PURCHASENUMBER AS NVARCHAR(MAX)), ', ') WITHIN GROUP (ORDER BY PURCHASEDATE, PURCHASEID) AS PURCHASENUMBER,
                    STRING_AGG(CONVERT(NVARCHAR(MAX), CONVERT(VARCHAR(8), PURCHASEDATE, 112)), ', ') WITHIN GROUP (ORDER BY PURCHASEDATE, PURCHASEID) AS PURCHASEDATE
                FROM per_pi
                GROUP BY PODETAILID
            )
            INSERT INTO #TAB_PO (
                COMPID, POID, PODETAILID, PONUMBER, PODATE, CREATEDDATE, CREATEDBY,
                SUPPLIERCODE, SUPPLIERNAME, ITEMID, ITEMCODE, ITEMNAME, CATEGORY, ITEMTYPE,
                UOMLEVEL, UOMNAME, QTYORDERED, QTYDELIVERED,
                PURCHASEID, PURCHASENUMBER, PURCHASEDATE,
                ISCOMPLETE, ISVOID, POISCLOSE, ISCLOSE, ISOPEN, VOIDDT, CLOSEDT
            )
            SELECT
                @LoopCompany, b.POID, b.PODETAILID, b.PONUMBER, b.PODATE, b.CREATEDDATE, b.CREATEDBY,
                b.SUPPLIERCODE, b.SUPPLIERNAME, b.ITEMID, b.ITEMCODE, b.ITEMNAME, b.CATEGORY, b.ITEMTYPE,
                b.UOMLEVEL, b.UOMNAME, b.QTYORDERED, ISNULL(p.QTY, 0),
                p.PURCHASEID, p.PURCHASENUMBER, p.PURCHASEDATE,
                0, b.ISVOID, b.POISCLOSE, b.ISCLOSE, 1, b.VOIDDT, b.CLOSEDT
            FROM #PO_BASE b
            LEFT JOIN per_po p ON p.PODETAILID = b.PODETAILID;
        END;

        FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;
    END;

    CLOSE CompanyCursor;
    DEALLOCATE CompanyCursor;

    -- Sisa, status, dan aging (sama seperti sebelumnya)
    UPDATE t SET
        t.QTYOUT     = t.QTYORDERED - t.QTYDELIVERED,
        t.ISCOMPLETE = c.IS_COMPLETE,
        t.ISOPEN     = c.IS_OPEN,
        t.AGING      = CASE
                           WHEN t.ISVOID = 1       THEN 'VOID'
                           WHEN c.IS_OPEN = 1      THEN CAST(DATEDIFF(DAY, t.PODATE, GETDATE()) AS NVARCHAR(5))
                           WHEN c.IS_COMPLETE = 1  THEN 'COMPLETED'
                           WHEN t.ISCLOSE = 1 OR t.POISCLOSE = 1 THEN 'CLOSED'
                           ELSE '0'
                       END
    FROM #TAB_PO t
    CROSS APPLY (
        SELECT
            IS_COMPLETE = CASE WHEN t.QTYORDERED - t.QTYDELIVERED <= 0 THEN 1 ELSE 0 END,
            IS_OPEN     = CASE
                              WHEN t.QTYORDERED - t.QTYDELIVERED <= 0 OR t.ISCLOSE = 1 OR t.POISCLOSE = 1 OR t.ISVOID = 1 THEN 0
                              ELSE 1
                          END
    ) c;

    SELECT *
    FROM #TAB_PO
    WHERE AGING LIKE @PO_ST
    ORDER BY COMPID ASC, PODATE DESC, POID DESC, PODETAILID ASC;

    DROP TABLE #TAB_PO;
    DROP TABLE #PO_BASE;
    DROP TABLE #PI;
END;
GO
