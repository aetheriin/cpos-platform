-- Referensi tabel pengguna login dashboard (SQL Server).
--
-- Tabel Anda SUDAH ADA, jadi bagian CREATE TABLE di bawah dilewati sendiri (IF OBJECT_ID ... IS NULL). Bagian yang penting adalah
-- GRANT di akhir: akun database yang dipakai server (DB_USER, atau DB_APP_USER kalau diisi) harus boleh membaca, menambah, mengubah,
-- dan menghapus baris di tabel ini, supaya System Administrator bisa membuat, mengedit, dan menghapus akun dari aplikasi.
--
-- Kolom yang dipakai aplikasi (nama harus persis): id, username, password_hash, full_name, role, division, company, created_at.
-- Aplikasi tidak mengisi id, jadi id harus terisi otomatis (IDENTITY, atau nilai bawaan seperti NEWID()).
-- Kolom users.role boleh berisi nama role atau RoleId dari tabel role (RoleId, DivisionId, RoleName, RoleDescription, Status, CreatedAt).
-- Siapa boleh melihat laporan apa TIDAK diatur di sini atau di kode, tetapi di tabel izin (lihat permission.sql) lewat menu Permission Control.

IF OBJECT_ID('dbo.users', 'U') IS NULL
CREATE TABLE dbo.users (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    username      NVARCHAR(50)  NOT NULL,
    password_hash NVARCHAR(300) NOT NULL,
    full_name     NVARCHAR(150) NOT NULL,
    role          NVARCHAR(50)  NOT NULL,
    division      NVARCHAR(100) NULL,
    company       NVARCHAR(100) NULL,
    created_at    DATETIME2     NOT NULL CONSTRAINT DF_users_created DEFAULT SYSDATETIME()
);

-- Username harus unik (collation bawaan SQL Server tidak peka huruf besar-kecil, sama dengan pencarian di aplikasi).
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_users_username' AND object_id = OBJECT_ID('dbo.users'))
    CREATE UNIQUE INDEX UX_users_username ON dbo.users (username);

-- Izin untuk akun database aplikasi (ganti nama_akun; hapus tanda -- di depannya):
-- GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.users TO [nama_akun];
-- Tabel role hanya dibaca (untuk pilihan role di formulir dan untuk mengubah RoleId menjadi nama):
-- GRANT SELECT ON dbo.role TO [nama_akun];
-- Tabel company juga hanya dibaca (pilihan Company; nama unik dari kolom CompName, hanya yang punya baris Status aktif):
-- GRANT SELECT ON dbo.company TO [nama_akun];
