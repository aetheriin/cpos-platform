/* Analytics di CPOS: hak bawaan menu laporan Analytics. Jalankan di database CPOS setelah CPOS\database\schema.sql.
   Menu & alamatnya (/an/<id laporan>) sudah dibuat schema.sql; di sini hanya hak awal, dan hanya bila menu Analytics belum punya
   aturan sama sekali (setelah itu diatur di Admin › Hak Akses, skrip ini aman dijalankan ulang).
   HO = lihat semua laporan Analytics (Dashboard › Analytical Dashboard, Reports › Purchase Invoice & Goods Transfer). */
SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID
               WHERE m.MenuCode = 'AN_DASHBOARD' OR m.Url LIKE '/an/%')
BEGIN
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, 1, 'ROLE', ld.LevelDetID
    FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode = 'HO'
    WHERE (m.MenuCode = 'AN_DASHBOARD' OR m.Url LIKE '/an/%' OR m.MenuCode = 'G_REPORTS')
      AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a WHERE a.MenuID = m.MenuID AND a.ActionID = 1 AND a.TargetType = 'ROLE'
                      AND a.LevelDetID = ld.LevelDetID);
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'Analytics/database/001_analytics.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('Analytics/database/001_analytics.sql', 'ANALYTICS');
GO
