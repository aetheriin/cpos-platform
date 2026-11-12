-- Stored procedure laporan Kas & Bank (bank statement), dibuat di database Main. Pengganti query yang dulu dikirim aplikasi (ledger.py).
-- Satu perusahaan per panggilan; aplikasi memanggil semua perusahaan bersamaan.
--   @CompID  perusahaan, mis. 'YBS' (server dan database ERP dibaca dari dbo.company)
--   @Bagian  'MUTASI' = transaksi bank @Mulai..@Akhir, kolom seperti ledger bank ERP (USP_FI_BankAccounts_QueryHistory, @ForLedger = 1)
--            'SALDO'  = saldo per rekening sebelum @Mulai (membaca seluruh riwayat, lambat; aplikasi menyimpan hasilnya)
--            'GIRO'   = jasa giro @Mulai..@Akhir (aturan SP_GET_GIROTRANSACTION), @Akun = kode akun giro dipisah |
--            'KURS'   = kurs voucher rekening valas per tanggal @Mulai..@Akhir
--   @Mulai, @Akhir  tanggal, @Akhir ikut dihitung
--   @Kode    kode rekening bank dipisah |, mis. 'BNI IDR|BNI USD'
-- Data mentah saja: urutan, saldo berjalan, kurs, dan rupiah dihitung di aplikasi (laporan/kas_bank/sumber.py).
-- Hanya MEMBACA database ERP; yang ditulis hanya tabel sementara (#).
-- Jalankan sekali di database Main, lalu cek: EXEC dbo.KAS_BANK 'YBS', 'MUTASI', '2026-10-01', '2026-10-31', 'BNI IDR';
CREATE OR ALTER PROCEDURE dbo.KAS_BANK
    @CompID varchar(10),
    @Bagian varchar(10),
    @Mulai date,
    @Akhir date,
    @Kode nvarchar(max) = N'',
    @Akun nvarchar(max) = N''
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
    END

    DECLARE @b nvarchar(max);
    IF @Bagian IN ('MUTASI', 'SALDO') SET @b = N'
SET NOCOUNT ON
-- SALDO: saldo sebelum @Mulai (seluruh riwayat, lambat). MUTASI: transaksi @Mulai sampai @Akhir saja; saldo awal dari simpanan aplikasi.
DECLARE @DateFrom DATETIME = dbo.UDF_Common_FloorDate (@Mulai)
DECLARE @DateEnd DATETIME = dbo.UDF_Common_FloorDate (CASE WHEN @Bagian = ''SALDO'' THEN DATEADD(day, -1, @Mulai) ELSE @Akhir END)

-- Rekening yang diminta (kode dipisah |). Ledger ERP: satu @BankAccountID per panggilan.
SELECT BankAccountID, BankAccountCode, BankName INTO #Rek FROM FI_BankAccounts
 WHERE ''|'' + @Kode + ''|'' LIKE ''%|'' + RTRIM(BankAccountCode) + ''|%''   -- tanpa STRING_SPLIT: tingkat kompatibilitas database ERP lama
DECLARE @Ids VARCHAR(MAX) = STUFF((SELECT '','' + CAST(BankAccountID AS VARCHAR(20)) FROM #Rek FOR XML PATH('''')), 1, 1, '''')

CREATE TABLE #History (
	BankAccountID INT, OrderIndex INT IDENTITY(1,1), DocumentDate DATETIME, DocumentDateTime DATETIME, DocumentID INT, PriorityIndex INT,
	DocumentNumber VARCHAR(50), DocumentTypeID VARCHAR(50), Amount MONEY, Balance MONEY, Remarks VARCHAR(5000), AssociateType VARCHAR(1),
	AssociateID INT, AssociateCode VARCHAR(1000), AssociateName VARCHAR(1000), XtraID INT NOT NULL DEFAULT(0), VoucherRemarks VARCHAR(5000),
	ExchangeRate MONEY, LocalAmount MONEY, LocalBalance MONEY, TransRate MONEY, DetailID INT NOT NULL DEFAULT(0),
	SummarizedAs VARCHAR(50) NOT NULL DEFAULT(''''), CashFlowID INT NOT NULL DEFAULT(0), SubDocumentID INT NOT NULL DEFAULT(0), CFRemarks VARCHAR(80) NULL)
CREATE INDEX IX_1 ON #History (XtraID)
CREATE INDEX IX_2 ON #History (AssociateID)
CREATE INDEX IX_3 ON #History (DocumentID)
CREATE INDEX IX_4 ON #History (BankAccountID)

DECLARE @MasterTable VARCHAR(300), @DetailTable VARCHAR(300), @SubDetailTable VARCHAR(300), @SubDetailJoin VARCHAR(300), @DateField VARCHAR(300),
	@VoidField VARCHAR(300), @AmountField VARCHAR(200), @AssociateField VARCHAR(300), @AssociateType VARCHAR(300), @DocumentIDField VARCHAR(300),
	@DocumentNumberField VARCHAR(300), @JoinCondition VARCHAR(2000), @ExtraFilter VARCHAR(2000), @SQL NVARCHAR(MAX), @PriorityIndex INT,
	@BankAccountIDField VARCHAR(300), @WhereExpr VARCHAR(5000), @AltAssociateNameField VARCHAR(300), @DetailsField VARCHAR(300),
	@SummarizedAs VARCHAR(300), @DocumentTypeID VARCHAR(30), @IsPositive BIT

DECLARE XCursor CURSOR LOCAL FOR
 SELECT DateField, DetailTable, MasterTable, JoinCondition, AmountField, VoidField, ExtraFilter, BankAccountIDField,
        SubDetailTable, SubDetailJoin, DocumentIDField, DocumentNumberField, DocumentTypeID, PriorityIndex, AssociateType, AssociateField, IsPositive,
        CASE WHEN MasterTable NOT IN (''FI_Deposit'', ''FI_Reconcile'') THEN AltAssociateNameField ELSE '''' END, DetailsField, SummarizedAs
   FROM SH_BankCalculations WITH (NOLOCK)
OPEN XCursor
FETCH FROM XCursor INTO @DateField, @DetailTable, @MasterTable, @JoinCondition, @AmountField, @VoidField, @ExtraFilter, @BankAccountIDField,
	@SubDetailTable, @SubDetailJoin, @DocumentIDField, @DocumentNumberField, @DocumentTypeID, @PriorityIndex, @AssociateType, @AssociateField,
	@IsPositive, @AltAssociateNameField, @DetailsField, @SummarizedAs
WHILE @@FETCH_STATUS = 0 BEGIN
	IF ISNULL(@DetailsField, '''') = '''' SET @DetailsField = ''NULL''
	SET @SQL = ''INSERT #History (SummarizedAs, BankAccountID, DocumentDate, DocumentDateTime, DocumentID, DocumentNumber, DocumentTypeID, Amount, PriorityIndex, Remarks, AssociateID, AssociateType, AssociateName, XtraID, ExchangeRate, DetailID, SubDocumentID)''
	SET @SQL = @SQL + CHAR(13) + ''SELECT @SummarizedAs, '' + @BankAccountIDField + '', '' + @DateField + '', '' +
		CASE WHEN @MasterTable = ''PALM_Tickets'' THEN ''NULL'' ELSE ''M.CreateDate'' END + '', M.'' + @DocumentIDField + '', '' + @DocumentNumberField + '', @DocumentTypeID, '' +
		CASE WHEN ISNULL(@IsPositive, 0) = 1 THEN '''' ELSE ''-'' END + ''ISNULL('' + @AmountField + '', 0), @PriorityIndex, '' + @DetailsField + '', '' +
		CASE WHEN LEN(@AssociateField) > 0 THEN @AssociateField ELSE ''NULL'' END + '', @AssociateType, '' + CASE WHEN ISNULL(@AltAssociateNameField, '''') > '''' THEN @AltAssociateNameField ELSE ''NULL'' END +
		'', '' + CASE WHEN @DetailTable IN (''FI_ClearingDetails'',''FI_TransferConfDetails'') THEN ''I.VoucherID'' ELSE ''0'' END + '', 1, '' +
		CASE WHEN @MasterTable = ''FI_Deposit'' AND @DetailTable > '''' THEN ''I.DepositDetailID'' WHEN @MasterTable = ''FI_Clearing'' THEN ''I.ClearingDetailID'' ELSE ''0'' END + '', '' +
		CASE WHEN @DetailTable = ''FI_ReconcileDetails'' THEN ''I.ReconcileDetailID'' WHEN @SubDetailTable = ''FI_ARAP'' THEN ''SDT.VoucherID'' ELSE ''0'' END
	IF @DetailTable > '''' BEGIN
		SET @SQL = @SQL + CHAR(13) + ''  FROM '' + @DetailTable + '' I '' + CASE WHEN @DetailTable NOT LIKE ''(%'' THEN ''WITH (NOLOCK) '' ELSE '''' END
		SET @SQL = @SQL + CHAR(13) + ''  JOIN '' + @MasterTable + '' M WITH (NOLOCK) ON '' + @JoinCondition
	END ELSE
		SET @SQL = @SQL + CHAR(13) + ''  FROM '' + @MasterTable + '' M WITH (NOLOCK) ''
	IF @SubDetailTable > '''' AND @SubDetailJoin > ''''
		SET @SQL = @SQL + CHAR(13) + ''  JOIN '' + @SubDetailTable + '' SDT WITH (NOLOCK) ON '' + @SubDetailJoin
	SET @WhereExpr = @DateField + '' <= @EndDate''
	IF LEN(ISNULL(@VoidField, '''')) > 0 SET @WhereExpr = @WhereExpr + '' AND '' + @VoidField + '' != 1''
	IF LEN(ISNULL(@ExtraFilter, '''')) > 0 SET @WhereExpr = @WhereExpr + '' AND '' + @ExtraFilter
	SET @WhereExpr = @WhereExpr + '' AND '' + @BankAccountIDField + '' IN ('' + @Ids + '')''   -- ledger ERP: = @BankAccountID
	IF @Bagian = ''MUTASI'' SET @WhereExpr = @WhereExpr + '' AND '' + @DateField + '' >= @StartDate''   -- tanpa riwayat lama; saldo awal dari cache
	SET @SQL = @SQL + CHAR(13) + '' WHERE '' + @WhereExpr
	EXEC SP_ExecuteSQL @SQL, N''@StartDate DATETIME, @EndDate DATETIME, @DocumentTypeID VARCHAR(80), @PriorityIndex INT, @BankAccountID INT, @AssociateType VARCHAR(1), @SummarizedAs VARCHAR(50)'',
		@DateFrom, @DateEnd, @DocumentTypeID, @PriorityIndex, 0, @AssociateType, @SummarizedAs
	FETCH FROM XCursor INTO @DateField, @DetailTable, @MasterTable, @JoinCondition, @AmountField, @VoidField, @ExtraFilter, @BankAccountIDField,
		@SubDetailTable, @SubDetailJoin, @DocumentIDField, @DocumentNumberField, @DocumentTypeID, @PriorityIndex, @AssociateType, @AssociateField,
		@IsPositive, @AltAssociateNameField, @DetailsField, @SummarizedAs
END
DEALLOCATE XCursor

UPDATE #History
   SET DocumentTypeID = ''BS.'' + CASE WHEN V.IsAR = 1 THEN ''AR'' ELSE ''AP'' END, DocumentID = V.VoucherID, DocumentNumber = V.VoucherNo
  FROM #History H
	JOIN FI_ClearingDetails CD ON CD.ClearingDetailID = H.DetailID
	JOIN FI_ARAP V ON V.VoucherID = CD.VoucherID
 WHERE DocumentTypeID LIKE ''%Clearing%'' AND dbo.UDF_SH_Settings_GetAsBit (''FI_BankAccounts.ShowClearing'', 0) = 0

IF dbo.UDF_SH_Settings_GetAsBit (''SeparateBankCharge'', 0) = 1 BEGIN
	UPDATE #History
	   SET Amount = Amount + dbo.UDF_Common_ConvertRate(0, (CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * ((V.BCLocal*0)+(V.BankCharges+V.BankCharges2))),
			CASE WHEN V.IsAR = 0 AND BA.CurrencyID != V.CurrencyID THEN V.ExchangeRate WHEN V.IsAR = 0 THEN 1 ELSE CashRate END)
	  FROM #History H
		JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
		JOIN FI_BankAccounts BA ON BA.BankAccountID = H.BankAccountID   -- ledger ERP: mata uang rekening yang diminta
	 WHERE H.DocumentTypeID LIKE ''BS.A[RP]'' AND SummarizedAs IN (''Receipt'', ''Payment'', ''PaymentTransfer'')

	UPDATE #History
	   SET Amount = Amount + (CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * ((V.BCLocal*0)+dbo.UDF_Common_ConvertRate(0, V.BankCharges+V.BankCharges2, CashRate)))
	  FROM #History H
		JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
	 WHERE H.DocumentTypeID LIKE ''BS.A[RP]'' AND SummarizedAs IN (''Expense'',''ExpenseT'',''Income'')

	UPDATE #History SET Amount = Amount + dbo.UDF_FI_Clearing_GetBankCharges (H.DocumentID) FROM #History H WHERE H.DocumentTypeID LIKE ''BS.Clearing''

	INSERT #History (BankAccountID, DocumentDate, DocumentDateTime, DocumentID, PriorityIndex, DocumentNumber, DocumentTypeID, Amount, Balance, Remarks,
	                 AssociateType, AssociateID, AssociateCode, AssociateName, XtraID, VoucherRemarks, ExchangeRate, SummarizedAs)
	SELECT H.BankAccountID, H.DocumentDate, H.DocumentDateTime, H.DocumentID, H.PriorityIndex, H.DocumentNumber, H.DocumentTypeID,
	       CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * -dbo.UDF_Common_ConvertRate (0, V.BankCharges, V.CashRate), NULL,
	       dbo.UDF_Common_CombineDescription (''Bank Charges'', H.Remarks, ''''),
	       H.AssociateType, H.AssociateID, H.AssociateCode, H.AssociateName, H.XtraID, H.VoucherRemarks, H.ExchangeRate, H.SummarizedAs
	  FROM #History H JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
	 WHERE H.DocumentTypeID LIKE ''BS.A[RP]'' AND V.BankCharges != 0 AND SummarizedAs IN (''Receipt'', ''Payment'', ''PaymentTransfer'', ''Expense'',''ExpenseT'',''Income'')

	INSERT #History (BankAccountID, DocumentDate, DocumentDateTime, DocumentID, PriorityIndex, DocumentNumber, DocumentTypeID, Amount, Balance, Remarks,
	                 AssociateType, AssociateID, AssociateCode, AssociateName, XtraID, VoucherRemarks, ExchangeRate, SummarizedAs)
	SELECT H.BankAccountID, H.DocumentDate, H.DocumentDateTime, H.DocumentID, H.PriorityIndex, H.DocumentNumber, H.DocumentTypeID,
	       CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * dbo.UDF_Common_ConvertRate (0, V.BCLocal, 1), NULL,
	       dbo.UDF_Common_CombineDescription (''Bank Charges'', H.Remarks, ''''),
	       H.AssociateType, H.AssociateID, H.AssociateCode, H.AssociateName, H.XtraID, H.VoucherRemarks, H.ExchangeRate, H.SummarizedAs
	  FROM #History H
		JOIN FI_TransferConf TC ON TC.TransferConfID = H.DocumentID
		JOIN FI_TransferConfDetails TCD ON TC.TransferConfID = TCD.TransferConfID
		JOIN FI_ARAP V ON V.VoucherID = TCD.VoucherID
	 WHERE H.DocumentTypeID LIKE ''BS.TransferConf'' AND V.BCLocal != 0

	-- ledger ERP: hanya baris rekening yang diminta (H.BankAccountID = @BankAccountID), jadi di sini untuk semua rekening
	INSERT #History (BankAccountID, DocumentDate, DocumentDateTime, DocumentID, PriorityIndex, DocumentNumber, DocumentTypeID, Amount, Balance, Remarks,
	                 AssociateType, AssociateID, AssociateCode, AssociateName, XtraID, VoucherRemarks, ExchangeRate, SummarizedAs)
	SELECT DISTINCT H.BankAccountID, H.DocumentDate, H.DocumentDateTime, H.DocumentID, H.PriorityIndex, H.DocumentNumber, H.DocumentTypeID,
	       CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * dbo.UDF_Common_ConvertRate (0, V.BCLocal, 1), NULL,
	       dbo.UDF_Common_CombineDescription (''Bank Charges'', '''', ''''),
	       H.AssociateType, H.AssociateID, H.AssociateCode, H.AssociateName, H.XtraID, H.VoucherRemarks, H.ExchangeRate, H.SummarizedAs
	  FROM #History H JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
	 WHERE H.DocumentTypeID LIKE ''BS.A[RP]'' AND V.BCLocal != 0 AND SummarizedAs IN (''Receipt'', ''Payment'', ''PaymentTransfer'', ''Expense'',''ExpenseT'',''Income'')
	   AND dbo.UDF_SH_Settings_GetAsBit (''USP_FI_BankAccounts_QueryHistory.AddBCLocal'', 1) = 1

	INSERT #History (BankAccountID, DocumentDate, DocumentDateTime, DocumentID, PriorityIndex, DocumentNumber, DocumentTypeID, Amount, Balance, Remarks,
	                 AssociateType, AssociateID, AssociateCode, AssociateName, XtraID, VoucherRemarks, ExchangeRate, SummarizedAs)
	SELECT H.BankAccountID, H.DocumentDate, H.DocumentDateTime, H.DocumentID, H.PriorityIndex, H.DocumentNumber, H.DocumentTypeID,
	       CASE WHEN V.IsAR = 0 THEN -1 ELSE 1 END * -dbo.UDF_Common_ConvertRate (0, V.BankCharges2, V.CashRate), NULL,
	       dbo.UDF_Common_CombineDescription (''Bank Charges 2'', H.Remarks, ''''),
	       H.AssociateType, H.AssociateID, H.AssociateCode, H.AssociateName, H.XtraID, H.VoucherRemarks, H.ExchangeRate, H.SummarizedAs
	  FROM #History H JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
	 WHERE H.DocumentTypeID LIKE ''BS.A[RP]'' AND V.BankCharges2 != 0 AND SummarizedAs IN (''Receipt'', ''Payment'', ''PaymentTransfer'', ''Expense'',''ExpenseT'',''Income'')
	   AND H.Remarks NOT LIKE ''Bank Charges%''

	INSERT #History (BankAccountID, DocumentDate, DocumentDateTime, DocumentID, PriorityIndex, DocumentNumber, DocumentTypeID, Amount, Balance, Remarks,
	                 AssociateType, AssociateID, AssociateCode, AssociateName, XtraID, VoucherRemarks, ExchangeRate, SummarizedAs)
	SELECT H.BankAccountID, H.DocumentDate, H.DocumentDateTime, H.DocumentID, H.PriorityIndex, H.DocumentNumber, H.DocumentTypeID,
	       -1 * dbo.UDF_FI_Clearing_GetBankCharges (H.DocumentID), NULL,
	       dbo.UDF_Common_CombineDescription (''Bank Charges'', H.Remarks, ''''),
	       H.AssociateType, H.AssociateID, H.AssociateCode, H.AssociateName, H.XtraID, H.VoucherRemarks, H.ExchangeRate, H.SummarizedAs
	  FROM #History H
	 WHERE H.DocumentTypeID LIKE ''BS.Clearing'' AND dbo.UDF_FI_Clearing_GetBankCharges (H.DocumentID) != 0
END

-- Saldo awal per rekening (ledger ERP: baris "Beginning Balance", hanya kalau tidak nol)
IF @Bagian = ''SALDO'' BEGIN
	SELECT RTRIM(K.BankAccountCode) BankAccountCode, SUM(H.Amount) Amount
	  FROM #History H JOIN #Rek K ON K.BankAccountID = H.BankAccountID
	 WHERE H.DocumentDate < @DateFrom GROUP BY K.BankAccountCode HAVING SUM(H.Amount) != 0
	RETURN
END

DELETE #History WHERE DocumentDate < @DateFrom

UPDATE #History SET DocumentTypeID = CASE WHEN V.Class = 1 THEN ''HMS.FO.ReceiptVoucher'' ELSE ''HMS.FO.DepositVoucher'' END
  FROM #History H JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
 WHERE V.Class > 0 AND V.IsAR = 1 AND DocumentTypeID = ''BS.AR''

UPDATE #History SET Remarks = dbo.UDF_Common_CombineDescription (''Ext. Ref: '' + ExternalRef, H.Remarks, '''')
  FROM #History H JOIN FI_ARAP V ON V.VoucherID = H.DocumentID
 WHERE DocumentTypeID LIKE ''BS.A[RP]'' AND V.ExternalRef != ''''

UPDATE #History
   SET Remarks = LEFT(ISNULL(dbo.UDF_Common_CombineRemarks (dbo.UDF_Common_CombineRemarks (CASE WHEN DocumentTypeID = ''HRM.Loan'' THEN ''Pinjaman ke '' ELSE ''Pelunasan Pinjaman dari '' END + E.FullName, R.Remarks), L.Remarks), ''''), 3000)
  FROM #History R JOIN HRM_Loans L ON L.LoanID = R.DocumentID JOIN HRM_Employees E ON E.EmployeeID = L.EmployeeID
 WHERE DocumentTypeID LIKE ''HRM.Loan%''

UPDATE #History
   SET Remarks = LEFT(ISNULL(dbo.UDF_Common_CombineRemarks (dbo.UDF_Common_CombineRemarks (''Pencairan Simpanan ke '' + E.FullName, R.Remarks), L.Remarks), ''''), 3000)
  FROM #History R JOIN HRM_SavingWithdrawals L ON L.SavingWithdrawalID = R.DocumentID JOIN HRM_Employees E ON E.EmployeeID = L.EmployeeID
 WHERE DocumentTypeID = ''HRM.SavingWithdrawal''

UPDATE #History
   SET AssociateType = CASE WHEN V.IsAR = 1 THEN ''C'' ELSE ''S'' END, AssociateID = V.AssociateID, Remarks = dbo.UDF_FI_Deposit_GetDescription (D.DepositID)
  FROM #History R JOIN FI_Deposit D ON D.DepositID = R.DocumentID JOIN FI_ARAP V ON V.VoucherID = D.SourceARAPVoucherID
 WHERE DocumentTypeID = ''BS.Deposit''

UPDATE #History SET Remarks = dbo.UDF_FI_Deposit_GetDescription (D.DepositID)
  FROM #History R JOIN FI_Deposit D ON D.DepositID = R.DocumentID LEFT JOIN FI_ARAP V ON V.VoucherID = D.SourceARAPVoucherID
 WHERE DocumentTypeID = ''BS.Deposit'' AND V.VoucherID IS NULL

UPDATE #History SET AssociateName = RTRIM(B.BankName + '' '' + B.AccountNo)
  FROM #History R
	JOIN FI_Deposit D ON D.DepositID = R.DocumentID AND DocumentTypeID = ''BS.Deposit''
	JOIN FI_BankAccounts B ON B.BankAccountID = CASE WHEN R.BankAccountID = D.SourceBankAccountID THEN D.DestinationBankAccountID ELSE D.SourceBankAccountID END

UPDATE #History SET AssociateName = RTRIM(B.BankName + '' '' + B.AccountNo)
  FROM #History R JOIN FI_Reconcile D ON D.ReconcileID = R.DocumentID AND DocumentTypeID = ''BS.Reconcile'' JOIN FI_BankAccounts B ON B.BankAccountID = D.BankAccountID

UPDATE #History
   SET Remarks = UPPER(dbo.UDF_Common_CombineText5(COALESCE(dbo.UDF_Common_NullIfEmpty(AX.VehicleNo), AX.AssetCode), DV.DriverName, R.Remarks, '''', ''''))
  FROM #History R
	JOIN BI_DriverLedgers D ON D.DriverLedgerID = R.DocumentID AND DocumentTypeID = ''BI.DriverLedger''
	LEFT JOIN TRS_Drivers DV ON DV.DriverID = D.DriverID
	LEFT JOIN FA_Assets AX ON AX.AssetID = D.AssetID

UPDATE #History SET AssociateName = DV.DriverName
  FROM #History R JOIN BI_DriverLedgers D ON D.DriverLedgerID = R.DocumentID AND DocumentTypeID = ''BI.DriverLedger'' JOIN TRS_Drivers DV ON DV.DriverID = D.DriverID

-- Transaksi dalam periode, kolom dan urutan seperti hasil ledger ERP
SELECT RTRIM(K.BankAccountCode) BankAccountCode, K.BankName, R.DocumentDate, R.DocumentDateTime, R.DocumentNumber DocumentNo, R.DocumentTypeID, R.AssociateType,
       COALESCE(PCU.UserName, CASE WHEN ISNULL(R.AssociateName, '''') > '''' THEN R.AssociateName WHEN R.AssociateType = ''C'' THEN C.CustomerName
                WHEN R.AssociateType = ''S'' THEN S.SupplierName ELSE AEN.PayTo END) AssociateName,
       R.Amount,
       ISNULL(CASE WHEN R.DocumentTypeID LIKE ''BS.Purchase%'' THEN dbo.UDF_AP_Purchases_GetItemDetails(R.DocumentID)
                   WHEN PCV.Remarks IS NOT NULL THEN PCV.Remarks
                   WHEN R.DocumentTypeID LIKE ''BS.A[RP]Note'' OR R.DocumentTypeID LIKE ''BS.A[RP]DiscountNote'' THEN RN.Remarks
                   WHEN R.DocumentTypeID LIKE ''BS.AssetExpenseNote'' THEN dbo.UDF_FA_AssetExpenseNotes_GetItemDetails (R.DocumentID)
                   WHEN LEN(VX.Remarks) > 0 THEN VX.Remarks
                   WHEN R.XtraID > 0 THEN VX.VoucherNo
                   WHEN DD.DepositID > 0 AND LEN(DD.BDCheckNo) > 0 THEN DD.BDCheckNo + CASE WHEN LEN(R.Remarks) > 0 THEN '' -- '' ELSE '''' END + R.Remarks
                   ELSE R.Remarks END, '''') Remarks,
       VX.CreatedBy VoucherCreateBy, R.PriorityIndex
  FROM #History R
	JOIN #Rek K ON K.BankAccountID = R.BankAccountID
	LEFT JOIN AR_Customers C ON C.CustomerID = R.AssociateID AND R.AssociateType = ''C''
	LEFT JOIN AP_Suppliers S ON S.SupplierID = R.AssociateID AND R.AssociateType = ''S''
	LEFT JOIN FA_AssetExpenseNotes AEN ON AEN.AssetExpenseID = R.DocumentID AND R.DocumentTypeID LIKE ''BS.AssetExpenseNote''
	LEFT JOIN FI_PendingCashV2 PCV ON PCV.PendingCashID = R.DocumentID AND R.DocumentTypeID = ''BS.PendingCashV2''
	LEFT JOIN FI_PendingCashUsers PCU ON PCU.UserID = PCV.UserID
	LEFT JOIN FI_ARAP VX ON VX.VoucherID = CASE WHEN R.XtraID > 0 THEN R.XtraID WHEN R.DocumentTypeID LIKE ''BS.A[RP]'' THEN R.DocumentID ELSE 0 END
	LEFT JOIN FI_Deposit DD ON DD.DepositID = R.DocumentID AND R.DocumentTypeID = ''BS.Deposit''
	LEFT JOIN FI_ARAPNotes RN ON RN.ARAPNoteID = R.DocumentID AND (R.DocumentTypeID LIKE ''BS.A[RP]Note'' OR R.DocumentTypeID LIKE ''BS.A[RP]DiscountNote'')
 ORDER BY K.BankAccountCode, R.DocumentDate, CASE WHEN SIGN(R.Amount) >= 0 THEN 1 ELSE 2 END, R.DocumentDateTime, R.PriorityIndex

';
    ELSE IF @Bagian = 'GIRO' SET @b = N'SET NOCOUNT ON
SELECT h.VOUCHERDATE, h.VOUCHERNO, h.ASSOCIATENAME, RTRIM(b.BankAccountCode) BANKACCOUNTCODE, h.AMOUNTPAID AS AMOUNT
  FROM FI_ARAP h
  JOIN FI_ARAPEXTRAITEMS d ON h.VOUCHERID = d.VOUCHERID
  JOIN AC_ACCOUNTS A ON d.ACCOUNTID = A.ACCOUNTID
  JOIN FI_BankAccounts b ON b.BankAccountID = h.BANKACCOUNTID
 WHERE h.ISAR = 1 AND h.VOID = 0 AND h.VOUCHERDATE >= @Mulai AND h.VOUCHERDATE < DATEADD(day, 1, @Akhir)
   AND ''|'' + @Akun + ''|'' LIKE ''%|'' + RTRIM(A.ACCOUNTCODE) + ''|%''
   AND ''|'' + @Kode + ''|'' LIKE ''%|'' + RTRIM(b.BankAccountCode) + ''|%''
';
    ELSE IF @Bagian = 'KURS' SET @b = N'SET NOCOUNT ON
SELECT CAST(h.VoucherDate AS DATE) AS Tanggal, c.Currency, h.ExchangeRate, COUNT(*) AS Jumlah
  FROM FI_ARAP h
  JOIN FI_BankAccounts b ON b.BankAccountID = h.BankAccountID
  JOIN CO_Currency c ON c.CurrencyID = b.CurrencyID
 WHERE h.VOID = 0 AND c.Currency <> ''IDR'' AND h.ExchangeRate > 1 AND h.VoucherDate >= @Mulai AND h.VoucherDate < DATEADD(day, 1, @Akhir)
   AND NOT EXISTS (SELECT 1 FROM CO_ExchangeRate e WHERE e.SourceCurrencyID = b.CurrencyID AND e.Rate = h.ExchangeRate)
 GROUP BY CAST(h.VoucherDate AS DATE), c.Currency, h.ExchangeRate
';
    ELSE
    BEGIN
        RAISERROR('@Bagian harus MUTASI, SALDO, GIRO, atau KURS.', 16, 1);
        RETURN;
    END

    -- Dijalankan di dalam database ERP perusahaan itu (objek ERP ditulis tanpa nama database, seperti di SP ERP aslinya).
    DECLARE @x nvarchar(max) = N'EXEC ' + QUOTENAME(@Server) + N'.' + QUOTENAME(@DB) + N'.dbo.sp_executesql @b, '
        + N'N''@Mulai datetime, @Akhir datetime, @Kode nvarchar(max), @Akun nvarchar(max), @Bagian varchar(10)'', @Mulai, @Akhir, @Kode, @Akun, @Bagian';
    EXEC sp_executesql @x, N'@b nvarchar(max), @Mulai datetime, @Akhir datetime, @Kode nvarchar(max), @Akun nvarchar(max), @Bagian varchar(10)',
        @b, @Mulai, @Akhir, @Kode, @Akun, @Bagian;
END
GO

GRANT EXECUTE ON dbo.KAS_BANK TO pythonReport;
GO
