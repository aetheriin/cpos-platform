"""Form Netto Sumber sebagai modul CPOS: isian netto sumber tiket penjualan Tiket yang kosong atau salah.
Tiket dibaca dari dbo.TIKET_PENJUALAN (sama dengan laporan Tiket Penjualan di Analytics), isian disimpan di dbo.NettoSumberIsian
(database/perubahan/029_netto_sumber.sql). Tiket tidak diubah. Menu FM_NETTO_SUMBER, di Master › Netto Sumber sejak 030."""
from flask import Blueprint

netto_sumber_bp = Blueprint("netto_sumber", __name__, url_prefix="/netto-sumber")   # template & static: frontend\cpos\...\netto_sumber

from modules.netto_sumber import routes  # noqa: E402,F401  (mendaftarkan route ke netto_sumber_bp)
