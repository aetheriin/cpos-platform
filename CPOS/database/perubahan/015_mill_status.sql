/* Kolom dbo.Mill.Active menjadi Status. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF COL_LENGTH('dbo.Mill', 'Active') IS NOT NULL AND COL_LENGTH('dbo.Mill', 'Status') IS NULL
    EXEC sp_rename 'dbo.Mill.Active', 'Status', 'COLUMN';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/015_mill_status.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/015_mill_status.sql', 'CPOS');
GO
