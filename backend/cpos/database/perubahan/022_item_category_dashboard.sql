/* Analytical Dashboard Item Category: halaman CPOS untuk dbo.top_item_category_analysis di database Main.
   Hak Lihat awal menyalin laporan Analytics AN_TBS; setelahnya dapat diatur di Admin › Hak Akses. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'AN_ITEM_CATEGORY')
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
    SELECT 'AN_ITEM_CATEGORY', N'Item Category Analysis', p.MenuID, 2, '/item-dashboard', 'fa-boxes-stacked', 'ANALYTICS', 10
    FROM dbo.Menu p WHERE p.MenuCode = 'AN_DASHBOARD';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'AN_ITEM_CATEGORY')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, Active)
    SELECT baru.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.Active
    FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID AND m.MenuCode = 'AN_TBS'
    CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'AN_ITEM_CATEGORY') baru;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/022_item_category_dashboard.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/022_item_category_dashboard.sql', 'CPOS');
GO
