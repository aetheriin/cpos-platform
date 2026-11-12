@echo off
title CPOS System - Backend Deteksi Plat

REM 1. Buat Virtual Drive sementara untuk menangani folder jaringan UNC
pushd "%~dp0"

REM 2. Aktifkan Virtual Environment yang sudah ada
call venv\Scripts\activate.bat

REM 3. Jalankan server web Python
python server_web.py %*

REM 4. Bersihkan virtual drive setelah ditutup
popd
pause