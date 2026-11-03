"""Kamera deteksi & pengaturan yang diatur Admin di CPOS (Admin › Perangkat › Kamera Deteksi Plat, Admin › Pengaturan Site)."""
from anpr.database import get_koneksi

# sama dengan nilai bawaan di CPOS/utils/pengaturan.py (dipakai bila Admin belum pernah mengubah)
BAWAAN = {"PLAT_MIN_CONF_PERSEN": 85, "PLAT_JEDA_ULANG_MENIT": 1}


def kamera_dari_db():
    """[(nama, rtsp_url)] kamera aktif. Gagal baca database -> []."""
    try:
        conn = get_koneksi(timeout=5)
        try:
            cur = conn.cursor()
            cur.execute("SELECT CamDetName, RtspUrl FROM dbo.CameraDeteksi WHERE Active = 1 ORDER BY SortOrder, CamDetName")
            return [(n, u) for n, u in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"[SQL] gagal baca kamera deteksi: {e}")
        return []


def baca_pengaturan():
    """{'conf': 0.85, 'jeda_detik': 60.0}; None bila database tidak terjangkau (nilai yang sedang berjalan dipertahankan)."""
    try:
        conn = get_koneksi(timeout=3)
        try:
            cur = conn.cursor()
            cur.execute("SELECT SettingKey, SettingValue FROM dbo.Setting WHERE SettingKey IN ('PLAT_MIN_CONF_PERSEN', 'PLAT_JEDA_ULANG_MENIT')")
            nilai = dict(cur.fetchall())
        finally:
            conn.close()
        def angka(kunci):
            try:
                return int(nilai.get(kunci, BAWAAN[kunci]))
            except ValueError:
                return BAWAAN[kunci]
        return {"conf": angka("PLAT_MIN_CONF_PERSEN") / 100, "jeda_detik": angka("PLAT_JEDA_ULANG_MENIT") * 60.0}
    except Exception as e:  # noqa: BLE001
        print(f"[SQL] gagal baca pengaturan: {e}")
        return None