"""New Item Request sebagai modul CPOS: cari item yang paling mirip (semua perusahaan / per perusahaan), tebak kategori,
dan tampilkan pembelian terakhir. Mesin pencarian sama dengan aplikasi Item Similarity Search (modules/item_request/mesin.py).
Menu FM_NEW_ITEM (Forms › New Item Request); hak di Admin › Hak Akses."""
from flask import Blueprint

item_request_bp = Blueprint("item_request", __name__, url_prefix="/item-request")   # template & static: frontend\cpos\...\item_request

from modules.item_request import routes  # noqa: E402,F401  (mendaftarkan route ke item_request_bp)
