"""Modul tambahan CPOS (aplikasi yang digabung ke CPOS, mis. RekapIn). Susunan tiap modul sama:

    modules/<nama>/__init__.py      Blueprint modul (didaftarkan di app.py)
    modules/<nama>/routes.py        halaman & API (controller)
    modules/<nama>/db.py, ...       akses data modul itu (model); pakai utils/db_utils.query & ubah untuk database CPOS
    modules/<nama>/database/*.sql   skrip database modul (opsional, dijalankan setelah database/schema.sql)
    modules/<nama>/requirements.txt library tambahan (opsional, dipasang otomatis oleh jalankan.bat)
    frontend/cpos/templates/<nama>, frontend/cpos/static/<nama>   tampilan (view)

Yang sudah ada di CPOS dipakai bersama, tidak dibuat ulang di modul: login & hak akses (utils/hak_akses), daftar perusahaan
(utils/area.company_site), harga (utils/harga), persetujuan (utils/persetujuan), koneksi database lain (utils/koneksi_lain)."""
