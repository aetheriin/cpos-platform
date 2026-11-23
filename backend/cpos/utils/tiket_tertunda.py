"""Worker penyelesaian timbang Tiket yang menunggu DO2."""
import logging
import threading
import time

from utils import db_tiket, db_tiket_pisah

log = logging.getLogger("weighbridge")
INTERVAL_DETIK = 60


def _proses_satu(baris):
    ticket_id = int(baris["ticket_id"])
    ticket_no = str(baris["ticket_no"]).strip()

    hasil_lama = db_tiket.baca_hasil_pisah_tiket(ticket_id)

    if hasil_lama:
        anak = hasil_lama["anak"]

        if anak:
            if len(anak) != 2:
                raise RuntimeError(
                    "Tiket memiliki jumlah tiket pecahan yang tidak sesuai."
                )

            no_do1 = hasil_lama["no_do1"].strip().casefold()
            kandidat_do2 = [
                t["no_do"]
                for t in anak
                if t["no_do"].strip().casefold() != no_do1
            ]
            if len(kandidat_do2) != 1:
                raise RuntimeError(
                    "DO2 dari tiket pecahan Tiket tidak dapat dipastikan."
                )

            db_tiket_pisah.selesaikan_timbang_pending(
                ticket_id,
                kandidat_do2[0],
            )
            return

        if (
            hasil_lama["step"] >= 2
            and hasil_lama["datetimeout"] is not None
            and not hasil_lama["pisahted"]
            and not hasil_lama["void"]
        ):
            db_tiket_pisah.selesaikan_timbang_pending(ticket_id)
            return

    hasil = db_tiket.simpan_berat_tiket(
        ticket_no,
        baris["berat_akhir"],
        str(baris["operator_id"]),
        waktu_timbang=baris["waktu_timbang"],
    )

    if hasil.get("pending_do2"):
        raise RuntimeError("DO2 yang cocok belum tersedia di Tiket.")

    if hasil.get("step") != 2:
        raise RuntimeError("Timbang akhir belum berhasil diselesaikan di Tiket.")

    if hasil.get("no_do2") and len(hasil.get("tiket_pisah", [])) != 2:
        raise RuntimeError("Tiket belum mengembalikan dua tiket hasil pisah.")

    db_tiket_pisah.selesaikan_timbang_pending(
        ticket_id,
        hasil.get("no_do2"),
    )


def proses_antrean_timbang_pending():
    for baris in db_tiket_pisah.daftar_timbang_akhir_pending():
        ticket_id = int(baris["ticket_id"])
        try:
            _proses_satu(baris)
            log.info(
                "Timbang tertunda tiket %s berhasil diproses.",
                baris["ticket_no"],
            )
        except Exception as e:
            try:
                db_tiket_pisah.catat_percobaan_timbang_pending(ticket_id, str(e))
            except Exception:
                log.exception(
                    "Gagal memperbarui status antrean tiket %s.",
                    baris["ticket_no"],
                )
            log.warning(
                "Tiket Tiket %s masih menunggu DO2: %s",
                baris["ticket_no"],
                e,
            )


def mulai_worker_timbang_pending():
    def loop():
        while True:
            try:
                proses_antrean_timbang_pending()
            except Exception:
                log.exception("Worker timbang Tiket tertunda mengalami kesalahan.")
            time.sleep(INTERVAL_DETIK)

    threading.Thread(
        target=loop,
        daemon=True,
        name="tiket-timbang-pending",
    ).start()