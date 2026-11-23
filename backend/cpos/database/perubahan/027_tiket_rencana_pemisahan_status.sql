/* PendingStatus: nilai awal harus NULL (tidak ada timbang tertunda). Hapus default lama, bersihkan nilai di luar daftar, pasang ulang CHECK. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
DECLARE @df sysname = (SELECT d.name FROM sys.default_constraints d JOIN sys.columns c ON c.object_id = d.parent_object_id AND c.column_id = d.parent_column_id
                       WHERE d.parent_object_id = OBJECT_ID('dbo.TiketRencanaPemisahan') AND c.name = 'PendingStatus');
IF @df IS NOT NULL
BEGIN
    DECLARE @sql nvarchar(max) = N'ALTER TABLE dbo.TiketRencanaPemisahan DROP CONSTRAINT ' + QUOTENAME(@df);
    EXEC(@sql);
END
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_TiketRencanaPemisahan_PendingStatus' AND parent_object_id = OBJECT_ID('dbo.TiketRencanaPemisahan'))
    ALTER TABLE dbo.TiketRencanaPemisahan DROP CONSTRAINT CK_TiketRencanaPemisahan_PendingStatus;
GO
ALTER TABLE dbo.TiketRencanaPemisahan ALTER COLUMN PendingStatus VARCHAR(30) NULL;
GO
UPDATE dbo.TiketRencanaPemisahan SET PendingStatus = NULL
WHERE PendingStatus IS NOT NULL AND PendingStatus NOT IN ('MENUNGGU_DO2', 'SELESAI_PISAH', 'SELESAI_TANPA_PISAH');
GO
ALTER TABLE dbo.TiketRencanaPemisahan ADD CONSTRAINT CK_TiketRencanaPemisahan_PendingStatus
    CHECK (PendingStatus IS NULL OR PendingStatus IN ('MENUNGGU_DO2', 'SELESAI_PISAH', 'SELESAI_TANPA_PISAH'));
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/027_tiket_pisah_plan_pending_status.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/027_tiket_pisah_plan_pending_status.sql', 'CPOS');
GO