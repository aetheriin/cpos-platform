"""Halaman & API New Item Request. Hak: menu FM_NEW_ITEM (Lihat) di Admin › Hak Akses."""
from datetime import date, datetime

from flask import render_template, request, jsonify
from flask_login import login_required

from modules.item_request import item_request_bp, mesin
from utils.hak_akses import izin, halaman as lihat_halaman, remah_menu

KODE = "FM_NEW_ITEM"


@item_request_bp.route("")
@login_required
@lihat_halaman(KODE)
def halaman_item():
    mesin.mulai_muat()
    return render_template("item_request/index.html", halaman="item_request", kode_aktif=KODE, remah=remah_menu(KODE),
                           top_n=mesin.TOP_N, top_beli=mesin.LAST_PURCHASE_TOP)


@item_request_bp.route("/api/status")
@login_required
@izin(KODE, "lihat")
def api_status():
    return jsonify(mesin.status())


@item_request_bp.route("/api/muat-ulang", methods=["POST"])
@login_required
@izin(KODE, "lihat")
def api_muat_ulang():
    """Coba muat lagi setelah gagal (mis. koneksi atau library belum ada)."""
    if mesin.status()["keadaan"] == "GAGAL":
        mesin.mulai_muat(ulang=True)
    return jsonify(mesin.status())


def _tanggal(v):
    if isinstance(v, (datetime, date)):
        return v.strftime("%d-%m-%Y")
    return str(v) if v else None


@item_request_bp.route("/api/cari", methods=["POST"])
@login_required
@izin(KODE, "lihat")
def api_cari():
    query = (request.form.get("item") or "").strip()
    company = (request.form.get("company") or "SEMUA").strip() or "SEMUA"
    if not query:
        return jsonify({"error": "Isi nama item yang dicari"}), 400
    if mesin.status()["keadaan"] != "SIAP":
        return jsonify({"error": "Data item belum siap: " + (mesin.status()["pesan"] or "sedang dimuat")}), 503
    results, category = mesin.cari(query, company)
    hasil = []
    for r in results:
        beli = r.get("LastPurchase")
        hasil.append({"similarity": float(r["Similarity"]), "comp": r["COMP"], "item_code": r["ItemCode"],
                      "item_name": r["ItemName"], "category": r["Category"],
                      "beli": {"no": beli["PurchaseNo"], "tanggal": _tanggal(beli["PurchaseDate"]),
                               "qty": None if beli["Qty"] is None else float(beli["Qty"]),
                               "harga": None if beli["Price"] is None else float(beli["Price"])} if beli else None})
    return jsonify({"query": query, "company": company, "category": category, "hasil": hasil})
