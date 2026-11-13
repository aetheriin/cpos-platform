/* Tahap 3 PREP: lepaskan FK Supplier/Product dari transaksi non-Kontrak/DO.
   WAJIB setelah refactor code VehicleContract, Invoice, WeightBridge, ProductPrice, FlowRule.
   Tidak menghapus tabel/data. Simpan SupplierID/ProductID legacy nullable untuk histori.
   Target Main. Rerunnable.
*/
SET NOCOUNT ON; SET XACT_ABORT ON; USE [Main];
IF OBJECT_ID('dbo.SchemaLog','U') IS NULL THROW 51030,'SchemaLog tidak ditemukan.',1;
IF COL_LENGTH('dbo.VehicleContract','AscendSupplierID') IS NULL
 OR COL_LENGTH('dbo.Invoice','AscendSupplierID') IS NULL
 OR COL_LENGTH('dbo.WeightBridge','AscendCustomerID') IS NULL
 OR COL_LENGTH('dbo.ProductPrice','ProductNameSnapshot') IS NULL
 OR COL_LENGTH('dbo.FlowRule','ProductNameSnapshot') IS NULL
 THROW 51030,'Jalankan migration 026 dahulu.',1;
BEGIN TRANSACTION;
DECLARE @tbl SYSNAME,@fk SYSNAME,@sql NVARCHAR(500);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
 SELECT OBJECT_NAME(fk.parent_object_id),fk.name
 FROM sys.foreign_keys fk
 WHERE fk.parent_object_id IN (OBJECT_ID('dbo.VehicleContract'),OBJECT_ID('dbo.Invoice'),OBJECT_ID('dbo.WeightBridge'),OBJECT_ID('dbo.ProductPrice'),OBJECT_ID('dbo.FlowRule'))
 AND fk.referenced_object_id IN (OBJECT_ID('dbo.Supplier'),OBJECT_ID('dbo.Product'));
OPEN c; FETCH NEXT FROM c INTO @tbl,@fk;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @sql=N'ALTER TABLE dbo.'+QUOTENAME(@tbl)+N' DROP CONSTRAINT '+QUOTENAME(@fk)+N';';
 EXEC sys.sp_executesql @sql;
 FETCH NEXT FROM c INTO @tbl,@fk;
END;
CLOSE c; DEALLOCATE c;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.VehicleContract') AND name='SupplierID' AND is_nullable=0)
 ALTER TABLE dbo.VehicleContract ALTER COLUMN SupplierID INT NULL;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.VehicleContract') AND name='ProductID' AND is_nullable=0)
 ALTER TABLE dbo.VehicleContract ALTER COLUMN ProductID INT NULL;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.Invoice') AND name='SupplierID' AND is_nullable=0)
 ALTER TABLE dbo.Invoice ALTER COLUMN SupplierID INT NULL;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.WeightBridge') AND name='SupplierID' AND is_nullable=0)
 ALTER TABLE dbo.WeightBridge ALTER COLUMN SupplierID INT NULL;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.WeightBridge') AND name='ProductID' AND is_nullable=0)
 ALTER TABLE dbo.WeightBridge ALTER COLUMN ProductID INT NULL;
IF NOT EXISTS(SELECT 1 FROM dbo.SchemaLog WHERE Script='database/perubahan/030_non_contract_ascend_nullable.sql')
 INSERT dbo.SchemaLog(Script,App) VALUES('database/perubahan/030_non_contract_ascend_nullable.sql','CPOS');
COMMIT;
GO
