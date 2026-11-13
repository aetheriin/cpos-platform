/* AUDIT READ-ONLY: dependensi tabel Supplier/Product lokal sebelum migrasi ke Ascend.
   Jalankan pada database Main (tidak mengubah data/schema).
   Hasil: FK, kolom, objek SQL, dan row-count referensi.
*/
SET NOCOUNT ON;

DECLARE @Target TABLE (TableName sysname PRIMARY KEY);
INSERT INTO @Target VALUES (N'Supplier'), (N'Product'), (N'SupplierTypeDetails'),
                           (N'SupplierType'), (N'SupplierGroup'), (N'SupplierCompany');

-- 1) Foreign key yang menuju/berasal dari tabel target
SELECT
    fk.name AS FKName,
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS SchemaReferencing,
    OBJECT_NAME(fk.parent_object_id) AS TableReferencing,
    pc.name AS ColumnReferencing,
    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS SchemaReferenced,
    OBJECT_NAME(fk.referenced_object_id) AS TableReferenced,
    rc.name AS ColumnReferenced,
    fk.delete_referential_action_desc AS OnDelete,
    fk.update_referential_action_desc AS OnUpdate
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
WHERE OBJECT_NAME(fk.parent_object_id) IN (SELECT TableName FROM @Target)
   OR OBJECT_NAME(fk.referenced_object_id) IN (SELECT TableName FROM @Target)
ORDER BY TableReferencing, FKName;

-- 2) Kolom SupplierID/ProductID/TypeCode di seluruh tabel (termasuk yang belum FK)
SELECT OBJECT_SCHEMA_NAME(c.object_id) AS [Schema], OBJECT_NAME(c.object_id) AS [Table],
       c.name AS [Column], TYPE_NAME(c.user_type_id) AS [DataType],
       c.is_nullable AS IsNullable
FROM sys.columns c
JOIN sys.tables t ON t.object_id = c.object_id
WHERE c.name IN (N'SupplierID',N'ProductID',N'TransportID',N'CustomerID',
                 N'SupplierTypeID',N'TypeCode',N'SupplierGroupID')
ORDER BY [Table], [Column];

-- 3) View/procedure/function/trigger dengan definisi menyebut nama master lokal
SELECT o.type_desc, OBJECT_SCHEMA_NAME(o.object_id) AS [Schema],
       o.name AS ObjectName
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.type IN ('V','P','FN','IF','TF','TR')
  AND (m.definition LIKE '%Supplier%' OR m.definition LIKE '%Product%')
ORDER BY o.type_desc, [Schema], ObjectName;

-- 4) Jumlah data master dan tabel terkait; angka ini tidak menentukan aman/tidaknya DROP.
SELECT N'Supplier' AS TableName, COUNT_BIG(*) AS RowCount FROM dbo.Supplier
UNION ALL SELECT N'Product', COUNT_BIG(*) FROM dbo.Product
UNION ALL SELECT N'SupplierTypeDetails', COUNT_BIG(*) FROM dbo.SupplierTypeDetails
UNION ALL SELECT N'SupplierType', COUNT_BIG(*) FROM dbo.SupplierType
UNION ALL SELECT N'SupplierGroup', COUNT_BIG(*) FROM dbo.SupplierGroup
UNION ALL SELECT N'SupplierCompany', COUNT_BIG(*) FROM dbo.SupplierCompany;
