@echo off
REM Menghentikan dan melepas tugas terjadwal "CPOS Platform" serta aturan firewall-nya. Klik kanan > Run as administrator.
REM File aplikasi, .env, dan library Python di C:\ProgramData\CPOS-Platform tidak dihapus (hapus manual bila perlu).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0copot.ps1"
pause
