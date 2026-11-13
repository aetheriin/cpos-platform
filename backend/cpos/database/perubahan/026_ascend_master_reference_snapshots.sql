/* Tahap 1 migrasi master Supplier/Product ke Ascend.
   Hanya menambahkan referensi eksternal + snapshot historis. Tidak menghapus tabel/kolom lokal.
   ID Ascend sengaja NULL: tidak boleh dipetakan dari nama/kode lokal tanpa verifikasi.
   Target database bisnis aplikasi: Main. Aman dijalankan ulang.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
USE [Main];
GO

IF OBJECT_ID('dbo.SchemaLog', 'U') IS NULL
    THROW 51026, 'SchemaLog tidak ditemukan di Main; hentikan migrasi.', 1;
IF OBJECT_ID('dbo.Supplier', 'U') IS NULL OR OBJECT_ID('dbo.Product', 'U') IS NULL
    THROW 51026, 'Master lokal Supplier/Product tidak ditemukan di Main; periksa target database.', 1;
IF OBJECT_ID('dbo.Contract', 'U') IS NULL OR OBJECT_ID('dbo.DOTransport', 'U') IS NULL
   OR OBJECT_ID('dbo.VehicleContract', 'U') IS NULL OR OBJECT_ID('dbo.Invoice', 'U') IS NULL
   OR OBJECT_ID('dbo.WeightBridge', 'U') IS NULL OR OBJECT_ID('dbo.Blacklist', 'U') IS NULL
   OR OBJECT_ID('dbo.ProductPrice', 'U') IS NULL OR OBJECT_ID('dbo.FlowRule', 'U') IS NULL
    THROW 51026, 'Tabel transaksi yang diharapkan tidak lengkap; hentikan migrasi.', 1;
GO

BEGIN TRANSACTION;

-- Customer/Supplier/Product code snapshots + Ascend product code.
IF COL_LENGTH('dbo.Contract', 'CustomerCodeSnapshot') IS NULL ALTER TABLE dbo.Contract ADD CustomerCodeSnapshot NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contract', 'AscendProductCode') IS NULL ALTER TABLE dbo.Contract ADD AscendProductCode NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contract', 'ProductCodeSnapshot') IS NULL ALTER TABLE dbo.Contract ADD ProductCodeSnapshot NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.DOTransport', 'TransportCodeSnapshot') IS NULL ALTER TABLE dbo.DOTransport ADD TransportCodeSnapshot NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.ProductPrice', 'AscendProductCode') IS NULL ALTER TABLE dbo.ProductPrice ADD AscendProductCode NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.FlowRule', 'AscendProductCode') IS NULL ALTER TABLE dbo.FlowRule ADD AscendProductCode NVARCHAR(100) NULL;

-- Kontrak/DO
IF COL_LENGTH('dbo.Contract', 'AscendCustomerID') IS NULL
    ALTER TABLE dbo.Contract ADD AscendCustomerID INT NULL;
IF COL_LENGTH('dbo.Contract', 'CustomerNameSnapshot') IS NULL
    ALTER TABLE dbo.Contract ADD CustomerNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.Contract', 'ProductNameSnapshot') IS NULL
    ALTER TABLE dbo.Contract ADD ProductNameSnapshot NVARCHAR(150) NULL;

IF COL_LENGTH('dbo.DOTransport', 'AscendTransportID') IS NULL
    ALTER TABLE dbo.DOTransport ADD AscendTransportID INT NULL;
IF COL_LENGTH('dbo.DOTransport', 'TransportNameSnapshot') IS NULL
    ALTER TABLE dbo.DOTransport ADD TransportNameSnapshot NVARCHAR(150) NULL;

-- Kontrak kendaraan
IF COL_LENGTH('dbo.VehicleContract', 'AscendSupplierID') IS NULL
    ALTER TABLE dbo.VehicleContract ADD AscendSupplierID INT NULL;
IF COL_LENGTH('dbo.VehicleContract', 'SupplierNameSnapshot') IS NULL
    ALTER TABLE dbo.VehicleContract ADD SupplierNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.VehicleContract', 'ProductNameSnapshot') IS NULL
    ALTER TABLE dbo.VehicleContract ADD ProductNameSnapshot NVARCHAR(150) NULL;

-- Invoice
IF COL_LENGTH('dbo.Invoice', 'AscendSupplierID') IS NULL
    ALTER TABLE dbo.Invoice ADD AscendSupplierID INT NULL;
IF COL_LENGTH('dbo.Invoice', 'SupplierNameSnapshot') IS NULL
    ALTER TABLE dbo.Invoice ADD SupplierNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.Invoice', 'AscendTransportID') IS NULL
    ALTER TABLE dbo.Invoice ADD AscendTransportID INT NULL;
IF COL_LENGTH('dbo.Invoice', 'TransportNameSnapshot') IS NULL
    ALTER TABLE dbo.Invoice ADD TransportNameSnapshot NVARCHAR(150) NULL;

-- Tiket timbangan: snapshot memastikan histori tetap dapat dibaca setelah master lokal dilepas.
IF COL_LENGTH('dbo.WeightBridge', 'AscendCustomerID') IS NULL
    ALTER TABLE dbo.WeightBridge ADD AscendCustomerID INT NULL;
IF COL_LENGTH('dbo.WeightBridge', 'CustomerNameSnapshot') IS NULL
    ALTER TABLE dbo.WeightBridge ADD CustomerNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.WeightBridge', 'AscendTransportID') IS NULL
    ALTER TABLE dbo.WeightBridge ADD AscendTransportID INT NULL;
IF COL_LENGTH('dbo.WeightBridge', 'TransportNameSnapshot') IS NULL
    ALTER TABLE dbo.WeightBridge ADD TransportNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.WeightBridge', 'ProductNameSnapshot') IS NULL
    ALTER TABLE dbo.WeightBridge ADD ProductNameSnapshot NVARCHAR(150) NULL;

-- Blacklist dan informasi mitra yang menyertai pengajuan.
IF COL_LENGTH('dbo.Blacklist', 'AscendSupplierID') IS NULL
    ALTER TABLE dbo.Blacklist ADD AscendSupplierID INT NULL;
IF COL_LENGTH('dbo.Blacklist', 'SupplierNameSnapshot') IS NULL
    ALTER TABLE dbo.Blacklist ADD SupplierNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.Blacklist', 'AscendCustomerID') IS NULL
    ALTER TABLE dbo.Blacklist ADD AscendCustomerID INT NULL;
IF COL_LENGTH('dbo.Blacklist', 'CustomerNameSnapshot') IS NULL
    ALTER TABLE dbo.Blacklist ADD CustomerNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.Blacklist', 'AscendTransportID') IS NULL
    ALTER TABLE dbo.Blacklist ADD AscendTransportID INT NULL;
IF COL_LENGTH('dbo.Blacklist', 'TransportNameSnapshot') IS NULL
    ALTER TABLE dbo.Blacklist ADD TransportNameSnapshot NVARCHAR(150) NULL;

-- Tabel turunan Product yang masih menyimpan transaksi/aturan.
IF COL_LENGTH('dbo.ProductPrice', 'ProductNameSnapshot') IS NULL
    ALTER TABLE dbo.ProductPrice ADD ProductNameSnapshot NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.FlowRule', 'ProductNameSnapshot') IS NULL
    ALTER TABLE dbo.FlowRule ADD ProductNameSnapshot NVARCHAR(150) NULL;

-- Blacklist: izinkan entitas Ascend tanpa SupplierID lokal (constraint target lama).
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_Blacklist_Target' AND parent_object_id=OBJECT_ID('dbo.Blacklist'))
    ALTER TABLE dbo.Blacklist DROP CONSTRAINT CK_Blacklist_Target;
ALTER TABLE dbo.Blacklist ADD CONSTRAINT CK_Blacklist_Target CHECK (
 (TableName='Users' AND UserID IS NOT NULL AND IDVehicle IS NULL AND SupplierID IS NULL) OR
 (TableName='DetailVehicle' AND IDVehicle IS NOT NULL AND UserID IS NULL AND SupplierID IS NULL) OR
 (TableName='Supplier' AND (SupplierID IS NOT NULL OR AscendSupplierID IS NOT NULL OR AscendCustomerID IS NOT NULL OR AscendTransportID IS NOT NULL) AND UserID IS NULL AND IDVehicle IS NULL)
);

-- Constraint DOTransport mendukung third-party via Ascend ID.
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_DOTrans_ThirdParty' AND parent_object_id=OBJECT_ID('dbo.DOTransport'))
 ALTER TABLE dbo.DOTransport DROP CONSTRAINT CK_DOTrans_ThirdParty;
ALTER TABLE dbo.DOTransport ADD CONSTRAINT CK_DOTrans_ThirdParty CHECK (
 (TransportMode='PIHAK_KETIGA' AND (TransportID IS NOT NULL OR AscendTransportID IS NOT NULL)) OR
 (TransportMode<>'PIHAK_KETIGA' AND TransportID IS NULL AND AscendTransportID IS NULL)
);
-- Snapshot hanya menyalin nama lama. Tidak menebak/memasangkan ID ke Ascend.
UPDATE c
SET CustomerNameSnapshot = COALESCE(c.CustomerNameSnapshot, s.SupplierName),
    ProductNameSnapshot = COALESCE(c.ProductNameSnapshot, p.ProductName)
FROM dbo.Contract c
LEFT JOIN dbo.Supplier s ON s.SupplierID = c.SupplierID
LEFT JOIN dbo.Product p ON p.ProductID = c.ProductID;

UPDATE dt
SET TransportNameSnapshot = COALESCE(dt.TransportNameSnapshot, s.SupplierName)
FROM dbo.DOTransport dt
LEFT JOIN dbo.Supplier s ON s.SupplierID = dt.TransportID;

UPDATE vc
SET SupplierNameSnapshot = COALESCE(vc.SupplierNameSnapshot, s.SupplierName),
    ProductNameSnapshot = COALESCE(vc.ProductNameSnapshot, p.ProductName)
FROM dbo.VehicleContract vc
LEFT JOIN dbo.Supplier s ON s.SupplierID = vc.SupplierID
LEFT JOIN dbo.Product p ON p.ProductID = vc.ProductID;

UPDATE i
SET SupplierNameSnapshot = COALESCE(i.SupplierNameSnapshot, s.SupplierName),
    TransportNameSnapshot = COALESCE(i.TransportNameSnapshot, t.SupplierName)
FROM dbo.Invoice i
LEFT JOIN dbo.Supplier s ON s.SupplierID = i.SupplierID
LEFT JOIN dbo.Supplier t ON t.SupplierID = i.TransportID;

UPDATE w
SET CustomerNameSnapshot = COALESCE(w.CustomerNameSnapshot, s.SupplierName),
    TransportNameSnapshot = COALESCE(w.TransportNameSnapshot, t.SupplierName),
    ProductNameSnapshot = COALESCE(w.ProductNameSnapshot, p.ProductName)
FROM dbo.WeightBridge w
LEFT JOIN dbo.Supplier s ON s.SupplierID = w.SupplierID
LEFT JOIN dbo.Supplier t ON t.SupplierID = w.TransportID
LEFT JOIN dbo.Product p ON p.ProductID = w.ProductID;

UPDATE b
SET SupplierNameSnapshot = COALESCE(b.SupplierNameSnapshot, s.SupplierName),
    CustomerNameSnapshot = COALESCE(b.CustomerNameSnapshot, c.SupplierName),
    TransportNameSnapshot = COALESCE(b.TransportNameSnapshot, t.SupplierName)
FROM dbo.Blacklist b
LEFT JOIN dbo.Supplier s ON s.SupplierID = b.SupplierID
LEFT JOIN dbo.Supplier c ON c.SupplierID = b.CustomerID
LEFT JOIN dbo.Supplier t ON t.SupplierID = b.TransportID;

UPDATE pp
SET ProductNameSnapshot = COALESCE(pp.ProductNameSnapshot, p.ProductName)
FROM dbo.ProductPrice pp
LEFT JOIN dbo.Product p ON p.ProductID = pp.ProductID;

UPDATE fr
SET ProductNameSnapshot = COALESCE(fr.ProductNameSnapshot, p.ProductName)
FROM dbo.FlowRule fr
LEFT JOIN dbo.Product p ON p.ProductID = fr.ProductID;

IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/026_ascend_master_reference_snapshots.sql')
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/026_ascend_master_reference_snapshots.sql', 'CPOS');

COMMIT TRANSACTION;
GO
