"""Pengaturan dari file .env dan daftar_kamera.json."""
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote
from anpr.pengaturan_db import kamera_dari_db
from dotenv import load_dotenv

FOLDER_PROYEK = Path(__file__).resolve().parent.parent
FILE_ENV = FOLDER_PROYEK.parent / ".env"   # backend\.env, sama dengan CPOS

def _teks(nama, bawaan=""):
    return (os.getenv(nama) or bawaan).strip()


def _angka(nama, bawaan):
    nilai = _teks(nama)
    return type(bawaan)(nilai) if nilai else bawaan


@dataclass
class Konfigurasi:
    nama_kamera: str
    kamera_ip: str
    kamera_port: int
    kamera_user: str
    kamera_pass: str
    kamera_stream: int        # 1 = main stream (resolusi penuh), 2 = sub stream
    rtsp_url: str             # bila diisi, menggantikan ip/user/pass/stream
    detektor_model: str
    ocr_model: str
    min_conf_deteksi: float
    min_conf_ocr: float
    margin_crop: float
    min_frame_sama: int
    jendela_detik: float
    jeda_ulang_detik: float
    simpan_semua_bacaan: bool
    folder_hasil: Path
    lebar_tampilan: int

    def daftar_url_rtsp(self):
        """URL RTSP yang dicoba berurutan."""
        if self.rtsp_url:
            return [self.rtsp_url]
        akun = f"{quote(self.kamera_user, safe='')}:{quote(self.kamera_pass, safe='')}@" if self.kamera_user else ""
        dasar = f"rtsp://{akun}{self.kamera_ip}:{self.kamera_port}"
        return [f"{dasar}/media/video{self.kamera_stream}",
                f"{dasar}/unicast/c1/s{self.kamera_stream - 1}/live"]


def sembunyikan_sandi(url):
    """URL untuk ditampilkan di layar / log tanpa password."""
    if "@" not in url or "://" not in url:
        return url
    awal, sisa = url.split("://", 1)
    akun, host = sisa.rsplit("@", 1)
    user = akun.split(":", 1)[0]
    return f"{awal}://{user}:***@{host}"


def muat_konfigurasi():
    load_dotenv(FILE_ENV)
    folder_hasil = Path(_teks("FOLDER_HASIL", "hasil"))
    if not folder_hasil.is_absolute():
        folder_hasil = FOLDER_PROYEK / folder_hasil
    return Konfigurasi(
        nama_kamera=_teks("NAMA_KAMERA", "DEPAN").upper(),
        kamera_ip=_teks("KAMERA_IP"),
        kamera_port=_angka("KAMERA_PORT", 554),
        kamera_user=_teks("KAMERA_USER", "admin"),
        kamera_pass=os.getenv("KAMERA_PASS") or "",
        kamera_stream=_angka("KAMERA_STREAM", 1),
        rtsp_url=_teks("RTSP_URL"),
        detektor_model=_teks("DETEKTOR_MODEL", "yolo-v9-t-384-license-plate-end2end"),
        ocr_model=_teks("OCR_MODEL", "cct-s-v2-global-model"),
        min_conf_deteksi=_angka("MIN_CONF_DETEKSI", 0.4),
        min_conf_ocr=_angka("MIN_CONF_OCR", 0.7),
        margin_crop=_angka("MARGIN_CROP", 0.05),
        min_frame_sama=_angka("MIN_FRAME_SAMA", 3),
        jendela_detik=_angka("JENDELA_DETIK", 5.0),
        jeda_ulang_detik=_angka("JEDA_ULANG_DETIK", 60.0),
        simpan_semua_bacaan=_teks("SIMPAN_SEMUA_BACAAN", "1") == "1",
        folder_hasil=folder_hasil,
        lebar_tampilan=_angka("LEBAR_TAMPILAN", 1280),
    )


def muat_semua_kamera():
    """Ambil daftar kamera aktif dari Admin > Perangkat.
    Mengembalikan None jika database gagal dibaca.
    """
    dasar = muat_konfigurasi()
    kamera_db = kamera_dari_db()

    if kamera_db is None:
        return None

    hasil = []
    for nama, url in kamera_db:
        if not url:
            continue

        hasil.append(replace(
            dasar,
            nama_kamera=nama.upper(),
            kamera_ip="",
            kamera_user="",
            kamera_pass="",
            rtsp_url=url,
        ))

    return hasil
