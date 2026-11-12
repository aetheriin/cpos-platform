/* Kejadian gerbang plat: bacaan plat yang sama dari kamera-kamera satu gerbang digabung; arah & sisi plat ditentukan backend deteksi. Aman dijalankan ulang. */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
USE [CPOS];
GO
IF OBJECT_ID('dbo.KejadianPlat') IS NULL
BEGIN
CREATE TABLE dbo.KejadianPlat (
    KejadianID   BIGINT IDENTITY(1,1) PRIMARY KEY,
    Gate         VARCHAR(30)  NOT NULL,
    CompAreaID   BIGINT       NOT NULL CONSTRAINT FK_Kejadian_Area REFERENCES dbo.CompanyArea (CompAreaID),
    PlatNomor    NVARCHAR(15) NOT NULL,                       -- plat dari bacaan dengan keyakinan tertinggi
    IDVehicle    INT NULL CONSTRAINT FK_Kejadian_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),   -- NULL = plat belum terdaftar
    Arah         VARCHAR(11)  NOT NULL CONSTRAINT DF_Kejadian_Arah DEFAULT ('BELUM_PASTI')
                              CONSTRAINT CK_Kejadian_Arah CHECK (Arah IN ('MASUK', 'KELUAR', 'BELUM_PASTI')),
    WaktuMulai   DATETIME     NOT NULL,
    WaktuAkhir   DATETIME     NOT NULL,
    JumlahKamera INT          NOT NULL CONSTRAINT DF_Kejadian_Jml DEFAULT (1),
    ConfMax      FLOAT NULL,
    CreateDate   DATETIME     NOT NULL CONSTRAINT DF_Kejadian_Create DEFAULT (GETDATE())
);
CREATE INDEX IX_Kejadian_Gate ON dbo.KejadianPlat (Gate, CompAreaID, WaktuMulai DESC);
CREATE INDEX IX_Kejadian_Plat ON dbo.KejadianPlat (PlatNomor, WaktuMulai DESC);
END
GO
IF COL_LENGTH('dbo.RiwayatDeteksi', 'KejadianID') IS NULL
    ALTER TABLE dbo.RiwayatDeteksi
        ADD KejadianID BIGINT NULL CONSTRAINT FK_RiwDet_Kejadian REFERENCES dbo.KejadianPlat (KejadianID),
            Sisi VARCHAR(8) NULL CONSTRAINT CK_RiwDet_Sisi CHECK (Sisi IN ('DEPAN', 'BELAKANG'));
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_RiwDet_Kejadian' AND object_id = OBJECT_ID('dbo.RiwayatDeteksi'))
    CREATE INDEX IX_RiwDet_Kejadian ON dbo.RiwayatDeteksi (KejadianID);
GO
-- login detektor (mis. plat_agen) menulis kejadian & melengkapi bacaan

-- Pastikan user database plat_agen tersedia.
IF SUSER_ID(N'plat_agen') IS NOT NULL
   AND USER_ID(N'plat_agen') IS NULL
BEGIN
    CREATE USER [plat_agen] FOR LOGIN [plat_agen];
END
GO

-- Hak akses backend deteksi plat.
IF USER_ID(N'plat_agen') IS NOT NULL
BEGIN
    GRANT SELECT, INSERT, UPDATE
        ON dbo.KejadianPlat TO [plat_agen];

    GRANT UPDATE
        ON dbo.RiwayatDeteksi (KejadianID, Sisi)
        TO [plat_agen];
END
ELSE
BEGIN
    PRINT 'PERINGATAN: Login plat_agen belum tersedia.';
    PRINT 'GRANT dilewati. Buat login terlebih dahulu.';
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/008_kejadian_plat.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/008_kejadian_plat.sql', 'CPOS');
GO