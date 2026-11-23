import logging

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.hak_akses import lihat, MENU_OPERASI, izin
from utils.area import area_data
from utils.db_utils import get_history_umum
from utils import db_ascend, db_ascend_split

sortasi_bp = Blueprint('sortasi', __name__)

@sortasi_bp.route("/api/sortasi/simpan", methods=["POST"])
@login_required
@izin('FORM_SORTASI', 'tambah')
def sortasi_simpan():
    no_tiket = (request.form.get("no_tiket") or "").strip()
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih."}), 400

    tiket = db_ascend.cari_tiket_ascend_berdasarkan_no_tiket(no_tiket)
    if not tiket:
        return jsonify({
            "error": "Tiket Ascend tidak ditemukan atau sudah selesai."
        }), 404

    if (
        tiket.get("ticket_type") != "TBSLuar"
        or (tiket.get("produk") or "").strip().casefold() != "tbs"
    ):
        return jsonify({
            "error": "Sortasi hanya tersedia untuk tiket TBS Luar produk TBS."
        }), 400

    berat = db_ascend.baca_berat_tiket_ascend(no_tiket)
    if not berat or berat.get("berat_bruto") is None:
        return jsonify({
            "error": "Timbang pertama harus tersimpan sebelum sortasi."
        }), 409

    if not db_ascend_split.tiket_di_area(
        tiket["ticket_id"],
        area_data(current_user.id),
    ):
        return jsonify({"error": "Tiket tidak ditemukan pada area Anda."}), 404

    try:
        hasil = db_ascend.simpan_hasil_sortasi_tiket_ascend(
            no_tiket,
            deduction_kg=request.form.get("deduction_kg") or None,
            mentah=request.form.get("mentah") or None,
            busuk=request.form.get("busuk") or None,
            tangkai=request.form.get("tangkai") or None,
            sampah=request.form.get("sampah") or None,
            matang=request.form.get("matang") or None,
            brondolan=request.form.get("brondolan") or None,
            operator=current_user.username,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal menyimpan Sortasi Ascend untuk tiket %s",
            no_tiket,
        )
        return jsonify({
            "error": "Sortasi gagal disimpan ke Ascend. Periksa status tiket sebelum mencoba lagi."
        }), 503

    return jsonify({
        "message": "Hasil Sortasi berhasil disimpan ke tiket Ascend.",
        "no_tiket": hasil["ticket_no"],
        "deduction_kg": hasil["deduction_kg"],
        "netto": hasil["netto"],
    }), 200

@sortasi_bp.route("/api/history/sortasi")
@login_required
@lihat(*MENU_OPERASI)
def history_sortasi():
    return jsonify(get_history_umum('sortasi', id_area=area_data(current_user.id)))