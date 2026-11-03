@echo off
REM Menghentikan CPOS + Analytics di PC ini (kalau jendela jalankan.bat tidak terlihat / sudah ditutup tapi masih berjalan).
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.ExecutablePath -like '*\cpos-platform\venv-*' };" ^
  "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "if ($p) { 'CPOS dan Analytics sudah dihentikan.' } else { 'Tidak ada yang sedang berjalan.' }"
pause
