"""Klien gateway video go2rtc (dipasang IT di LAN cabang / HO, lihat docs/PANDUAN_CCTV.md).

Browser tidak pernah menghubungi kamera atau gateway langsung: gambar diambil server CPOS lalu diteruskan, sehingga
hak akses & cakupan area tetap berlaku dan alamat / password kamera tidak keluar dari jaringan cabang.
- frame():  satu gambar JPEG (grid, diperbarui tiap beberapa detik), disimpan sebentar supaya banyak penonton = satu ambil;
- mjpeg():  video MJPEG terus-menerus (layar penuh), dibatasi jumlahnya (CCTV_MAKS_LIVE) supaya thread server tidak habis.
Akun API gateway (opsional): CCTV_GATEWAY_USER / CCTV_GATEWAY_PASSWORD di .env."""
import os
import threading
import time
from urllib.parse import quote

import requests

TIMEOUT = (3, 8)            # detik: sambung, baca
SIMPAN_FRAME = 1.5          # detik: frame yang sama dipakai bersama penonton lain
_frame = {}                 # (url, stream) -> (waktu, bytes)
_kunci = threading.Lock()
_slot_live = threading.BoundedSemaphore(int(os.getenv("CCTV_MAKS_LIVE", "4")))


class GatewayGagal(Exception):
    """Gateway / kamera tidak menjawab; pesannya aman ditampilkan."""


def _auth():
    user = os.getenv("CCTV_GATEWAY_USER", "").strip()
    return (user, os.getenv("CCTV_GATEWAY_PASSWORD", "")) if user else None


def _alamat(url, jalur, stream):
    return f"{url.rstrip('/')}{jalur}?src={quote(stream, safe='')}"


def frame(url, stream):
    """JPEG terbaru stream itu (bytes)."""
    kunci = (url, stream)
    with _kunci:
        ada = _frame.get(kunci)
        if ada and time.monotonic() - ada[0] < SIMPAN_FRAME:
            return ada[1]
    try:
        r = requests.get(_alamat(url, "/api/frame.jpeg", stream), auth=_auth(), timeout=TIMEOUT)
    except requests.RequestException as e:
        raise GatewayGagal(f"Gateway video tidak terjangkau ({url})") from e
    if r.status_code != 200 or not r.content.startswith(b"\xff\xd8"):
        raise GatewayGagal(f"Kamera tidak mengirim gambar (stream {stream}, kode {r.status_code})")
    with _kunci:
        _frame[kunci] = (time.monotonic(), r.content)
        if len(_frame) > 200:
            for k in sorted(_frame, key=lambda k: _frame[k][0])[:100]:
                del _frame[k]
    return r.content


def ambil_slot_live():
    """Satu slot video layar penuh (dilepas dengan lepas_slot_live); penuh = GatewayGagal."""
    if not _slot_live.acquire(timeout=2):
        raise GatewayGagal("Terlalu banyak video layar penuh yang sedang dibuka. Tutup salah satu, lalu coba lagi.")


def lepas_slot_live():
    _slot_live.release()


def mjpeg(url, stream, maks_detik=600):
    """(content-type, generator potongan bytes) video MJPEG. Berhenti sendiri setelah maks_detik (penonton diminta buka ulang)."""
    try:
        r = requests.get(_alamat(url, "/api/stream.mjpeg", stream), auth=_auth(), timeout=TIMEOUT, stream=True)
    except requests.RequestException as e:
        raise GatewayGagal(f"Gateway video tidak terjangkau ({url})") from e
    if r.status_code != 200:
        r.close()
        raise GatewayGagal(f"Kamera tidak mengirim video (stream {stream}, kode {r.status_code})")

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


def cek(url):
    """Daftar nama stream di gateway (tes koneksi admin)."""
    try:
        r = requests.get(url.rstrip("/") + "/api/streams", auth=_auth(), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise GatewayGagal(f"Gateway video tidak terjangkau / bukan go2rtc ({url})") from e
    return sorted(data.keys()) if isinstance(data, dict) else []
