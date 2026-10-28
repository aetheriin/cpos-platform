/* Normalisasi data orang & cakupan data (mengikuti ERD Blueprint CPOS). Untuk database yang sudah berjalan;
   database baru langsung dari schema.sql. Jalankan SEKALI di SSMS (aman dijalankan ulang: tiap langkah dicek dulu).

   1. Cakupan data per aturan Hak Akses: AccessMenu.MenuDetails (JSON). Tabel UserCompany (PT dikelola) dihapus:
      akun kantor pusat kembali melihat semua PT, batasi lewat Admin › Hak Akses › Cakupan data.
   2. Jenis orang dibaca dari relasi: Users.CategoryCode & UserCategory dihapus.
      Karyawan / Security / BHL tanpa jabatan diberi jabatan (Umum · Staff, Security · Staff, Sortasi · BHL).
      Driver & tamu mendapat profil visitor (Guest baru) lewat Users.GuestID.
   3. VisitPurpose dihapus; kunjungan lama (Guest lama) dan absensi lama (FaceActivity lama) dipindah ke FaceActivity baru
      (semua aktivitas scan). FaceRecog menjadi foto wajah saat scan; wajah terdaftar tetap di Users.FaceEmbeddingData.
   4. Menu: Pengenalan Wajah dihapus; Visitor & Staff Logs (/visitor-logs) berisi Scan Wajah, Logs, Data Orang.
   SEBELUM MENJALANKAN: backup database. */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO
USE [CPOS];
GO
/* ---------- 1. Cakupan data ---------- */
IF COL_LENGTH('dbo.AccessMenu', 'MenuDetails') IS NULL
    ALTER TABLE dbo.AccessMenu ADD MenuDetails NVARCHAR(MAX) NULL
        CONSTRAINT CK_AccessMenu_Details CHECK (MenuDetails IS NULL OR ISJSON(MenuDetails) = 1);
GO
CREATE OR ALTER FUNCTION dbo.fn_AccessRules (@UserID BIGINT, @LevelDetID INT)
RETURNS TABLE AS RETURN
WITH siapa AS (
    SELECT ld.LevelDetID, ld.LevelID, ld.DeptID, u.UserID
    FROM dbo.LevelDetails ld
    JOIN dbo.Level lv ON lv.LevelID = ld.LevelID
    LEFT JOIN dbo.Users u ON u.UserID = @UserID AND u.Active = 1 AND u.UserLevelID = ld.LevelDetID
    WHERE lv.IsAdmin = 0
      AND ((@UserID IS NULL AND ld.LevelDetID = @LevelDetID) OR (@UserID IS NOT NULL AND u.UserID IS NOT NULL))
)
SELECT a.AccessMenuID, a.MenuID, a.ActionID, a.TargetType, a.IsDeny, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.MenuDetails
FROM dbo.AccessMenu a CROSS JOIN siapa s
WHERE a.Active = 1
  AND (a.TargetType = 'ALL'
       OR (a.TargetType = 'ROLE'  AND a.LevelDetID = s.LevelDetID)
       OR (a.TargetType = 'LEVEL' AND a.LevelID = s.LevelID)
       OR (a.TargetType = 'DEPT'  AND a.DeptID = s.DeptID)
       OR (a.TargetType = 'USER'  AND a.UserID = s.UserID));
GO
GO
IF OBJECT_ID('dbo.UserCompany') IS NOT NULL DROP TABLE dbo.UserCompany;
GO
CREATE OR ALTER FUNCTION dbo.fn_UserScopeInfo (@UserID BIGINT)
RETURNS TABLE AS RETURN
SELECT u.UserID, u.CompAreaID AS OwnAreaID, a.CompID AS OwnCompID,
       CAST(ISNULL(m.IsHeadOffice, 0) AS BIT) AS IsHeadOffice,
       CAST(CASE WHEN u.CompAreaID IS NULL OR m.IsHeadOffice = 1 THEN 1 ELSE 0 END AS BIT) AS AllAreas
FROM dbo.Users u
LEFT JOIN dbo.CompanyArea a ON a.CompAreaID = u.CompAreaID
LEFT JOIN dbo.Mill m ON m.MillID = a.MillID
WHERE u.UserID = @UserID AND u.Active = 1;
GO
CREATE OR ALTER FUNCTION dbo.fn_UserScope (@UserID BIGINT)
RETURNS TABLE AS RETURN
SELECT a.CompAreaID, a.AreaCode, a.AreaName, a.CompID, c.CompName, a.Active,
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
SELECT a.CompAreaID, a.AreaCode, a.AreaName, a.CompID, c.CompName, a.Active,
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
/* @MenuCode NULL = cakupan bawaan; diisi = cakupan menu itu (Admin › Hak Akses › Cakupan data). */
CREATE OR ALTER PROCEDURE dbo.sp_UserScope
    @UserID   BIGINT,
    @MenuCode VARCHAR(40) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @MenuCode IS NULL
        SELECT s.*, i.IsHeadOffice, i.AllAreas
        FROM dbo.fn_UserScope(@UserID) s CROSS JOIN dbo.fn_UserScopeInfo(@UserID) i
        ORDER BY s.CompID, s.AreaCode, s.AreaName;
    ELSE
        SELECT s.*, i.IsHeadOffice, i.AllAreas
        FROM dbo.fn_UserMenuScope(@UserID, @MenuCode) s CROSS JOIN dbo.fn_UserScopeInfo(@UserID) i
        ORDER BY s.CompID, s.AreaCode, s.AreaName;
END
GO

/* ---------- 2. Status scan, jabatan BHL / Umum ---------- */
INSERT INTO dbo.Status (StatusCode, StatusName, StatusColor, SortOrder)
SELECT v.k, v.n, v.w, v.u FROM (VALUES ('WAJAH_BERHASIL', N'Scan berhasil', 'hijau', 20), ('WAJAH_TIDAK_DIKENALI', N'Wajah tidak dikenali', 'kuning', 21),
                                      ('WAJAH_DITOLAK', N'Ditolak (blacklist)', 'merah', 22)) v (k, n, w, u)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Status s WHERE s.StatusCode = v.k);
IF NOT EXISTS (SELECT 1 FROM dbo.Level WHERE LevelName = N'BHL')
    INSERT INTO dbo.Level (LevelName, IsAdmin, SortOrder) VALUES (N'BHL', 0, 6);
INSERT INTO dbo.LevelDetails (LevelDetCode, LevelDetName, LevelID, DeptID, HomeUrl)
SELECT v.kode, d.DeptName + N' · ' + l.LevelName, l.LevelID, d.DeptID, v.awal
FROM (VALUES ('UMUM', N'Staff', 'UMUM', '/dashboard'), ('SORTASI_BHL', N'BHL', 'SRT', '/weighbridge?tab=sortasi')) v (kode, lvl, dept, awal)
JOIN dbo.Level l ON l.LevelName = v.lvl JOIN dbo.Department d ON d.DeptID = v.dept
WHERE NOT EXISTS (SELECT 1 FROM dbo.LevelDetails x WHERE x.LevelDetCode = v.kode)
  AND NOT EXISTS (SELECT 1 FROM dbo.LevelDetails x WHERE x.DeptID = v.dept AND x.LevelID = l.LevelID AND x.CompAreaID IS NULL);
GO
/* ---------- 3. Tabel lama disisihkan ---------- */
IF COL_LENGTH('dbo.Guest', 'CheckInDate') IS NOT NULL AND OBJECT_ID('dbo.Guest_lama') IS NULL EXEC sp_rename 'dbo.Guest', 'Guest_lama';
IF COL_LENGTH('dbo.FaceRecog', 'UserID') IS NOT NULL AND OBJECT_ID('dbo.FaceRecog_lama') IS NULL EXEC sp_rename 'dbo.FaceRecog', 'FaceRecog_lama';
IF COL_LENGTH('dbo.FaceActivity', 'Status') IS NOT NULL AND OBJECT_ID('dbo.FaceActivity_lama') IS NULL EXEC sp_rename 'dbo.FaceActivity', 'FaceActivity_lama';
IF OBJECT_ID('dbo.TR_FaceRecog_Utama') IS NOT NULL DROP TRIGGER dbo.TR_FaceRecog_Utama;
GO
IF OBJECT_ID('dbo.Guest') IS NULL
BEGIN
    CREATE TABLE dbo.Guest (
        GuestID       BIGINT IDENTITY(1,1) PRIMARY KEY,
        BlacklistID   BIGINT        NULL CONSTRAINT FK_Guest_Blacklist REFERENCES dbo.Blacklist (BlacklistID),
        CompanyFrom   NVARCHAR(255) NULL,
        VisitorNeeds  NVARCHAR(255) NULL,
        NoKTP         VARCHAR(20)   NULL,
        Active        BIT NOT NULL CONSTRAINT DF_Guest_Active DEFAULT (1),
        Description   NVARCHAR(255) NULL,
        CreateDate    DATETIME NOT NULL CONSTRAINT DF_Guest_Create DEFAULT (GETDATE())
    );
END
IF OBJECT_ID('dbo.FaceRecog') IS NULL
    CREATE TABLE dbo.FaceRecog (
        FaceID      BIGINT IDENTITY(1,1) PRIMARY KEY,
        FaceName    NVARCHAR(120) NULL,
        FaceDet     VARBINARY(MAX) NULL,
        Blacklist   BIGINT NULL CONSTRAINT FK_FaceRecog_Blacklist REFERENCES dbo.Blacklist (BlacklistID),
        PhotoPath   VARCHAR(255) NULL,
        CreateDate  DATETIME NOT NULL CONSTRAINT DF_FaceRecog2_Create DEFAULT (GETDATE())
    );
IF OBJECT_ID('dbo.FaceActivity') IS NULL
BEGIN
    CREATE TABLE dbo.FaceActivity (
        ActivityID    BIGINT IDENTITY(1,1) PRIMARY KEY,
        UserID        BIGINT NULL CONSTRAINT FK_FaceAct2_User REFERENCES dbo.Users (UserID),
        FaceID        BIGINT NULL CONSTRAINT FK_FaceAct2_Face REFERENCES dbo.FaceRecog (FaceID),
        ActivityType  VARCHAR(10) NULL CONSTRAINT CK_FaceAct2_Type CHECK (ActivityType IN ('MASUK', 'KELUAR')),
        StatusID      INT NOT NULL CONSTRAINT FK_FaceAct2_Status REFERENCES dbo.Status (StatusID),
        LogDate       DATETIME NOT NULL CONSTRAINT DF_FaceAct2_LogDate DEFAULT (GETDATE()),
        LogDay        AS CAST(LogDate AS DATE) PERSISTED,
        Description   NVARCHAR(255) NULL,
        VisitToID     BIGINT NULL CONSTRAINT FK_FaceAct2_VisitTo REFERENCES dbo.Users (UserID),
        NoVehicle     VARCHAR(15) NULL,
        CompAreaID    BIGINT NULL CONSTRAINT FK_FaceAct2_Area REFERENCES dbo.CompanyArea (CompAreaID),
        TimeStatus    VARCHAR(20) NULL CONSTRAINT CK_FaceAct2_Time CHECK (TimeStatus IN ('TEPAT_WAKTU', 'TERLAMBAT', 'PULANG_AWAL', 'HARI_LIBUR')),
        DiffMinutes   INT NULL,
        FaceDistance  FLOAT NULL,
        Device        VARCHAR(50) NULL,
        IPAddress     VARCHAR(45) NULL,
        CreateBy      BIGINT NULL CONSTRAINT FK_FaceAct2_CreateBy REFERENCES dbo.Users (UserID)
    );
    CREATE INDEX IX_FaceAct2_User_Day ON dbo.FaceActivity (UserID, LogDay);
    CREATE INDEX IX_FaceAct2_Day ON dbo.FaceActivity (LogDay) INCLUDE (CompAreaID, StatusID);
END
GO
/* ---------- 4. Data orang: jabatan karyawan, profil visitor ---------- */
IF COL_LENGTH('dbo.Users', 'CategoryCode') IS NOT NULL
BEGIN
    EXEC('UPDATE u SET UserLevelID = ld.LevelDetID
          FROM dbo.Users u JOIN dbo.LevelDetails ld
            ON ld.LevelDetCode = CASE u.CategoryCode WHEN ''SECURITY'' THEN ''SECURITY'' WHEN ''BHL'' THEN ''SORTASI_BHL'' ELSE ''UMUM'' END
          WHERE u.UserLevelID IS NULL AND u.CategoryCode IN (''EMPLOYEE'', ''SECURITY'', ''BHL'')');
    EXEC('INSERT INTO dbo.Guest (CompanyFrom, VisitorNeeds, NoKTP, Description)
          SELECT (SELECT TOP 1 g.CompanyFrom FROM dbo.Guest_lama g WHERE g.UserID = u.UserID AND g.CompanyFrom IS NOT NULL ORDER BY g.CheckInDate DESC),
                 NULL, u.NoKTP, ''#USER:'' + CAST(u.UserID AS VARCHAR(20))
          FROM dbo.Users u WHERE u.GuestID IS NULL AND u.UserLevelID IS NULL AND u.CategoryCode IN (''DRIVER'', ''TAMU'')');
    UPDATE u SET GuestID = g.GuestID FROM dbo.Users u JOIN dbo.Guest g ON g.Description = '#USER:' + CAST(u.UserID AS VARCHAR(20));
    UPDATE dbo.Guest SET Description = NULL WHERE Description LIKE '#USER:%';
END
GO
-- Wajah terdaftar: satu per orang (wajah utama lama)
IF OBJECT_ID('dbo.FaceRecog_lama') IS NOT NULL
    EXEC('UPDATE u SET u.FaceEmbeddingData = f.FaceDet, u.UploadPath = f.PhotoPath
          FROM dbo.Users u CROSS APPLY (SELECT TOP 1 FaceDet, PhotoPath FROM dbo.FaceRecog_lama
                                       WHERE UserID = u.UserID AND Active = 1 ORDER BY IsMain DESC, FaceID DESC) f
          WHERE u.FaceEmbeddingData IS NULL');
GO
/* ---------- 5. Aktivitas lama -> FaceActivity ---------- */
IF OBJECT_ID('dbo.FaceActivity_lama') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dbo.FaceActivity)
    EXEC('DECLARE @peta TABLE (lama INT, face BIGINT);
          MERGE dbo.FaceRecog t USING (SELECT ActivityID, PhotoPath, LogDate FROM dbo.FaceActivity_lama WHERE PhotoPath IS NOT NULL) s ON 1 = 0
          WHEN NOT MATCHED THEN INSERT (PhotoPath, CreateDate) VALUES (s.PhotoPath, s.LogDate)
          OUTPUT s.ActivityID, inserted.FaceID INTO @peta;
          INSERT INTO dbo.FaceActivity (UserID, FaceID, ActivityType, StatusID, LogDate, TimeStatus, DiffMinutes, FaceDistance, Device, IPAddress)
          SELECT a.UserID, p.face, CASE a.ActivityType WHEN ''PULANG'' THEN ''KELUAR'' ELSE a.ActivityType END,
                 st.StatusID, a.LogDate, a.TimeStatus, a.DiffMinutes, a.FaceDistance, a.Device, a.IPAddress
          FROM dbo.FaceActivity_lama a LEFT JOIN @peta p ON p.lama = a.ActivityID
          JOIN dbo.Status st ON st.StatusCode = CASE a.Status WHEN ''BERHASIL'' THEN ''WAJAH_BERHASIL''
                                                WHEN ''DITOLAK_BLACKLIST'' THEN ''WAJAH_DITOLAK'' ELSE ''WAJAH_TIDAK_DIKENALI'' END;');
GO
IF OBJECT_ID('dbo.Guest_lama') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dbo.FaceActivity WHERE Description IS NOT NULL OR VisitToID IS NOT NULL)
    EXEC('DECLARE @ok INT = (SELECT StatusID FROM dbo.Status WHERE StatusCode = ''WAJAH_BERHASIL'');
          INSERT INTO dbo.FaceActivity (UserID, ActivityType, StatusID, LogDate, Description, VisitToID, NoVehicle, CompAreaID, CreateBy)
          SELECT g.UserID, ''MASUK'', @ok, g.CheckInDate, LEFT(ISNULL(p.PurposeName, N'''') + ISNULL(N'' · '' + g.Description, N''''), 255),
                 g.VisitToID, g.NoVehicle, g.CompAreaID, g.CreateBy
          FROM dbo.Guest_lama g LEFT JOIN dbo.VisitPurpose p ON p.PurposeID = g.PurposeID
          UNION ALL
          SELECT g.UserID, ''KELUAR'', @ok, g.CheckOutDate, NULL, NULL, NULL, g.CompAreaID, g.CreateBy
          FROM dbo.Guest_lama g WHERE g.CheckOutDate IS NOT NULL;');
GO
/* ---------- 6. Kategori lama di blacklist & alur persetujuan -> jenis orang ---------- */
UPDATE dbo.Blacklist SET CategoryCode = 'KARYAWAN' WHERE CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL');
UPDATE dbo.ApprovalRequest SET CategoryCode = 'KARYAWAN' WHERE CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL');
-- Alur ganda setelah digabung (mis. Karyawan & Security): yang dipakai alur dengan id terkecil
DELETE s FROM dbo.ApprovalFlowStep s JOIN dbo.ApprovalFlow a ON a.ApprovalFlowID = s.ApprovalFlowID
WHERE a.CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL')
  AND EXISTS (SELECT 1 FROM dbo.ApprovalFlow b WHERE b.RequestType = a.RequestType AND b.ApprovalFlowID < a.ApprovalFlowID
              AND (b.CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL', 'KARYAWAN')));
DELETE a FROM dbo.ApprovalFlow a
WHERE a.CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL')
  AND EXISTS (SELECT 1 FROM dbo.ApprovalFlow b WHERE b.RequestType = a.RequestType AND b.ApprovalFlowID < a.ApprovalFlowID
              AND (b.CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL', 'KARYAWAN')));
UPDATE dbo.ApprovalFlow SET CategoryCode = 'KARYAWAN' WHERE CategoryCode IN ('EMPLOYEE', 'SECURITY', 'BHL');
GO
/* ---------- 7. Hapus kolom & tabel lama ---------- */
IF OBJECT_ID('dbo.TR_LogData_UserCategory') IS NOT NULL DROP TRIGGER dbo.TR_LogData_UserCategory;
IF OBJECT_ID('dbo.TR_LogData_VisitPurpose') IS NOT NULL DROP TRIGGER dbo.TR_LogData_VisitPurpose;
IF COL_LENGTH('dbo.Users', 'CategoryCode') IS NOT NULL
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Users_Active_Category') DROP INDEX IX_Users_Active_Category ON dbo.Users;
    IF OBJECT_ID('dbo.FK_Users_Category') IS NOT NULL ALTER TABLE dbo.Users DROP CONSTRAINT FK_Users_Category;
    IF OBJECT_ID('dbo.DF_Users_Category') IS NOT NULL ALTER TABLE dbo.Users DROP CONSTRAINT DF_Users_Category;
    ALTER TABLE dbo.Users DROP COLUMN CategoryCode;
END
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Users_Active')
    CREATE INDEX IX_Users_Active ON dbo.Users (Active) INCLUDE (UserCode, Nama, GuestID, UserLevelID);
IF OBJECT_ID('dbo.FK_Users_Guest') IS NULL
    ALTER TABLE dbo.Users ADD CONSTRAINT FK_Users_Guest FOREIGN KEY (GuestID) REFERENCES dbo.Guest (GuestID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Users_Guest')
    CREATE UNIQUE INDEX UX_Users_Guest ON dbo.Users (GuestID) WHERE GuestID IS NOT NULL;
IF OBJECT_ID('dbo.FaceActivity_lama') IS NOT NULL DROP TABLE dbo.FaceActivity_lama;
IF OBJECT_ID('dbo.FaceRecog_lama') IS NOT NULL DROP TABLE dbo.FaceRecog_lama;
IF OBJECT_ID('dbo.Guest_lama') IS NOT NULL DROP TABLE dbo.Guest_lama;
IF OBJECT_ID('dbo.VisitPurpose') IS NOT NULL DROP TABLE dbo.VisitPurpose;
IF OBJECT_ID('dbo.UserCategory') IS NOT NULL DROP TABLE dbo.UserCategory;
GO
CREATE OR ALTER VIEW dbo.UserProfile AS
SELECT u.UserID, u.UserCode, u.NoKTP, u.Nama, u.Email, u.IsUpload, u.CurrentHash,
       CAST(CASE WHEN u.UserLevelID IS NOT NULL THEN 'KARYAWAN' WHEN s.LicenseNumber IS NOT NULL THEN 'DRIVER' ELSE 'TAMU' END
            AS VARCHAR(10)) AS PersonType,
       CAST(CASE WHEN u.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS IsBlacklisted, u.BlacklistID,
       u.Active, u.CreateDate, u.UpdateDate, u.UserName, u.CompAreaID, u.UserDeptID, u.UserLevelID, u.GuestID,
       g.CompanyFrom, g.VisitorNeeds,
       s.LicenseNumber, s.LicenseID, s.LicenseCode, s.ExpiredSIM,
       u.FaceEmbeddingData AS FaceDet, u.UploadPath AS PhotoPath
FROM dbo.Users u
LEFT JOIN dbo.Guest g ON g.GuestID = u.GuestID
OUTER APPLY (SELECT TOP 1 ld.LicenseNumber, ld.SIMType AS LicenseID, l.LicenseCode, ld.ExpiredSIM
             FROM dbo.LicenseDetail ld JOIN dbo.License l ON l.LicenseID = ld.SIMType
             WHERE ld.UserID = u.UserID AND ld.Active = 1
             ORDER BY ld.ExpiredSIM DESC, ld.DetailLicenseID DESC) s;
GO
CREATE OR ALTER TRIGGER dbo.TR_Users_GuestBlacklist ON dbo.Users AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(BlacklistID) OR UPDATE(GuestID)
        UPDATE g SET g.BlacklistID = i.BlacklistID
        FROM dbo.Guest g JOIN inserted i ON i.GuestID = g.GuestID
        WHERE ISNULL(g.BlacklistID, -1) <> ISNULL(i.BlacklistID, -1);
END
GO
UPDATE g SET g.BlacklistID = u.BlacklistID FROM dbo.Guest g JOIN dbo.Users u ON u.GuestID = g.GuestID
WHERE ISNULL(g.BlacklistID, -1) <> ISNULL(u.BlacklistID, -1);
GO
/* ---------- 8. Menu: Visitor & Staff Logs ---------- */
UPDATE dbo.Menu SET Url = '/visitor-logs', MenuName = N'Visitor & Staff Logs' WHERE MenuCode = 'KUNJUNGAN';
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder)
SELECT v.kode, v.nama, p.MenuID, 3, v.url, v.urut
FROM (VALUES ('VSL_SCAN', N'Scan Wajah', '/visitor-logs?tab=scan', 1), ('VSL_LOGS', N'Logs', '/visitor-logs?tab=logs', 2)) v (kode, nama, url, urut)
JOIN dbo.Menu p ON p.MenuCode = 'KUNJUNGAN'
WHERE NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = v.kode);
UPDATE m SET ParentMenuID = p.MenuID, MenuLevel = 3, MenuName = N'Data Orang', Url = '/visitor-logs?tab=orang', SortOrder = 3
FROM dbo.Menu m JOIN dbo.Menu p ON p.MenuCode = 'KUNJUNGAN' WHERE m.MenuCode = 'PERSONEL';
-- Aksi Tambah / Ubah kunjungan pindah ke Scan Wajah; Data Orang bisa Setujui (pendaftaran orang)
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT s.MenuID, ma.ActionID FROM dbo.MenuAction ma JOIN dbo.Menu k ON k.MenuID = ma.MenuID AND k.MenuCode = 'KUNJUNGAN'
CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'VSL_SCAN') s
WHERE NOT EXISTS (SELECT 1 FROM dbo.MenuAction x WHERE x.MenuID = s.MenuID AND x.ActionID = ma.ActionID);
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT MenuID, 5 FROM dbo.Menu WHERE MenuCode = 'PERSONEL'
  AND NOT EXISTS (SELECT 1 FROM dbo.MenuAction x JOIN dbo.Menu m ON m.MenuID = x.MenuID WHERE m.MenuCode = 'PERSONEL' AND x.ActionID = 5);
-- Hak lama KUNJUNGAN disalin ke Scan Wajah (semua aksi) dan Logs (Lihat); hak lama PERSONEL juga membuka induknya
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, MenuDetails, Active)
SELECT t.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.MenuDetails, a.Active
FROM dbo.AccessMenu a JOIN dbo.Menu k ON k.MenuID = a.MenuID AND k.MenuCode = 'KUNJUNGAN'
JOIN dbo.Menu t ON t.MenuCode = 'VSL_SCAN' OR (t.MenuCode = 'VSL_LOGS' AND a.ActionID = 1)
WHERE NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = t.MenuID);
INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, Active)
SELECT DISTINCT k.MenuID, 1, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, 0, 1
FROM dbo.AccessMenu a JOIN dbo.Menu p ON p.MenuID = a.MenuID AND p.MenuCode = 'PERSONEL'
CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'KUNJUNGAN') k
WHERE a.IsDeny = 0 AND a.ActionID = 1
  AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu x WHERE x.MenuID = k.MenuID AND x.ActionID = 1 AND x.IsDeny = 0 AND x.TargetType = a.TargetType
                  AND ISNULL(x.LevelDetID, -1) = ISNULL(a.LevelDetID, -1) AND ISNULL(x.LevelID, -1) = ISNULL(a.LevelID, -1)
                  AND ISNULL(x.DeptID, '') = ISNULL(a.DeptID, '') AND ISNULL(x.UserID, -1) = ISNULL(a.UserID, -1));
DELETE ma FROM dbo.MenuAction ma JOIN dbo.Menu m ON m.MenuID = ma.MenuID WHERE m.MenuCode = 'KUNJUNGAN';
DELETE a FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'KUNJUNGAN' AND a.ActionID <> 1;
-- Menu Pengenalan Wajah (Absensi, Log Audit) dihapus
DELETE a FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode IN ('ABSENSI', 'AUDIT_LOG', 'FACE_RECOGNITION');
DELETE FROM dbo.Menu WHERE MenuCode IN ('ABSENSI', 'AUDIT_LOG');
DELETE FROM dbo.Menu WHERE MenuCode = 'FACE_RECOGNITION' AND NOT EXISTS (SELECT 1 FROM dbo.Menu c WHERE c.ParentMenuID = dbo.Menu.MenuID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/004_normalisasi_orang.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/004_normalisasi_orang.sql', 'CPOS');
GO
