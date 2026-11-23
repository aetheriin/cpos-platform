/* Menu Netto Sumber pindah dari Forms ke Master, tepat setelah Harga CPO & Kernel (sama-sama isian data acuan).
   Kode menu tetap FM_NETTO_SUMBER, jadi hak akses yang sudah diatur di Admin › Hak Akses tidak berubah. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
UPDATE m
SET ParentMenuID = p.MenuID,
    SortOrder = ISNULL((SELECT h.SortOrder FROM dbo.Menu h WHERE h.MenuCode = 'RK_HARGA'), 50) + 1
FROM dbo.Menu m
JOIN dbo.Menu p ON p.MenuCode = 'G_MASTER'
WHERE m.MenuCode = 'FM_NETTO_SUMBER';
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/030_netto_sumber_ke_master.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/030_netto_sumber_ke_master.sql', 'CPOS');
GO
SELECT m.MenuCode, m.MenuName, p.MenuName AS Grup, m.SortOrder
FROM dbo.Menu m
JOIN dbo.Menu p ON p.MenuID = m.ParentMenuID
WHERE p.MenuCode = 'G_MASTER'
ORDER BY m.SortOrder, m.MenuName;
