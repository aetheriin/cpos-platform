/* Laporan Analytics baru "Pembelian TBS Mingguan" (Analytics/backend/laporan/tbs_mingguan, SP dbo.tbsdetailybsweekly):
   menu Dashboard › Analytical Dashboard › Pembelian TBS Mingguan (/an/tbs_mingguan). Hak lihat awal disalin dari
   laporan TBS Transaction Analyst (AN_TBS); setelah itu diatur di Admin › Hak Akses. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'AN_TBS_MINGGUAN')
BEGIN
    UPDATE dbo.Menu SET SortOrder = 8 WHERE MenuCode = 'AN_COST';
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder, AppCode)
    SELECT 'AN_TBS_MINGGUAN', N'Pembelian TBS Mingguan', p.MenuID, 3, '/an/tbs_mingguan', 7, 'ANALYTICS'
    FROM dbo.Menu p WHERE p.MenuCode = 'AN_DASHBOARD';
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'AN_TBS_MINGGUAN')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, Active)
    SELECT baru.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.Active
    FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID AND m.MenuCode = 'AN_TBS'
    CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'AN_TBS_MINGGUAN') baru;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/003_tbs_mingguan.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/003_tbs_mingguan.sql', 'CPOS');
GO
