/* Nama menu laporan /an/po_amt menjadi PO Spend Analysis. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
UPDATE dbo.Menu SET MenuName = N'PO Spend Analysis' WHERE MenuCode = 'AN_PO_AMT';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/016_nama_po_spend.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/016_nama_po_spend.sql', 'CPOS');
GO
