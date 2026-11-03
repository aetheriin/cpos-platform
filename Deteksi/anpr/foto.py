"""Simpan foto bukti ke folder sharing server Accurate (FOLDER_FOTO); bila tidak terjangkau, ke FOLDER_FOTO_CADANGAN.
Yang masuk database hanya path relatif: tahun/bulan/tanggal/kamera/HHMMSS_PLAT.jpg"""
import os
from datetime import datetime
from pathlib import Path

import cv2
from dotenv import load_dotenv

from anpr.konfigurasi import FOLDER_PROYEK

load_dotenv(FOLDER_PROYEK / ".env")


def _nama_aman(teks):
    return "".join(c if c.isalnum() else "_" for c in teks)


def simpan_foto(waktu, kamera, plat, frame_bergambar, crop):
    """Return (path_foto_relatif, path_plat_relatif); (None, None) bila semua lokasi gagal."""
    w = datetime.fromtimestamp(waktu)
    rel_folder = Path(f"{w:%Y}") / f"{w:%m}" / f"{w:%d}" / _nama_aman(kamera)
    nama = f"{w:%H%M%S}_{_nama_aman(plat)}"
    ok1, buf_foto = cv2.imencode(".jpg", frame_bergambar, [cv2.IMWRITE_JPEG_QUALITY, 85])
    ok2, buf_plat = cv2.imencode(".jpg", crop)
    if not (ok1 and ok2):
        return None, None
    for akar in (os.getenv("FOLDER_FOTO"), os.getenv("FOLDER_FOTO_CADANGAN")):
        if not akar:
            continue
        try:
            folder = Path(akar) / rel_folder
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{nama}.jpg").write_bytes(buf_foto.tobytes())
            (folder / f"{nama}_plat.jpg").write_bytes(buf_plat.tobytes())
            return (rel_folder / f"{nama}.jpg").as_posix(), (rel_folder / f"{nama}_plat.jpg").as_posix()
        except OSError as e:
            print(f"[FOTO] gagal simpan ke {akar}: {e}")
    return None, None