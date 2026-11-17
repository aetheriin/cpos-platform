from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils.hak_akses import izin, boleh, halaman as lihat_halaman
from utils import db_ascend, db_ascend_split, notifikasi
from utils.area import area_data

kelebihan_do_bp = Blueprint("kelebihan_do", __name__)


@kelebihan_do_bp.route("/kelebihan-do")
@login_required
@lihat_halaman("KELEBIHAN_DO")
def halaman():
    return render_template(
        "kelebihan_do/kelebihan_do.html",
        halaman="kelebihan_do",
        boleh_monitor_split=boleh("KONTRAK_DO", "lihat"),
    )


@kelebihan_do_bp.route("/api/kelebihan-do/ascend-split")
@login_required
@izin("KONTRAK_DO", "lihat")
def daftar_ascend_split():
    rows = db_ascend_split.daftar_monitor_split()

    for row in rows:
        row["tiket_split"] = []
        row["no_do1"] = None

        if row["status"] == "SELESAI_SPLIT":
            hasil = db_ascend.baca_hasil_split_ascend(row["ticket_id"])
            if hasil:
                row["no_do1"] = hasil["no_do1"]
                row["tiket_split"] = hasil["anak"]

    return jsonify(rows)


@kelebihan_do_bp.route("/api/notifikasi")
@login_required
def notifikasi_daftar():
    rows, belum = notifikasi.daftar(
        current_user,
        id_area=area_data(current_user.id),
    )
    return jsonify({"notifikasi": rows, "belum_dibaca": belum})


@kelebihan_do_bp.route("/api/notifikasi/baca", methods=["POST"])
@login_required
def notifikasi_baca():
    teks = (request.form.get("id_notifikasi") or "").strip()
    notifikasi.tandai_baca(
        current_user,
        int(teks) if teks.isdigit() else None,
        id_area=area_data(current_user.id),
    )
    return jsonify({"message": "Notifikasi ditandai sudah dibaca"}) 