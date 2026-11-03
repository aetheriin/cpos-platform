/* Contoh skrip perubahan database (salin, beri nomor urut berikutnya: 001_<ringkas>.sql, 002_..., lalu hapus komentar ini).

   Aturan:
   - Server yang sudah berjalan TIDAK dibuat ulang dari schema.sql: perubahan tabel / prosedur ditulis di sini dan dijalankan
     berurutan. Ubahan yang sama juga dimasukkan ke database/schema.sql supaya server baru langsung lengkap.
   - Aman dijalankan ulang (IF NOT EXISTS / CREATE OR ALTER), dan mencatat dirinya di dbo.SchemaLog.
   - Skrip milik modul (RekapIn) ada di CPOS/modules/<modul>/database, milik Analytics di Analytics/database. */
SET NOCOUNT ON;
IF COL_LENGTH('dbo.Setting', 'Keterangan') IS NULL
    ALTER TABLE dbo.Setting ADD Keterangan NVARCHAR(200) NULL;   -- contoh
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/_contoh.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/_contoh.sql', 'CPOS');
GO
