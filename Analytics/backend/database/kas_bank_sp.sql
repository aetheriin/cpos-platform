-- Laporan Kas & Bank: dua SP di database test, versi yang bisa mengambil rentang beberapa bulan sekaligus dan satu rekening saja.
-- Parameter lama (@PERIOD saja) tetap berjalan seperti sebelumnya, jadi pemanggil lain tidak terpengaruh.
--   @PERIOD          YYYYMM bulan pertama
--   @PERIOD_AKHIR    YYYYMM bulan terakhir (NULL = sama dengan @PERIOD)
--   @COMPID          satu perusahaan (NULL = semua perusahaan CLOUD)
--   @BANKACCOUNTCODE satu rekening (NULL = semua rekening aktif)
-- Aplikasi memanggil satu rekening per panggilan secara bersamaan, dengan rentang 1 Januari sampai bulan ini: ledger report ERP
-- hanya dipanggil sekali per rekening (sebelumnya sekali per rekening per bulan, berurutan).
-- Versi asli disimpan di kas_bank_sp_asli.sql.
USE test;
GO

ALTER PROCEDURE [dbo].[SP_GET_BANKDAILYDETAILS]
	@PERIOD NVARCHAR(6),
	@PERIOD_AKHIR NVARCHAR(6) = NULL,
	@COMPID NVARCHAR(50) = NULL,
	@BANKACCOUNTCODE NVARCHAR(100) = NULL
AS
BEGIN
	SET NOCOUNT ON;

	CREATE TABLE #BankHistory (
        Tag nvarchar(max), BankAccount NVARCHAR(MAX), DocumentDate DATE, DocumentID nvarchar(max), DocumentNo NVARCHAR(MAX),
        DocumentTypeID NVARCHAR(MAX), DocumentType NVARCHAR(MAX), AssociateID NVARCHAR(MAX), AssociateType NVARCHAR(MAX),
        AssociateCode NVARCHAR(MAX), AssociateName NVARCHAR(MAX), Amount DECIMAL(18,4), ForceDB DECIMAL(18,4), ForceCR DECIMAL(18,4),
        AmtIn DECIMAL(18,4), AmtOut DECIMAL(18,4), AmtBalance DECIMAL(18,4), StateImage NVARCHAR(MAX), Remarks NVARCHAR(MAX),
        VoucherRemarks NVARCHAR(MAX), IsOB BIT, VoucherID int, VoucherTypeID NVARCHAR(MAX), VoucherNo NVARCHAR(MAX), CheckNo NVARCHAR(MAX),
        ExchangeRate DECIMAL(18,4), LocalBalance DECIMAL(18,4), LocalAmount DECIMAL(18,4), Rate DECIMAL(18,4), TransRate DECIMAL(18,4),
        DetailID int, DeliveryOrder NVARCHAR(MAX), ContractNo NVARCHAR(MAX), CashFlowID int, SummarizedRemarks NVARCHAR(MAX),
        CashFlowDescription NVARCHAR(MAX), SubDocumentNo NVARCHAR(MAX), CFRemarks NVARCHAR(MAX), CashFlowCode NVARCHAR(MAX),
        VoucherCreateBy NVARCHAR(MAX), Netto DECIMAL(18,4), DocumentDateTime date, PriorityIndex int, VoucherInternalRemarks nvarchar(max),
        DeductedPPh DECIMAL(18,4), AmountTax DECIMAL(18,4), BankAccountCode nvarchar(max), BankName NVARCHAR(MAX), AccountNo NVARCHAR(MAX),
        AccountOwner NVARCHAR(MAX)
    );
    -- hasil = kolom COMPANYID + semua kolom #BankHistory, urutannya sama dengan versi lama
    SELECT CAST(NULL AS NVARCHAR(50)) AS COMPANYID, * INTO #BANKRESULT FROM #BankHistory WHERE 1 = 0;

    DECLARE @STARTDATE NVARCHAR(8) = @PERIOD + '01';
    DECLARE @ENDDATE NVARCHAR(8) = CONVERT(NVARCHAR(8), EOMONTH(ISNULL(@PERIOD_AKHIR, @PERIOD) + '01'), 112);
    DECLARE @COMP NVARCHAR(50), @IP NVARCHAR(100), @DB NVARCHAR(100), @KODE NVARCHAR(100), @AMAN NVARCHAR(200), @SQL NVARCHAR(MAX);

    DECLARE Rekening CURSOR LOCAL FAST_FORWARD FOR
        SELECT C.COMPNM, C.IPADDRESS, C.[DBID], B.BANKACCOUNTCODE, B.SECURITYCODE
        FROM dbo.company C
        INNER JOIN dbo.BANK B ON B.COMPID = C.COMPNM AND B.ACTIVE = 1
        WHERE C.[TYPE] = 'CLOUD'
          AND (@COMPID IS NULL OR C.COMPNM = @COMPID)
          AND (@BANKACCOUNTCODE IS NULL OR B.BANKACCOUNTCODE = @BANKACCOUNTCODE);

    OPEN Rekening;
    FETCH NEXT FROM Rekening INTO @COMP, @IP, @DB, @KODE, @AMAN;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SQL = N'EXEC ' + QUOTENAME(@IP) + N'.' + QUOTENAME(@DB) + N'.dbo.USP_FI_BankAccounts_LedgerReport @a, @k, @s, @e';
        INSERT INTO #BankHistory
        EXEC sp_executesql @SQL, N'@a NVARCHAR(200), @k NVARCHAR(100), @s NVARCHAR(8), @e NVARCHAR(8)', @AMAN, @KODE, @STARTDATE, @ENDDATE;

        INSERT INTO #BANKRESULT SELECT @COMP, * FROM #BankHistory;
        TRUNCATE TABLE #BankHistory;
        FETCH NEXT FROM Rekening INTO @COMP, @IP, @DB, @KODE, @AMAN;
    END
    CLOSE Rekening;
    DEALLOCATE Rekening;

    SELECT * FROM #BANKRESULT;
END
GO

ALTER PROCEDURE [dbo].[SP_GET_GIROTRANSACTION]
	@PERIOD NVARCHAR(6),
	@PERIOD_AKHIR NVARCHAR(6) = NULL,
	@COMPID NVARCHAR(50) = NULL
AS
BEGIN
	SET NOCOUNT ON;

	CREATE TABLE #GIRO (
		COMPID NVARCHAR(50), VOUCHERID INT, VOUCHERDATE DATE, VOUCHERNO NVARCHAR(MAX), ASSOCIATENAME NVARCHAR(MAX),
		BANKACCOUNTID INT, BANKACCOUNTCODE NVARCHAR(MAX), AMOUNT DECIMAL(18, 4), PERIODE NVARCHAR(6)
	);

    DECLARE @MULAI DATE = CAST(@PERIOD + '01' AS DATE);
    DECLARE @SELESAI DATE = DATEADD(DAY, 1, EOMONTH(CAST(ISNULL(@PERIOD_AKHIR, @PERIOD) + '01' AS DATE)));
    DECLARE @COMP NVARCHAR(50), @IP NVARCHAR(100), @DB NVARCHAR(100), @AKUN NVARCHAR(20), @ID INT, @KODE NVARCHAR(100), @SQL NVARCHAR(MAX);

    -- Satu kueri per pasangan akun giro dan rekening, seperti versi lama, tapi tanggal disaring langsung di kolomnya (bisa memakai indeks)
    DECLARE Giro CURSOR LOCAL FAST_FORWARD FOR
        SELECT C.COMPNM, C.IPADDRESS, C.[DBID], ACC.ACCOUNTCODE, B.BANKACCOUNTID, B.BANKACCOUNTCODE
        FROM dbo.company C
        INNER JOIN dbo.GIROACCOUNT ACC ON ACC.COMPID = C.COMPNM
        INNER JOIN dbo.BANK B ON B.COMPID = ACC.COMPID AND B.ACTIVE = 1
        WHERE C.[TYPE] = 'CLOUD' AND (@COMPID IS NULL OR C.COMPNM = @COMPID);

    OPEN Giro;
    FETCH NEXT FROM Giro INTO @COMP, @IP, @DB, @AKUN, @ID, @KODE;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SQL = N'SELECT @c, h.VOUCHERID, h.VOUCHERDATE, h.VOUCHERNO, h.ASSOCIATENAME, h.BANKACCOUNTID, @k, h.AMOUNTPAID,
                CONVERT(NVARCHAR(6), h.VOUCHERDATE, 112)
            FROM ' + QUOTENAME(@IP) + N'.' + QUOTENAME(@DB) + N'.DBO.FI_ARAP h
            INNER JOIN ' + QUOTENAME(@IP) + N'.' + QUOTENAME(@DB) + N'.DBO.FI_ARAPEXTRAITEMS d ON h.VOUCHERID = d.VOUCHERID
            INNER JOIN ' + QUOTENAME(@IP) + N'.' + QUOTENAME(@DB) + N'.DBO.AC_ACCOUNTS A ON d.ACCOUNTID = A.ACCOUNTID
            WHERE h.ISAR = 1 AND h.VOID = 0 AND A.ACCOUNTCODE = @a AND h.BANKACCOUNTID = @i
              AND h.VOUCHERDATE >= @m AND h.VOUCHERDATE < @s';
        INSERT INTO #GIRO
        EXEC sp_executesql @SQL, N'@c NVARCHAR(50), @k NVARCHAR(100), @a NVARCHAR(20), @i INT, @m DATE, @s DATE',
            @COMP, @KODE, @AKUN, @ID, @MULAI, @SELESAI;
        FETCH NEXT FROM Giro INTO @COMP, @IP, @DB, @AKUN, @ID, @KODE;
    END
    CLOSE Giro;
    DEALLOCATE Giro;

    SELECT * FROM #GIRO;
END
GO
