/* New Item Request (modules/item_request): alamat menu Forms › New Item Request + hak Lihat untuk semua user
   (bisa dibatasi di Admin › Hak Akses). Untuk database CPOS yang sudah berjalan. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [CPOS];
GO
-- Sebelumnya menu ini menunjuk halaman kosong /halaman/FM_NEW_ITEM
UPDATE dbo.Menu SET Url = '/item-request' WHERE MenuCode = 'FM_NEW_ITEM' AND (Url IS NULL OR Url = '/halaman/FM_NEW_ITEM');
GO
IF NOT EXISTS (SELECT 1 FROM dbo.AccessMenu a JOIN dbo.Menu m ON m.MenuID = a.MenuID WHERE m.MenuCode = 'FM_NEW_ITEM')
    INSERT INTO dbo.AccessMenu (MenuID, ActionID, TargetType)
    SELECT m.MenuID, 1, 'ALL' FROM dbo.Menu m WHERE m.MenuCode = 'FM_NEW_ITEM';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/002_item_request.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/002_item_request.sql', 'CPOS');
GO
