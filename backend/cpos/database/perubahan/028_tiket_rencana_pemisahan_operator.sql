SET NOCOUNT ON;
USE [Main];
GO

IF OBJECT_ID('dbo.TiketRencanaPemisahan', 'U') IS NULL
BEGIN
    RAISERROR ('Tabel dbo.TiketRencanaPemisahan tidak ditemukan.', 16, 1);
END
ELSE
BEGIN
    ALTER TABLE dbo.TiketRencanaPemisahan
        ALTER COLUMN CreatedBy BIGINT NULL;

    ALTER TABLE dbo.TiketRencanaPemisahan
        ALTER COLUMN PendingFinalBy BIGINT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.SchemaLog
    WHERE Script = 'database/perubahan/028_tiket_pisah_operator_bigint.sql'
)
BEGIN
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/028_tiket_pisah_operator_bigint.sql', 'CPOS');
END
GO