"""RekapIn sebagai modul CPOS: Dashboard, Request Operator, Harga CPO & Kernel, Kategori Request, laporan Pembelian TBS.

Login, hak akses (menu RK_*, Admin › Hak Akses), sidebar, dan tampilan memakai milik CPOS. Data sendiri ada di schema
database `rekap` (modules/rekapin/database/001_rekap.sql); harga memakai dbo.DailyPrice yang sama dengan Dashboard CPOS."""
from flask import Blueprint

rekapin_bp = Blueprint("rekapin", __name__, url_prefix="/rekapin")   # template & static: frontend\cpos\templates|static\rekapin

from modules.rekapin import routes  # noqa: E402,F401  (mendaftarkan route ke rekapin_bp)
