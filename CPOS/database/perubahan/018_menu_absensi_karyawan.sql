/* Menu Absensi Karyawan (level 2 di Forms), dipindah dari tab Logs Visitor & Staff Logs. Hak Lihat Logs disalin. Aman dijalankan ulang. */
SET NOCOUNT ON;
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT 'ABSENSI_KARYAWAN', N'Absensi Karyawan', p.MenuID, 2, '/absensi-karyawan', 'fa-user-clock', 'CPOS', 15
FROM dbo.Menu p
WHERE p.MenuCode = 'G_FORMS'
  AND NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = 'ABSENSI_KARYAWAN');
GO
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, MenuDetails, Active)
SELECT t.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.MenuDetails, a.Active
FROM dbo.AccessMenu a
JOIN dbo.Menu s ON s.MenuID = a.MenuID AND s.MenuCode = 'VSL_LOGS'
JOIN dbo.Menu t ON t.MenuCode = 'ABSENSI_KARYAWAN'
WHERE a.ActionID = 1
  AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = t.MenuID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/018_menu_absensi_karyawan.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/018_menu_absensi_karyawan.sql', 'CPOS');
GO