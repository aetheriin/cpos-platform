/* Laporan Analytics baru "Tiket Penjualan" (backend/analytics/laporan/tiket_penjualan, SP dbo.TIKET_PENJUALAN):
   menu Dashboard › Analytical Dashboard › Tiket Penjualan (/an/tiket_penjualan), setelah Weighbridge Fraud Analyst.
   Hak Lihat awal disalin dari Weighbridge Fraud Analyst (AN_WB_FRAUD); setelah itu diatur di Admin › Hak Akses. Aman dijalankan ulang. */
SET NOCOUNT ON;
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, AppCode, SortOrder)
SELECT 'AN_TIKET_PENJUALAN', N'Tiket Penjualan', p.MenuID, 3, '/an/tiket_penjualan', 'ANALYTICS', 5
FROM dbo.Menu p
WHERE p.MenuCode = 'AN_DASHBOARD'
  AND NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = 'AN_TIKET_PENJUALAN' OR m.Url = '/an/tiket_penjualan');
GO
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, MenuDetails, Active)
SELECT t.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.MenuDetails, a.Active
FROM dbo.AccessMenu a
JOIN dbo.Menu s ON s.MenuID = a.MenuID AND s.MenuCode = 'AN_WB_FRAUD'
JOIN dbo.Menu t ON t.Url = '/an/tiket_penjualan'
WHERE a.ActionID = 1
  AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = t.MenuID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/025_menu_tiket_penjualan.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/025_menu_tiket_penjualan.sql', 'CPOS');
GO
SELECT m.MenuCode, m.MenuName, m.Url, m.SortOrder, (SELECT COUNT(*) FROM dbo.AccessMenu a WHERE a.MenuID = m.MenuID) AS HakAkses
FROM dbo.Menu m WHERE m.MenuCode = 'AN_TIKET_PENJUALAN';
