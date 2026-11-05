/* Kolom dbo.CompanyArea.Active menjadi Status. Dua fungsi cakupan ikut diperbarui; kolom hasilnya tetap bernama Active supaya pemakainya tidak berubah.
   Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF COL_LENGTH('dbo.CompanyArea', 'Active') IS NOT NULL AND COL_LENGTH('dbo.CompanyArea', 'Status') IS NULL
    EXEC sp_rename 'dbo.CompanyArea.Active', 'Status', 'COLUMN';
GO
CREATE OR ALTER FUNCTION dbo.fn_UserScope (@UserID BIGINT)
RETURNS TABLE AS RETURN
SELECT a.CompAreaID, a.AreaCode, a.AreaName, a.CompID, c.CompName, a.Status AS Active,
       CAST(CASE WHEN a.CompAreaID = i.OwnAreaID THEN 1 ELSE 0 END AS BIT) AS IsOwnArea
FROM dbo.fn_UserScopeInfo(@UserID) i
JOIN dbo.CompanyArea a ON i.AllAreas = 1 OR a.CompAreaID = i.OwnAreaID
JOIN dbo.Company c ON c.CompID = a.CompID;
GO
CREATE OR ALTER FUNCTION dbo.fn_UserMenuScope (@UserID BIGINT, @MenuCode VARCHAR(40))
RETURNS TABLE AS RETURN
WITH aturan AS (
    SELECT ISNULL(JSON_VALUE(r.MenuDetails, '$.cakupan'), 'AREA') AS Cakupan, r.MenuDetails
    FROM dbo.fn_AccessRules(@UserID, NULL) r
    JOIN dbo.Menu m ON m.MenuID = r.MenuID
    WHERE m.MenuCode = @MenuCode AND r.ActionID = 1 AND r.IsDeny = 0
)
SELECT a.CompAreaID, a.AreaCode, a.AreaName, a.CompID, c.CompName, a.Status AS Active,
       CAST(CASE WHEN a.CompAreaID = i.OwnAreaID THEN 1 ELSE 0 END AS BIT) AS IsOwnArea
FROM dbo.fn_UserScopeInfo(@UserID) i
JOIN dbo.CompanyArea a ON EXISTS (
         SELECT 1 FROM aturan t
         WHERE t.Cakupan = 'SEMUA'
            OR (t.Cakupan = 'PT' AND a.CompID = i.OwnCompID)
            OR (t.Cakupan = 'PT_TERTENTU' AND a.CompID IN (SELECT j.value FROM OPENJSON(t.MenuDetails, '$.pt') j))
            OR (t.Cakupan = 'AREA' AND (i.AllAreas = 1 OR a.CompAreaID = i.OwnAreaID)))
JOIN dbo.Company c ON c.CompID = a.CompID;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/014_companyarea_status.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/014_companyarea_status.sql', 'CPOS');
GO
