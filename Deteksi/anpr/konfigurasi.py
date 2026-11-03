"""Pengaturan dari file .env dan daftar_kamera.json."""
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

FOLDER_PROYEK = Path(__file__).resolve().parent.parent


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
    load_dotenv(FOLDER_PROYEK / ".env")
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
    """Memuat konfigurasi dari .env dan menggabungkannya dengan daftar_kamera.json dari Web UI."""
    konf1 = muat_konfigurasi()
    hasil = []

    # 1. Kamera Pertama dari .env
    if konf1.kamera_ip or konf1.rtsp_url:
        hasil.append(konf1)

    # 2. Kamera Kedua dari .env (Jika ada)
    ip2, url2 = _teks("KAMERA2_IP"), _teks("KAMERA2_RTSP_URL")
    if ip2 or url2:
        port2 = _angka("KAMERA2_PORT", 554)
        user2 = _teks("KAMERA2_USER", "admin")
        pass2 = os.getenv("KAMERA2_PASS") or ""
        stream2 = _angka("KAMERA2_STREAM", 1)
        if not url2:
            akun = f"{quote(user2, safe='')}:{quote(pass2, safe='')}@" if user2 else ""
            url2 = f"rtsp://{akun}{ip2}:{port2}/Streaming/Channels/10{stream2}"
        hasil.append(replace(konf1, nama_kamera=_teks("KAMERA2_NAMA", "BELAKANG").upper(),
                             kamera_ip=ip2, kamera_port=port2, kamera_user=user2, kamera_pass=pass2,
                             kamera_stream=stream2, rtsp_url=url2))

    # 3. Kamera Tambahan dari Web UI (daftar_kamera.json)
    file_kamera = FOLDER_PROYEK / "daftar_kamera.json"
    if os.path.exists(file_kamera):
        with open(file_kamera, "r", encoding="utf-8") as f:
            try:
                kamera_json = json.load(f)
                for k in kamera_json:
                    if not any(x.nama_kamera == k["nama_kamera"].upper() for x in hasil):
                        hasil.append(replace(konf1, nama_kamera=k["nama_kamera"].upper(), rtsp_url=k["rtsp_url"]))
            except json.JSONDecodeError:
                pass

    # 4. Kamera dari database CPOS (Admin › Perangkat › Kamera Deteksi Plat)
    from anpr.pengaturan_db import kamera_dari_db
    for nama, url in kamera_dari_db():
        if not any(x.nama_kamera == nama.upper() for x in hasil):
            hasil.append(replace(konf1, nama_kamera=nama.upper(), rtsp_url=url))

    if not hasil:
        return [konf1]
    return hasil
