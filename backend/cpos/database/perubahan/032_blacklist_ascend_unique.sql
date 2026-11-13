/* Tahap 4: unique blacklist aktif per identitas Ascend.
   Duplikasi existing harus diselesaikan manual sebelum migration. Tidak menghapus baris.
*/
SET NOCOUNT ON; SET XACT_ABORT ON; USE [Main];
IF COL_LENGTH('dbo.Blacklist','AscendCustomerID') IS NULL
 OR COL_LENGTH('dbo.Blacklist','AscendSupplierID') IS NULL
 OR COL_LENGTH('dbo.Blacklist','AscendTransportID') IS NULL
 THROW 51032,'Jalankan migration 026 dahulu.',1;
IF EXISTS(SELECT AscendCustomerID FROM dbo.Blacklist WHERE RevokeDate IS NULL AND AscendCustomerID IS NOT NULL GROUP BY AscendCustomerID HAVING COUNT_BIG(*)>1)
 THROW 51032,'Ada blacklist aktif Customer Ascend duplikat. Audit dan selesaikan sebelum migration.',1;
IF EXISTS(SELECT AscendSupplierID FROM dbo.Blacklist WHERE RevokeDate IS NULL AND AscendSupplierID IS NOT NULL GROUP BY AscendSupplierID HAVING COUNT_BIG(*)>1)
 THROW 51032,'Ada blacklist aktif Supplier Ascend duplikat. Audit dan selesaikan sebelum migration.',1;
IF EXISTS(SELECT AscendTransportID FROM dbo.Blacklist WHERE RevokeDate IS NULL AND AscendTransportID IS NOT NULL GROUP BY AscendTransportID HAVING COUNT_BIG(*)>1)
 THROW 51032,'Ada blacklist aktif Pengangkutan Ascend duplikat. Audit dan selesaikan sebelum migration.',1;
BEGIN TRANSACTION;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.Blacklist') AND name='UX_Blacklist_AscendCustomer_Active')
 CREATE UNIQUE INDEX UX_Blacklist_AscendCustomer_Active ON dbo.Blacklist(AscendCustomerID) WHERE RevokeDate IS NULL AND AscendCustomerID IS NOT NULL;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.Blacklist') AND name='UX_Blacklist_AscendSupplier_Active')
 CREATE UNIQUE INDEX UX_Blacklist_AscendSupplier_Active ON dbo.Blacklist(AscendSupplierID) WHERE RevokeDate IS NULL AND AscendSupplierID IS NOT NULL;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.Blacklist') AND name='UX_Blacklist_AscendTransport_Active')
 CREATE UNIQUE INDEX UX_Blacklist_AscendTransport_Active ON dbo.Blacklist(AscendTransportID) WHERE RevokeDate IS NULL AND AscendTransportID IS NOT NULL;
IF NOT EXISTS(SELECT 1 FROM dbo.SchemaLog WHERE Script='database/perubahan/032_blacklist_ascend_unique.sql')
 INSERT dbo.SchemaLog(Script,App) VALUES('database/perubahan/032_blacklist_ascend_unique.sql','CPOS');
COMMIT;
GO
