/* Deteksi Plat (uji coba 1 minggu): tabel UserC (pemilik, sementara) & RiwayatDeteksi + menu Mills Operation › Deteksi Plat.
   Plat & jenis kendaraan memakai tabel yang sudah ada (DetailVehicle, VehicleType). Aman dijalankan ulang. */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
USE [CPOS];
GO
IF OBJECT_ID('dbo.UserC') IS NULL
BEGIN
CREATE TABLE dbo.UserC (
    UserCID     INT IDENTITY(1,1) PRIMARY KEY,
    Nama        NVARCHAR(100) NOT NULL,
    IDVehicle   INT NOT NULL CONSTRAINT FK_UserC_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    Keterangan  NVARCHAR(255) NULL,
    Active      BIT NOT NULL CONSTRAINT DF_UserC_Active DEFAULT (1),
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_UserC_Create DEFAULT (GETDATE()),
    CONSTRAINT UX_UserC_Vehicle UNIQUE (IDVehicle)
);
END
GO
IF OBJECT_ID('dbo.RiwayatDeteksi') IS NULL
BEGIN
CREATE TABLE dbo.RiwayatDeteksi (
    DeteksiID       BIGINT IDENTITY(1,1) PRIMARY KEY,
    Waktu           DATETIME     NOT NULL,
    Kamera          VARCHAR(50)  NOT NULL,
    IDVehicle       INT NULL CONSTRAINT FK_RiwDet_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),   -- NULL = plat belum terdaftar
    PlatNomor       NVARCHAR(15) NOT NULL,
    JenisTerdeteksi VARCHAR(20)  NULL,    -- hasil YOLOX (Mobil/Motor/Bus/Truk); dipakai bila plat belum terdaftar
    ConfOCR         FLOAT NULL,
    FotoPath        VARCHAR(255) NULL,    -- path relatif terhadap folder foto
    PlatPath        VARCHAR(255) NULL,    -- potongan plat saja
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_RiwDet_Create DEFAULT (GETDATE())
);
CREATE INDEX IX_RiwDet_Waktu   ON dbo.RiwayatDeteksi (Waktu DESC);
CREATE INDEX IX_RiwDet_Vehicle ON dbo.RiwayatDeteksi (IDVehicle);
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'MON_PLAT')
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
    SELECT 'MON_PLAT', N'Deteksi Plat', MenuID, 2, '/deteksi-plat', 'fa-car-side', 'CPOS', 46 FROM dbo.Menu WHERE MenuCode = 'G_MILLS';
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'MON_PLAT')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, 1, 'ROLE', ld.LevelDetID FROM dbo.Menu m JOIN dbo.LevelDetails ld ON ld.LevelDetCode IN ('HO', 'SECURITY')
    WHERE m.MenuCode = 'MON_PLAT';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/006_deteksi_plat.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/006_deteksi_plat.sql', 'CPOS');
GO