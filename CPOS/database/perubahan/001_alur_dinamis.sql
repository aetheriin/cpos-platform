/* Alur tiket dinamis (tahap 1): alur per Area + Produk, tahap paralel, Security Keluar, tahap milik tiket.
   Untuk database CPOS yang sudah berjalan (database baru sudah lengkap dari schema.sql). Aman dijalankan ulang.
   Hanya menambah tabel / kolom / baris; perilaku halaman belum berubah. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF COL_LENGTH('dbo.Flow', 'Description') IS NULL
    ALTER TABLE dbo.Flow ADD Description NVARCHAR(255) NULL;
GO
-- Tahap paralel: GroupNo sama = boleh dikerjakan dalam urutan bebas. Alur lama: satu tahap satu kelompok.
IF COL_LENGTH('dbo.FlowStep', 'GroupNo') IS NULL
BEGIN
    ALTER TABLE dbo.FlowStep ADD GroupNo TINYINT NULL;
    EXEC ('UPDATE dbo.FlowStep SET GroupNo = StepNo');
    EXEC ('ALTER TABLE dbo.FlowStep ALTER COLUMN GroupNo TINYINT NOT NULL');
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.FlowStage WHERE StageCode = 'SECURITY_KELUAR')
    INSERT INTO dbo.FlowStage (StageCode, StageName, SortOrder) VALUES ('SECURITY_KELUAR', N'Security Keluar', 6);
GO
IF OBJECT_ID('dbo.FlowRule', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FlowRule (
        FlowRuleID  INT IDENTITY(1,1) PRIMARY KEY,
        CompAreaID  BIGINT NOT NULL CONSTRAINT FK_FlowRule_Area REFERENCES dbo.CompanyArea (CompAreaID),
        ProductID   INT NULL CONSTRAINT FK_FlowRule_Product REFERENCES dbo.Product (ProductID),
        FlowID      INT NOT NULL CONSTRAINT FK_FlowRule_Flow REFERENCES dbo.Flow (FlowID),
        Active      BIT NOT NULL CONSTRAINT DF_FlowRule_Active DEFAULT (1),
        CreateBy    BIGINT NULL CONSTRAINT FK_FlowRule_User REFERENCES dbo.Users (UserID),
        CreateDate  DATETIME NOT NULL CONSTRAINT DF_FlowRule_Date DEFAULT (GETDATE())
    );
    CREATE UNIQUE INDEX UX_FlowRule_AreaProduct ON dbo.FlowRule (CompAreaID, ProductID) WHERE ProductID IS NOT NULL;
    CREATE UNIQUE INDEX UX_FlowRule_AreaAll ON dbo.FlowRule (CompAreaID) WHERE ProductID IS NULL;
END
GO
IF OBJECT_ID('dbo.WeightBridgeStage', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.WeightBridgeStage (
        TicketNumber  VARCHAR(50) NOT NULL CONSTRAINT FK_WBStage_WB REFERENCES dbo.WeightBridge (TicketNumber),
        StageCode     VARCHAR(20) NOT NULL CONSTRAINT FK_WBStage_Stage REFERENCES dbo.FlowStage (StageCode),
        StepNo        TINYINT NOT NULL,
        GroupNo       TINYINT NOT NULL,
        Status        VARCHAR(10) NOT NULL CONSTRAINT DF_WBStage_Status DEFAULT ('MENUNGGU')
                      CONSTRAINT CK_WBStage_Status CHECK (Status IN ('MENUNGGU', 'SELESAI', 'DILEWATI')),
        FinishDate    DATETIME NULL,
        FinishBy      BIGINT NULL CONSTRAINT FK_WBStage_User REFERENCES dbo.Users (UserID),
        CONSTRAINT PK_WBStage PRIMARY KEY (TicketNumber, StageCode)
    );
    CREATE INDEX IX_WBStage_Menunggu ON dbo.WeightBridgeStage (StageCode, Status) INCLUDE (TicketNumber, GroupNo);
END
GO
-- Hak akun aplikasi (bila memakai login khusus weighbridge_app)
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'weighbridge_app')
BEGIN
    GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.FlowRule TO [weighbridge_app];
    GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.WeightBridgeStage TO [weighbridge_app];
    GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Flow TO [weighbridge_app];
    GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.FlowStep TO [weighbridge_app];
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/001_alur_dinamis.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/001_alur_dinamis.sql', 'CPOS');
GO
