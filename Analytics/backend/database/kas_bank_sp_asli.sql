-- Versi asli SP Kas & Bank (diambil 2026-11-03), untuk dikembalikan kalau perlu: ganti CREATE jadi ALTER lalu jalankan.
USE test;
GO
-- =============================================
-- Author:		<Author,,Name>
-- Create date: <Create Date,,>
-- Description:	<Description,,>
-- =============================================
CREATE PROCEDURE [dbo].[SP_GET_BANKDAILYDETAILS] --'202608' 
	@PERIOD NVARCHAR(6)
AS
BEGIN
	-- SET NOCOUNT ON added to prevent extra result sets from
	-- interfering with SELECT statements.
	SET NOCOUNT ON;

	IF OBJECT_ID('tempdb..#BankHistory') IS NOT NULL DROP TABLE #BankHistory;
	IF OBJECT_ID('tempdb..#BANKRESULT') IS NOT NULL DROP TABLE #BANKRESULT;
    -- Insert statements for procedure here
	CREATE TABLE #BankHistory (
        Tag nvarchar(max),
        BankAccount NVARCHAR(MAX),
        DocumentDate DATE,
        DocumentID nvarchar(max),
        DocumentNo NVARCHAR(MAX),
        DocumentTypeID NVARCHAR(MAX),
        DocumentType NVARCHAR(MAX),
        --DocumentReference NVARCHAR(MAX),
        AssociateID NVARCHAR(MAX),
        AssociateType NVARCHAR(MAX),
        AssociateCode NVARCHAR(MAX),
        AssociateName NVARCHAR(MAX),
        Amount DECIMAL(18,4),
        ForceDB DECIMAL(18,4),
        ForceCR DECIMAL(18,4),
        AmtIn DECIMAL(18,4),
        AmtOut DECIMAL(18,4),
        AmtBalance DECIMAL(18,4),
        StateImage NVARCHAR(MAX),
        Remarks NVARCHAR(MAX),
        VoucherRemarks NVARCHAR(MAX),
        IsOB BIT,
        VoucherID int,
        VoucherTypeID NVARCHAR(MAX),
        VoucherNo NVARCHAR(MAX),
        CheckNo NVARCHAR(MAX),
        ExchangeRate DECIMAL(18,4),
        LocalBalance DECIMAL(18,4),
        LocalAmount DECIMAL(18,4),
        Rate DECIMAL(18,4),
        TransRate DECIMAL(18,4),
        DetailID int,
        DeliveryOrder NVARCHAR(MAX),
        ContractNo NVARCHAR(MAX),
        CashFlowID int,
        SummarizedRemarks NVARCHAR(MAX),
        CashFlowDescription NVARCHAR(MAX),
        SubDocumentNo NVARCHAR(MAX),
        CFRemarks NVARCHAR(MAX),
        CashFlowCode NVARCHAR(MAX),
        VoucherCreateBy NVARCHAR(MAX),
        Netto DECIMAL(18,4),
        DocumentDateTime date,
        PriorityIndex int,
        VoucherInternalRemarks nvarchar(max),
        DeductedPPh DECIMAL(18,4),
        AmountTax DECIMAL(18,4),
        BankAccountCode nvarchar(max),
        BankName NVARCHAR(MAX),
        AccountNo NVARCHAR(MAX),
        AccountOwner NVARCHAR(MAX)
    )
    CREATE TABLE #BANKRESULT (
        COMPANYID nvarchar(max),
        Tag nvarchar(max),
        BankAccount NVARCHAR(MAX),
        DocumentDate DATE,
        DocumentID nvarchar(max),
        DocumentNo NVARCHAR(MAX),
        DocumentTypeID NVARCHAR(MAX),
        DocumentType NVARCHAR(MAX),
        --DocumentReference NVARCHAR(MAX),
        AssociateID NVARCHAR(MAX),
        AssociateType NVARCHAR(MAX),
        AssociateCode NVARCHAR(MAX),
        AssociateName NVARCHAR(MAX),
        Amount DECIMAL(18,4),
        ForceDB DECIMAL(18,4),
        ForceCR DECIMAL(18,4),
        AmtIn DECIMAL(18,4),
        AmtOut DECIMAL(18,4),
        AmtBalance DECIMAL(18,4),
        StateImage NVARCHAR(MAX),
        Remarks NVARCHAR(MAX),
        VoucherRemarks NVARCHAR(MAX),
        IsOB BIT,
        VoucherID int,
        VoucherTypeID NVARCHAR(MAX),
        VoucherNo NVARCHAR(MAX),
        CheckNo NVARCHAR(MAX),
        ExchangeRate DECIMAL(18,4),
        LocalBalance DECIMAL(18,4),
        LocalAmount DECIMAL(18,4),
        Rate DECIMAL(18,4),
        TransRate DECIMAL(18,4),
        DetailID int,
        DeliveryOrder NVARCHAR(MAX),
        ContractNo NVARCHAR(MAX),
        CashFlowID int,
        SummarizedRemarks NVARCHAR(MAX),
        CashFlowDescription NVARCHAR(MAX),
        SubDocumentNo NVARCHAR(MAX),
        CFRemarks NVARCHAR(MAX),
        CashFlowCode NVARCHAR(MAX),
        VoucherCreateBy NVARCHAR(MAX),
        Netto DECIMAL(18,4),
        DocumentDateTime date,
        PriorityIndex int,
        VoucherInternalRemarks nvarchar(max),
        DeductedPPh DECIMAL(18,4),
        AmountTax DECIMAL(18,4),
        BankAccountCode nvarchar(max),
        BankName NVARCHAR(MAX),
        AccountNo NVARCHAR(MAX),
        AccountOwner NVARCHAR(MAX)
    )

	DECLARE @LoopCompany NVARCHAR(50);
    DECLARE @LoopIP       NVARCHAR(100);
    DECLARE @LoopDBID     NVARCHAR(100);
    DECLARE @STARTDATE NVARCHAR(8), @ENDDATE NVARCHAR(8)
    
    SET @STARTDATE = @PERIOD + '01'
    SELECT @ENDDATE = CONVERT(NVARCHAR(8), EOMONTH(@STARTDATE), 112)


	DECLARE CompanyCursor CURSOR LOCAL FOR 
    SELECT COMPNM, IPADDRESS, [DBID] 
    FROM dbo.company WHERE [TYPE] = 'CLOUD';

	OPEN CompanyCursor;
    FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        DECLARE @BANKID NVARCHAR(2), 
            @BANKCODE NVARCHAR(100),
            @BANKNAME NVARCHAR(200),
            @SECURITYCODE NVARCHAR(200)
        DECLARE BANKCursor CURSOR LOCAL FOR 
        SELECT BANKACCOUNTID, BANKACCOUNTCODE, BANKNAME, SECURITYCODE 
        FROM BANK WHERE COMPID LIKE @LoopCompany AND ACTIVE = 1;
	    
        OPEN BANKCursor;
        FETCH NEXT FROM BANKCURSOR INTO @BANKID, 
            @BANKCODE,
            @BANKNAME,
            @SECURITYCODE;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            DECLARE @SQL NVARCHAR(MAX)
            SET @SQL = N'EXEC ' + QUOTENAME(@LoopIP) + N'.' + QUOTENAME(@LoopDBID) + N'.dbo.USP_FI_BankAccounts_LedgerReport ''' + @SECURITYCODE + ''',''' + @BANKCODE + ''',''' + @STARTDATE + ''', ''' + @ENDDATE + ''''
            INSERT INTO #bankhistory
            EXEC SP_EXECUTESQL @SQL

            INSERT INTO #BANKRESULT 
            SELECT @LoopCompany, * FROM #BankHistory
            DELETE #BankHistory
            FETCH NEXT FROM BANKCURSOR INTO @BANKID, 
                @BANKCODE,
                @BANKNAME,
                @SECURITYCODE;
        END

        CLOSE BANKCURSOR
        DEALLOCATE BANKCURSOR

		FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;
	END
    CLOSE COMPANYCURSOR
    DEALLOCATE COMPANYCURSOR

    --UPDATE #BankHistory SET DocumentDate = @STARTDATE WHERE DocumentDate IS NULL
    SELECT * FROM #BANKRESULT
END

GO
-- =============================================
-- Author:		<Author,,Name>
-- Create date: <Create Date,,>
-- Description:	<Description,,>
-- =============================================
CREATE PROCEDURE [dbo].[SP_GET_GIROTRANSACTION]--'' 
	@PERIOD NVARCHAR(6)
AS
BEGIN
	-- SET NOCOUNT ON added to prevent extra result sets from
	-- interfering with SELECT statements.
	SET NOCOUNT ON;

	IF OBJECT_ID('tempdb..#GIRO') IS NOT NULL DROP TABLE #GIRO;

	CREATE TABLE #GIRO (
		COMPID NVARCHAR(50),
		VOUCHERID INT,
		VOUCHERDATE DATE,
		VOUCHERNO NVARCHAR(MAX),
		ASSOCIATENAME NVARCHAR(MAX),
		BANKACCOUNTID INT,
		BANKACCOUNTCODE NVARCHAR(MAX),
		AMOUNT DECIMAL(18, 4),
		PERIODE NVARCHAR(6)
	)


	DECLARE @LoopCompany NVARCHAR(50);
    DECLARE @LoopIP       NVARCHAR(100);
    DECLARE @LoopDBID     NVARCHAR(100);

	DECLARE CompanyCursor CURSOR LOCAL FOR 
    SELECT COMPNM, IPADDRESS, [DBID] 
    FROM dbo.company WHERE [TYPE] LIKE 'CLOUD';

	OPEN CompanyCursor;
    FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;
	DECLARE @SQL NVARCHAR(MAX)

    WHILE @@FETCH_STATUS = 0
    BEGIN
		DECLARE @FullDatabasePath NVARCHAR(MAX)
        SET @FullDatabasePath = QUOTENAME(@LoopIP) + '.' + QUOTENAME(@LoopDBID);

		DECLARE @ACCOUNTCODE NVARCHAR(20), @BANKACCOUNTID NVARCHAR(20), @BANKACCOUNTCODE NVARCHAR(100)
		
		DECLARE RATE CURSOR LOCAL FOR 
		SELECT ACCOUNTCODE, BANKACCOUNTID, BANKACCOUNTCODE
		FROM GIROACCOUNT ACC INNER JOIN BANK B ON B.COMPID = ACC.COMPID AND B.COMPID LIKE @LoopCompany AND B.ACTIVE = 1;
		
		OPEN RATE;
		FETCH NEXT FROM RATE INTO @ACCOUNTCODE, @BANKACCOUNTID, @BANKACCOUNTCODE;

		WHILE @@FETCH_STATUS = 0
		BEGIN
			SET @SQL = N'SELECT ''' + @LoopCompany + ''', 
					h.VOUCHERID,
					h.VOUCHERDATE,
					h.VOUCHERNO,
					h.ASSOCIATENAME,
					h.BANKACCOUNTID,
					''' + @BANKACCOUNTCODE + ''',
					h.AMOUNTPAID,
					CONVERT(NVARCHAR(6), h.VOUCHERDATE, 112)
				FROM ' + @FullDatabasePath + '.DBO.FI_ARAP h 
				INNER JOIN ' + @FullDatabasePath + '.DBO.FI_ARAPEXTRAITEMS d 
				ON h.VOUCHERID = d.VOUCHERID AND h.ISAR = 1 AND h.VOID = 0
				INNER JOIN ' + @FullDatabasePath + '.DBO.AC_ACCOUNTS A
				ON d.ACCOUNTID = A.ACCOUNTID 
				AND A.ACCOUNTCODE = ''' + @ACCOUNTCODE + ''' 
				AND h.BANKACCOUNTID = ''' + @BANKACCOUNTID + '''
				AND CONVERT(NVARCHAR(6), h.VOUCHERDATE, 112) = ''' + @PERIOD + ''''
				
			--PRINT @SQL
			INSERT INTO #GIRO
			EXEC SP_EXECUTESQL @SQL
			FETCH NEXT FROM RATE INTO @ACCOUNTCODE, @BANKACCOUNTID, @BANKACCOUNTCODE;
		END

		CLOSE RATE
		DEALLOCATE RATE

		FETCH NEXT FROM CompanyCursor INTO @LoopCompany, @LoopIP, @LoopDBID;
	END
	CLOSE COMPANYCURSOR
	DEALLOCATE COMPANYCURSOR

	SELECT * FROM #GIRO
END

GO
