"""Menyimpan hasil ke folder hasil/: CSV harian + gambar bukti.

hasil/plat_YYYY-MM-DD.csv     satu baris per plat yang pasti terbaca (setelah voting)
hasil/bacaan_YYYY-MM-DD.csv   semua bacaan per frame (untuk analisa salah baca), bila SIMPAN_SEMUA_BACAAN=1
hasil/YYYY-MM-DD/             gambar frame + crop plat, juga snapshot manual (tombol S)
CSV memakai pemisah ';' dan UTF-8 BOM supaya langsung rapi dibuka di Excel berbahasa Indonesia.
"""
import csv
from datetime import datetime

import cv2

KOLOM_PLAT = ["waktu", "kamera", "plat", "jumlah_frame", "conf_ocr", "conf_deteksi", "lebar_plat_px",
              "bacaan_mentah", "bacaan_mirip", "gambar", "crop"]
KOLOM_BACAAN = ["waktu", "kamera", "bacaan_mentah", "plat", "conf_ocr", "conf_min", "conf_deteksi",
                "lebar_plat_px", "keterangan", "proses_ms"]


def _nama_aman(teks):
    return "".join(c if c.isalnum() else "_" for c in teks)


class Penyimpan:
    def __init__(self, folder_hasil, nama_kamera):
        self.folder = folder_hasil
        self.kamera = nama_kamera
        self.folder.mkdir(parents=True, exist_ok=True)

    def _tulis_csv(self, nama, kolom, baris):
        path = self.folder / nama
        baru = not path.exists()
        with open(path, "a", newline="", encoding="utf-8-sig" if baru else "utf-8") as f:
            w = csv.writer(f, delimiter=";")
            if baru:
                w.writerow(kolom)
            w.writerow(baris)

    def _folder_hari(self, waktu):
        folder = self.folder / waktu.strftime("%Y-%m-%d")
        folder.mkdir(exist_ok=True)
        return folder

    def simpan_plat(self, hasil, frame_bergambar):
        w = datetime.fromtimestamp(hasil.waktu)
        dasar = self._folder_hari(w) / f"{w:%H%M%S}_{self.kamera}_{_nama_aman(hasil.plat)}"
        b = hasil.bacaan_terbaik
        cv2.imwrite(f"{dasar}.jpg", frame_bergambar, [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(f"{dasar}_plat.jpg", b.crop)
        mirip = ", ".join(f"{p} ({n}x)" for p, n in hasil.kandidat_lain.items())
        self._tulis_csv(f"plat_{w:%Y-%m-%d}.csv", KOLOM_PLAT, [
            f"{w:%Y-%m-%d %H:%M:%S}", self.kamera, hasil.plat, hasil.jumlah_frame,
            f"{hasil.conf_ocr:.2f}", f"{b.conf_deteksi:.2f}", b.lebar_px, b.teks_mentah, mirip,
            dasar.with_suffix(".jpg").name, f"{dasar.name}_plat.jpg",
        ])

    def simpan_bacaan(self, waktu, bacaan_list, proses_ms):
        w = datetime.fromtimestamp(waktu)
        for b in bacaan_list:
            self._tulis_csv(f"bacaan_{w:%Y-%m-%d}.csv", KOLOM_BACAAN, [
                f"{w:%Y-%m-%d %H:%M:%S}.{w.microsecond // 1000:03d}", self.kamera, b.teks_mentah,
                b.plat or "", f"{b.conf_ocr:.2f}", f"{b.conf_min:.2f}", f"{b.conf_deteksi:.2f}",
                b.lebar_px, b.keterangan, f"{proses_ms:.0f}",
            ])

    def simpan_snapshot(self, frame, waktu):
        w = datetime.fromtimestamp(waktu)
        path = self._folder_hari(w) / f"snapshot_{w:%H%M%S}_{self.kamera}.jpg"
        cv2.imwrite(str(path), frame)
        return path
