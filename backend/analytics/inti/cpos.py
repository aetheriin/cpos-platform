"""Masuk lewat CPOS (mode gabungan, CPOS_URL di .env diisi).

Analytics tidak punya login sendiri: tiap permintaan, cookie sesi CPOS milik browser diteruskan ke CPOS_URL/api/analytics/saya.
CPOS menjawab siapa penggunanya dan laporan apa saja yang boleh dibuka (hak Lihat menu /an/<id> di Admin › Hak Akses CPOS).
Jawaban disimpan sebentar (CACHE_DETIK) supaya tidak setiap klik bertanya ke CPOS."""
import json
import threading
import time
import urllib.error
import urllib.request

from inti import konfigurasi

CACHE_DETIK = 15     # logout / paksa keluar / ubah hak berlaku di Analytics paling lambat sekian detik
_cache = {}            # nilai cookie -> (waktu, jawaban CPOS atau None)
_kunci = threading.Lock()


class CposTidakTersedia(RuntimeError):
    pass


def aktif():
    return bool(konfigurasi.CPOS_URL)


def pengguna(nilai_cookie, user_agent=None, ip=None):
    """{id, username, nama, role, company: [..] / None (semua), laporan: [id], sid} atau None kalau sesi CPOS tidak berlaku."""
    if not nilai_cookie:
        return None
    sekarang = time.monotonic()
    kunci = (nilai_cookie, user_agent, ip)      # cookie yang disalin ke perangkat lain tidak boleh memakai hasil cache pemiliknya
    with _kunci:
        ada = _cache.get(kunci)
        if ada and sekarang - ada[0] < CACHE_DETIK:
            return ada[1]
    header = {"Cookie": f"{konfigurasi.CPOS_COOKIE}={nilai_cookie}", "Accept": "application/json"}
    if user_agent:      # supaya Admin › Sesi Aktif di CPOS tetap menampilkan perangkat pengguna, bukan server Analytics
        header["User-Agent"] = user_agent
    if ip:
        header["X-Analytics-Ip"] = ip
    permintaan = urllib.request.Request(konfigurasi.CPOS_URL.rstrip("/") + "/api/analytics/saya", headers=header)
    try:
        with urllib.request.urlopen(permintaan, timeout=10) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            raise CposTidakTersedia(f"CPOS menjawab {e.code}") from e
        data = None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CposTidakTersedia(str(e)) from e
    with _kunci:
        for k in [k for k, (w, _) in _cache.items() if sekarang - w >= CACHE_DETIK]:
            del _cache[k]
        _cache[kunci] = (sekarang, data)
    return data
