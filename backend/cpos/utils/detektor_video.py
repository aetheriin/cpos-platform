"""Video kamera dari backend deteksi plat (PC lain). CPOS hanya meneruskan: browser tidak pernah menghubungi PC deteksi langsung.
Alamat PC deteksi dari .env (URL_DETEKTOR, bawaan http://127.0.0.1:<DETEKTOR_PORT>), bukan dari input pengguna."""
import os
import re
import threading
import time
from urllib.parse import quote

import requests

TIMEOUT = (3, 8)
POLA_NAMA = re.compile(r"^[A-Za-z0-9 _-]{1,30}$")
_slot = threading.BoundedSemaphore(int(os.getenv("DETEKTOR_MAKS_LIVE", "3")))


class DetektorGagal(Exception):
    """Backend deteksi tidak menjawab; pesannya aman ditampilkan."""


def _alamat(jalur, nama=None):
    dasar = (os.getenv("URL_DETEKTOR") or f"http://127.0.0.1:{os.getenv('DETEKTOR_PORT') or 8000}").strip().rstrip("/")
    if nama is None:
        return f"{dasar}{jalur}"
    if not POLA_NAMA.match(nama):
        raise DetektorGagal("Nama kamera tidak valid")
    return f"{dasar}{jalur}{quote(nama, safe='')}"


def status():
    """JSON /api/status backend deteksi: {'ai_ms': .., 'kamera': [{nama, status, resolusi, fps}], ..}"""
    try:
        r = requests.get(_alamat("/api/status"), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise DetektorGagal("Backend deteksi tidak terjangkau") from e
    except ValueError as e:
        raise DetektorGagal("Jawaban backend deteksi tidak dikenal") from e


def snapshot(nama):
    """Satu gambar JPEG terbaru (sudah bertanda kotak plat & hasil bacaan)."""
    try:
        r = requests.get(_alamat("/snapshot/", nama), timeout=TIMEOUT)
    except requests.RequestException as e:
        raise DetektorGagal("Backend deteksi tidak terjangkau") from e
    if r.status_code != 200 or not r.content.startswith(b"\xff\xd8"):
        raise DetektorGagal(f"Kamera {nama} tidak ditemukan di backend deteksi")
    return r.content


def ambil_slot():
    """Satu slot video layar penuh (dilepas dengan lepas_slot); penuh = DetektorGagal."""
    if not _slot.acquire(timeout=2):
        raise DetektorGagal("Terlalu banyak video layar penuh yang sedang dibuka. Tutup salah satu, lalu coba lagi.")


def lepas_slot():
    _slot.release()


def mjpeg(nama, maks_detik=600):
    """(content-type, generator potongan bytes) video MJPEG. Berhenti sendiri setelah maks_detik."""
    try:
        r = requests.get(_alamat("/video/", nama), timeout=TIMEOUT, stream=True)
    except requests.RequestException as e:
        raise DetektorGagal("Backend deteksi tidak terjangkau") from e
    if r.status_code != 200:
        r.close()
        raise DetektorGagal(f"Kamera {nama} tidak ditemukan di backend deteksi")

    def isi():
        mulai = time.monotonic()
        try:
            for potong in r.iter_content(chunk_size=32 * 1024):
                yield potong
                if time.monotonic() - mulai > maks_detik:
                    break
        finally:
            r.close()
    return r.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame"), isi()