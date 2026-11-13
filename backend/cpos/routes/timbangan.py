import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify
from utils.hak_akses import lihat, MENU_OPERASI
from utils.area import area_data
from utils.area_filter import area_cocok
from flask_login import login_required, current_user
from utils.serial_reader import baca_status, reset_deteksi_stabil, wajib_kembali_nol
from utils.db_utils import (
    get_data_timbangan, simpan_timbang_pertama, simpan_timbang_kedua, catat_timeline,
    cari_transaksi_aktif, get_history_timbangan_by_supplier
)
from utils.serializers import serialisasi_tiket
from utils.hak_akses import izin
from utils.db_jembatan import jembatan_dipilih
from utils import alur, db_kelebihan_do, log_aktivitas, db_ascend, db_ascend_split
from utils.db_master import cek_kapasitas

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

KOSONG = {"berat_bruto": None, "berat_tara": None, "berat_netto": None, "potongan_kg": None, "netto_akhir": None}


def _tiket_di_area(id_comp_area):
    """Tiket site lain diperlakukan seperti tidak ada (tanpa memberi tahu bahwa nomornya ada)."""
    return area_cocok(area_data(current_user.id), id_comp_area)


@timbangan_bp.route("/api/timbang/data/<no_tiket>")
@login_required
@lihat(*MENU_OPERASI)
def timbang_data(no_tiket):
    if request.args.get("sumber", "").upper() == "ASCEND":
        try:
            data = db_ascend.baca_berat_tiket_ascend(no_tiket)
        except Exception:
            logging.exception(
                "Gagal membaca berat tiket Ascend %s",
                no_tiket,
            )
            return jsonify({
                "error": "Berat tiket Ascend belum dapat dibaca."
            }), 503

        if not data:
            return jsonify({
                "berat_bruto": None,
                "berat_tara": None,
                "berat_netto": None,
            })

        try:
            rencana = db_ascend_split.baca_status_timbang_pending(no_tiket)
        except Exception:
            logging.exception(
                "Gagal membaca status pending tiket Ascend %s",
                no_tiket,
            )
            return jsonify({
                "error": "Status timbang tiket Ascend belum dapat dibaca."
            }), 503

        # Berat akhir pending tetap ditampilkan untuk keperluan penimbangan.
        # Status pending, DO2, dan tiket pasangan tidak dikirim ke API operasional.
        if rencana and rencana["status"] == "MENUNGGU_DO2":
            berat_akhir = rencana["berat_akhir_pending"]
            if berat_akhir is not None:
                data["berat_bruto"] = berat_akhir
                if data["berat_tara"] is not None:
                    data["berat_netto"] = (
                        berat_akhir - data["berat_tara"]
                    )

        return jsonify(data)
    row = get_data_timbangan(no_tiket)
    if not row or not _tiket_di_area(row.id_comp_area):
        return jsonify(KOSONG)
    return jsonify({"berat_bruto": row.berat_bruto, "berat_tara": row.berat_tara, "berat_netto": row.berat_netto,
                    "potongan_kg": row.total_potongan_kg, "netto_akhir": _netto_akhir(row),
                    "jembatan_masuk": row.kode_jembatan})

def _netto_akhir(row):
    if row.berat_netto is None:
        return None
    return round(row.berat_netto - (row.total_potongan_kg or 0), 2)

@timbangan_bp.route("/api/timbang/scan-qr", methods=["POST"])
@login_required
@lihat(*MENU_OPERASI)
def timbang_scan_qr():
    try:
        tiket_ascend = db_ascend.cari_tiket_ascend_berdasarkan_no_tiket(
            request.form.get("no_tiket", "").strip()
        )
    except Exception:
        logging.getLogger("weighbridge").exception(
            "Gagal mencari tiket Ascend lewat scan QR"
        )
        return jsonify({
            "error": "Tiket Ascend belum dapat diperiksa. Coba lagi."
        }), 503

    if tiket_ascend:
        return jsonify({
            "status": "ADA_TIKET",
            "sumber": "ASCEND",
            "no_tiket": tiket_ascend["no_tiket"],
            "no_plat": tiket_ascend["no_plat"],
            "no_do": tiket_ascend["no_do"],
            "supplier": tiket_ascend["associate"],
            "produk": tiket_ascend["produk"],
            "ticket_type": tiket_ascend["ticket_type"],
            "jenis_transaksi": tiket_ascend["jenis_transaksi"],
            "id_supplier": None,
            "driver": None,
        }), 200
    row = cari_transaksi_aktif(no_tiket=request.form.get("no_tiket", "").strip())
    if not row or not _tiket_di_area(row.id_comp_area):
        return jsonify({"error": "Tiket tidak ditemukan atau sudah selesai"}), 404
    return jsonify(serialisasi_tiket(row)), 200

HARI_HISTORY_MAKS = 30


@timbangan_bp.route("/api/history-timbangan-supplier")
@login_required
@lihat(*MENU_OPERASI)
def history_supplier():
    id_supplier = request.args.get("id_supplier")
    tanggal = None
    if request.args.get("tanggal"):            # filter per hari, hanya 30 hari terakhir
        try:
            tanggal = datetime.strptime(request.args["tanggal"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Format tanggal salah"}), 400
        if not 0 <= (date.today() - tanggal).days < HARI_HISTORY_MAKS:
            return jsonify({"error": f"Tanggal hanya bisa dipilih {HARI_HISTORY_MAKS} hari terakhir"}), 400
    rows = (get_history_timbangan_by_supplier(id_supplier, tanggal=tanggal, id_area=area_data(current_user.id))
            if id_supplier else [])
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else None} for r in rows])

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

    if request.form.get("sumber", "").upper() == "ASCEND":
        try:
            hasil = db_ascend.simpan_berat_tiket_ascend(
                no_tiket,
                status["berat"],
                str(current_user.id),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 409
        except Exception:
            logging.getLogger("weighbridge").exception(
                "Gagal menyimpan timbang Ascend untuk tiket %s",
                no_tiket,
            )
            return jsonify({
                "error": (
                    "Berat gagal disimpan ke Ascend. "
                    "Periksa status tiket sebelum mencoba lagi."
                )
            }), 503

        if hasil.get("step") == 2 and hasil.get("no_do2"):
            try:
                db_ascend_split.simpan_pasangan_do2(
                    hasil["ticket_id"],
                    hasil["ticket_no"],
                    hasil["no_do2"],
                    int(current_user.id),
                )
            except Exception:
                logging.getLogger("weighbridge").exception(
                    "Split Ascend tersimpan, tetapi catatan pasangan DO2 gagal diperbarui."
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
                "tiket_split": [],
                "peringatan": [],
                "kelebihan_do": None,
            }), 202

        if hasil["step"] == 1:
            label = "Tara" if hasil["ticket_type"] == "Produk" else "Bruto"
            pesan = f"Timbang pertama ({label}) tersimpan di Ascend."
        else:
            pesan = (
                f"Timbang terakhir tersimpan di Ascend. "
                f"Netto: {hasil['berat_netto']:,.0f} kg."
            )

        return jsonify({
            "message": pesan,
            "peringatan": [],
            "kelebihan_do": None,
            "tiket_split": hasil.get("tiket_split", []),
        }), 200
    trx = cari_transaksi_aktif(no_tiket=no_tiket)
    data_lama = get_data_timbangan(no_tiket)
    if trx is None or data_lama is None:
        return jsonify({"error": "Tiket tidak ditemukan, sudah selesai, atau ditolak"}), 404
    if data_lama.berat_netto is not None:
        return jsonify({"error": "Tiket ini sudah selesai ditimbang"}), 400

    berat = status["berat"]
    if data_lama.berat_bruto is None and data_lama.berat_tara is None:
        # Alur dinamis: timbang 1 hanya bila tahapnya sedang ditunggu (mis. alur Lab dulu -> tunggu hasil lab)
        _, pesan = alur.cek_tahap(no_tiket, "TIMBANG_1")
        if pesan:
            return jsonify({"error": pesan}), 400
        jenis = simpan_timbang_pertama(no_tiket, berat, current_user.id, jembatan["id_jembatan"])
        wajib_kembali_nol(jembatan["id_jembatan"])
        catat_timeline(no_tiket, 'TIMBANG_MASUK', current_user.id)
        if jenis == 'PENIMBANGAN_SAJA':
            return jsonify({"message": f"Penimbangan selesai. Netto: {berat} kg",
                            "kelebihan_do": _cek_kelebihan(no_tiket), "peringatan": _cek_kapasitas(no_tiket)}), 200
        label = "Tara" if jenis == 'PENJUALAN' else "Bruto"
        return jsonify({"message": f"{label} berhasil disimpan di {jembatan['kode']}: {berat} kg. "
                                   f"Timbang keluar juga harus di {jembatan['kode']}.",
                        "peringatan": _cek_kapasitas(no_tiket)}), 200

    # Timbang kedua: alur dinamis -> tahap Timbang 2 sedang ditunggu; tiket lama -> setelah inspeksi (status TIMBANG_2)
    dinamis, pesan = alur.cek_tahap(no_tiket, "TIMBANG_2")
    if pesan:
        return jsonify({"error": pesan.replace("Belum bisa:", "Belum bisa timbang kedua,")}), 400
    if not dinamis and trx.status_alur != 'TIMBANG_2':
        menunggu = (alur.menunggu(trx.id_alur, trx.status_alur) if trx.id_alur
                    else "sortasi" if trx.kategori == 'TBS' else "hasil lab (Diterima)")
        return jsonify({"error": f"Belum bisa timbang kedua, tiket masih menunggu {menunggu}"}), 400

    if data_lama.id_jembatan != jembatan["id_jembatan"]:
        return jsonify({"error": f"Tiket ini masuk di {data_lama.kode_jembatan}. Timbang keluar harus di "
                                 f"{data_lama.kode_jembatan}, bukan {jembatan['kode']}."}), 400
    try:
        netto = simpan_timbang_kedua(no_tiket, berat, current_user.id, jembatan["id_jembatan"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    wajib_kembali_nol(jembatan["id_jembatan"])
    catat_timeline(no_tiket, 'TIMBANG_KELUAR', current_user.id)
    hasil = get_data_timbangan(no_tiket)
    pesan = f"Selesai! Netto: {netto} kg"
    if hasil.total_potongan_kg is not None:
        pesan += f", potongan sortasi: {hasil.total_potongan_kg} kg, netto akhir: {_netto_akhir(hasil)} kg"
    return jsonify({"message": pesan, "kelebihan_do": _cek_kelebihan(no_tiket), "peringatan": _cek_kapasitas(no_tiket)}), 200


def _cek_kapasitas(no_tiket):
    """Peringatan tara / muatan dari kapasitas jenis kendaraan (Data Master › Kendaraan). Tidak menahan penimbangan."""
    try:
        peringatan = cek_kapasitas(no_tiket)
    except Exception:       # noqa: BLE001
        logging.getLogger("weighbridge").exception("Gagal cek kapasitas %s", no_tiket)
        return []
    for teks in peringatan:
        log_aktivitas.catat("TIMBANGAN", "PERINGATAN_KAPASITAS", id_baris=no_tiket, baru={"pesan": teks},
                            user_id=current_user.id, ip=request.remote_addr)
    return peringatan


def _cek_kelebihan(no_tiket):
    """DO tiket ini lewat kuota -> tiket split + notifikasi KTU / HO. Gagal di sini tidak membatalkan timbangan."""
    try:
        return db_kelebihan_do.proses_tiket_selesai(no_tiket, current_user.id)
    except Exception:       # noqa: BLE001
        logging.getLogger("weighbridge").exception("Gagal memproses kelebihan DO %s", no_tiket)
        return None