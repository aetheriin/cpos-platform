import os

from dotenv import load_dotenv
from flask_login import LoginManager

# Letak folder (repo):  backend\.env  backend\cpos\ (kode ini)  backend\deteksi\  frontend\cpos\ (templates, static)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AKAR = os.path.dirname(os.path.dirname(BASE_DIR))
ENV = os.path.join(AKAR, "backend", ".env")       # satu .env untuk CPOS, Analytics, Deteksi
load_dotenv(ENV)
FRONTEND = os.path.abspath(os.getenv("FRONTEND_DIR") or os.path.join(AKAR, "frontend"))
TEMPLATE_DIR = os.path.join(FRONTEND, "cpos", "templates")
STATIC_DIR = os.path.join(FRONTEND, "cpos", "static")
# Foto plat yang disimpan Deteksi: FOLDER_FOTO_PLAT, atau FOLDER_FOTO (tempat Deteksi menyimpan), atau foto_bukti Deteksi di PC ini
FOLDER_FOTO_PLAT = ((os.getenv("FOLDER_FOTO_PLAT") or os.getenv("FOLDER_FOTO") or "").strip()
                    or os.path.join(AKAR, "backend", "deteksi", "foto_bukti"))

# File upload (foto wajah, surat blacklist, snapshot absensi) disimpan PRIVAT di luar folder static,
# hanya bisa dibuka lewat route /berkas/... yang wajib login. Path di database tetap "uploads/...".
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "data", "uploads")))
UPLOAD_LAMA = os.path.join(STATIC_DIR, "uploads")     # lokasi lama (publik), dipindah saat start
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"

