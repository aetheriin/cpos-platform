/* Tahap 2B: snapshot + Ascend identity pada Contract/DOTransport.
   Additive; aman rerun; tidak menghapus kolom legacy atau tabel master.
*/
SET NOCOUNT ON; SET XACT_ABORT ON; USE [Main];
IF OBJECT_ID('dbo.SchemaLog','U') IS NULL THROW 51029,'SchemaLog tidak ditemukan.',1;
IF COL_LENGTH('dbo.Contract','AscendCustomerID') IS NULL OR COL_LENGTH('dbo.DOTransport','AscendTransportID') IS NULL
 THROW 51029,'Jalankan migration 026 dahulu.',1;
BEGIN TRANSACTION;
IF COL_LENGTH('dbo.Contract','AscendProductCode') IS NULL ALTER TABLE dbo.Contract ADD AscendProductCode NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contract','CustomerCodeSnapshot') IS NULL ALTER TABLE dbo.Contract ADD CustomerCodeSnapshot NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contract','ProductCodeSnapshot') IS NULL ALTER TABLE dbo.Contract ADD ProductCodeSnapshot NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.DOTransport','TransportCodeSnapshot') IS NULL ALTER TABLE dbo.DOTransport ADD TransportCodeSnapshot NVARCHAR(100) NULL;
IF NOT EXISTS(SELECT 1 FROM dbo.SchemaLog WHERE Script='database/perubahan/029_contract_ascend_identity.sql')
 INSERT dbo.SchemaLog(Script,App) VALUES('database/perubahan/029_contract_ascend_identity.sql','CPOS');
COMMIT;
GO
