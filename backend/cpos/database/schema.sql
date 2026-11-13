SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
IF DB_ID('CPOS') IS NULL CREATE DATABASE CPOS;
GO
/* Baca data tidak menunggu kunci tulis (migrasi 018) */
ALTER DATABASE CPOS SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE [CPOS]
GO

CREATE TABLE dbo.Company (
    CompID       VARCHAR(5)       NOT NULL PRIMARY KEY,           -- kode perusahaan, mis. YBS, SUN
    CompName     NVARCHAR(100) NOT NULL,
    CompAddress  NVARCHAR(255) NULL,
    Status       BIT NOT NULL CONSTRAINT DF_Company_Active DEFAULT (1),
    Description  NVARCHAR(255) NULL,
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_Company_Create DEFAULT (GETDATE())
);
-- Mill = tipe area, sama untuk semua perusahaan (HO, PKS, REFINERY, ...). IsHeadOffice = kantor pusat
CREATE TABLE dbo.Mill (
    MillID       BIGINT IDENTITY(1,1) PRIMARY KEY,
    MillCode     VARCHAR(10)   NOT NULL CONSTRAINT UX_Mill_Code UNIQUE,
    MillName     NVARCHAR(50)  NOT NULL,
    IsHeadOffice BIT NOT NULL CONSTRAINT DF_Mill_HO DEFAULT (0),
    Status       BIT NOT NULL CONSTRAINT DF_Mill_Active DEFAULT (1),
    Description  NVARCHAR(255) NULL,
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_Mill_Create DEFAULT (GETDATE())
);
-- Area milik perusahaan (YBS · OFFICE, YBS · REFINERY). AreaCode ikut MillCode.
CREATE TABLE dbo.CompanyArea (
    CompAreaID   BIGINT IDENTITY(1,1) PRIMARY KEY,
    CompID       VARCHAR(5)       NOT NULL CONSTRAINT FK_CompArea_Company REFERENCES dbo.Company (CompID),
    MillID       BIGINT        NULL CONSTRAINT FK_CompArea_Mill REFERENCES dbo.Mill (MillID),
    AreaCode     VARCHAR(10)   NOT NULL,
    AreaName     NVARCHAR(100) NOT NULL,
    AreaDesc     NVARCHAR(255) NULL,
    AreaAddress  NVARCHAR(255) NULL,
    Status       BIT NOT NULL CONSTRAINT DF_CompArea_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_CompArea_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_CompArea_CompName ON dbo.CompanyArea (CompID, AreaName);
CREATE TABLE dbo.Department (
    DeptID       VARCHAR(5)       NOT NULL PRIMARY KEY,           -- kode departemen, mis. TBG, HRD
    DeptName     NVARCHAR(120) NOT NULL CONSTRAINT UX_Department_Name UNIQUE,
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_Department_Active DEFAULT (1)
);
-- Departemen yang ada di sebuah area; akun memakai baris ini (Users.UserDeptID)
CREATE TABLE dbo.DepartmentDetails (
    DeptDetailID BIGINT IDENTITY(1,1) PRIMARY KEY,
    CompAreaID   BIGINT        NOT NULL CONSTRAINT FK_DeptDet_Area REFERENCES dbo.CompanyArea (CompAreaID),
    DeptID       VARCHAR(5)       NOT NULL CONSTRAINT FK_DeptDet_Dept REFERENCES dbo.Department (DeptID),
    Location     NVARCHAR(120) NOT NULL CONSTRAINT DF_DeptDet_Location DEFAULT ('SITE'),   -- SITE / HO
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_DeptDet_Active DEFAULT (1),
    CONSTRAINT UX_DeptDet_AreaDept UNIQUE (CompAreaID, DeptID)
);
-- Jabatan umum: Admin, Manager, Supervisor, Staff, Magang (ditambah di Admin › Organisasi)
CREATE TABLE dbo.Level (
    LevelID      INT IDENTITY(1,1) PRIMARY KEY,
    LevelName    NVARCHAR(120) NOT NULL CONSTRAINT UX_Level_Name UNIQUE,
    Description  NVARCHAR(255) NULL,
    IsAdmin      BIT NOT NULL CONSTRAINT DF_Level_Admin DEFAULT (0),     -- admin sistem: hanya menu Admin
    SortOrder    INT NOT NULL CONSTRAINT DF_Level_Sort DEFAULT (100),
    Active       BIT NOT NULL CONSTRAINT DF_Level_Active DEFAULT (1)
);
-- Peran = Departemen + Level (mis. "Security · Staff"); hak menu (AccessMenu) & halaman awal menempel di sini.
-- CompAreaID NULL = berlaku di semua area. Dibuat otomatis saat hak akses / akun pertama memakai gabungan ini.
CREATE TABLE dbo.LevelDetails (
    LevelDetID   INT IDENTITY(1,1) PRIMARY KEY,
    CompAreaID   BIGINT        NULL CONSTRAINT FK_LevelDet_Area REFERENCES dbo.CompanyArea (CompAreaID),
    LevelID      INT           NOT NULL CONSTRAINT FK_LevelDet_Level REFERENCES dbo.Level (LevelID),
    DeptID       VARCHAR(5)       NULL CONSTRAINT FK_LevelDet_Dept REFERENCES dbo.Department (DeptID),   -- NULL = admin sistem
    LevelDetCode VARCHAR(30)   NOT NULL CONSTRAINT UX_LevelDet_Code UNIQUE,
    LevelDetName NVARCHAR(120) NOT NULL,
    HomeUrl      VARCHAR(100)  NOT NULL CONSTRAINT DF_LevelDet_Home DEFAULT ('/weighbridge?view=list'),
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_LevelDet_Active DEFAULT (1)
);
CREATE UNIQUE INDEX UX_LevelDet_Role ON dbo.LevelDetails (DeptID, LevelID) WHERE CompAreaID IS NULL AND DeptID IS NOT NULL;
-- Menu 3 level (flowchart navbar): Lv1 grup, Lv2 halaman, Lv3 bagian / sub-halaman. Url NULL = belum ada (tautan '#').
CREATE TABLE dbo.Menu (
    MenuID       INT IDENTITY(1,1) PRIMARY KEY,
    MenuCode     VARCHAR(40)   NOT NULL CONSTRAINT UX_Menu_Code UNIQUE,
    MenuName     NVARCHAR(100) NOT NULL,
    Description  NVARCHAR(255) NULL,
    ParentMenuID INT           NULL CONSTRAINT FK_Menu_Parent REFERENCES dbo.Menu (MenuID),
    MenuLevel    TINYINT       NOT NULL CONSTRAINT DF_Menu_Level DEFAULT (2) CONSTRAINT CK_Menu_Level CHECK (MenuLevel BETWEEN 1 AND 3),
    Url          VARCHAR(200)  NULL,
    Icon         VARCHAR(40)   NULL,
    AppCode      VARCHAR(20)   NOT NULL CONSTRAINT DF_Menu_App DEFAULT ('CPOS'),   -- CPOS / ANALYTICS / REKAPIN
    SortOrder    INT NOT NULL CONSTRAINT DF_Menu_Sort DEFAULT (0),
    CompAreaID   BIGINT        NULL CONSTRAINT FK_Menu_Area REFERENCES dbo.CompanyArea (CompAreaID),   -- NULL = semua area
    Active       BIT NOT NULL CONSTRAINT DF_Menu_Active DEFAULT (1)
);
CREATE TABLE dbo.ActionType (
    ActionID     INT           NOT NULL PRIMARY KEY,
    TypeName     VARCHAR(100)  NOT NULL CONSTRAINT UX_ActionType_Name UNIQUE,
    Description  VARCHAR(255)  NULL,
    Active       BIT NOT NULL CONSTRAINT DF_ActionType_Active DEFAULT (1)
);
-- Aksi yang berlaku di sebuah menu selain View (Lihat selalu ada), mis. Blacklist: Create, Delete, Approve
CREATE TABLE dbo.MenuAction (
    MenuID       INT NOT NULL CONSTRAINT FK_MenuAction_Menu REFERENCES dbo.Menu (MenuID) ON DELETE CASCADE,
    ActionID     INT NOT NULL CONSTRAINT FK_MenuAction_Action REFERENCES dbo.ActionType (ActionID),
    CONSTRAINT PK_MenuAction PRIMARY KEY (MenuID, ActionID)
);
/* Aturan hak menu (Admin › Hak Akses): satu baris per menu x aksi x sasaran.
   TargetType: ALL = semua user, ROLE = peran (LevelDetails: departemen + jabatan), LEVEL = jabatan, DEPT = departemen,
   USER = satu user. Kolom sasaran yang sesuai TargetType yang diisi, sisanya NULL.
   IsDeny 1 = Larang: aksi itu dicabut untuk sasaran ini; Larang selalu mengalahkan Izinkan.
   MenuDetails = cakupan data aturan Izinkan (JSON, sama di semua baris aksi satu aturan; NULL = area sendiri):
     {"cakupan":"AREA"} area pengguna (kantor pusat: semua) · {"cakupan":"PT"} semua area PT pengguna ·
     {"cakupan":"SEMUA"} semua PT · {"cakupan":"PT_TERTENTU","pt":["YBS","SJN"]}. Beberapa aturan cocok = digabung. */
CREATE TABLE dbo.AccessMenu (
    AccessMenuID INT IDENTITY(1,1) PRIMARY KEY,
    MenuID       INT         NOT NULL CONSTRAINT FK_AccessMenu_Menu REFERENCES dbo.Menu (MenuID),
    ActionID     INT         NOT NULL CONSTRAINT FK_AccessMenu_Action REFERENCES dbo.ActionType (ActionID),
    TargetType   VARCHAR(5)  NOT NULL CONSTRAINT CK_AccessMenu_Type CHECK (TargetType IN ('ALL', 'ROLE', 'LEVEL', 'DEPT', 'USER')),
    LevelDetID   INT         NULL CONSTRAINT FK_AccessMenu_LevelDet REFERENCES dbo.LevelDetails (LevelDetID),
    LevelID      INT         NULL CONSTRAINT FK_AccessMenu_Level REFERENCES dbo.Level (LevelID),
    DeptID       VARCHAR(5)  NULL CONSTRAINT FK_AccessMenu_Dept REFERENCES dbo.Department (DeptID),
    UserID       BIGINT      NULL,                       -- FK ke Users ditambahkan setelah tabel Users dibuat
    IsDeny       BIT NOT NULL CONSTRAINT DF_AccessMenu_Deny DEFAULT (0),
    MenuDetails  NVARCHAR(MAX) NULL CONSTRAINT CK_AccessMenu_Details CHECK (MenuDetails IS NULL OR ISJSON(MenuDetails) = 1),
    Active       BIT NOT NULL CONSTRAINT DF_AccessMenu_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_AccessMenu_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_AccessMenu_Target CHECK (
           (TargetType = 'ALL'   AND LevelDetID IS NULL     AND LevelID IS NULL     AND DeptID IS NULL     AND UserID IS NULL)
        OR (TargetType = 'ROLE'  AND LevelDetID IS NOT NULL AND LevelID IS NULL     AND DeptID IS NULL     AND UserID IS NULL)
        OR (TargetType = 'LEVEL' AND LevelDetID IS NULL     AND LevelID IS NOT NULL AND DeptID IS NULL     AND UserID IS NULL)
        OR (TargetType = 'DEPT'  AND LevelDetID IS NULL     AND LevelID IS NULL     AND DeptID IS NOT NULL AND UserID IS NULL)
        OR (TargetType = 'USER'  AND LevelDetID IS NULL     AND LevelID IS NULL     AND DeptID IS NULL     AND UserID IS NOT NULL))
);
CREATE UNIQUE INDEX UX_AccessMenu_Rule ON dbo.AccessMenu (MenuID, ActionID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny);
CREATE INDEX IX_AccessMenu_User ON dbo.AccessMenu (UserID) WHERE UserID IS NOT NULL;
-- Widget dashboard (tampilannya dibuat di kode: templates/dashboard/widget/<WidgetCode>.html)
CREATE TABLE dbo.Widget (
    WidgetCode   VARCHAR(30)   NOT NULL PRIMARY KEY,
    WidgetName   NVARCHAR(100) NOT NULL,
    Description  NVARCHAR(255) NULL,
    SortOrder    INT NOT NULL CONSTRAINT DF_Widget_Sort DEFAULT (0),
    Active       BIT NOT NULL CONSTRAINT DF_Widget_Active DEFAULT (1)
);
-- Isi dashboard per aturan: menempel di baris aturan Izinkan-Lihat menu dashboard; urut SortOrder.
-- User memakai aturan paling spesifik yang cocok & punya widget: USER > ROLE > LEVEL > DEPT > ALL.
CREATE TABLE dbo.AccessMenuWidget (
    AccessMenuID INT         NOT NULL CONSTRAINT FK_AMWidget_Access REFERENCES dbo.AccessMenu (AccessMenuID) ON DELETE CASCADE,
    WidgetCode   VARCHAR(30) NOT NULL CONSTRAINT FK_AMWidget_Widget REFERENCES dbo.Widget (WidgetCode),
    SortOrder    INT NOT NULL CONSTRAINT DF_AMWidget_Sort DEFAULT (0),
    CONSTRAINT PK_AccessMenuWidget PRIMARY KEY (AccessMenuID, WidgetCode)
);
GO
/* Isi awal ada di bagian DATA AWAL (paling bawah). */

/* =========================== MASTER =========================== */

-- Users = SEMUA orang (karyawan, security, BHL, driver, tamu). UserID = YYMMDD + urutan 4 digit (mis. 2601010001), dibuat aplikasi.
-- Jenis orang dibaca dari relasi (view UserProfile.PersonType): jabatan terisi (UserLevelID) = Karyawan (termasuk Security
-- & BHL lewat departemen / jabatannya); GuestID terisi = visitor: punya SIM aktif = Driver, selain itu Tamu.
-- Punya login bila UserName terisi (wajib ada peran UserLevelID). BlacklistID terisi = sedang diblacklist.
-- FaceEmbeddingData / UploadPath = wajah terdaftar (satu per orang; dari kamera atau upload, perubahan tercatat di Log).
CREATE TABLE dbo.Users (
    UserID            BIGINT        NOT NULL PRIMARY KEY,
    CompAreaID        BIGINT        NULL CONSTRAINT FK_Users_Area REFERENCES dbo.CompanyArea (CompAreaID),
    UserName          VARCHAR(50)   NULL,                                   -- username login; NULL = tanpa akun
    UserDeptID        BIGINT        NULL CONSTRAINT FK_Users_DeptDet REFERENCES dbo.DepartmentDetails (DeptDetailID),   -- NULL = admin sistem
    UserLevelID       INT           NULL CONSTRAINT FK_Users_LevelDet REFERENCES dbo.LevelDetails (LevelDetID),
    NoKTP             VARCHAR(20)   NULL,                                   -- NIK 16 digit
    GuestID           BIGINT        NULL,                                   -- FK ke Guest (profil visitor)
    Nama              NVARCHAR(100) NOT NULL,
    Email             NVARCHAR(100) NULL,
    FaceEmbeddingData VARBINARY(MAX) NULL,
    UploadPath        NVARCHAR(255) NULL,
    CurrentHash       VARCHAR(64)   NULL,
    CreateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Create DEFAULT (GETDATE()),
    UpdateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Update DEFAULT (GETDATE()),
    Active            BIT NOT NULL CONSTRAINT DF_Users_Active DEFAULT (1),
    IsUpload          BIT NOT NULL CONSTRAINT DF_Users_Upload DEFAULT (0),     -- data sudah dilengkapi / diperbarui
    BlacklistID       BIGINT        NULL,                                   -- FK ke Blacklist (dibuat setelah tabel Blacklist)
    Description       NVARCHAR(255) NULL,
    LastLogin         DATETIME      NULL,
    SessionVersion    INT NOT NULL CONSTRAINT DF_Users_SessVer DEFAULT (0),     -- naik = semua sesi user dicabut
    CONSTRAINT CK_Users_Login CHECK (UserName IS NULL OR UserLevelID IS NOT NULL)
);
CREATE UNIQUE INDEX UX_Users_UserName ON dbo.Users (UserName) WHERE UserName IS NOT NULL;
CREATE UNIQUE INDEX UX_Users_NoKTP ON dbo.Users (NoKTP) WHERE NoKTP IS NOT NULL;
CREATE INDEX IX_Users_Active ON dbo.Users (Active) INCLUDE (Nama, GuestID, UserLevelID);
-- Password (hash) + riwayat (History JSON: hash terakhir, terbaru dulu) untuk menolak pemakaian ulang.
-- MustChange = 1 -> wajib buat password baru saat login.
CREATE TABLE dbo.PasswordManager (
    UserID      BIGINT        NOT NULL PRIMARY KEY CONSTRAINT FK_PwMgr_User REFERENCES dbo.Users (UserID),
    UserPasswd  VARCHAR(255)  NOT NULL,
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_PwMgr_Create DEFAULT (GETDATE()),
    MustChange  BIT NOT NULL CONSTRAINT DF_PwMgr_Must DEFAULT (1),
    History     NVARCHAR(MAX) NOT NULL CONSTRAINT DF_PwMgr_History DEFAULT (N'[]')
                CONSTRAINT CK_PwMgr_History CHECK (ISJSON(History) = 1),
    Term        INT           NULL,
    Description NVARCHAR(255) NULL
);
ALTER TABLE dbo.AccessMenu ADD CONSTRAINT FK_AccessMenu_User FOREIGN KEY (UserID) REFERENCES dbo.Users (UserID);
GO

/* SIM (License + LicenseDetail), profil visitor (Guest), wajah tertangkap kamera (FaceRecog) */
CREATE TABLE dbo.License (
    LicenseID    INT IDENTITY(1,1) PRIMARY KEY,
    LicenseCode  VARCHAR(20)   NOT NULL CONSTRAINT UX_License_Code UNIQUE,
    LicenseType  NVARCHAR(50)  NOT NULL,
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_License_Active DEFAULT (1)
);
CREATE TABLE dbo.LicenseDetail (
    DetailLicenseID INT IDENTITY(1,1) PRIMARY KEY,
    UserID          BIGINT NOT NULL CONSTRAINT FK_LicDet_User REFERENCES dbo.Users (UserID),
    SIMType         INT NOT NULL CONSTRAINT FK_LicDet_License REFERENCES dbo.License (LicenseID),
    LicenseNumber   VARCHAR(30) NOT NULL,
    ExpiredSIM      DATE NULL,                 -- NULL hanya untuk data lama yang belum dilengkapi
    Active          BIT NOT NULL CONSTRAINT DF_LicDet_Active DEFAULT (1),
    CreateBy        BIGINT NULL CONSTRAINT FK_LicDet_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_LicDet_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_LicDet_NumberActive ON dbo.LicenseDetail (LicenseNumber) WHERE Active = 1;
CREATE INDEX IX_LicDet_User ON dbo.LicenseDetail (UserID, Active);
-- Profil visitor (driver / tamu), ditunjuk Users.GuestID. Keperluan kunjungan tiap kedatangan di FaceActivity.Description.
CREATE TABLE dbo.Guest (
    GuestID       BIGINT IDENTITY(1,1) PRIMARY KEY,
    BlacklistID   BIGINT        NULL,                -- = Users.BlacklistID orangnya (FK setelah tabel Blacklist)
    CompanyFrom   NVARCHAR(255) NULL,                -- asal perusahaan / transportir
    VisitorNeeds  NVARCHAR(255) NULL,                -- keperluan yang biasa (isian awal form kunjungan)
    NoKTP         VARCHAR(20)   NULL,
    Active        BIT NOT NULL CONSTRAINT DF_Guest_Active DEFAULT (1),
    Description   NVARCHAR(255) NULL,
    CreateDate    DATETIME NOT NULL CONSTRAINT DF_Guest_Create DEFAULT (GETDATE())
);
ALTER TABLE dbo.Users ADD CONSTRAINT FK_Users_Guest FOREIGN KEY (GuestID) REFERENCES dbo.Guest (GuestID);
CREATE UNIQUE INDEX UX_Users_Guest ON dbo.Users (GuestID) WHERE GuestID IS NOT NULL;
-- Wajah yang tertangkap kamera setiap scan (bukti), termasuk yang tidak dikenali. Wajah terdaftar ada di Users.
-- FaceName = nama yang dikenali saat itu (NULL = tidak dikenal); Blacklist = BlacklistID orang itu saat scan.
CREATE TABLE dbo.FaceRecog (
    FaceID      BIGINT IDENTITY(1,1) PRIMARY KEY,
    FaceName    NVARCHAR(120) NULL,
    FaceDet     VARBINARY(MAX) NULL,                -- embedding saat scan
    Blacklist   BIGINT NULL,                        -- FK ke Blacklist (setelah tabel Blacklist)
    PhotoPath   VARCHAR(255) NULL,
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_FaceRecog_Create DEFAULT (GETDATE())
);
GO
/* Dokumen umum (migrasi 010) */
CREATE TABLE dbo.DocumentType (
    DocTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    DocTypeCode        VARCHAR(30)   NOT NULL CONSTRAINT UX_JenisDok_Kode UNIQUE,
    DocTypeName        NVARCHAR(100) NOT NULL,
    RequireFile  BIT NOT NULL CONSTRAINT DF_JenisDok_WajibFile DEFAULT (1),
    Active   BIT NOT NULL CONSTRAINT DF_JenisDok_Aktif DEFAULT (1)
);
CREATE TABLE dbo.Document (
    DocumentID  INT IDENTITY(1,1) PRIMARY KEY,
    DocTypeID    INT NOT NULL CONSTRAINT FK_Dokumen_Jenis REFERENCES dbo.DocumentType (DocTypeID),
    DocNumber  NVARCHAR(100) NOT NULL,
    DocDate     DATE NOT NULL,
    Subject     NVARCHAR(255) NULL,
    CreateBy  BIGINT NOT NULL CONSTRAINT FK_Dokumen_User REFERENCES dbo.Users (UserID),
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_Dokumen_Created DEFAULT (GETDATE())
);
CREATE INDEX IX_Dokumen_Jenis_No ON dbo.Document (DocTypeID, DocNumber);
CREATE TABLE dbo.DocumentFile (
    FileID      INT IDENTITY(1,1) PRIMARY KEY,
    DocumentID   INT NOT NULL CONSTRAINT FK_DokFile_Dokumen REFERENCES dbo.Document (DocumentID),
    FilePath    VARCHAR(255)  NOT NULL,          -- 'uploads/dokumen/...' (privat, dibuka lewat /berkas/)
    OriginalName    NVARCHAR(255) NULL,
    MimeType         VARCHAR(100)  NULL,
    FileSize  INT NULL,
    SHA256       CHAR(64) NULL,                   -- NULL hanya untuk file lama (sebelum migrasi 010)
    SortOrder       TINYINT NOT NULL CONSTRAINT DF_DokFile_Urutan DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_DokFile_Created DEFAULT (GETDATE())
);
CREATE INDEX IX_DokFile_Dokumen ON dbo.DocumentFile (DocumentID, SortOrder);
GO
-- Profil orang + jenis orang + SIM aktif terbaru + wajah terdaftar
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

-- Customer (membeli / menjual) & pengangkutan pihak ketiga
-- Mata uang, bank & rekening (disiapkan untuk keuangan; belum ada layar)
CREATE TABLE dbo.Currency (
    CurrencyID    INT IDENTITY(1,1) PRIMARY KEY,
    CurrencyCode  VARCHAR(10)   NOT NULL CONSTRAINT UX_Currency_Code UNIQUE,
    CurrencyName  NVARCHAR(100) NOT NULL,
    CurrencyRate  DECIMAL(20, 4) NULL,                 -- kurs ke IDR
    Description   NVARCHAR(255) NULL,
    Active        BIT NOT NULL CONSTRAINT DF_Currency_Active DEFAULT (1)
);
CREATE TABLE dbo.Bank (
    BankAccountID  INT IDENTITY(1,1) PRIMARY KEY,
    BankName       NVARCHAR(300) NOT NULL,
    BankRegion     NVARCHAR(170) NULL,
    CurrencyID     INT NULL CONSTRAINT FK_Bank_Currency REFERENCES dbo.Currency (CurrencyID),
    CompAreaID     BIGINT NULL CONSTRAINT FK_Bank_Area REFERENCES dbo.CompanyArea (CompAreaID),
    Active         BIT NOT NULL CONSTRAINT DF_Bank_Active DEFAULT (1)
);
CREATE TABLE dbo.BankDetails (
    BankAccountDetailsID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    BankAccountID         INT NOT NULL CONSTRAINT FK_BankDet_Bank REFERENCES dbo.Bank (BankAccountID),
    BankAccountCode       NVARCHAR(100) NOT NULL,          -- no. rekening
    BankName              NVARCHAR(300) NULL,              -- atas nama
    Balance               DECIMAL(20, 2) NULL,
    Active                BIT NOT NULL CONSTRAINT DF_BankDet_Active DEFAULT (1)
);
GO
-- Supplier lokal = referensi relasional transaksi/blacklist; master identitas berasal dari Ascend.
CREATE TABLE dbo.Supplier (
    SupplierID            INT IDENTITY(1,1) PRIMARY KEY,
    SupplierCode          VARCHAR(20)   NOT NULL CONSTRAINT UX_Supplier_Code UNIQUE,
    SupplierName          VARCHAR(100)  NOT NULL,
    SupplierAddress       NVARCHAR(255) NULL,
    BankAccountDetailsID  BIGINT NULL CONSTRAINT FK_Supplier_BankDet REFERENCES dbo.BankDetails (BankAccountDetailsID),
    BlacklistID           BIGINT NULL,
    Description           NVARCHAR(255) NULL,
    Active                BIT NOT NULL CONSTRAINT DF_Supplier_Active DEFAULT (1),
    CreateDate            DATETIME NOT NULL CONSTRAINT DF_Supplier_Create DEFAULT (GETDATE())
);
/* SupplierCompany dan SupplierTypeDetails dihapus: master mitra bersumber dari Ascend. */
GO

-- Alur tahap tiket (migrasi 012): urutan tahap per alur, dipakai produk & transaksi
CREATE TABLE dbo.FlowStage (
    StageCode    VARCHAR(20)  NOT NULL PRIMARY KEY,
    StageName    NVARCHAR(50) NOT NULL,
    SortOrder  TINYINT NOT NULL
);
GO
CREATE TABLE dbo.Flow (
    FlowID    INT IDENTITY(1,1) PRIMARY KEY,
    FlowCode       VARCHAR(20)   NOT NULL CONSTRAINT UX_Alur_Kode UNIQUE,
    FlowName       NVARCHAR(100) NOT NULL,
    Description    NVARCHAR(255) NULL,
    Active  BIT NOT NULL CONSTRAINT DF_Alur_Aktif DEFAULT (1)
);
GO
CREATE TABLE dbo.FlowStep (
    FlowID     INT NOT NULL CONSTRAINT FK_AlurTahap_Alur REFERENCES dbo.Flow (FlowID),
    StepNo      TINYINT NOT NULL,
    StageCode  VARCHAR(20) NOT NULL CONSTRAINT FK_AlurTahap_Tahap REFERENCES dbo.FlowStage (StageCode),
    GroupNo     TINYINT NOT NULL,          -- tahap dengan GroupNo sama = paralel (boleh dikerjakan dalam urutan bebas)
    CONSTRAINT PK_AlurTahap PRIMARY KEY (FlowID, StepNo),
    CONSTRAINT UX_AlurTahap_Tahap UNIQUE (FlowID, StageCode)
);
GO

CREATE TABLE dbo.ProductType (
    ProductTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    ProductTypeCode  VARCHAR(20)   NOT NULL CONSTRAINT UX_ProductType_Code UNIQUE,     -- TBS, PRODUK_PKS
    ProductTypeName  NVARCHAR(50)  NOT NULL,
    Description      VARCHAR(150)  NULL,
    Active           BIT NOT NULL CONSTRAINT DF_ProductType_Active DEFAULT (1)
);
-- Produk + standar mutu (batas FFA / kadar air / kotoran, dipakai Lab)
CREATE TABLE dbo.Product (
    ProductID      INT IDENTITY(1,1) PRIMARY KEY,
    ProductName    VARCHAR(100) NOT NULL,
    Category       VARCHAR(20)  NOT NULL CONSTRAINT FK_Product_Type REFERENCES dbo.ProductType (ProductTypeCode),
    FlowID         INT NOT NULL CONSTRAINT FK_Product_Flow REFERENCES dbo.Flow (FlowID),       -- alur tahap tiket
    StandardFFA    FLOAT NOT NULL CONSTRAINT DF_Product_FFA DEFAULT (5.0),
    StandardMoist  FLOAT NOT NULL CONSTRAINT DF_Product_Moist DEFAULT (0.5),
    StandardDirt   FLOAT NOT NULL CONSTRAINT DF_Product_Dirt DEFAULT (0.5),
    Active         BIT NOT NULL CONSTRAINT DF_Product_Active DEFAULT (1)
);
-- Harga per produk per tanggal (disiapkan untuk keuangan; belum ada layar). Void, bukan dihapus
CREATE TABLE dbo.ProductPrice (
    ProductPriceID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    ProductID       INT NULL, -- legacy
    ProductNameSnapshot NVARCHAR(150) NULL,
    AscendProductCode NVARCHAR(100) NULL,
    CompID          VARCHAR(5) NULL CONSTRAINT FK_ProductPrice_Company REFERENCES dbo.Company (CompID),  -- NULL = semua perusahaan
    PriceDate       DATE NOT NULL,
    Price           DECIMAL(14, 2) NOT NULL,
    CurrencyID      INT NULL CONSTRAINT FK_ProductPrice_Currency REFERENCES dbo.Currency (CurrencyID),
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_ProductPrice_Create DEFAULT (GETDATE()),
    CreateBy        BIGINT NULL CONSTRAINT FK_ProductPrice_CreateBy REFERENCES dbo.Users (UserID),
    IsVoid          BIT NOT NULL CONSTRAINT DF_ProductPrice_Void DEFAULT (0),
    VoidDate        DATETIME NULL,
    VoidBy          BIGINT NULL CONSTRAINT FK_ProductPrice_VoidBy REFERENCES dbo.Users (UserID)
);
CREATE INDEX IX_ProductPrice_Product_Date ON dbo.ProductPrice (ProductID, PriceDate DESC) WHERE IsVoid = 0;
GO

-- Kurs mata uang ke rupiah (Data Master › Kurs Mata Uang). Riwayat: berlaku sejak RateDate sampai kurs berikutnya; salah input di-void.
-- TRANSAKSI = kurs transaksi (JISDOR / pajak), PENUTUPAN = kurs akhir bulan. CompID NULL = semua perusahaan. Dibaca laporan Analytics.
CREATE TABLE dbo.ExchangeRate (
    ExchangeRateID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    CurrencyID      INT NOT NULL CONSTRAINT FK_ExchangeRate_Currency REFERENCES dbo.Currency (CurrencyID),
    RateType        VARCHAR(10) NOT NULL CONSTRAINT CK_ExchangeRate_Type CHECK (RateType IN ('TRANSAKSI', 'PENUTUPAN')),
    RateDate        DATE NOT NULL,
    Rate            DECIMAL(18, 4) NOT NULL CONSTRAINT CK_ExchangeRate_Rate CHECK (Rate > 0),
    CompID          VARCHAR(5) NULL CONSTRAINT FK_ExchangeRate_Company REFERENCES dbo.Company (CompID),
    Source          VARCHAR(10) NULL,
    Description     NVARCHAR(255) NULL,
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_ExchangeRate_Create DEFAULT (GETDATE()),
    CreateBy        BIGINT NULL CONSTRAINT FK_ExchangeRate_CreateBy REFERENCES dbo.Users (UserID),
    IsVoid          BIT NOT NULL CONSTRAINT DF_ExchangeRate_Void DEFAULT (0),
    VoidDate        DATETIME NULL,
    VoidBy          BIGINT NULL CONSTRAINT FK_ExchangeRate_VoidBy REFERENCES dbo.Users (UserID)
);
CREATE UNIQUE INDEX UX_ExchangeRate_Berlaku ON dbo.ExchangeRate (CurrencyID, RateType, RateDate, CompID) WHERE IsVoid = 0;
GO

-- Jenis kendaraan. Kapasitas: peringatan di timbangan; kosong = tidak dicek
CREATE TABLE dbo.VehicleType (
    VehicleTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    VehicleTypeCode  VARCHAR(20)  NOT NULL CONSTRAINT UX_VehicleType_Code UNIQUE,
    NameType         NVARCHAR(50) NOT NULL,
    Active           BIT NOT NULL CONSTRAINT DF_VehicleType_Active DEFAULT (1),
    WeightCar        DECIMAL(10, 2) NULL,          -- berat kosong (kg)
    MaxLoad          DECIMAL(10, 2) NULL,          -- muatan maksimal (kg)
    Seat             INT NULL
);
GO
-- Kendaraan: plat & STNK unik. BlacklistID terisi = sedang diblacklist
CREATE TABLE dbo.DetailVehicle (
    IDVehicle    INT IDENTITY(1,1) PRIMARY KEY,
    NoVehicle    VARCHAR(15) NOT NULL CONSTRAINT UX_DetailVehicle_No UNIQUE,
    NoSTNK       VARCHAR(50) NOT NULL,
    VehicleType  INT NULL CONSTRAINT FK_DetailVehicle_Type REFERENCES dbo.VehicleType (VehicleTypeID),
    BlacklistID  BIGINT NULL,
    Active       BIT NOT NULL CONSTRAINT DF_DetailVehicle_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_DetailVehicle_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_DetailVehicle_Stnk ON dbo.DetailVehicle (NoSTNK);
GO

-- Supir terdaftar per truk (supir utama disarankan saat Create Ticket)
CREATE TABLE dbo.VehicleDriver (
    VehicleDriverID INT IDENTITY(1,1) PRIMARY KEY,
    IDVehicle   INT NOT NULL CONSTRAINT FK_VD_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    UserID      BIGINT NOT NULL CONSTRAINT FK_VD_User REFERENCES dbo.Users (UserID),
    IsMain      BIT NOT NULL CONSTRAINT DF_VD_Main DEFAULT (0),
    Active      BIT NOT NULL CONSTRAINT DF_VD_Active DEFAULT (1),
    CreateBy    BIGINT NULL CONSTRAINT FK_VD_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_VD_Create DEFAULT (GETDATE()),
    UpdateDate  DATETIME NOT NULL CONSTRAINT DF_VD_Update DEFAULT (GETDATE()),
    CONSTRAINT UQ_VD_Vehicle_User UNIQUE (IDVehicle, UserID)
);
CREATE INDEX IX_VD_User ON dbo.VehicleDriver (UserID) INCLUDE (IDVehicle, Active, IsMain);
GO

-- Kontrak per truk (modal Update > Kontrak Truk di Form Security)
CREATE TABLE dbo.VehicleContract (
    VehicleContractID  INT IDENTITY(1,1) PRIMARY KEY,
    ContractNumber     VARCHAR(50) NULL,
    IDVehicle          INT NOT NULL CONSTRAINT FK_VC_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    SupplierID         INT NULL, -- legacy
    ProductID          INT NULL, -- legacy
    AscendSupplierID INT NULL,
    SupplierNameSnapshot NVARCHAR(150) NULL,
    ProductNameSnapshot NVARCHAR(150) NULL,
    TransactionType    VARCHAR(20) NULL,
    StartDate          DATE NOT NULL,
    EndDate            DATE NULL,
    Active             BIT NOT NULL CONSTRAINT DF_VC_Active DEFAULT (1),
    Description        VARCHAR(255) NULL,
    CreateBy           BIGINT NULL CONSTRAINT FK_VC_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate         DATETIME NOT NULL CONSTRAINT DF_VC_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_VC_Type CHECK (TransactionType IS NULL OR TransactionType IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_VC_Period CHECK (EndDate IS NULL OR EndDate >= StartDate)
);
CREATE INDEX IX_VC_Vehicle ON dbo.VehicleContract (IDVehicle, Active);
CREATE INDEX IX_VC_Vehicle_Supplier ON dbo.VehicleContract (IDVehicle, SupplierID, Active);
GO

-- Kontrak & DO (migrasi 013, diisi HO): 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
-- Jenis tiket (pembelian / penjualan / penimbangan saja); IsPayment disiapkan untuk keuangan
CREATE TABLE dbo.WeightBridgeType (
    WeightTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    WeightTypeCode  VARCHAR(20)  NOT NULL CONSTRAINT UX_WBType_Code UNIQUE,
    WeightTypeName  NVARCHAR(50) NOT NULL,
    IsPayment       BIT NOT NULL CONSTRAINT DF_WBType_Payment DEFAULT (0),
    Active          BIT NOT NULL CONSTRAINT DF_WBType_Active DEFAULT (1)
);
ALTER TABLE dbo.VehicleContract ADD CONSTRAINT FK_VC_WBType FOREIGN KEY (TransactionType) REFERENCES dbo.WeightBridgeType (WeightTypeCode);
-- Status tiket: nama & warna diatur di Admin › Organisasi
CREATE TABLE dbo.Status (
    StatusID     INT IDENTITY(1,1) PRIMARY KEY,
    StatusCode   VARCHAR(30)   NOT NULL CONSTRAINT UX_Status_Code UNIQUE,
    StatusName   NVARCHAR(50)  NOT NULL,
    StatusColor  VARCHAR(10)   NOT NULL CONSTRAINT DF_Status_Color DEFAULT ('abu'),
    SortOrder    TINYINT NOT NULL CONSTRAINT DF_Status_Sort DEFAULT (0),
    Description  NVARCHAR(255) NULL
);
-- Kontrak (diisi HO): 1 kontrak = 1 produk = 1 DO
CREATE TABLE dbo.Contract (
    ContractID       INT IDENTITY(1,1) PRIMARY KEY,
    ContractNumber   VARCHAR(50) NOT NULL CONSTRAINT UX_Contract_No UNIQUE,
    TransactionType  VARCHAR(20) NOT NULL CONSTRAINT FK_Contract_WBType REFERENCES dbo.WeightBridgeType (WeightTypeCode),
    SupplierID       INT NULL, -- legacy customer ID
    ProductID        INT NULL, -- legacy product ID
    AscendCustomerID INT NULL,
    CustomerNameSnapshot NVARCHAR(150) NULL,
    CustomerCodeSnapshot NVARCHAR(100) NULL,
    ProductNameSnapshot NVARCHAR(150) NULL,
    AscendProductCode NVARCHAR(100) NULL,
    ProductCodeSnapshot NVARCHAR(100) NULL,
    ContractDate     DATE NOT NULL CONSTRAINT DF_Contract_Date DEFAULT (CAST(GETDATE() AS DATE)),
    ContractQty      DECIMAL(14, 2) NULL,
    Price            DECIMAL(14, 2) NULL,
    PPN              BIT NOT NULL CONSTRAINT DF_Contract_Ppn DEFAULT (0),
    IncludePPN       BIT NOT NULL CONSTRAINT DF_Contract_InclPpn DEFAULT (0),
    CurrencyID       INT NULL CONSTRAINT FK_Contract_Currency REFERENCES dbo.Currency (CurrencyID),
    CompID           VARCHAR(5) NULL CONSTRAINT FK_Contract_Company REFERENCES dbo.Company (CompID),
    Description      VARCHAR(200) NULL,
    Active           BIT NOT NULL CONSTRAINT DF_Contract_Active DEFAULT (1),
    CreateBy         BIGINT NULL CONSTRAINT FK_Contract_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate       DATETIME NOT NULL CONSTRAINT DF_Contract_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_Contract_Type CHECK (TransactionType IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Contract_Qty CHECK (ContractQty IS NULL OR ContractQty > 0)
);
GO
CREATE TABLE dbo.DeliveryOrder (
    DeliveryOrderID  INT IDENTITY(1,1) PRIMARY KEY,
    DONumber         VARCHAR(50) NOT NULL CONSTRAINT UX_DO_Number UNIQUE,
    ContractID       INT NOT NULL CONSTRAINT FK_DO_Contract REFERENCES dbo.Contract (ContractID),
    DODate           DATE NOT NULL CONSTRAINT DF_DO_Date DEFAULT (CAST(GETDATE() AS DATE)),
    ExpiredDate      DATE NULL,
    Description      VARCHAR(200) NULL,
    Active           BIT NOT NULL CONSTRAINT DF_DO_Active DEFAULT (1),
    CreateBy         BIGINT NULL CONSTRAINT FK_DO_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate       DATETIME NOT NULL CONSTRAINT DF_DO_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_DO_Contract ON dbo.DeliveryOrder (ContractID);     -- 1 kontrak = 1 DO
GO
-- Pengangkutan per DO (boleh beberapa): PENGIRIM / PENERIMA / PIHAK_KETIGA (TransportID)
CREATE TABLE dbo.DOTransport (
    DOTransportID    INT IDENTITY(1,1) PRIMARY KEY,
    DeliveryOrderID  INT NOT NULL CONSTRAINT FK_DOTrans_DO REFERENCES dbo.DeliveryOrder (DeliveryOrderID),
    TransportMode    VARCHAR(15) NOT NULL,
    TransportID      INT NULL, -- legacy SupplierID
    AscendTransportID INT NULL,
    TransportNameSnapshot NVARCHAR(150) NULL,
    TransportCodeSnapshot NVARCHAR(100) NULL,
    DOQty            DECIMAL(14, 2) NULL,               -- alokasi (opsional), total <= Contract.ContractQty
    PriceTransport   DECIMAL(14, 2) NULL,               -- ongkos angkut per kg
    CONSTRAINT CK_DOTrans_Mode CHECK (TransportMode IN ('PENGIRIM', 'PENERIMA', 'PIHAK_KETIGA')),
    CONSTRAINT CK_DOTrans_ThirdParty CHECK ((TransportMode = 'PIHAK_KETIGA' AND (TransportID IS NOT NULL OR AscendTransportID IS NOT NULL))
                                            OR (TransportMode <> 'PIHAK_KETIGA' AND TransportID IS NULL AND AscendTransportID IS NULL))
);
CREATE UNIQUE INDEX UX_DOTransport_Legacy ON dbo.DOTransport (DeliveryOrderID, TransportMode, TransportID) WHERE AscendTransportID IS NULL;
CREATE UNIQUE INDEX UX_DOTransport_Ascend ON dbo.DOTransport (DeliveryOrderID, TransportMode, AscendTransportID) WHERE AscendTransportID IS NOT NULL;
