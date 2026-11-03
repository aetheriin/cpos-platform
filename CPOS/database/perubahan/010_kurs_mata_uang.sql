/* Kurs mata uang ke rupiah (Data Master › Kurs Mata Uang, /master?tab=kurs).
   Riwayat per tanggal berlaku: kurs dipakai sejak RateDate sampai ada kurs berikutnya. Tidak diubah; salah input dibatalkan (void)
   lalu input ulang. Jenis: TRANSAKSI (mis. JISDOR / kurs pajak) dan PENUTUPAN (akhir bulan, penilaian ulang saldo valas).
   CompID kosong = berlaku untuk semua perusahaan. Dibaca laporan Analytics (Cash Flow) lewat login pythonReport (hanya SELECT).
   Hak awal disalin dari menu Mata Uang & Bank; setelah itu diatur di Admin › Hak Akses. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
IF OBJECT_ID('dbo.ExchangeRate') IS NULL
BEGIN
    CREATE TABLE dbo.ExchangeRate (
        ExchangeRateID  BIGINT IDENTITY(1,1) PRIMARY KEY,
        CurrencyID      INT NOT NULL CONSTRAINT FK_ExchangeRate_Currency REFERENCES dbo.Currency (CurrencyID),
        RateType        VARCHAR(10) NOT NULL CONSTRAINT CK_ExchangeRate_Type CHECK (RateType IN ('TRANSAKSI', 'PENUTUPAN')),
        RateDate        DATE NOT NULL,                                   -- berlaku sejak tanggal ini
        Rate            DECIMAL(18, 4) NOT NULL CONSTRAINT CK_ExchangeRate_Rate CHECK (Rate > 0),   -- 1 unit mata uang = Rate rupiah
        CompID          VARCHAR(5) NULL CONSTRAINT FK_ExchangeRate_Company REFERENCES dbo.Company (CompID),  -- NULL = semua perusahaan
        Source          VARCHAR(10) NULL,                                -- JISDOR / PAJAK / BANK / INTERNET / LAINNYA
        Description     NVARCHAR(255) NULL,
        CreateDate      DATETIME NOT NULL CONSTRAINT DF_ExchangeRate_Create DEFAULT (GETDATE()),
        CreateBy        BIGINT NULL CONSTRAINT FK_ExchangeRate_CreateBy REFERENCES dbo.Users (UserID),
        IsVoid          BIT NOT NULL CONSTRAINT DF_ExchangeRate_Void DEFAULT (0),
        VoidDate        DATETIME NULL,
        VoidBy          BIGINT NULL CONSTRAINT FK_ExchangeRate_VoidBy REFERENCES dbo.Users (UserID)
    );
    -- satu kurs berlaku per mata uang, jenis, tanggal, dan perusahaan (NULL dihitung sama)
    CREATE UNIQUE INDEX UX_ExchangeRate_Berlaku ON dbo.ExchangeRate (CurrencyID, RateType, RateDate, CompID) WHERE IsVoid = 0;
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'MASTER_KURS')
    INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder, AppCode)
    SELECT 'MASTER_KURS', N'Kurs Mata Uang', p.MenuID, 3, '/master?tab=kurs', 6, 'CPOS'
    FROM dbo.Menu p WHERE p.MenuCode = 'MASTER';
GO
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT baru.MenuID, ma.ActionID
FROM dbo.MenuAction ma JOIN dbo.Menu m ON m.MenuID = ma.MenuID AND m.MenuCode = 'MASTER_KEUANGAN'
CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'MASTER_KURS') baru
WHERE NOT EXISTS (SELECT 1 FROM dbo.MenuAction x WHERE x.MenuID = baru.MenuID AND x.ActionID = ma.ActionID);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'MASTER_KURS')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny, Active)
    SELECT baru.MenuID, a.ActionID, a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny, a.Active
    FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID AND m.MenuCode = 'MASTER_KEUANGAN'
    CROSS JOIN (SELECT MenuID FROM dbo.Menu WHERE MenuCode = 'MASTER_KURS') baru;
GO
-- Analytics (login pythonReport) hanya boleh membaca kurs & daftar mata uang
IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'pythonReport')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'pythonReport')
        CREATE USER [pythonReport] FOR LOGIN [pythonReport];
    GRANT SELECT ON dbo.ExchangeRate TO [pythonReport];
    GRANT SELECT ON dbo.Currency TO [pythonReport];
END
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/010_kurs_mata_uang.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/010_kurs_mata_uang.sql', 'CPOS');
GO
