"""Satu .env untuk semua aplikasi: backend\\.env (dimuat sekali di sini, sebelum modul inti lain).

Analytics memakai DB_SERVER / DB_NAME yang sama dengan CPOS, dengan akun database sendiri bila ANALYTICS_DB_* diisi.
Alamat CPOS untuk memeriksa login (CPOS_URL) dibuat dari PORT CPOS bila tidak diisi.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV)
for _k in ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD"):
    if os.getenv("ANALYTICS_" + _k):
        os.environ[_k] = os.environ["ANALYTICS_" + _k]
os.environ.setdefault("CPOS_URL", f"http://127.0.0.1:{os.getenv('PORT') or 5000}")
