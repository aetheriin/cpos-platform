SET NOCOUNT ON;
USE [Main];
GO

IF OBJECT_ID('dbo.AscendTicketSplitPlan', 'U') IS NULL
BEGIN
    RAISERROR ('Tabel dbo.AscendTicketSplitPlan tidak ditemukan.', 16, 1);
END
ELSE
BEGIN
    ALTER TABLE dbo.AscendTicketSplitPlan
        ALTER COLUMN CreatedBy BIGINT NULL;

    ALTER TABLE dbo.AscendTicketSplitPlan
        ALTER COLUMN PendingFinalBy BIGINT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.SchemaLog
    WHERE Script = 'database/perubahan/028_ascend_split_operator_bigint.sql'
)
BEGIN
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/028_ascend_split_operator_bigint.sql', 'CPOS');
END
GO