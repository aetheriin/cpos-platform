import logging
import secrets
import threading
import time
from datetime import datetime

from utils.db_utils import get_connection, _rows_to_dicts

log = logging.getLogger("weighbridge")
JEDA_TULIS_DETIK = 60

_lock = threading.Lock()
_terakhir_tulis = {}


def sid_baru():
    return secrets.token_hex(12)


def _jalankan(sql, *params, ambil=False):
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, *params)
            hasil = _rows_to_dicts(cursor) if ambil else cursor.rowcount
            conn.commit()
            return hasil
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - sesi tetap jalan walau pencatatan gagal (mis. migrasi 007 belum dijalankan)
        log.exception("Gagal mengakses tabel UserSession")
        return [] if ambil else 0


def catat(sid, user, ip, agen, login=None, aktif=True):
    """Ditulis saat pertama kali sesi terlihat di proses ini, lalu maks. 1x / menit untuk request aktif.
    Polling (aktif=False) tidak memperbarui waktu aktif."""
    sekarang = time.time()
    with _lock:
        terakhir = _terakhir_tulis.get(sid)
        if terakhir is not None and (not aktif or sekarang - terakhir < JEDA_TULIS_DETIK):
            return
        _terakhir_tulis[sid] = sekarang
    waktu_login = datetime.fromtimestamp(login) if login else datetime.now()
    _jalankan("""MERGE UserSession AS t USING (SELECT ? AS sid) AS s ON t.SessionID = s.sid
                 WHEN MATCHED THEN UPDATE SET LastActive = GETDATE()
                 WHEN NOT MATCHED THEN INSERT (SessionID, UserID, IPAddress, UserAgent, LoginDate, LastActive)
                                       VALUES (?, ?, ?, ?, ?, GETDATE());""",
              sid, sid, user.id, ip, (agen or "")[:200], waktu_login)


def ip_klien(req):
    """IP pemakai. Backend Analytics di server yang sama memanggil dari 127.0.0.1 dan membawa IP browser di X-Analytics-Ip.
    Bukan X-Forwarded-For, karena waitress membuang header itu."""
    ip = req.remote_addr
    if ip in ("127.0.0.1", "::1"):
        terusan = (req.headers.get("X-Analytics-Ip") or "").split(",")[0].strip()
        return terusan or ip
    return ip


def periksa(sid, user_id, ip, agen):
    """Cookie sesi disimpan di browser, jadi yang menentukan sesi masih berlaku adalah tabel UserSession.
    None = sah. 'BERAKHIR' = sudah logout atau dicabut. 'ASING' = cookie dipakai di perangkat yang bukan tempat login."""
    if not sid:
        return "BERAKHIR"
    rows = _jalankan("SELECT UserID AS id_user, IPAddress AS ip, UserAgent AS agen, EndDate AS akhir FROM UserSession WHERE SessionID = ?",
                     sid, ambil=True)
    if not rows or rows[0]["akhir"] is not None or rows[0]["id_user"] != user_id:
        return "BERAKHIR"
    if (rows[0]["agen"] or "") != (agen or "")[:200]:
        return "ASING"
    return None


def hapus(sid, alasan="LOGOUT"):
    if sid:
        with _lock:
            _terakhir_tulis.pop(sid, None)
        _jalankan("UPDATE UserSession SET EndDate = GETDATE(), EndReason = ? WHERE SessionID = ? AND EndDate IS NULL", alasan, sid)


def hapus_user(user_id, alasan="PAKSA_KELUAR", kecuali_sid=None):
    """Akhiri semua sesi aktif seorang user (paksa keluar, reset password, login di perangkat lain)."""
    return _jalankan("""UPDATE UserSession SET EndDate = GETDATE(), EndReason = ?
                        WHERE UserID = ? AND EndDate IS NULL AND SessionID <> ?""", alasan, user_id, kecuali_sid or "")


def ada_sesi_lain(user_id, batas_idle_detik):
    rows = _jalankan("""SELECT TOP 1 IPAddress AS ip FROM UserSession WHERE UserID = ? AND EndDate IS NULL
                        AND LastActive >= DATEADD(second, ?, GETDATE())""", user_id, -int(batas_idle_detik), ambil=True)
    return rows[0]["ip"] if rows else None


def alasan_berakhir(sid):
    """Kenapa sesi ini berakhir (untuk pesan di halaman login perangkat lama)."""
    if not sid:
        return None
    rows = _jalankan("SELECT EndReason AS alasan FROM UserSession WHERE SessionID = ?", sid, ambil=True)
    return rows[0]["alasan"] if rows else None


def daftar(batas_idle_detik):
    """Sesi yang belum berakhir & belum melewati batas idle, terbaru di atas (dari semua PC / proses server)."""
    rows = _jalankan("""SELECT s.SessionID AS sid, s.UserID AS user_id, u.UserName AS username, u.Nama AS nama,
                               ld.LevelDetCode AS role, s.IPAddress AS ip, s.UserAgent AS agen, s.LoginDate AS login_at,
                               s.LastActive AS terakhir_aktif
                        FROM UserSession s JOIN Users u ON u.UserID = s.UserID
                        JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID
                        WHERE s.EndDate IS NULL AND s.LastActive >= DATEADD(second, ?, GETDATE())
                        ORDER BY s.LastActive DESC""", -int(batas_idle_detik), ambil=True)
    return [{**r, "login": r["login_at"].timestamp(), "terakhir_aktif": r["terakhir_aktif"].timestamp()} for r in rows]
