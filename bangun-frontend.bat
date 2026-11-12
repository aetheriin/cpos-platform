@echo off
REM Membangun ulang tampilan. Butuh Node.js. Dibangun di folder lokal PC ini supaya node_modules tidak ada di folder bersama.
REM   frontend\analytics  -> frontend\analytics\dist              (setelah ada perubahan di frontend\analytics\src)
REM   frontend\cpos       -> frontend\cpos\static\css\tailwind.css (setelah ada kelas Tailwind baru di templates / static)
setlocal
set AKAR=%~dp0frontend
set KERJA=%LOCALAPPDATA%\cpos-platform\bangun-frontend

echo == Analytics
robocopy "%AKAR%\analytics" "%KERJA%\analytics" /E /XD node_modules dist /NFL /NDL /NJH /NJS /NP >nul
cd /d "%KERJA%\analytics"
call npm install --no-audit --no-fund || goto gagal
call npm run build || goto gagal
robocopy "%KERJA%\analytics\dist" "%AKAR%\analytics\dist" /MIR /NFL /NDL /NJH /NJS /NP >nul

echo == CPOS (Tailwind)
robocopy "%AKAR%\cpos" "%KERJA%\cpos" /E /XD node_modules uploads /NFL /NDL /NJH /NJS /NP >nul
cd /d "%KERJA%\cpos"
call npm install --no-audit --no-fund || goto gagal
call npm run build-css || goto gagal
copy /y "%KERJA%\cpos\static\css\tailwind.css" "%AKAR%\cpos\static\css\tailwind.css" >nul

echo.
echo Selesai. Muat ulang halaman di browser (Ctrl+F5).
pause
exit /b 0
:gagal
echo.
echo Gagal membangun. Lihat pesan di atas.
pause
exit /b 1
