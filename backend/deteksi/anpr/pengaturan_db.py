"""Kamera deteksi, info gerbang & pengaturan yang diatur Admin di CPOS (Admin › Perangkat › Kamera Deteksi Plat, Admin › Pengaturan Site)."""
from anpr.database import get_koneksi

# sama dengan nilai bawaan di backend/cpos/utils/pengaturan.py (dipakai bila Admin belum pernah mengubah)
BAWAAN = {"PLAT_MIN_CONF_PERSEN": 85, "PLAT_JEDA_ULANG_MENIT": 1, "PLAT_JENDELA_GERBANG_DETIK": 60}


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
        return None


def info_kamera():
    """{nama: {'gate', 'facing', 'area'}} kamera aktif yang punya gerbang; None bila database tidak terjangkau."""
    try:
        conn = get_koneksi(timeout=3)
        try:
            cur = conn.cursor()
            cur.execute("SELECT CamDetName, Gate, Facing, CompAreaID FROM dbo.CameraDeteksi WHERE Active = 1 AND Gate IS NOT NULL")
            return {n: {"gate": g, "facing": f, "area": a} for n, g, f, a in cur.fetchall()}
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"[SQL] gagal baca info gerbang: {e}")
        return None


def baca_pengaturan():
    """{'conf': 0.85, 'jeda_detik': 60.0, 'jendela_detik': 60.0}; None bila database tidak terjangkau (nilai yang berjalan dipertahankan)."""
    try:
        conn = get_koneksi(timeout=3)
        try:
            cur = conn.cursor()
            cur.execute("SELECT SettingKey, SettingValue FROM dbo.Setting WHERE SettingKey IN "
                        "('PLAT_MIN_CONF_PERSEN', 'PLAT_JEDA_ULANG_MENIT', 'PLAT_JENDELA_GERBANG_DETIK')")
            nilai = dict(cur.fetchall())
        finally:
            conn.close()

        def angka(kunci):
            try:
                return int(nilai.get(kunci, BAWAAN[kunci]))
            except ValueError:
                return BAWAAN[kunci]
        return {"conf": angka("PLAT_MIN_CONF_PERSEN") / 100, "jeda_detik": angka("PLAT_JEDA_ULANG_MENIT") * 60.0,
                "jendela_detik": float(angka("PLAT_JENDELA_GERBANG_DETIK"))}
    except Exception as e:  # noqa: BLE001
        print(f"[SQL] gagal baca pengaturan: {e}")
        return None