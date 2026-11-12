@echo off
REM Menghentikan CPOS, Analytics, dan Deteksi Plat di PC ini (kalau jendela jalankan.bat sudah ditutup tapi masih berjalan).
REM Yang dihentikan hanya Python milik aplikasi ini (venv di %LOCALAPPDATA%\cpos-platform dan %LOCALAPPDATA%\deteksi-plat).
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.ExecutablePath -like '*\cpos-platform\venv-*' -or $_.ExecutablePath -like '*\deteksi-plat\venv\*' };" ^
  "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "if ($p) { 'CPOS, Analytics, dan Deteksi sudah dihentikan.' } else { 'Tidak ada yang sedang berjalan.' }"
pause
