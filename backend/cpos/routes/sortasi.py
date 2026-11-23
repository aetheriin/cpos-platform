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

    nilai = {
        nama: request.form.get(nama) or 0
        for nama in (
            "mentah", "busuk", "tangkai",
            "sampah", "matang", "brondolan",
        )
    }

    try:
        db_ascend_split.simpan_sortasi_tiket_ascend(
            tiket["ticket_id"],
            no_tiket,
            nilai["mentah"],
            nilai["busuk"],
            nilai["tangkai"],
            nilai["sampah"],
            nilai["matang"],
            nilai["brondolan"],
            request.form.get("catatan", ""),
            current_user.id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal menyimpan sortasi tiket Ascend %s",
            no_tiket,
        )
        return jsonify({
            "error": "Sortasi gagal disimpan. Periksa statusnya sebelum mencoba lagi."
        }), 503

    total_persen = round(
        float(nilai["mentah"])
        + float(nilai["tangkai"])
        + float(nilai["sampah"]),
        2,
    )

    return jsonify({
        "message": (
            f"Sortasi tersimpan. Potongan {total_persen}% "
            "akan dihitung dari Netto saat timbang terakhir."
        ),
        "total_persen_potongan": total_persen,
        "total_potongan_kg": None,
    }), 200

@sortasi_bp.route("/api/history/sortasi")
@login_required
@lihat(*MENU_OPERASI)
def history_sortasi():
    return jsonify(get_history_umum('sortasi', id_area=area_data(current_user.id)))