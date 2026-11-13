/* Hapus master klasifikasi/relasi perusahaan Supplier yang tidak lagi dipakai.
   Supplier tetap dipertahankan sementara sebagai referensi internal transaksi & blacklist.
   Target database mengikuti database bisnis CPOS saat ini, yaitu Main. Jalankan setelah backup database Main. */
SET NOCOUNT ON;
USE [Main];
GO

/* SupplierGroup hanya dipakai oleh kolom Supplier.SupplierGroupID */
IF COL_LENGTH('dbo.Supplier', 'SupplierGroupID') IS NOT NULL
BEGIN
    IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Supplier_Group')
        ALTER TABLE dbo.Supplier DROP CONSTRAINT FK_Supplier_Group;

    ALTER TABLE dbo.Supplier DROP COLUMN SupplierGroupID;
END;
GO

/* Drop tabel relasi terlebih dahulu sebelum tabel referensi jenis */
IF OBJECT_ID('dbo.SupplierTypeDetails', 'U') IS NOT NULL
    DROP TABLE dbo.SupplierTypeDetails;
GO
IF OBJECT_ID('dbo.SupplierCompany', 'U') IS NOT NULL
    DROP TABLE dbo.SupplierCompany;
GO
IF OBJECT_ID('dbo.SupplierGroup', 'U') IS NOT NULL
    DROP TABLE dbo.SupplierGroup;
GO
IF OBJECT_ID('dbo.SupplierType', 'U') IS NOT NULL
    DROP TABLE dbo.SupplierType;
GO

IF OBJECT_ID('dbo.SchemaLog', 'U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/025_hapus_master_supplier_tidak_dipakai.sql')
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/025_hapus_master_supplier_tidak_dipakai.sql', 'CPOS');
GO
