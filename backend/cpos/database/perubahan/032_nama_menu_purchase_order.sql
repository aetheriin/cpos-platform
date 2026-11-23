/* Nama menu Reports "Purchase Orders" (RP_PO) menjadi "Purchase Order", tunggal seperti Purchase Request dan Purchase Invoice.
   Judul halaman Analytics-nya ikut berubah di kode. Aman dijalankan ulang. */
SET NOCOUNT ON;
UPDATE dbo.Menu SET MenuName = N'Purchase Order' WHERE MenuCode = 'RP_PO' AND MenuName <> N'Purchase Order';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/032_nama_menu_purchase_order.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/032_nama_menu_purchase_order.sql', 'CPOS');
GO
SELECT MenuCode, MenuName, Url FROM dbo.Menu WHERE MenuCode IN ('RP_PR', 'RP_PO', 'RP_PI');
