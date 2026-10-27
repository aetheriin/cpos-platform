/* Alur tiket dinamis (tahap 2): status ringkas "Menunggu Keluar" (tinggal tahap Security Keluar).
   Untuk database CPOS yang sudah berjalan. Aman dijalankan ulang. Jalankan setelah 001_alur_dinamis.sql. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Status WHERE StatusCode = 'MENUNGGU_KELUAR')
    INSERT INTO dbo.Status (StatusCode, StatusName, StatusColor, SortOrder) VALUES ('MENUNGGU_KELUAR', N'Menunggu Keluar', 'kuning', 6);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/002_status_keluar.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/002_status_keluar.sql', 'CPOS');
GO
