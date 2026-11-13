/* Tahap 2A: lepaskan ketergantungan FK Contract/DOTransport ke master lokal.
   Kolom legacy tetap dipertahankan sebagai nullable untuk kompatibilitas histori.
   Tidak menghapus Supplier/Product dan tidak menghapus data transaksi.
   Jalankan setelah 026; target Main; rerunnable.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
USE [Main];
GO
IF OBJECT_ID('dbo.SchemaLog','U') IS NULL
    THROW 51028, 'SchemaLog tidak ditemukan di Main.', 1;
IF OBJECT_ID('dbo.Contract','U') IS NULL OR OBJECT_ID('dbo.DOTransport','U') IS NULL
    THROW 51028, 'Contract/DOTransport tidak ditemukan.', 1;
IF COL_LENGTH('dbo.Contract','AscendCustomerID') IS NULL
   OR COL_LENGTH('dbo.Contract','CustomerNameSnapshot') IS NULL
   OR COL_LENGTH('dbo.Contract','ProductNameSnapshot') IS NULL
   OR COL_LENGTH('dbo.DOTransport','AscendTransportID') IS NULL
   OR COL_LENGTH('dbo.DOTransport','TransportNameSnapshot') IS NULL
    THROW 51028, 'Jalankan migration 026 terlebih dahulu.', 1;
GO
BEGIN TRANSACTION;
-- FK bernama sesuai schema.sql CPOS. Drop hanya relasi master lokal, bukan tabel.
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_Contract_Supplier' AND parent_object_id=OBJECT_ID('dbo.Contract'))
    ALTER TABLE dbo.Contract DROP CONSTRAINT FK_Contract_Supplier;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_Contract_Product' AND parent_object_id=OBJECT_ID('dbo.Contract'))
    ALTER TABLE dbo.Contract DROP CONSTRAINT FK_Contract_Product;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_DOTrans_Supplier' AND parent_object_id=OBJECT_ID('dbo.DOTransport'))
    ALTER TABLE dbo.DOTransport DROP CONSTRAINT FK_DOTrans_Supplier;

-- ID lokal lama masih ada untuk histori, tetapi transaksi baru dapat memakai Ascend ID.
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.Contract') AND name='SupplierID' AND is_nullable=0)
    ALTER TABLE dbo.Contract ALTER COLUMN SupplierID INT NULL;
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.Contract') AND name='ProductID' AND is_nullable=0)
    ALTER TABLE dbo.Contract ALTER COLUMN ProductID INT NULL;

IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script='database/perubahan/028_contract_ascend_nullable.sql')
    INSERT INTO dbo.SchemaLog (Script,App) VALUES ('database/perubahan/028_contract_ascend_nullable.sql','CPOS');
COMMIT TRANSACTION;
GO
