/* Form Netto Sumber (modul CPOS modules/netto_sumber): isian netto sumber tiket penjualan Ascend yang kosong atau salah.
   Tabel Ascend tidak diubah. Setiap simpan menambah baris baru, jadi riwayatnya utuh; yang berlaku baris terakhir per tiket.
   NettoSumber NULL = isian dibatalkan, tiket kembali memakai angka Ascend. Laporan Tiket Penjualan (Analytics) membaca tabel ini.
   Menu Forms › Netto Sumber (/netto-sumber). Hak di Admin › Hak Akses: Lihat, Tambah (isi tiket yang belum diisi),
   Ubah (ubah atau batalkan isian), Setujui (boleh mengubah isian bulan yang sudah ditutup). Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
IF OBJECT_ID('dbo.NettoSumberIsian', 'U') IS NULL
CREATE TABLE dbo.NettoSumberIsian (
    EntryID           BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_NettoSumberIsian PRIMARY KEY,
    CompID            VARCHAR(10)    NOT NULL,
    TicketType        VARCHAR(4)     NOT NULL CONSTRAINT DF_NettoSumberIsian_Type DEFAULT ('JUAL')
                      CONSTRAINT CK_NettoSumberIsian_Type CHECK (TicketType IN ('JUAL', 'BELI')),
    TicketNo          VARCHAR(50)    NOT NULL,
    TicketDate        DATE           NOT NULL,
    NettoSumber       DECIMAL(18, 2) NULL CONSTRAINT CK_NettoSumberIsian_Netto CHECK (NettoSumber IS NULL OR NettoSumber > 0),
    RefNo             NVARCHAR(50)   NULL,                  -- mis. nomor tiket timbang pihak lain
    Notes             NVARCHAR(500)  NULL,
    NettoAscend       DECIMAL(18, 2) NOT NULL,              -- netto timbangan kita saat diisi
    NettoSumberAscend DECIMAL(18, 2) NOT NULL,              -- netto sumber di Ascend saat diisi
    CreateBy          BIGINT         NOT NULL CONSTRAINT FK_NettoSumberIsian_User REFERENCES dbo.Users (UserID),
    CreateDate        DATETIME2(0)   NOT NULL CONSTRAINT DF_NettoSumberIsian_Create DEFAULT (SYSDATETIME())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NettoSumberIsian_Tiket' AND object_id = OBJECT_ID('dbo.NettoSumberIsian'))
    CREATE INDEX IX_NettoSumberIsian_Tiket ON dbo.NettoSumberIsian (CompID, TicketType, TicketNo, EntryID DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NettoSumberIsian_Tanggal' AND object_id = OBJECT_ID('dbo.NettoSumberIsian'))
    CREATE INDEX IX_NettoSumberIsian_Tanggal ON dbo.NettoSumberIsian (TicketType, TicketDate) INCLUDE (CompID, TicketNo);
GO
INSERT INTO dbo.Menu (MenuCode, MenuName, Description, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT 'FM_NETTO_SUMBER', N'Netto Sumber',
       N'Isi netto sumber tiket penjualan. Hak Setujui: boleh mengubah isian bulan yang sudah ditutup.',
       p.MenuID, 2, '/netto-sumber', 'fa-scale-balanced', 'CPOS', 50
FROM dbo.Menu p
WHERE p.MenuCode = 'G_FORMS'
  AND NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = 'FM_NETTO_SUMBER' OR m.Url = '/netto-sumber');
GO
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT m.MenuID, x.ActionID
FROM dbo.Menu m CROSS JOIN (VALUES (2), (3), (5)) x (ActionID)
WHERE m.MenuCode = 'FM_NETTO_SUMBER'
  AND NOT EXISTS (SELECT 1 FROM dbo.MenuAction a WHERE a.MenuID = m.MenuID AND a.ActionID = x.ActionID);
GO
-- Hak awal hanya bila menu ini belum punya aturan: HO boleh semua aksi. Peran lain diatur di Admin › Hak Akses.
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'FM_NETTO_SUMBER')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID)
    SELECT m.MenuID, x.ActionID, 'ROLE', ld.LevelDetID
    FROM dbo.Menu m
    JOIN dbo.LevelDetails ld ON ld.LevelDetCode = 'HO'
    CROSS JOIN (VALUES (1), (2), (3), (5)) x (ActionID)
    WHERE m.MenuCode = 'FM_NETTO_SUMBER';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/029_netto_sumber.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/029_netto_sumber.sql', 'CPOS');
GO
SELECT m.MenuCode, m.MenuName, m.Url, OBJECT_ID('dbo.NettoSumberIsian') AS TabelIsian,
       (SELECT COUNT(*) FROM dbo.MenuAction a WHERE a.MenuID = m.MenuID) AS Aksi,
       (SELECT COUNT(*) FROM dbo.AccessMenu a WHERE a.MenuID = m.MenuID) AS HakAkses
FROM dbo.Menu m WHERE m.MenuCode = 'FM_NETTO_SUMBER';
