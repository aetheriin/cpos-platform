@echo off
REM Memasang CPOS Platform di PC ini: menyala sendiri saat Windows menyala. Klik kanan > Run as administrator.
REM Rincian langkah di deploy\pasang.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pasang.ps1"
pause
