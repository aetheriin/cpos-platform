/* Menu laporan Analytics "PO Amount" (/an/po_amt), hak lihat awal disalin dari AN_TBS, dan kolom dbo.Company.Active menjadi Status.
   Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF COL_LENGTH('dbo.Company', 'Active') IS NOT NULL AND COL_LENGTH('dbo.Company', 'Status') IS NULL
    EXEC sp_rename 'dbo.Company.Active', 'Status', 'COLUMN';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'AN_PO_AMT')
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder, AppCode)
    SELECT 'AN_PO_AMT', N'PO Amount', p.MenuID, 3, '/an/po_amt', 9, 'ANALYTICS'
    FROM dbo.Menu p WHERE p.MenuCode = 'AN_DASHBOARD';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'AN_PO_AMT')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, Active)
    SELECT baru.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.Active
    FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID AND m.MenuCode = 'AN_TBS'
    CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'AN_PO_AMT') baru;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/013_po_amount_company_status.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/013_po_amount_company_status.sql', 'CPOS');
GO
