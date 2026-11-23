import logging
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify
from utils.hak_akses import lihat, MENU_OPERASI
from utils.area import area_data
from flask_login import login_required, current_user
from utils.serial_reader import baca_status, reset_deteksi_stabil, wajib_kembali_nol
from utils.hak_akses import izin
from utils.db_jembatan import jembatan_dipilih
from utils import db_tiket, db_tiket_pisah

timbangan_bp = Blueprint('timbangan', __name__)

@timbangan_bp.route("/api/timbang/status")
@login_required
def timbang_status():
    """Berat live jembatan yang dipilih PC ini (dibaca terus, walau belum ada tiket)."""
    j = jembatan_dipilih(request)
    if j is None:
        return jsonify({"berat": 0, "stabil": False, "terhubung": False, "siap_kunci": False, "jembatan": None,
                        "error": "Pilih jembatan timbang untuk PC ini"})
    return jsonify({**baca_status(j["id_jembatan"]), "jembatan": j["kode"]})

@timbangan_bp.route("/api/timbang/reset-baseline", methods=["POST"])
@login_required
@izin('FORM_TIMBANGAN', 'tambah')
def timbang_reset():
    j = jembatan_dipilih(request)
    if j:
        reset_deteksi_stabil(j["id_jembatan"])
    return jsonify({"message": "Titik nol timbangan berhasil diatur ulang"}), 200

@timbangan_bp.route("/api/timbang/data/<path:no_tiket>")
@login_required
@lihat(*MENU_OPERASI)
def timbang_data(no_tiket):
    try:
        data = db_tiket.baca_berat_tiket(no_tiket)
    except Exception:
        logging.exception(
            "Gagal membaca berat tiket Tiket %s",
            no_tiket,
        )
        return jsonify({
            "error": "Berat tiket Tiket belum dapat dibaca."
        }), 503

    if not data:
        return jsonify({
            "berat_bruto": None,
            "berat_tara": None,
            "berat_netto": None,
        })

    try:
        rencana = db_tiket_pisah.baca_status_timbang_pending(no_tiket)
    except Exception:
        logging.exception(
            "Gagal membaca status pending tiket Tiket %s",
            no_tiket,
        )
        return jsonify({
            "error": "Status timbang tiket Tiket belum dapat dibaca."
        }), 503

    # Berat akhir pending tetap ditampilkan untuk keperluan penimbangan.
    if rencana and rencana["status"] == "MENUNGGU_DO2":
        berat_akhir = rencana["berat_akhir_pending"]
        if berat_akhir is not None:
            data["berat_bruto"] = berat_akhir
            if data["berat_tara"] is not None:
                data["berat_netto"] = (
                    berat_akhir - data["berat_tara"]
                )

    return jsonify(data)

@timbangan_bp.route("/api/timbang/scan-qr", methods=["POST"])
@login_required
@lihat(*MENU_OPERASI)
def timbang_scan_qr():
    try:
        tiket = db_tiket.cari_tiket_berdasarkan_no_tiket(
            request.form.get("no_tiket", "").strip()
        )
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal mencari tiket Tiket lewat scan QR"
        )
        return jsonify({
            "error": "Tiket Tiket belum dapat diperiksa. Coba lagi."
        }), 503

    if tiket:
        return jsonify({
            "status": "ADA_TIKET",
            "sumber": "TIKET",
            "no_tiket": tiket["no_tiket"],
            "no_plat": tiket["no_plat"],
            "no_do": tiket["no_do"],
            "supplier": tiket["associate"],
            "associate_id": tiket["associate_id"],
            "produk": tiket["produk"],
            "ticket_type": tiket["ticket_type"],
            "jenis_transaksi": tiket["jenis_transaksi"],
            "id_supplier": None,
            "driver": None,
        }), 200
    return jsonify({
        "error": "Tiket Tiket tidak ditemukan atau sudah selesai."
    }), 404 

HARI_HISTORY_MAKS = 30


@timbangan_bp.route("/api/history-timbangan-tiket")
@login_required
@lihat(*MENU_OPERASI)
def history_tiket():
    teks_associate = (request.args.get("associate_id") or "").strip()
    ticket_type = (request.args.get("ticket_type") or "").strip()

    if not teks_associate.isdigit():
        return jsonify({"error": "Associate Tiket tidak valid."}), 400
    if ticket_type not in ("Produk", "TBSLuar"):
        return jsonify({"error": "Jenis tiket Tiket tidak valid."}), 400

    tanggal = None
    if request.args.get("tanggal"):
        try:
            tanggal = datetime.strptime(
                request.args["tanggal"], "%Y-%m-%d"
            ).date()
        except ValueError:
            return jsonify({"error": "Format tanggal salah."}), 400

        if not 0 <= (date.today() - tanggal).days < HARI_HISTORY_MAKS:
            return jsonify({
                "error": (
                    f"Tanggal hanya bisa dipilih "
                    f"{HARI_HISTORY_MAKS} hari terakhir."
                )
            }), 400

    if tanggal:
        mulai = tanggal
        sampai = tanggal + timedelta(days=1)
    else:
        sampai = date.today() + timedelta(days=1)
        mulai = sampai - timedelta(days=7)

    try:
        ticket_ids = db_tiket_pisah.daftar_ticket_id_di_area(
            area_data(current_user.id)
        )
        rows = db_tiket.riwayat_timbang_associate(
            ticket_ids,
            int(teks_associate),
            ticket_type,
            mulai,
            sampai,
        )
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal membaca riwayat timbang Tiket."
        )
        return jsonify({
            "error": "Riwayat timbang Tiket belum dapat dibaca."
        }), 503

    return jsonify([
        {
            **row,
            "created_at": (
                row["created_at"].strftime("%Y-%m-%d %H:%M")
                if row["created_at"] else None
            ),
        }
        for row in rows
    ])

@timbangan_bp.route("/api/timbang/simpan", methods=["POST"])
@login_required
@izin('FORM_TIMBANGAN', 'tambah')
def timbang_simpan():
    no_tiket = request.form.get("no_tiket", "").strip()
    if not no_tiket:
        return jsonify({"error": "No. Tiket wajib diisi"}), 400

    jembatan = jembatan_dipilih(request)
    if jembatan is None:
        return jsonify({"error": "Silakan pilih jembatan timbang untuk PC ini (di atas tampilan berat)"}), 400
    status = baca_status(jembatan["id_jembatan"])
    if not status.get("terhubung"):
        return jsonify({"error": f"Timbangan {jembatan['kode']} tidak terhubung: {status.get('error') or '-'}"}), 400
    if status.get("perlu_nol"):
        return jsonify({"error": "Timbangan belum kembali ke 0 sejak penimbangan sebelumnya. Pastikan truk sebelumnya "
                                 "sudah turun; bila angka tetap tersisa / minus, tekan ZERO di indikator."}), 400
    if not status.get("siap_kunci"):
        return jsonify({"error": "Berat belum stabil"}), 400
    if status["berat"] < jembatan.get("berat_min_kg", 0):
        return jsonify({"error": f"Berat {status['berat']:g} kg di bawah minimum {jembatan['berat_min_kg']:g} kg "
                                 f"(timbangan kosong / truk belum naik penuh)"}), 400

    try:
        hasil = db_tiket.simpan_berat_tiket(
            no_tiket,
            status["berat"],
            str(current_user.id),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal menyimpan timbang Tiket untuk tiket %s",
            no_tiket,
        )
        return jsonify({
            "error": (
                "Berat gagal disimpan ke Tiket. "
                "Periksa status tiket sebelum mencoba lagi."
            )
        }), 503

    if hasil.get("step") == 2 and hasil.get("no_do2"):
        try:
            db_tiket_pisah.simpan_pasangan_do2(
                hasil["ticket_id"],
                hasil["ticket_no"],
                hasil["no_do2"],
                int(current_user.id),
            )
        except Exception:
            logging.getLogger("weighbridge").exception(
                "Split Tiket tersimpan, tetapi catatan pasangan DO2 gagal diperbarui."
            )

    wajib_kembali_nol(jembatan["id_jembatan"])

    if hasil.get("pending_do2"):
        return jsonify({
            "message": (
                "Berat akhir sudah tersimpan. "
                "Tiket menunggu DO kedua dan akan diproses otomatis."
            ),
            "status": "MENUNGGU_DO2",
            "no_tiket": hasil["ticket_no"],
            "berat_netto": hasil["berat_netto"],
            "tiket_pisah": [],
            "peringatan": [],
            "kelebihan_do": None,
        }), 202

    if hasil["step"] == 1:
        label = "Tara" if hasil["ticket_type"] == "Produk" else "Bruto"
        pesan = f"Timbang pertama ({label}) tersimpan di Tiket."
    else:
        pesan = (
            f"Timbang terakhir tersimpan di Tiket. "
            f"Netto: {hasil['berat_netto']:,.0f} kg."
        )

    return jsonify({
        "message": pesan,
        "peringatan": [],
        "kelebihan_do": None,
        "tiket_pisah": hasil.get("tiket_pisah", []),
    }), 200
    