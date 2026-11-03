"""Baca plat nomor langsung dari CCTV (RTSP).

    python baca_plat.py              baca plat dari kamera di .env, tampilkan preview
    python baca_plat.py --cek        hanya cek sambungan kamera (tanpa AI): resolusi, FPS, URL yang jalan
    python baca_plat.py --video f    uji dari file rekaman (mp4/avi) atau foto (jpg/png) alih-alih kamera
    python baca_plat.py --tanpa-layar   tanpa jendela preview (hasil tetap ke konsol & folder hasil)

Tombol di jendela preview:  Q / Esc = keluar,  S = simpan snapshot (untuk bahan dataset / laporan masalah)
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from anpr.kamera import KameraRTSP, cv2
from anpr.konfigurasi import muat_konfigurasi, sembunyikan_sandi

HIJAU, MERAH, KUNING, PUTIH, HITAM = (40, 200, 40), (40, 40, 230), (0, 200, 255), (255, 255, 255), (0, 0, 0)
EKSTENSI_FOTO = {".jpg", ".jpeg", ".png", ".bmp"}


class SumberFile:
    """Rekaman video / foto dibaca berurutan (pengganti kamera untuk uji)."""

    def __init__(self, path):
        self.path = Path(path)
        self.foto = self.path.suffix.lower() in EKSTENSI_FOTO
        self.cap = None if self.foto else cv2.VideoCapture(str(self.path))
        self.status, self.fps, self._nomor, self._selesai = "file", 0.0, 0, False
        self.resolusi = None

    def mulai(self):
        return self

    def berhenti(self):
        if self.cap:
            self.cap.release()

    def ambil(self):
        if self._selesai:
            return None, 0, self._nomor
        if self.foto:
            frame = cv2.imread(str(self.path))
            self._selesai = True
        else:
            ok, frame = self.cap.read()
            frame = frame if ok else None
            self._selesai = frame is None
        if frame is not None:
            self._nomor += 1
            self.resolusi = (frame.shape[1], frame.shape[0])
        return frame, time.time(), self._nomor

    @property
    def habis(self):
        return self._selesai


def tulis(img, teks, xy, skala=0.7, warna=PUTIH, tebal=2):
    cv2.putText(img, teks, xy, cv2.FONT_HERSHEY_SIMPLEX, skala, HITAM, tebal + 3, cv2.LINE_AA)
    cv2.putText(img, teks, xy, cv2.FONT_HERSHEY_SIMPLEX, skala, warna, tebal, cv2.LINE_AA)


def gambar_bacaan(frame, bacaan_list, penstabil=None):
    """Kotak plat + teks: hijau = format plat valid, kuning = valid tapi sudah dilaporkan, merah = ditolak."""
    img = frame.copy()
    skala = max(0.6, img.shape[1] / 1800)
    for b in bacaan_list:
        x1, y1, x2, y2 = b.kotak
        if not b.diterima:
            warna, label = MERAH, f"{b.teks_mentah or '?'} ({b.keterangan})"
        elif penstabil and penstabil.sudah_dilaporkan(b.plat):
            warna, label = KUNING, f"{b.plat}  {b.conf_ocr:.0%}"
        else:
            warna, label = HIJAU, f"{b.plat}  {b.conf_ocr:.0%}"
        cv2.rectangle(img, (x1, y1), (x2, y2), warna, max(2, int(skala * 3)))
        tulis(img, label, (x1, max(30, y1 - 12)), skala, warna)
        tulis(img, f"lebar {b.lebar_px}px", (x1, y2 + int(30 * skala)), skala * 0.7, PUTIH)
    return img


def tampilkan(nama_jendela, img, lebar):
    if img.shape[1] > lebar:
        img = cv2.resize(img, (lebar, int(img.shape[0] * lebar / img.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.imshow(nama_jendela, img)
    return cv2.waitKey(1) & 0xFF


def jalankan(args):
    konf = muat_konfigurasi()
    if args.video:
        sumber = SumberFile(args.video).mulai()
    else:
        if not konf.kamera_ip and not konf.rtsp_url:
            sys.exit("KAMERA_IP belum diisi di file .env (salin .env.example menjadi .env lalu isi).")
        sumber = KameraRTSP(konf.daftar_url_rtsp(), konf.nama_kamera).mulai()

    pembaca = penstabil = penyimpan = None
    if not args.cek:
        from anpr.pembaca import PembacaPlat
        from anpr.penstabil import PenstabilPlat
        from anpr.penyimpan import Penyimpan

        pembaca = PembacaPlat(konf)
        foto = isinstance(sumber, SumberFile) and sumber.foto
        penstabil = PenstabilPlat(1 if foto else konf.min_frame_sama, konf.jendela_detik, konf.jeda_ulang_detik)
        penyimpan = Penyimpan(konf.folder_hasil, konf.nama_kamera)
        print(f"Hasil disimpan di: {konf.folder_hasil}")

    nama_jendela = f"Deteksi Plat - {konf.nama_kamera}"
    nomor_terakhir, terakhir_terbaca, waktu_info = 0, None, 0.0
    print("Berjalan. Tekan Q / Esc di jendela preview (atau Ctrl+C di sini) untuk berhenti.")
    try:
        while True:
            frame, waktu, nomor = sumber.ambil()
            if frame is None or nomor == nomor_terakhir:
                if isinstance(sumber, SumberFile) and sumber.habis:
                    if sumber.foto and not args.tanpa_layar:
                        print("Tekan tombol apa saja di jendela gambar untuk menutup.")
                        cv2.waitKey(0)
                    break
                time.sleep(0.01)
                if not args.tanpa_layar and (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
                continue
            nomor_terakhir = nomor

            if args.cek:
                tampil = frame.copy()
                proses_ms = 0.0
            else:
                bacaan = pembaca.baca(frame)
                proses_ms = pembaca.waktu_proses_ms
                if bacaan and konf.simpan_semua_bacaan:
                    penyimpan.simpan_bacaan(waktu, bacaan, proses_ms)
                for hasil in penstabil.tambah(waktu, bacaan, frame):
                    terakhir_terbaca = hasil
                    b = hasil.bacaan_terbaik
                    penyimpan.simpan_plat(hasil, gambar_bacaan(hasil.frame_terbaik, [b]))
                    mirip = f"  (juga terbaca: {', '.join(hasil.kandidat_lain)})" if hasil.kandidat_lain else ""
                    print(f"[{datetime.fromtimestamp(hasil.waktu):%H:%M:%S}] {konf.nama_kamera}  >>> "
                          f"{hasil.plat} <<<  {hasil.jumlah_frame} frame, OCR {hasil.conf_ocr:.0%}, "
                          f"lebar plat {b.lebar_px}px{mirip}")
                tampil = gambar_bacaan(frame, bacaan, penstabil)

            if time.time() - waktu_info >= 10:
                waktu_info = time.time()
                res = f"{sumber.resolusi[0]}x{sumber.resolusi[1]}" if sumber.resolusi else "-"
                print(f"   status: {sumber.status}, {res}, kamera {sumber.fps:.1f} fps"
                      + ("" if args.cek else f", proses AI {proses_ms:.0f} ms/frame"))

            if args.tanpa_layar:
                continue
            res = f"{sumber.resolusi[0]}x{sumber.resolusi[1]}" if sumber.resolusi else ""
            info = f"{konf.nama_kamera} | {sumber.status} | {res} | kamera {sumber.fps:.1f} fps"
            if not args.cek:
                info += f" | AI {proses_ms:.0f} ms"
            skala = max(0.6, tampil.shape[1] / 1800)
            tulis(tampil, info, (15, int(40 * skala)), skala)
            if terakhir_terbaca:
                tulis(tampil, f"Terakhir: {terakhir_terbaca.plat}  "
                              f"({datetime.fromtimestamp(terakhir_terbaca.waktu):%H:%M:%S})",
                      (15, int(95 * skala)), skala * 1.4, HIJAU, 3)
            tombol = tampilkan(nama_jendela, tampil, konf.lebar_tampilan)
            if tombol in (ord("q"), 27):
                break
            if tombol == ord("s"):
                from anpr.penyimpan import Penyimpan
                path = (penyimpan or Penyimpan(konf.folder_hasil, konf.nama_kamera)).simpan_snapshot(frame, waktu)
                print(f"Snapshot disimpan: {path}")
    except KeyboardInterrupt:
        pass
    finally:
        sumber.berhenti()
        if not args.tanpa_layar:
            cv2.destroyAllWindows()
    print("Selesai.")


def main():
    p = argparse.ArgumentParser(description="Baca plat nomor dari CCTV (RTSP)")
    p.add_argument("--cek", action="store_true", help="hanya cek sambungan kamera, tanpa AI")
    p.add_argument("--video", help="uji dari file video / foto alih-alih kamera")
    p.add_argument("--tanpa-layar", action="store_true", help="tanpa jendela preview")
    args = p.parse_args()
    if args.video:
        print(f"Sumber: file {args.video}")
    else:
        konf = muat_konfigurasi()
        print("Sumber: " + " atau ".join(sembunyikan_sandi(u) for u in konf.daftar_url_rtsp()))
    jalankan(args)


if __name__ == "__main__":
    main()
