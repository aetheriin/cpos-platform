"""Analytics di alamat yang sama dengan CPOS (/analytics), tanpa IIS/Caddy.

Dipasang di serve.py di depan aplikasi Flask, jadi permintaan /analytics tidak melewati CSRF, header keamanan, dan
pemeriksaan sesi CPOS (backend Analytics memeriksa login sendiri ke CPOS lewat cookie sesi):
  /analytics/api/...  diteruskan ke backend Analytics (uvicorn, ANALYTICS_BACKEND, bawaan http://127.0.0.1:8001)
  /analytics/...      file hasil build frontend (frontend/analytics/dist); alamat lain -> index.html (rute React)
Karena satu alamat, ANALYTICS_URL di .env cukup dibiarkan kosong (/analytics) dan sama untuk semua PC."""
import logging
import json
import mimetypes
import os
from pathlib import Path

import requests

from extensions import FRONTEND

AWALAN = "/analytics"
BACKEND = os.getenv("ANALYTICS_BACKEND", "http://127.0.0.1:8001").rstrip("/")
DIST = Path(os.getenv("ANALYTICS_DIST") or Path(FRONTEND) / "analytics" / "dist")
WAKTU_TUNGGU = 600   # detik; ekspor Excel besar bisa lama

# header hop-by-hop tidak boleh diteruskan proxy
_LEWATI = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
           "upgrade", "content-length", "content-encoding", "host"}
_sesi = requests.Session()
log = logging.getLogger("weighbridge")
# Pesan untuk pengguna; penyebab teknisnya (backend mati, frontend belum dibangun) dicatat di log untuk IT
PESAN_TIDAK_BISA = "Laporan sedang tidak bisa dibuka. Coba lagi beberapa saat. Bila masih sama, hubungi IT."


def pasang(app_cpos):
    """Bungkus aplikasi WSGI CPOS: /analytics dilayani di sini, sisanya ke CPOS."""
    def aplikasi(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == AWALAN:
            start_response("301 Moved Permanently", [("Location", AWALAN + "/")])
            return [b""]
        if not path.startswith(AWALAN + "/"):
            return app_cpos(environ, start_response)
        sisa = path[len(AWALAN):]
        if sisa.startswith("/api/") or sisa == "/api":
            return _teruskan(environ, start_response, sisa)
        return _berkas(start_response, sisa)
    return aplikasi


def _teruskan(environ, start_response, path):
    header = {k[5:].replace("_", "-").title(): v for k, v in environ.items() if k.startswith("HTTP_")}
    for k in ("CONTENT_TYPE", "CONTENT_LENGTH"):
        if environ.get(k):
            header[k.replace("_", "-").title()] = environ[k]
    for k in list(header):
        if k.lower() in _LEWATI:
            header.pop(k)
    header["X-Forwarded-For"] = _ip_browser(environ)
    panjang = int(environ.get("CONTENT_LENGTH") or 0)
    isi = environ["wsgi.input"].read(panjang) if panjang else None
    url = BACKEND + path + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else "")
    try:
        r = _sesi.request(environ["REQUEST_METHOD"], url, headers=header, data=isi, stream=True, allow_redirects=False,
                          timeout=(5, WAKTU_TUNGGU))
    except requests.RequestException as e:
        log.error("Backend Analytics di %s tidak menjawab (%s). Jalankan ulang jalankan.bat di server.", BACKEND, e)
        pesan = json.dumps({"detail": PESAN_TIDAK_BISA}).encode()
        start_response("502 Bad Gateway", [("Content-Type", "application/json"), ("Content-Length", str(len(pesan)))])
        return [pesan]
    start_response(f"{r.status_code} {r.reason}", [(k, v) for k, v in r.raw.headers.items() if k.lower() not in _LEWATI])
    return _alirkan(r)


def _ip_browser(environ):
    """IP PC pengguna. Di belakang Caddy (BEHIND_PROXY=1) alamat langsungnya 127.0.0.1, jadi dipakai entri terakhir X-Forwarded-For
    yang ditulis Caddy (sama dengan ProxyFix x_for=1 di app.py). Selain itu header kiriman browser diabaikan."""
    ip = environ.get("REMOTE_ADDR", "")
    if os.getenv("BEHIND_PROXY", "0") == "1" and ip in ("127.0.0.1", "::1"):
        terusan = [x.strip() for x in environ.get("HTTP_X_FORWARDED_FOR", "").split(",") if x.strip()]
        return terusan[-1] if terusan else ip
    return ip


def _alirkan(r):
    try:
        yield from r.raw.stream(64 * 1024, decode_content=True)
    finally:
        r.close()


def _berkas(start_response, sisa):
    berkas = (DIST / sisa.lstrip("/")).resolve()
    if not berkas.is_relative_to(DIST.resolve()) or not berkas.is_file():
        berkas = DIST / "index.html"           # rute React (/analytics/laporan/...) atau berkas tidak ada
    if not berkas.is_file():
        log.error("Frontend Analytics belum dibangun (%s tidak ada). Jalankan bangun-frontend.bat sekali.", DIST / "index.html")
        pesan = PESAN_TIDAK_BISA.encode()
        start_response("503 Service Unavailable", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(pesan)))])
        return [pesan]
    jenis = mimetypes.guess_type(berkas.name)[0] or "application/octet-stream"
    # berkas di assets/ bernama hash -> boleh disimpan lama; index.html selalu diperiksa ulang supaya build baru langsung terpakai
    simpan = "public, max-age=31536000, immutable" if "assets" in berkas.parts else "no-cache"
    data = berkas.read_bytes()
    start_response("200 OK", [("Content-Type", jenis), ("Content-Length", str(len(data))), ("Cache-Control", simpan),
                              ("X-Frame-Options", "SAMEORIGIN"), ("X-Content-Type-Options", "nosniff")])
    return [data]
