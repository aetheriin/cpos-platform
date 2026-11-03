/* Kamera deteksi plat yang diatur Admin (Admin › Perangkat › Kamera Deteksi Plat). Dibaca backend deteksi plat. Aman dijalankan ulang. */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
USE [CPOS];
GO
IF OBJECT_ID('dbo.CameraDeteksi') IS NULL
CREATE TABLE dbo.CameraDeteksi (
    CamDetID    INT IDENTITY(1,1) PRIMARY KEY,
    CamDetName  VARCHAR(30)   NOT NULL CONSTRAINT UX_CamDet_Name UNIQUE,    -- dipakai detektor & tampil di Riwayat (kolom Kamera)
    CompAreaID  BIGINT        NOT NULL CONSTRAINT FK_CamDet_Area REFERENCES dbo.CompanyArea (CompAreaID),
    Gate        VARCHAR(30)   NULL,                                         -- kamera dengan gerbang sama dipasangkan (fase In/Out)
    Facing      VARCHAR(6)    NOT NULL CONSTRAINT DF_CamDet_Facing DEFAULT ('MASUK') CONSTRAINT CK_CamDet_Facing CHECK (Facing IN ('MASUK', 'KELUAR')),
    RtspUrl     NVARCHAR(500) NOT NULL,                                     -- berisi password kamera: hanya Admin & login detektor
    Note        NVARCHAR(100) NULL,
    SortOrder   INT           NOT NULL CONSTRAINT DF_CamDet_Sort DEFAULT (0),
    Active      BIT           NOT NULL CONSTRAINT DF_CamDet_Active DEFAULT (1),
    UpdateDate  DATETIME      NOT NULL CONSTRAINT DF_CamDet_Upd DEFAULT (GETDATE())
);
GO
-- login yang dipakai detektor (mis. plat_agen) perlu membaca kamera & pengaturan
GRANT SELECT ON dbo.CameraDeteksi TO plat_agen;
GRANT SELECT ON dbo.Setting TO plat_agen;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/007_kamera_deteksi.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/007_kamera_deteksi.sql', 'CPOS');
GO