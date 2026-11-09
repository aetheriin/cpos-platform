"""Admin › Perangkat › Kamera Deteksi Plat: kamera RTSP yang dibaca backend deteksi plat (tabel dbo.CameraDeteksi).
Alamat RTSP memuat password kamera: ke browser hanya dikirim dalam bentuk tersamar."""
import re

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

FACING = {"MASUK": "Menghadap kendaraan masuk", "KELUAR": "Menghadap kendaraan keluar"}
VIEW_POSITION = {
    "DEPAN": "Depan",
    "BELAKANG": "Belakang",
    "KANAN": "Samping kanan",
    "KIRI": "Samping kiri",
    "ATAS": "Atas",
}


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


def tutup_sandi(url):
    return re.sub(r"(rtsp://[^:/@]+:)[^@]*@", r"\1***@", url or "")


@cache_ttl(30)
def daftar():
    baris = _query("""SELECT k.CamDetID AS id_kamera, k.CamDetName AS nama, k.CompAreaID AS id_comp_area,
                             a.CompID + ' · ' + a.AreaName AS area,
                             k.Gate AS gate, k.Facing AS facing, k.ViewPosition AS view_position,
                             k.RtspUrl AS rtsp, k.Note AS catatan, k.SortOrder AS urutan, k.Active AS is_active
                      FROM dbo.CameraDeteksi k JOIN dbo.CompanyArea a ON a.CompAreaID = k.CompAreaID
                      ORDER BY k.Active DESC, a.CompID, a.AreaName, k.SortOrder, k.CamDetName""")
    for b in baris:
        b["rtsp_tersamar"] = tutup_sandi(b.pop("rtsp"))
    return baris


def simpan(id_kamera, d):
    if _query("SELECT 1 AS x FROM dbo.CameraDeteksi WHERE CamDetName = ? AND CamDetID <> ?", d["nama"], id_kamera or 0):
        raise ValueError(f"Nama kamera {d['nama']} sudah dipakai")
    kolom = [
        d["nama"], d["id_comp_area"], d["gate"], d["facing"],
        d["view_position"], d["catatan"], d["urutan"],
        1 if d["is_active"] else 0,
    ]
    if id_kamera:
        sql = """UPDATE dbo.CameraDeteksi
                 SET CamDetName = ?, CompAreaID = ?, Gate = ?, Facing = ?,
                    ViewPosition = ?, Note = ?, SortOrder = ?, Active = ?,
                    UpdateDate = GETDATE()"""
        if d["rtsp"]:                            
            sql += ", RtspUrl = ?"
            kolom.append(d["rtsp"])
        if not _ubah(sql + " WHERE CamDetID = ?", *kolom, id_kamera):
            raise ValueError("Kamera tidak ditemukan")
    else:
        if not d["rtsp"]:
            raise ValueError("Isi alamat RTSP kamera")
        _ubah("""INSERT INTO dbo.CameraDeteksi
                 (CamDetName, CompAreaID, Gate, Facing, ViewPosition,
                 Note, SortOrder, Active, RtspUrl)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
             *kolom, d["rtsp"])
    daftar.hapus()