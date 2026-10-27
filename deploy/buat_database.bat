@echo off
rem Membuat database CPOS lengkap (CPOS + RekapIn + Analytics) dari nol di SQL Server.
rem Pemakaian (dari folder repo):  deploy\buat_database.bat NAMA_SERVER [user] [password]
rem   tanpa user = login Windows.  Contoh:  deploy\buat_database.bat localhost sa RahasiaSa123
rem Database CPOS dibuat bila belum ada (tidak perlu CREATE DATABASE dulu). Bila CPOS sudah berisi tabel, skrip gagal:
rem hapus dulu database CPOS yang lama di SSMS (hanya bila memang ingin mulai baru).
rem Server berjalan: jalankan hanya skrip baru di CPOS\database\perubahan, modules\*\database, Analytics\database.
setlocal
if "%~1"=="" (echo Pemakaian: deploy\buat_database.bat NAMA_SERVER [user] [password]& echo Jalankan dari Command Prompt, bukan klik dua kali.& pause & exit /b 1)
set "S=%~1"
if "%~2"=="" (set "AUTH=-E") else (set "AUTH=-U %~2 -P %~3")
set "Q=sqlcmd -S %S% %AUTH% -C -I -b"
cd /d "%~dp0.."

echo == 1. CPOS\database\schema.sql (database CPOS baru)
%Q% -i CPOS\database\schema.sql || goto gagal
echo == 2. Modul CPOS (RekapIn)
for %%f in (CPOS\modules\rekapin\database\*.sql) do (echo    %%f & %Q% -d CPOS -i "%%f" || goto gagal)
echo == 3. Analytics
for %%f in (Analytics\database\*.sql) do (echo    %%f & %Q% -d CPOS -i "%%f" || goto gagal)
echo.
echo Selesai. Cek: SELECT * FROM CPOS.dbo.SchemaLog
pause
exit /b 0
:gagal
echo GAGAL di langkah di atas. Perbaiki lalu jalankan lagi.
pause
exit /b 1
