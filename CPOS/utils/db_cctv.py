"""Monitoring CCTV (tahap 1): gateway video per area & kamera. Video diambil lewat gateway (go2rtc) di LAN cabang;
CPOS hanya menyimpan nama stream-nya (alamat RTSP & password kamera ada di konfigurasi gateway)."""
from utils.area_filter import sql_area
from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

TITIK = {"POS_MASUK": "Pos Security · Masuk", "POS_KELUAR": "Pos Security · Keluar", "JEMBATAN": "Jembatan Timbang",
         "SORTASI": "Sortasi / Loading Ramp", "UMUM": "Area Umum"}
PERAN = {"DEPAN": "Depan", "ATAS": "Atas", "PLAT": "Plat", "WAJAH": "Wajah", "UMUM": "Umum"}
AI = {"NONE": "Tanpa AI", "KAMERA": "AI bawaan kamera", "SERVER": "Server AI cabang"}


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        n = cursor.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ===== GATEWAY =====
def daftar_gateway():
    return _query("""SELECT g.GatewayID AS id_gateway, g.GatewayName AS nama, g.BaseUrl AS url, g.CompAreaID AS id_comp_area,
                            a.CompID + ' · ' + a.AreaName AS area, g.LastSeen AS terakhir, g.Active AS is_active,
                            (SELECT COUNT(*) FROM Camera c WHERE c.GatewayID = g.GatewayID AND c.Active = 1) AS jumlah_kamera
                     FROM CameraGateway g JOIN CompanyArea a ON a.CompAreaID = g.CompAreaID
                     ORDER BY g.Active DESC, a.CompID, g.GatewayName""")


def simpan_gateway(id_gateway, nama, url, id_area, aktif=True):
    if id_gateway:
        if not _ubah("UPDATE CameraGateway SET GatewayName = ?, BaseUrl = ?, CompAreaID = ?, Active = ? WHERE GatewayID = ?",
                     nama, url, id_area, 1 if aktif else 0, id_gateway):
            raise ValueError("Gateway tidak ditemukan")
    else:
        _ubah("INSERT INTO CameraGateway (GatewayName, BaseUrl, CompAreaID) VALUES (?, ?, ?)", nama, url, id_area)
    kamera.hapus()


# ===== KAMERA =====
_KOLOM = """c.CameraID AS id_kamera, c.CameraCode AS kode, c.CameraName AS nama, c.CompAreaID AS id_comp_area,
            a.CompID + ' · ' + a.AreaName AS area, c.GatewayID AS id_gateway, g.GatewayName AS gateway, g.BaseUrl AS url_gateway,
            c.Point AS titik, c.ScaleID AS id_jembatan, s.ScaleName AS jembatan, c.Role AS peran, c.Brand AS merk,
            c.MainStream AS stream_utama, c.SubStream AS stream_ringan, c.AIMode AS ai, c.LastSeen AS terakhir,
            c.SortOrder AS urutan, c.Active AS is_active, g.Active AS gateway_aktif"""
_FROM = """FROM Camera c JOIN CompanyArea a ON a.CompAreaID = c.CompAreaID JOIN CameraGateway g ON g.GatewayID = c.GatewayID
           LEFT JOIN Scale s ON s.ScaleID = c.ScaleID"""


@cache_ttl(30)
def kamera():
    """Semua kamera (admin & pemeriksaan akses), urut area lalu urutan."""
    return _query(f"SELECT {_KOLOM} {_FROM} ORDER BY c.Active DESC, a.CompID, a.AreaName, c.SortOrder, c.CameraCode")


def kamera_area(id_area):
    """Kamera aktif dalam cakupan area pengguna (None = semua area)."""
    f_area, a_area = sql_area("c.CompAreaID", id_area)
    return _query(f"SELECT {_KOLOM} {_FROM} WHERE c.Active = 1 AND g.Active = 1{f_area} ORDER BY a.CompID, a.AreaName, c.SortOrder, c.CameraCode",
                  *a_area)


def get_kamera(id_kamera):
    return next((k for k in kamera() if k["id_kamera"] == id_kamera), None)


def simpan_kamera(id_kamera, d):
    kolom = (d["kode"], d["nama"], d["id_comp_area"], d["id_gateway"], d["titik"], d["id_jembatan"], d["peran"], d["merk"],
             d["stream_utama"], d["stream_ringan"], d["ai"], d["urutan"], 1 if d["is_active"] else 0)
    if _query("SELECT 1 AS x FROM Camera WHERE CameraCode = ? AND CameraID <> ?", d["kode"], id_kamera or 0):
        raise ValueError(f"Kode kamera {d['kode']} sudah dipakai")
    if id_kamera:
        if not _ubah("""UPDATE Camera SET CameraCode = ?, CameraName = ?, CompAreaID = ?, GatewayID = ?, Point = ?, ScaleID = ?, Role = ?,
                               Brand = ?, MainStream = ?, SubStream = ?, AIMode = ?, SortOrder = ?, Active = ? WHERE CameraID = ?""",
                     *kolom, id_kamera):
            raise ValueError("Kamera tidak ditemukan")
    else:
        _ubah("""INSERT INTO Camera (CameraCode, CameraName, CompAreaID, GatewayID, Point, ScaleID, Role, Brand, MainStream, SubStream,
                                    AIMode, SortOrder, Active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", *kolom)
    kamera.hapus()


def tandai_terlihat(id_kamera, id_gateway):
    """Kamera & gateway menjawab: catat waktu terakhir terhubung (untuk status online)."""
    _ubah("UPDATE Camera SET LastSeen = GETDATE() WHERE CameraID = ?; UPDATE CameraGateway SET LastSeen = GETDATE() WHERE GatewayID = ?",
          id_kamera, id_gateway)
