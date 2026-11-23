/* TiketRencanaPemisahan: NoDO2 boleh NULL (DO2 baru dicari saat timbang akhir) + kolom timbang tertunda yang dipakai kode. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_TiketRencanaPemisahan_NoDO2' AND parent_object_id = OBJECT_ID('dbo.TiketRencanaPemisahan'))
    ALTER TABLE dbo.TiketRencanaPemisahan DROP CONSTRAINT CK_TiketRencanaPemisahan_NoDO2;
GO
ALTER TABLE dbo.TiketRencanaPemisahan ALTER COLUMN NoDO2 VARCHAR(50) NULL;
GO
ALTER TABLE dbo.TiketRencanaPemisahan ADD CONSTRAINT CK_TiketRencanaPemisahan_NoDO2
    CHECK (NoDO2 IS NULL OR LEN(LTRIM(RTRIM(NoDO2))) > 0);
GO
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingFinalScaleKg') IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingFinalScaleKg DECIMAL(18,3) NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingFinalAt')      IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingFinalAt DATETIME2(3) NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingFinalBy')      IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingFinalBy INT NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingStatus')       IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingStatus VARCHAR(30) NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingAttempts')     IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingAttempts INT NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingLastError')    IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingLastError NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.TiketRencanaPemisahan', 'PendingCompletedAt')  IS NULL ALTER TABLE dbo.TiketRencanaPemisahan ADD PendingCompletedAt DATETIME2(3) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_TiketRencanaPemisahan_PendingStatus' AND parent_object_id = OBJECT_ID('dbo.TiketRencanaPemisahan'))
    ALTER TABLE dbo.TiketRencanaPemisahan ADD CONSTRAINT CK_TiketRencanaPemisahan_PendingStatus
        CHECK (PendingStatus IS NULL OR PendingStatus IN ('MENUNGGU_DO2', 'SELESAI_PISAH', 'SELESAI_TANPA_PISAH'));
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/026_tiket_pisah_plan_perbaikan.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/026_tiket_pisah_plan_perbaikan.sql', 'CPOS');
GO