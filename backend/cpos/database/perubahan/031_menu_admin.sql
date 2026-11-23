/* Menu Admin di tabel Menu, supaya halaman Admin bisa diberikan ke pengguna non-admin lewat Admin › Hak Akses.
   Grup G_ADMIN (Lv1) + satu menu Lv2 per halaman Admin (/admin/<halaman>). Hak Lihat = boleh membuka halamannya,
   hak Ubah = boleh menyimpan perubahan di halaman itu. Log Keamanan, Audit Admin, dan Kesehatan Sistem hanya bisa dilihat.
   Akun admin tetap membuka semua halaman Admin seperti biasa. Hak menu Admin hanya bisa diatur oleh admin.
   Tidak ada hak awal: menu ini baru terlihat setelah admin memberikannya. Aman dijalankan ulang. */
SET NOCOUNT ON;
USE [Main];
GO
INSERT INTO dbo.Menu (MenuCode, MenuName, Description, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT 'G_ADMIN', N'Admin', N'Halaman pengelolaan sistem. Hanya admin yang bisa memberikan hak menu di grup ini.',
       NULL, 1, NULL, 'fa-user-gear', 'CPOS', ISNULL((SELECT MAX(SortOrder) FROM dbo.Menu WHERE MenuLevel = 1), 0) + 10
WHERE NOT EXISTS (SELECT 1 FROM dbo.Menu WHERE MenuCode = 'G_ADMIN');
GO
INSERT INTO dbo.Menu (MenuCode, MenuName, Description, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT x.MenuCode, x.MenuName, x.Description, g.MenuID, 2, x.Url, x.Icon, 'CPOS', x.SortOrder
FROM dbo.Menu g
CROSS JOIN (VALUES
    ('ADM_USERS',       N'Kelola Pengguna',   N'Tambah akun, ubah jabatan, departemen, dan area, atur ulang password, aktif / nonaktif', '/admin/users',       'fa-users',            10),
    ('ADM_HAK_AKSES',   N'Hak Akses',         N'Siapa mendapat menu apa. Menu di grup Admin hanya bisa diatur oleh admin',              '/admin/hak_akses',   'fa-user-shield',      20),
    ('ADM_ORGANISASI',  N'Organisasi',        N'Perusahaan, area, Mill, departemen, jabatan, dan status tiket',                        '/admin/organisasi',  'fa-sitemap',          30),
    ('ADM_SESI',        N'Sesi Aktif',        N'Pengguna yang sedang login, paksa keluar, buka kunci login',                           '/admin/sesi',        'fa-user-clock',       40),
    ('ADM_PERSETUJUAN', N'Alur Persetujuan',  N'Tahap persetujuan berjenjang per jenis pengajuan dan kategori',                        '/admin/persetujuan', 'fa-route',            50),
    ('ADM_ALUR_TIKET',  N'Alur Tiket',        N'Urutan tahap tiket per Area dan Produk',                                               '/admin/alur_tiket',  'fa-diagram-project',  60),
    ('ADM_VOID',        N'Pembatalan Tiket',  N'Batalkan tiket yang salah input, tercatat alasannya',                                  '/admin/void',        'fa-ban',              70),
    ('ADM_JADWAL',      N'Jadwal Kerja',      N'Jam masuk, jam pulang, dan toleransi absensi per hari',                                '/admin/jadwal',      'fa-calendar-days',    80),
    ('ADM_MENU',        N'Kelola Menu',       N'Susunan menu. Menu di grup Admin hanya bisa diubah oleh admin',                        '/admin/menu',        'fa-bars-staggered',   90),
    ('ADM_PENGATURAN',  N'Pengaturan Site',   N'Scan wajah, sesi login, kunci login, dan kolom wajib',                                 '/admin/pengaturan',  'fa-sliders',         100),
    ('ADM_PERANGKAT',   N'Perangkat',         N'Pos (token PC agen timbangan) dan jembatan timbang',                                   '/admin/perangkat',   'fa-plug',            110),
    ('ADM_KESEHATAN',   N'Kesehatan Sistem',  N'Database, cadangan data, disk, versi aplikasi',                                         '/admin/kesehatan',   'fa-heart-pulse',     120),
    ('ADM_LOG',         N'Log Keamanan',      N'Login, login gagal, akses ditolak, kios ditolak',                                      '/admin/log',         'fa-shield-halved',   130),
    ('ADM_AUDIT',       N'Audit Admin',       N'Jejak semua perubahan di halaman Admin',                                               '/admin/audit',       'fa-clipboard-list',  140)
) x (MenuCode, MenuName, Description, Url, Icon, SortOrder)
WHERE g.MenuCode = 'G_ADMIN'
  AND NOT EXISTS (SELECT 1 FROM dbo.Menu m WHERE m.MenuCode = x.MenuCode);
GO
-- Aksi Ubah untuk halaman yang punya tombol simpan; Log, Audit, dan Kesehatan hanya Lihat
INSERT INTO dbo.MenuAction (MenuID, ActionID)
SELECT m.MenuID, 3
FROM dbo.Menu m
WHERE m.MenuCode IN ('ADM_USERS', 'ADM_HAK_AKSES', 'ADM_ORGANISASI', 'ADM_SESI', 'ADM_PERSETUJUAN', 'ADM_ALUR_TIKET',
                     'ADM_VOID', 'ADM_JADWAL', 'ADM_MENU', 'ADM_PENGATURAN', 'ADM_PERANGKAT')
  AND NOT EXISTS (SELECT 1 FROM dbo.MenuAction a WHERE a.MenuID = m.MenuID AND a.ActionID = 3);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/031_menu_admin.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/031_menu_admin.sql', 'CPOS');
GO
SELECT m.MenuCode, m.MenuName, m.Url, m.SortOrder,
       (SELECT COUNT(*) FROM dbo.MenuAction a WHERE a.MenuID = m.MenuID) AS AksiUbah
FROM dbo.Menu m
LEFT JOIN dbo.Menu p ON p.MenuID = m.ParentMenuID
WHERE m.MenuCode = 'G_ADMIN' OR p.MenuCode = 'G_ADMIN'
ORDER BY m.MenuLevel, m.SortOrder;
