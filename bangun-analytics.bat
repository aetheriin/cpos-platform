@echo off
REM Membangun ulang tampilan Analytics (Analytics\frontend -> Analytics\frontend\dist).
REM Hanya perlu setelah ada perubahan di Analytics\frontend\src. Butuh Node.js.
REM Dibangun di folder lokal PC ini supaya node_modules tidak ada di folder bersama.
setlocal
set SUMBER=%~dp0Analytics\frontend
set KERJA=%LOCALAPPDATA%\cpos-platform\bangun-frontend
robocopy "%SUMBER%" "%KERJA%" /E /XD node_modules dist /NFL /NDL /NJH /NJS /NP >nul
cd /d "%KERJA%"
call npm install --no-audit --no-fund || goto gagal
call npm run build || goto gagal
robocopy "%KERJA%\dist" "%SUMBER%\dist" /MIR /NFL /NDL /NJH /NJS /NP >nul
echo.
echo Selesai. Muat ulang halaman laporan di browser (Ctrl+F5).
pause
exit /b 0
:gagal
echo.
echo Gagal membangun. Lihat pesan di atas.
pause
exit /b 1
