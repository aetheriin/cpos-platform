/* Kode personel (Users.UserCode, mis. DRV-001) tidak dipakai lagi: orang dikenali dari ID, nama, dan NIK.
   Kolom, indeks, dan pemakaiannya di view UserProfile / sp_CekSesi dihapus. Username login disimpan huruf besar.
   Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
CREATE OR ALTER VIEW dbo.UserProfile AS
SELECT u.UserID, u.NoKTP, u.Nama, u.Email, u.IsUpload, u.CurrentHash,
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
/* Sesi login masih berlaku? Dipakai aplikasi lain untuk menerima user yang sudah login di master page.
   Berlaku = belum logout / dipaksa keluar, belum melewati SESI_IDLE_MENIT sejak aktif terakhir dan SESI_MAKS_JAM sejak login,
   dan user masih aktif. @Touch = 1: catat aktivitas (sesi tidak dianggap idle). Kosong = tidak berlaku (arahkan ke login). */
CREATE OR ALTER PROCEDURE dbo.sp_CekSesi
    @SessionID VARCHAR(24),
    @Touch     BIT = 0
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @idle INT = dbo.fn_SettingInt('SESI_IDLE_MENIT', 120), @maks INT = dbo.fn_SettingInt('SESI_MAKS_JAM', 12);
    IF @Touch = 1
        UPDATE dbo.UserSession SET LastActive = GETDATE()
        WHERE SessionID = @SessionID AND EndDate IS NULL
          AND LastActive >= DATEADD(MINUTE, -@idle, GETDATE()) AND LoginDate >= DATEADD(HOUR, -@maks, GETDATE());
    SELECT s.SessionID, u.UserID, u.UserName, u.Nama, u.UserLevelID AS LevelDetID, ld.LevelDetName, lv.IsAdmin,
           u.CompAreaID, ld.HomeUrl, s.LoginDate, s.LastActive,
           CASE WHEN DATEADD(MINUTE, @idle, s.LastActive) < DATEADD(HOUR, @maks, s.LoginDate)
                THEN DATEADD(MINUTE, @idle, s.LastActive) ELSE DATEADD(HOUR, @maks, s.LoginDate) END AS ExpireDate
    FROM dbo.UserSession s
    JOIN dbo.Users u ON u.UserID = s.UserID
    JOIN dbo.LevelDetails ld ON ld.LevelDetID = u.UserLevelID
    JOIN dbo.Level lv ON lv.LevelID = ld.LevelID
    WHERE s.SessionID = @SessionID AND s.EndDate IS NULL AND u.Active = 1
      AND s.LastActive >= DATEADD(MINUTE, -@idle, GETDATE()) AND s.LoginDate >= DATEADD(HOUR, -@maks, GETDATE());
END
GO
IF COL_LENGTH('dbo.Users', 'UserCode') IS NOT NULL
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Users_UserCode' AND object_id = OBJECT_ID('dbo.Users'))
        DROP INDEX UX_Users_UserCode ON dbo.Users;
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Users_Active' AND object_id = OBJECT_ID('dbo.Users'))
        DROP INDEX IX_Users_Active ON dbo.Users;
    EXEC('CREATE INDEX IX_Users_Active ON dbo.Users (Active) INCLUDE (Nama, GuestID, UserLevelID)');
    ALTER TABLE dbo.Users DROP COLUMN UserCode;
END
GO
UPDATE dbo.Users SET UserName = UPPER(UserName)
WHERE UserName IS NOT NULL AND UserName <> UPPER(UserName) COLLATE Latin1_General_CS_AS;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/009_hapus_kode_personel.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/009_hapus_kode_personel.sql', 'CPOS');
GO
