@echo off
REM Membuat paket deploy CPOS Platform (zip) di deploy\paket. Butuh Git dan Node.js di PC ini.
REM   buat_paket.bat            -> dengan file .env yang sekarang
REM   buat_paket.bat -TanpaEnv  -> tanpa .env (diisi sendiri di PC tujuan dari .env.example)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0buat_paket.ps1" %*
pause
