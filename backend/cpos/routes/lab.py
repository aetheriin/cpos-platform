from flask import Blueprint, request, jsonify, current_app
from utils.hak_akses import lihat, MENU_OPERASI
from utils.area import area_data
from flask_login import login_required, current_user
from utils.db_utils import (get_standar_mutu, update_standar_mutu, get_history_umum, get_history_standar)
from utils.hak_akses import izin
from utils import db_ascend, db_ascend_split

lab_bp = Blueprint('lab', __name__)

@lab_bp.route("/api/lab/standar/<int:id_produk>")
@login_required
def lab_standar(id_produk):
    row = get_standar_mutu(id_produk)
    if row is None:
        return jsonify({"error": "Produk tidak ditemukan"}), 404
    return jsonify({"maks_ffa": row.maks_ffa, "maks_air": row.maks_air, "maks_kotoran": row.maks_kotoran})

@lab_bp.route("/api/lab/standar/update", methods=["POST"])
@login_required
@izin('FORM_LAB', 'ubah')
def lab_standar_update():
    f = request.form
    try:
        nilai = [float(f.get(k, "")) for k in ("maks_ffa", "maks_air", "maks_kotoran")]
        id_produk = int(f.get("id_produk", ""))
    except ValueError:
        return jsonify({"error": "Produk dan semua batas standar wajib diisi angka"}), 400
    if any(v < 0 or v > 100 for v in nilai):
        return jsonify({"error": "Batas standar harus 0 - 100 %"}), 400
    try:
        update_standar_mutu(id_produk, *nilai, user_id=current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"message": "Standar mutu berhasil diperbarui"}), 200


@lab_bp.route("/api/lab/standar/history")
@login_required
@lihat(*MENU_OPERASI)
def lab_standar_history():
    return jsonify([{**r, "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M")} for r in get_history_standar(2)])

@lab_bp.route("/api/lab/simpan", methods=["POST"])
@login_required
@izin('FORM_LAB', 'tambah')
def lab_simpan():
    f = request.form
    no_tiket = (f.get("no_tiket") or "").strip()

    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih."}), 400

    tiket = db_ascend.cari_tiket_ascend_berdasarkan_no_tiket(no_tiket)
    if not tiket:
        return jsonify({"error": "Tiket Ascend tidak ditemukan atau sudah selesai."}), 404

    produk = str(tiket.get("produk") or "").strip().upper()
    if tiket.get("ticket_type") != "Produk" or produk not in {"CPO", "PK", "KERNEL"}:
        return jsonify({
            "error": "Lab Ascend saat ini hanya menerima produk CPO, PK, dan Kernel."
        }), 400

    id_tiket_induk = tiket.get("parent_ticket_id") or tiket.get("ticket_id")
    if not id_tiket_induk or not db_ascend_split.tiket_di_area(
        id_tiket_induk,
        area_data(current_user.id),
    ):
        return jsonify({"error": "Tiket tidak ditemukan pada area Anda."}), 404

    try:
        hasil = db_ascend.simpan_hasil_lab_tiket_ascend(
            no_tiket,
            ffa=f.get("ffa") or None,
            suhu=f.get("suhu") or None,
            pct_air=f.get("kadar_air") or None,
            pct_kotoran=f.get("kadar_kotoran") or None,
            kcolor=f.get("warna_locis") or None,
            operator=current_user.username,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception(
            "Gagal menyimpan hasil Lab Ascend untuk tiket %s",
            no_tiket,
        )
        return jsonify({
            "error": "Hasil Lab gagal disimpan ke Ascend. Periksa status tiket sebelum mencoba lagi."
        }), 503

    waktu_lab = hasil.get("lab_datetime")
    return jsonify({
        "message": f"Hasil Lab {hasil['product']} berhasil disimpan ke Ascend.",
        "no_tiket": hasil["ticket_no"],
        "lab_by": hasil["lab_by"],
        "lab_datetime": waktu_lab.isoformat() if waktu_lab else None,
    }), 200

@lab_bp.route("/api/history/lab")
@login_required
@lihat(*MENU_OPERASI)
def history_lab():
    return jsonify(get_history_umum('lab_hasil', id_area=area_data(current_user.id)))