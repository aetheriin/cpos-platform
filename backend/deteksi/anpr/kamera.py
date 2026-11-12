"""Membaca stream RTSP di thread terpisah dan selalu menyimpan frame terbaru.

Frame lama dibuang supaya pembacaan plat tidak tertinggal di belakang video (buffer RTSP menumpuk
kalau proses AI lebih lambat dari FPS kamera). Kalau stream putus, kamera disambung ulang otomatis.
"""
import os
import threading
import time

# RTSP lewat TCP: lebih stabil daripada UDP (gambar tidak pecah saat jaringan sibuk).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402  (harus setelah opsi FFMPEG di atas)

from anpr.konfigurasi import sembunyikan_sandi  # noqa: E402


class KameraRTSP:
    def __init__(self, daftar_url, nama="KAMERA"):
        self.daftar_url = list(daftar_url)
        self.nama = nama
        self.url_aktif = None
        self.status = "menyambung"
        self.resolusi = None
        self.fps = 0.0
        self._frame = None
        self._waktu = 0.0
        self._nomor = 0
        self._kunci = threading.Lock()
        self._jalan = False
        self._thread = None

    def mulai(self):
        self._jalan = True
        self._thread = threading.Thread(target=self._loop, name=f"kamera-{self.nama}", daemon=True)
        self._thread.start()
        return self

    def berhenti(self):
        self._jalan = False
        if self._thread:
            self._thread.join(timeout=5)

    def ambil(self):
        """Return (frame, waktu, nomor_frame) terbaru, atau (None, 0, 0) kalau belum ada gambar."""
        with self._kunci:
            return self._frame, self._waktu, self._nomor

    def _buka(self):
        # URL yang terakhir berhasil dicoba lebih dulu
        urutan = ([self.url_aktif] if self.url_aktif else []) + [u for u in self.daftar_url if u != self.url_aktif]
        for url in urutan:
            print(f"[{self.nama}] Menyambung {sembunyikan_sandi(url)} ...")
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000,
                                                         cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    self.url_aktif = url
                    self.resolusi = (frame.shape[1], frame.shape[0])
                    print(f"[{self.nama}] Tersambung {self.resolusi[0]}x{self.resolusi[1]}")
                    return cap, frame
            cap.release()
        return None, None

    def _loop(self):
        jeda = 2
        while self._jalan:
            cap, frame = self._buka()
            if cap is None:
                self.status = f"gagal sambung, coba lagi {jeda} dtk"
                print(f"[{self.nama}] Gagal tersambung. Cek IP, user/password, dan RTSP aktif. Ulang {jeda} dtk")
                time.sleep(jeda)
                jeda = min(jeda * 2, 30)
                continue

            jeda = 2
            self.status = "tersambung"
            hitung, mulai = 0, time.time()
            while self._jalan and frame is not None:
                with self._kunci:
                    self._frame, self._waktu, self._nomor = frame, time.time(), self._nomor + 1
                hitung += 1
                if time.time() - mulai >= 2:
                    self.fps = hitung / (time.time() - mulai)
                    hitung, mulai = 0, time.time()
                ok, frame = cap.read()
                if not ok:
                    frame = None
            cap.release()
            if self._jalan:
                self.status = "putus, menyambung ulang"
                print(f"[{self.nama}] Stream putus, menyambung ulang...")
                with self._kunci:
                    self._frame = None
