/* Menu Lv3 Blacklist untuk tab List Request & Log Validasi (bilah tab disembunyikan, tiap tab jadi halaman dari sidebar). */
SET NOCOUNT ON;
USE [CPOS];
GO
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder)
SELECT v.kode, v.nama, p.MenuID, 3, v.url, v.urut
FROM (VALUES ('BL_REQUEST', N'List Request',  '/blacklist?tab=persetujuan', 4),
             ('BL_LOG',     N'Log Validasi',  '/blacklist?tab=log',         5)) v (kode, nama, url, urut)
JOIN dbo.Menu p ON p.MenuCode = 'BLACKLIST'
WHERE NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = v.kode);
GO
-- hak Lihat: ikut peran yang boleh melihat BL_PERSONEL
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
SELECT n.MenuID, 1, 'ROLE', a.LevelDetID
FROM dbo.AccessMenu a
JOIN dbo.Menu s ON s.MenuID = a.MenuID AND s.MenuCode = 'BL_PERSONEL'
JOIN dbo.Menu n ON n.MenuCode IN ('BL_REQUEST', 'BL_LOG')
WHERE a.ActionID = 1 AND a.TargetType = 'ROLE'
  AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = n.MenuID AND x.ActionID = 1 AND x.TargetType = 'ROLE' AND x.LevelDetID = a.LevelDetID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/012_menu_blacklist_tab.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/012_menu_blacklist_tab.sql', 'CPOS');
GO