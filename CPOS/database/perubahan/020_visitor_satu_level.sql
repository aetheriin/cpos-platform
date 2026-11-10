/* Visitor & Staff Logs jadi satu level: hak Scan Wajah & Logs digabung ke KUNJUNGAN, Data Orang (PERSONEL) naik jadi menu level 2. Aman dijalankan ulang. */
SET NOCOUNT ON;
DECLARE @kunj INT  = (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'KUNJUNGAN');
DECLARE @forms INT = (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'G_FORMS');
IF @kunj IS NULL OR @forms IS NULL THROW 50001, 'Menu KUNJUNGAN atau G_FORMS tidak ditemukan.', 1;

-- 1. KUNJUNGAN: aksi Tambah dan Ubah berlaku
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT @kunj, v.a FROM (VALUES (2), (3)) AS v(a)
WHERE NOT EXISTS (SELECT 1 FROM dbo.MenuAction x WHERE x.MenuID = @kunj AND x.ActionID = v.a);

-- 2. Salin hak dari Scan Wajah dan Logs ke KUNJUNGAN (yang sudah ada dilewati)
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, MenuDetails, Active)
SELECT DISTINCT @kunj, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.MenuDetails, a.Active
FROM dbo.AccessMenu a
JOIN dbo.Menu s ON s.MenuID = a.MenuID AND s.MenuCode IN ('VSL_SCAN', 'VSL_LOGS')
WHERE NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x
                  WHERE x.MenuID = @kunj AND x.ActionID = a.ActionID AND x.TargetType = a.TargetType AND x.IsDeny = a.IsDeny
                    AND ISNULL(x.LevelDetID, -1) = ISNULL(a.LevelDetID, -1) AND ISNULL(x.LevelID, -1) = ISNULL(a.LevelID, -1)
                    AND ISNULL(x.DeptID, -1) = ISNULL(a.DeptID, -1) AND ISNULL(x.UserID, -1) = ISNULL(a.UserID, -1));

-- 3. Hapus menu level 3 Scan Wajah dan Logs
DELETE FROM dbo.AccessMenu WHERE MenuID IN (SELECT MenuID FROM dbo.Menu WHERE MenuCode IN ('VSL_SCAN', 'VSL_LOGS'));
DELETE FROM dbo.Menu WHERE MenuCode IN ('VSL_SCAN', 'VSL_LOGS');

-- 4. Data Orang naik jadi menu level 2 di Forms (MenuID sama, semua hak PERSONEL tetap berlaku)
UPDATE dbo.Menu
SET ParentMenuID = @forms, MenuLevel = 2, Url = '/data-orang', Icon = 'fa-address-book', SortOrder = 12
WHERE MenuCode = 'PERSONEL';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/020_visitor_satu_level.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/020_visitor_satu_level.sql', 'CPOS');
GO