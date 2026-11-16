/* AscendTicketSplitPlan: NoDO2 boleh NULL (DO2 baru dicari saat timbang akhir) + kolom timbang tertunda yang dipakai kode. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_AscendTicketSplitPlan_NoDO2' AND parent_object_id = OBJECT_ID('dbo.AscendTicketSplitPlan'))
    ALTER TABLE dbo.AscendTicketSplitPlan DROP CONSTRAINT CK_AscendTicketSplitPlan_NoDO2;
GO
ALTER TABLE dbo.AscendTicketSplitPlan ALTER COLUMN NoDO2 VARCHAR(50) NULL;
GO
ALTER TABLE dbo.AscendTicketSplitPlan ADD CONSTRAINT CK_AscendTicketSplitPlan_NoDO2
    CHECK (NoDO2 IS NULL OR LEN(LTRIM(RTRIM(NoDO2))) > 0);
GO
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingFinalScaleKg') IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingFinalScaleKg DECIMAL(18,3) NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingFinalAt')      IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingFinalAt DATETIME2(3) NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingFinalBy')      IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingFinalBy INT NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingStatus')       IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingStatus VARCHAR(30) NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingAttempts')     IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingAttempts INT NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingLastError')    IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingLastError NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.AscendTicketSplitPlan', 'PendingCompletedAt')  IS NULL ALTER TABLE dbo.AscendTicketSplitPlan ADD PendingCompletedAt DATETIME2(3) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_AscendTicketSplitPlan_PendingStatus' AND parent_object_id = OBJECT_ID('dbo.AscendTicketSplitPlan'))
    ALTER TABLE dbo.AscendTicketSplitPlan ADD CONSTRAINT CK_AscendTicketSplitPlan_PendingStatus
        CHECK (PendingStatus IS NULL OR PendingStatus IN ('MENUNGGU_DO2', 'SELESAI_SPLIT', 'SELESAI_TANPA_SPLIT'));
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/026_ascend_split_plan_perbaikan.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/026_ascend_split_plan_perbaikan.sql', 'CPOS');
GO