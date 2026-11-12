/* Menu laporan Analytics "Outstanding" (/an/outstanding, level 2 di Reports, setelah Purchase Invoice).
   Hak Lihat awal disalin dari Purchase Invoice (RP_PI). Menu yang sudah dibuat manual dengan Url yang sama tidak dibuat dua kali,
   hanya diberi ikon Reports bila ikonnya masih kosong. Aman dijalankan ulang. */
SET NOCOUNT ON;
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT 'RP_OUTSTANDING', N'Outstanding', p.MenuID, 2, '/an/outstanding', 'fa-file-invoice', 'ANALYTICS', 35
FROM dbo.Menu p
WHERE p.MenuCode = 'G_REPORTS'
  AND NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = 'RP_OUTSTANDING' OR m.Url = '/an/outstanding');
GO
UPDATE dbo.Menu SET Icon = 'fa-file-invoice' WHERE Url = '/an/outstanding' AND NULLIF(LTRIM(RTRIM(Icon)), '') IS NULL;
GO
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, MenuDetails, Active)
SELECT t.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.MenuDetails, a.Active
FROM dbo.AccessMenu a
JOIN dbo.Menu s ON s.MenuID = a.MenuID AND s.MenuCode = 'RP_PI'
JOIN dbo.Menu t ON t.Url = '/an/outstanding'
WHERE a.ActionID = 1
  AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = t.MenuID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/021_menu_outstanding.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/021_menu_outstanding.sql', 'CPOS');
GO
