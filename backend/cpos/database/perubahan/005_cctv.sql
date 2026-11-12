/* Monitoring CCTV tahap 1 (live per area): tabel CameraGateway, Camera, CameraEvent + menu Mills Operation › Monitoring CCTV
   (/cctv). Hak lihat awal: peran Head Office & Security; setelah itu diatur di Admin › Hak Akses (termasuk cakupan data area).
   Aman dijalankan ulang. Panduan pemasangan gateway video: docs/PANDUAN_CCTV.md */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
USE [CPOS];
GO
IF OBJECT_ID('dbo.CameraGateway') IS NULL
BEGIN
CREATE TABLE dbo.CameraGateway (
    GatewayID    INT IDENTITY(1,1) PRIMARY KEY,
    CompAreaID   BIGINT NOT NULL CONSTRAINT FK_CamGw_Area REFERENCES dbo.CompanyArea (CompAreaID),
    GatewayName  NVARCHAR(100) NOT NULL,
    BaseUrl      VARCHAR(255)  NOT NULL,          -- alamat API gateway dari server CPOS, mis. http://192.168.10.5:1984
    LastSeen     DATETIME NULL,
    Active       BIT NOT NULL CONSTRAINT DF_CamGw_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_CamGw_Create DEFAULT (GETDATE())
);
END
GO
IF OBJECT_ID('dbo.Camera') IS NULL
BEGIN
CREATE TABLE dbo.Camera (
    CameraID     INT IDENTITY(1,1) PRIMARY KEY,
    CameraCode   VARCHAR(20)   NOT NULL CONSTRAINT UX_Camera_Code UNIQUE,
    CameraName   NVARCHAR(100) NOT NULL,
    CompAreaID   BIGINT NOT NULL CONSTRAINT FK_Camera_Area REFERENCES dbo.CompanyArea (CompAreaID),
    GatewayID    INT NOT NULL CONSTRAINT FK_Camera_Gateway REFERENCES dbo.CameraGateway (GatewayID),
    Point        VARCHAR(20)   NOT NULL CONSTRAINT CK_Camera_Point CHECK (Point IN ('POS_MASUK', 'POS_KELUAR', 'JEMBATAN', 'SORTASI', 'UMUM')),
    ScaleID      INT NULL CONSTRAINT FK_Camera_Scale REFERENCES dbo.Scale (ScaleID),          -- kamera milik jembatan timbang
    Role         VARCHAR(10)   NOT NULL CONSTRAINT DF_Camera_Role DEFAULT ('UMUM')
                 CONSTRAINT CK_Camera_Role CHECK (Role IN ('DEPAN', 'ATAS', 'PLAT', 'WAJAH', 'UMUM')),
    Brand        NVARCHAR(100) NULL,              -- merk / tipe (Hikvision, Dahua, ...)
    MainStream   VARCHAR(100)  NOT NULL,          -- nama stream di gateway (kualitas penuh, layar penuh)
    SubStream    VARCHAR(100)  NULL,              -- nama stream ringan (grid / dilihat dari HO); kosong = MainStream
    AIMode       VARCHAR(10)   NOT NULL CONSTRAINT DF_Camera_AI DEFAULT ('NONE')
                 CONSTRAINT CK_Camera_AI CHECK (AIMode IN ('NONE', 'KAMERA', 'SERVER')),   -- tahap berikutnya
    Settings     NVARCHAR(MAX) NULL CONSTRAINT CK_Camera_Settings CHECK (Settings IS NULL OR ISJSON(Settings) = 1),
    LastSeen     DATETIME NULL,
    SortOrder    INT NOT NULL CONSTRAINT DF_Camera_Sort DEFAULT (0),
    Active       BIT NOT NULL CONSTRAINT DF_Camera_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_Camera_Create DEFAULT (GETDATE())
);
CREATE INDEX IX_Camera_Area ON dbo.Camera (CompAreaID, Active);
END
GO
IF OBJECT_ID('dbo.CameraEvent') IS NULL
BEGIN
CREATE TABLE dbo.CameraEvent (
    EventID       BIGINT IDENTITY(1,1) PRIMARY KEY,
    CameraID      INT NOT NULL CONSTRAINT FK_CamEvent_Camera REFERENCES dbo.Camera (CameraID),
    EventType     VARCHAR(30) NOT NULL,           -- PLAT_TERBACA, TRUK_MASUK_ZONA, BERHENTI_LAMA, ORANG_DI_ZONA, KAMERA_PUTUS
    StartTime     DATETIME NOT NULL CONSTRAINT DF_CamEvent_Start DEFAULT (GETDATE()),
    EndTime       DATETIME NULL,
    DurationSec   INT NULL,
    PlateText     VARCHAR(15) NULL,
    Confidence    FLOAT NULL,
    IDVehicle     INT NULL CONSTRAINT FK_CamEvent_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    TicketNumber  VARCHAR(50) NULL,
    SnapshotPath  VARCHAR(255) NULL,
    Data          NVARCHAR(MAX) NULL CONSTRAINT CK_CamEvent_Data CHECK (Data IS NULL OR ISJSON(Data) = 1),
    Status        VARCHAR(10) NOT NULL CONSTRAINT DF_CamEvent_Status DEFAULT ('BARU')
                  CONSTRAINT CK_CamEvent_Status CHECK (Status IN ('BARU', 'DILIHAT', 'SELESAI'))
);
CREATE INDEX IX_CamEvent_Camera_Time ON dbo.CameraEvent (CameraID, StartTime DESC);
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'MON_CCTV')
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
    SELECT 'MON_CCTV', N'Monitoring CCTV', MenuID, 2, '/cctv', 'fa-video', 'CPOS', 45 FROM dbo.Menu WHERE MenuCode = 'G_MILLS';
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'MON_CCTV')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, 1, 'ROLE', ld.LevelDetID FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode IN ('HO', 'SECURITY')
    WHERE m.MenuCode = 'MON_CCTV';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/005_cctv.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/005_cctv.sql', 'CPOS');
GO
