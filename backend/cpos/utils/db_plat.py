"""Mills Operation › Deteksi Plat (uji coba): membaca riwayat yang ditulis backend deteksi plat (PC lain).
CPOS hanya menampilkan; tidak ada penulisan di sini.
Area: kamera deteksi didaftarkan per area (Admin › Perangkat › Kamera Deteksi Plat); riwayat mengikuti area kameranya (lewat nama kamera)."""
from utils.area_filter import sql_area
from utils.db_utils import query as _query

MENU = "MON_PLAT"

_KAMERA = """FROM dbo.RiwayatDeteksi r
             LEFT JOIN dbo.CameraDeteksi c ON c.CamDetName = r.Kamera"""

# Jenis: dari master (DetailVehicle -> VehicleType) bila plat terdaftar, kalau tidak dari hasil deteksi.
# Pemilik: UserC menyambung ke DetailVehicle; tanpa pemilik tampil "Tidak Diketahui".
_DARI = _KAMERA + """
             LEFT JOIN dbo.CompanyArea ar ON ar.CompAreaID = c.CompAreaID
             LEFT JOIN dbo.KejadianPlat kj ON kj.KejadianID = r.KejadianID
             LEFT JOIN dbo.DetailVehicle v ON v.IDVehicle = r.IDVehicle
             LEFT JOIN dbo.VehicleType t ON t.VehicleTypeID = v.VehicleType
             LEFT JOIN dbo.UserC u ON u.IDVehicle = r.IDVehicle AND u.Active = 1"""


def _cakupan(id_area, area_pilih):
    """Batas area: cakupan data user (Hak Akses) + area yang dipilih di halaman. id_area None = semua area."""
    where, par = [], []
    f_area, a_area = sql_area("c.CompAreaID", id_area)
    if f_area:
        where.append(f_area[5:])                      # buang ' AND '
        par += a_area
    if area_pilih:
        where.append("c.CompAreaID = ?")
        par.append(area_pilih)
    return where, par


def _filter(dari, sampai, id_area, area_pilih, nama_kamera, plat):
    where, par = ["r.Waktu >= ?", "r.Waktu < DATEADD(day, 1, ?)"], [dari, sampai]
    w, p = _cakupan(id_area, area_pilih)
    where += w
    par += p
    if nama_kamera:
        where.append("r.Kamera = ?")
        par.append(nama_kamera)
    if plat:
        where.append("r.PlatNomor LIKE ?")
        par.append(f"%{plat}%")
    return " AND ".join(where), par


def kamera(id_area, area_pilih=None):
    """Nama kamera yang punya riwayat dalam 30 hari terakhir (untuk dropdown filter riwayat)."""
    where, par = _cakupan(id_area, area_pilih)
    where.insert(0, "r.Waktu >= DATEADD(day, -30, GETDATE())")
    return [r["kamera"] for r in _query(f"SELECT DISTINCT r.Kamera AS kamera {_KAMERA} WHERE {' AND '.join(where)} ORDER BY r.Kamera", *par)]


def daftar(dari, sampai, id_area, area_pilih=None, nama_kamera=None, plat=None, batas=500):
    """dari / sampai = datetime (tanggal, inklusif)."""
    where, par = _filter(dari, sampai, id_area, area_pilih, nama_kamera, plat)
    return _query(f"""SELECT TOP {int(batas)} r.DeteksiID AS id, CONVERT(VARCHAR(19), r.Waktu, 120) AS waktu, r.Kamera AS kamera,
                             ISNULL(ar.CompID + ' · ' + ar.AreaName, '-') AS area,
                             kj.Arah AS arah, r.Sisi AS sisi,
                             COALESCE(t.NameType, r.JenisTerdeteksi, N'Tidak diketahui') AS jenis, r.PlatNomor AS plat, r.ConfOCR AS conf,
                             ISNULL(u.Nama, N'Tidak Diketahui') AS pemilik,
                             CAST(CASE WHEN u.UserCID IS NULL THEN 0 ELSE 1 END AS BIT) AS ada_pemilik,
                             CAST(CASE WHEN r.IDVehicle IS NULL THEN 0 ELSE 1 END AS BIT) AS terdaftar,
                             CAST(CASE WHEN r.FotoPath IS NULL THEN 0 ELSE 1 END AS BIT) AS ada_foto
                      {_DARI} WHERE {where} ORDER BY r.Waktu DESC""", *par)


def id_terakhir(dari, sampai, id_area, area_pilih=None, nama_kamera=None, plat=None):
    """ID riwayat terbesar dengan saringan yang sama: murah, dipakai halaman untuk mengecek ada plat baru atau tidak."""
    where, par = _filter(dari, sampai, id_area, area_pilih, nama_kamera, plat)
    return _query(f"SELECT ISNULL(MAX(r.DeteksiID), 0) AS id {_KAMERA} WHERE {where}", *par)[0]["id"]


def path_foto(id_deteksi, potongan_plat, id_area):
    kolom = "PlatPath" if potongan_plat else "FotoPath"          # konstanta, bukan input pengguna
    where, par = _cakupan(id_area, None)
    baris = _query(f"SELECT r.{kolom} AS p {_KAMERA} WHERE r.DeteksiID = ?" + "".join(f" AND {w}" for w in where), id_deteksi, *par)
    return baris[0]["p"] if baris else None