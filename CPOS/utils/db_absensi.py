"""Jadwal kerja per area (Admin › Organisasi). Absensi karyawan dicatat di FaceActivity (utils/db_aktivitas.py)."""
from datetime import datetime, time, date
from utils.db_utils import get_connection, _rows_to_dicts
from utils.cache import cache_ttl


def _jam(v):
    """Kolom TIME dari pyodbc bisa berupa time atau string 'HH:MM:SS'."""
    if v is None or isinstance(v, time):
        return v
    return time.fromisoformat(str(v)[:8])


def _jadwal_dict(r):
    return {"hari": r["hari"], "nama_hari": r["nama_hari"], "jam_masuk": _jam(r["jam_masuk"]),
            "jam_pulang": _jam(r["jam_pulang"]), "is_libur": bool(r["is_libur"]),
            "toleransi_menit": r["toleransi_menit"] or 0}


@cache_ttl(300)
def get_jadwal_kerja(id_comp_area=None):
    """Jadwal mingguan satu area (migrasi 014). Tanpa area -> area pertama."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT DayNo AS hari, DayName AS nama_hari, TimeIn AS jam_masuk, TimeOut AS jam_pulang, IsHoliday AS is_libur, ToleranceMinutes AS toleransi_menit FROM WorkSchedule
                      WHERE CompAreaID = COALESCE(?, (SELECT MIN(CompAreaID) FROM WorkSchedule))
                      ORDER BY DayNo""", id_comp_area)
    data = [_jadwal_dict(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_jadwal_hari(hari, id_comp_area=None):
    return next((j for j in get_jadwal_kerja(id_comp_area) if j["hari"] == hari), None)
