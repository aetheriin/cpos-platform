/* Menu Reports "Purchase Request" (RP_PR) dan "Purchase Orders" (RP_PO) diarahkan ke laporan Analytics yang baru
   (/an/purchase_request dan /an/purchase_order), menggantikan halaman kosong /halaman/RP_PR dan /halaman/RP_PO.
   Hak Lihat yang sudah ada di kedua menu tetap dipakai. Aman dijalankan ulang. */
SET NOCOUNT ON;
UPDATE dbo.Menu SET Url = '/an/purchase_request' WHERE MenuCode = 'RP_PR' AND ISNULL(Url, '') <> '/an/purchase_request';
UPDATE dbo.Menu SET Url = '/an/purchase_order'   WHERE MenuCode = 'RP_PO' AND ISNULL(Url, '') <> '/an/purchase_order';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/023_menu_purchase_request_order.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/023_menu_purchase_request_order.sql', 'CPOS');
GO
SELECT MenuCode, MenuName, Url FROM dbo.Menu WHERE MenuCode IN ('RP_PR', 'RP_PO', 'RP_PI');
