"""Worker penyelesaian timbang Ascend yang menunggu DO2."""
import logging
import threading
import time

from utils import db_ascend, db_ascend_split

log = logging.getLogger("weighbridge")
INTERVAL_DETIK = 60


def _proses_satu(baris):
    ticket_id = int(baris["ticket_id"])
    ticket_no = str(baris["ticket_no"]).strip()

    hasil_lama = db_ascend.baca_hasil_split_ascend(ticket_id)

    if hasil_lama:
        anak = hasil_lama["anak"]

        if anak:
            if len(anak) != 2:
                raise RuntimeError(
                    "Ascend memiliki jumlah tiket pecahan yang tidak sesuai."
                )

            no_do1 = hasil_lama["no_do1"].strip().casefold()
            kandidat_do2 = [
                t["no_do"]
                for t in anak
                if t["no_do"].strip().casefold() != no_do1
            ]
            if len(kandidat_do2) != 1:
                raise RuntimeError(
                    "DO2 dari tiket pecahan Ascend tidak dapat dipastikan."
                )

            db_ascend_split.selesaikan_timbang_pending(
                ticket_id,
                kandidat_do2[0],
            )
            return

        if (
            hasil_lama["step"] >= 2
            and hasil_lama["datetimeout"] is not None
            and not hasil_lama["splitted"]
            and not hasil_lama["void"]
        ):
            db_ascend_split.selesaikan_timbang_pending(ticket_id)
            return

    hasil = db_ascend.simpan_berat_tiket_ascend(
        ticket_no,
        baris["berat_akhir"],
        str(baris["operator_id"]),
        waktu_timbang=baris["waktu_timbang"],
    )

    if hasil.get("pending_do2"):
        raise RuntimeError("DO2 yang cocok belum tersedia di Ascend.")

    if hasil.get("step") != 2:
        raise RuntimeError("Timbang akhir belum berhasil diselesaikan di Ascend.")

    if hasil.get("no_do2") and len(hasil.get("tiket_split", [])) != 2:
        raise RuntimeError("Ascend belum mengembalikan dua tiket hasil split.")

    db_ascend_split.selesaikan_timbang_pending(
        ticket_id,
        hasil.get("no_do2"),
    )


def proses_antrean_timbang_pending():
    for baris in db_ascend_split.daftar_timbang_akhir_pending():
        ticket_id = int(baris["ticket_id"])
        try:
            _proses_satu(baris)
            log.info(
                "Timbang tertunda tiket Ascend %s berhasil diproses.",
                baris["ticket_no"],
            )
        except Exception as e:
            try:
                db_ascend_split.catat_percobaan_timbang_pending(ticket_id, str(e))
            except Exception:
                log.exception(
                    "Gagal memperbarui status antrean tiket %s.",
                    baris["ticket_no"],
                )
            log.warning(
                "Tiket Ascend %s masih menunggu DO2: %s",
                baris["ticket_no"],
                e,
            )


def mulai_worker_timbang_pending():
    def loop():
        while True:
            try:
                proses_antrean_timbang_pending()
            except Exception:
                log.exception("Worker timbang Ascend tertunda mengalami kesalahan.")
            time.sleep(INTERVAL_DETIK)

    threading.Thread(
        target=loop,
        daemon=True,
        name="ascend-timbang-pending",
    ).start()