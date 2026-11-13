/* Tahap 2C: unique key DOTransport mendukung ID lokal dan Ascend sekaligus.
   Jalankan setelah 026 dan 028. Tidak menghapus data.
*/
SET NOCOUNT ON; SET XACT_ABORT ON; USE [Main];
IF OBJECT_ID('dbo.SchemaLog','U') IS NULL THROW 51031,'SchemaLog tidak ditemukan.',1;
IF COL_LENGTH('dbo.DOTransport','AscendTransportID') IS NULL
 THROW 51031,'Jalankan migration 026 dahulu.',1;
BEGIN TRANSACTION;
IF EXISTS(SELECT 1 FROM sys.key_constraints WHERE name='UX_DOTransport' AND parent_object_id=OBJECT_ID('dbo.DOTransport'))
 ALTER TABLE dbo.DOTransport DROP CONSTRAINT UX_DOTransport;
IF EXISTS(SELECT 1 FROM sys.indexes WHERE name='UX_DOTransport_Legacy' AND object_id=OBJECT_ID('dbo.DOTransport'))
 DROP INDEX UX_DOTransport_Legacy ON dbo.DOTransport;
IF EXISTS(SELECT 1 FROM sys.indexes WHERE name='UX_DOTransport_Ascend' AND object_id=OBJECT_ID('dbo.DOTransport'))
 DROP INDEX UX_DOTransport_Ascend ON dbo.DOTransport;
CREATE UNIQUE INDEX UX_DOTransport_Legacy ON dbo.DOTransport (DeliveryOrderID,TransportMode,TransportID) WHERE AscendTransportID IS NULL;
CREATE UNIQUE INDEX UX_DOTransport_Ascend ON dbo.DOTransport (DeliveryOrderID,TransportMode,AscendTransportID) WHERE AscendTransportID IS NOT NULL;
IF NOT EXISTS(SELECT 1 FROM dbo.SchemaLog WHERE Script='database/perubahan/031_do_transport_ascend_unique.sql')
 INSERT dbo.SchemaLog(Script,App) VALUES('database/perubahan/031_do_transport_ascend_unique.sql','CPOS');
COMMIT;
GO
