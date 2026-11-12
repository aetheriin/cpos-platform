"""Deteksi plat + OCR memakai model jadi dari fast-alpr (ONNX, jalan di CPU)."""
import time
from dataclasses import dataclass

from anpr.plat import rapikan_bacaan


@dataclass
class Bacaan:
    kotak: tuple            # (x1, y1, x2, y2) di frame asli
    conf_deteksi: float
    teks_mentah: str        # keluaran OCR apa adanya
    conf_ocr: float         # rata-rata keyakinan per karakter
    conf_min: float         # karakter paling tidak yakin
    plat: str | None        # format baku 'BM 1455 JJ', None kalau tidak lolos
    keterangan: str         # alasan ditolak / jumlah koreksi karakter
    crop: object            # gambar plat (numpy BGR)

    @property
    def lebar_px(self):
        return self.kotak[2] - self.kotak[0]

    @property
    def diterima(self):
        return self.plat is not None


class PembacaPlat:
    def __init__(self, konf):
        from fast_alpr import ALPR  # impor di sini supaya mode --cek tidak perlu memuat model

        self.konf = konf
        print(f"Memuat model deteksi '{konf.detektor_model}' dan OCR '{konf.ocr_model}' "
              "(pertama kali akan mengunduh, butuh internet)...")
        alpr = ALPR(detector_model=konf.detektor_model, detector_conf_thresh=konf.min_conf_deteksi,
                    ocr_model=konf.ocr_model, ocr_device="cpu")
        self.detektor = alpr.detector
        self.ocr = alpr.ocr
        self.waktu_proses_ms = 0.0

    def baca(self, frame):
        mulai = time.perf_counter()
        hasil = []
        tinggi, lebar = frame.shape[:2]
        for det in self.detektor.predict(frame):
            b = det.bounding_box
            mx = int((b.x2 - b.x1) * self.konf.margin_crop)
            my = int((b.y2 - b.y1) * self.konf.margin_crop)
            x1, y1 = max(b.x1 - mx, 0), max(b.y1 - my, 0)
            x2, y2 = min(b.x2 + mx, lebar), min(b.y2 + my, tinggi)
            if x2 - x1 < 8 or y2 - y1 < 4:
                continue
            crop = frame[y1:y2, x1:x2].copy()
            ocr = self.ocr.predict(crop)
            teks = (ocr.text if ocr else "") or ""
            conf = ocr.confidence if ocr else 0.0
            # confidence berisi satu nilai per slot (termasuk slot kosong di belakang): ambil sepanjang teks
            per_huruf = list(conf[:len(teks)]) if isinstance(conf, list) else [float(conf)]
            conf_ocr = sum(per_huruf) / len(per_huruf) if per_huruf else 0.0
            conf_min = min(per_huruf) if per_huruf else 0.0

            plat, info = rapikan_bacaan(teks)
            if plat and conf_ocr < self.konf.min_conf_ocr:
                plat, info = None, f"OCR kurang yakin ({conf_ocr:.0%})"
            keterangan = info if plat is None else ("" if info == 0 else f"{info} karakter dikoreksi")
            hasil.append(Bacaan((b.x1, b.y1, b.x2, b.y2), float(det.confidence), teks,
                                conf_ocr, conf_min, plat, keterangan, crop))
        self.waktu_proses_ms = (time.perf_counter() - mulai) * 1000
        return hasil
