/* RekapIn (modul CPOS): tabel milik RekapIn di schema rekap. Aman dijalankan ulang.
   User, perusahaan, harga harian, dan hak akses memakai tabel inti CPOS (dbo.Users, dbo.Company, dbo.DailyPrice, dbo.AccessMenu).
   Jalankan setelah CPOS\database\schema.sql. */
USE [CPOS]
GO
IF SCHEMA_ID('rekap') IS NULL EXEC ('CREATE SCHEMA rekap');
GO
-- Kategori kesalahan request operator (dulu tabel features)
IF OBJECT_ID('rekap.RequestCategory', 'U') IS NULL
CREATE TABLE rekap.RequestCategory (
    CategoryID   INT IDENTITY(1,1) PRIMARY KEY,
    CategoryName NVARCHAR(180) NOT NULL CONSTRAINT UX_RkCategory_Name UNIQUE,
    Active       BIT NOT NULL CONSTRAINT DF_RkCategory_Active DEFAULT (1),
    CreateBy     BIGINT NULL CONSTRAINT FK_RkCategory_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_RkCategory_Create DEFAULT (GETDATE())
);
GO
-- Request operator (dulu operator_requests): operator = user CPOS, tiket = tiket timbang
IF OBJECT_ID('rekap.OperatorRequest', 'U') IS NULL
CREATE TABLE rekap.OperatorRequest (
    RequestID     INT IDENTITY(1,1) PRIMARY KEY,
    OperatorID    BIGINT        NOT NULL CONSTRAINT FK_RkRequest_Operator REFERENCES dbo.Users (UserID),
    CategoryID    INT           NOT NULL CONSTRAINT FK_RkRequest_Category REFERENCES rekap.RequestCategory (CategoryID),
    TicketNumber  NVARCHAR(100) NOT NULL,
    TicketDetails NVARCHAR(MAX) NOT NULL CONSTRAINT DF_RkRequest_Details DEFAULT (N'{}')
                  CONSTRAINT CK_RkRequest_Details CHECK (ISJSON(TicketDetails) = 1),
    Remarks       NVARCHAR(MAX) NOT NULL CONSTRAINT DF_RkRequest_Remarks DEFAULT (N''),
    ActionRemarks NVARCHAR(255) NOT NULL CONSTRAINT DF_RkRequest_ActRemarks DEFAULT (N''),
    Status        VARCHAR(10)   NOT NULL CONSTRAINT DF_RkRequest_Status DEFAULT ('Pending')
                  CONSTRAINT CK_RkRequest_Status CHECK (Status IN ('Pending', 'Approved', 'Rejected', 'Done')),
    CreateBy      BIGINT        NOT NULL CONSTRAINT FK_RkRequest_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate    DATETIME      NOT NULL CONSTRAINT DF_RkRequest_Create DEFAULT (GETDATE()),
    ActionBy      BIGINT        NULL CONSTRAINT FK_RkRequest_ActionBy REFERENCES dbo.Users (UserID),
    ActionDate    DATETIME      NULL,          -- disetujui / ditolak
    DoneBy        BIGINT        NULL CONSTRAINT FK_RkRequest_DoneBy REFERENCES dbo.Users (UserID),
    DoneDate      DATETIME      NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_RkRequest_Status')
    CREATE INDEX IX_RkRequest_Status ON rekap.OperatorRequest (Status, CreateDate DESC);
GO
-- Kategori awal (contoh dari RekapIn)
INSERT INTO rekap.RequestCategory (CategoryName)
SELECT v.n FROM (VALUES (N'Salah input netto'), (N'Salah input nomor kendaraan'), (N'Salah pilih supplier'),
                        (N'Tiket ganda'), (N'Salah input potongan'), (N'Lainnya')) v (n)
WHERE NOT EXISTS (SELECT 1 FROM rekap.RequestCategory c WHERE c.CategoryName = v.n);
GO
-- Alamat menu RekapIn di sidebar CPOS (menu sudah terdaftar di schema.sql, kode RK_*)
UPDATE m SET Url = v.url
FROM dbo.Menu m JOIN (VALUES ('RK_DASHBOARD', '/rekapin/dashboard'), ('RK_REQUEST', '/rekapin/request'), ('RK_HARGA', '/rekapin/harga'),
                             ('RK_FITUR', '/rekapin/kategori'), ('RK_TBS_DAILY', '/rekapin/tbs/daily'),
                             ('RK_TBS_WEEKLY', '/rekapin/tbs/weekly'), ('RK_TBS_MONTHLY', '/rekapin/tbs/monthly')) v (kode, url)
  ON v.kode = m.MenuCode
WHERE m.Url IS NULL;
GO
-- Hak bawaan (hanya bila menu RekapIn belum punya aturan; setelah itu diatur di Admin › Hak Akses):
-- HO = semua menu & aksi RekapIn (termasuk gerbang Reports); operator timbangan = lihat & buat Request Operator.
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode LIKE 'RK[_]%')
BEGIN
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, x.ActionID, 'ROLE', ld.LevelDetID
    FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode = 'HO'
    CROSS APPLY (SELECT 1 AS ActionID UNION SELECT ma.ActionID FROM dbo.MenuAction ma WHERE ma.MenuID = m.MenuID) x
    WHERE m.MenuCode LIKE 'RK[_]%';
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, x.ActionID, 'ROLE', ld.LevelDetID
    FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode = 'OPERATOR_TIMBANG'
    CROSS APPLY (VALUES (1), (2)) x (ActionID)
    WHERE m.MenuCode = 'RK_REQUEST';
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, 1, 'ROLE', ld.LevelDetID
    FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode = 'HO'
    WHERE m.MenuCode = 'G_REPORTS'
      AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a WHERE a.MenuID = m.MenuID AND a.ActionID = 1 AND a.TargetType = 'ROLE' AND a.LevelDetID = ld.LevelDetID);
END
GO
-- Hak akun aplikasi (bila memakai login khusus weighbridge_app, lihat CPOS\database\keamanan)
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'weighbridge_app')
BEGIN
    GRANT SELECT, INSERT, UPDATE ON SCHEMA::rekap TO [weighbridge_app];
    GRANT DELETE ON rekap.OperatorRequest TO [weighbridge_app];
    GRANT DELETE ON dbo.DailyPrice TO [weighbridge_app];
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'modules/rekapin/database/001_rekap.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('modules/rekapin/database/001_rekap.sql', 'REKAPIN');
GO
