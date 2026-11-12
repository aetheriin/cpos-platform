USE [Main];
GO
SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

ALTER PROCEDURE [dbo].[last_purchase_by_item]
    @Company  VARCHAR(10),
    @ItemCode VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @db SYSNAME;

    SET @db = CASE @Company
        WHEN 'SJN' THEN 'as_sjn'
        WHEN 'YBS' THEN 'as_ybs222'
        WHEN 'SUN' THEN 'as_sun_ybs'
        WHEN 'ORI' THEN 'as_ori'
        ELSE NULL
    END;

    IF @db IS NULL
    BEGIN
        RAISERROR('Company tidak valid: %s', 16, 1, @Company);
        RETURN;
    END;

    CREATE TABLE #Result
    (
        Company          VARCHAR(10),
        ItemCode         NVARCHAR(100),
        ItemName         NVARCHAR(MAX),
        PurchaseNo       NVARCHAR(100),
        PurchaseDate     DATETIME,
        SupplierID       INT,
        SupplierName     NVARCHAR(MAX),
        Qty              DECIMAL(19,4),
        Cost             DECIMAL(19,4),
        WarehouseName    NVARCHAR(200),
        WarehouseBalance DECIMAL(19,4),
        TotalBalance     DECIMAL(19,4)
    );

    DECLARE @InnerSQL NVARCHAR(MAX) = N'
        SET NOCOUNT ON;

        DECLARE @ToMajor BIT = 1;
        DECLARE @ItemCode VARCHAR(100) = ''__ITEMCODE__'';

        CREATE TABLE #ItemBalance
        (
            ItemID INT,
            WarehouseID INT,
            UOMLevel TINYINT,
            Balance MONEY
        );

        IF dbo.UDF_SH_Settings_GetAsBit(
            ''USP_IC_Items_StockListForAPI.ToMinor'', 0
        ) = 1
        BEGIN
            SET @ToMajor = 0;
        END;

        EXEC USP_IC_Items_Calculate
            @AllItems = 1,
            @PerDate = NULL,
            @OutputKind = ''PerLocationBalanceReports'',
            @OutputTable = ''#ItemBalance'',
            @IncludeBroken = 1,
            @IncludeConsignmentOutlets = 1,
            @GoodStockOnly = NULL;

        SELECT
            X.ItemID,
            X.WarehouseID,
            FLOOR(
                CASE
                    WHEN @ToMajor = 1 THEN
                        X.Balance /
                        dbo.UDF_Common_ConvertToSmallestUOMEx(
                            I.Packing2, I.Packing3, I.Packing4, 1, 1
                        )
                    ELSE X.Balance
                END
            ) AS Balance
        INTO #WH
        FROM
        (
            SELECT
                I.ItemID,
                IB.WarehouseID,
                SUM(
                    dbo.UDF_Common_ConvertToSmallestUOMEx(
                        I.Packing2, I.Packing3, I.Packing4,
                        IB.Balance, IB.UOMLevel
                    )
                ) AS Balance
            FROM #ItemBalance IB
            INNER JOIN IC_Items I
                ON I.ItemID = IB.ItemID
            WHERE I.ItemCode = @ItemCode
            GROUP BY I.ItemID, IB.WarehouseID
        ) X
        INNER JOIN IC_Items I
            ON I.ItemID = X.ItemID;

        SELECT TOP 1
            IT.ItemID,
            IT.ItemCode,
            IT.ItemName,
            P.PurchaseNumber AS PurchaseNo,
            P.PurchaseDate,
            P.SupplierID,
            S.SupplierName,
            D.Quantity AS Qty,
            D.Cost
        INTO #LP
        FROM IC_Items IT
        INNER JOIN AP_PurchaseDetails D
            ON D.ItemID = IT.ItemID
        INNER JOIN AP_Purchases P
            ON P.PurchaseID = D.PurchaseID
        LEFT JOIN AP_Suppliers S
            ON S.SupplierID = P.SupplierID
        WHERE IT.ItemCode = @ItemCode
        ORDER BY
            P.PurchaseDate DESC,
            P.PurchaseID DESC;

        SELECT
            ''__COMPANY__'' AS Company,
            LP.ItemCode,
            LP.ItemName,
            LP.PurchaseNo,
            LP.PurchaseDate,
            LP.SupplierID,
            LP.SupplierName,
            LP.Qty,
            LP.Cost,
            W.Name AS WarehouseName,
            ISNULL(WH.Balance, 0) AS WarehouseBalance,
            ISNULL(SUM(WH.Balance) OVER (PARTITION BY LP.ItemID), 0) AS TotalBalance
        FROM #LP LP
        CROSS JOIN IC_Warehouses W
        LEFT JOIN #WH WH
            ON  WH.ItemID = LP.ItemID
            AND WH.WarehouseID = W.WarehouseID
        ORDER BY W.Name;

        DROP TABLE #ItemBalance;
        DROP TABLE #WH;
        DROP TABLE #LP;
    ';

    DECLARE @CurrentInner NVARCHAR(MAX) = @InnerSQL;

    SET @CurrentInner = REPLACE(@CurrentInner, '__COMPANY__', REPLACE(@Company, '''', ''''''));
    SET @CurrentInner = REPLACE(@CurrentInner, '__ITEMCODE__', REPLACE(@ItemCode, '''', ''''''));
    SET @CurrentInner = REPLACE(@CurrentInner, '''', '''''');

    DECLARE @RemoteCall NVARCHAR(MAX) =
        N'EXEC ' + QUOTENAME(@db) + N'..sp_executesql N''' + @CurrentInner + N'''';

    SET XACT_ABORT OFF;

    INSERT INTO #Result
    EXEC (@RemoteCall) AT [ASCEND_CLOUD];

    SELECT
        Company,
        ItemCode,
        ItemName,
        PurchaseNo,
        PurchaseDate,
        SupplierID,
        SupplierName,
        Qty,
        Cost,
        WarehouseName,
        WarehouseBalance,
        TotalBalance
    FROM #Result
    ORDER BY WarehouseName;

    DROP TABLE #Result;
END;
GO
