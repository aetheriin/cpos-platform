"""Item Category Dashboard sebagai modul CPOS: analisis kategori item dari database Main (dbo.top_item_category_analysis).
Menu AN_ITEM_CATEGORY (Analytical Dashboard); koneksi sama dengan New Item Request (modules/item_request/mesin.py)."""
from flask import Blueprint

item_dashboard_bp = Blueprint("item_dashboard", __name__, url_prefix="/item-dashboard")   # template & static: frontend\cpos\...\item_dashboard

from modules.item_dashboard import routes  # noqa: E402,F401  (mendaftarkan route ke item_dashboard_bp)
