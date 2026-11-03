from utils.db_utils import get_connection, _rows_to_dicts

MENU = "MON_PLAT"

# Pemilik & master kendaraan dicocokkan saat tampil (bukan saat simpan): pemilik baru di UserC langsung berlaku untuk riwayat lama.
_DARI = """FROM dbo.RiwayatDeteksi r
           LEFT JOIN dbo.VehicleType t ON t.VehicleTypeID = r.VehicleTypeID
           LEFT JOIN dbo.UserC u ON u.PlatNomor = r.PlatNomor AND u.Active = 1
           LEFT JOIN dbo.DetailVehicle v ON v.NoVehicle = r.PlatNomor"""


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def kamera():
    return [r["kamera"] for r in _query("SELECT DISTINCT Kamera AS kamera FROM dbo.RiwayatDeteksi ORDER BY Kamera")]


def daftar(dari, sampai, nama_kamera=None, plat=None, batas=500):
    """dari / sampai = datetime (tanggal, inklusif)."""
    where, par = ["r.Waktu >= ?", "r.Waktu < DATEADD(day, 1, ?)"], [dari, sampai]
    if nama_kamera:
        where.append("r.Kamera = ?")
        par.append(nama_kamera)
    if plat:
        where.append("r.PlatNomor LIKE ?")
        par.append(f"%{plat}%")
    return _query(f"""SELECT TOP {int(batas)} r.DeteksiID AS id, CONVERT(VARCHAR(19), r.Waktu, 120) AS waktu, r.Kamera AS kamera,
                             ISNULL(t.NameType, N'Tidak diketahui') AS jenis, r.PlatNomor AS plat, r.ConfOCR AS conf,
                             ISNULL(u.Nama, N'Tidak Diketahui') AS pemilik,
                             CAST(CASE WHEN u.UserCID IS NULL THEN 0 ELSE 1 END AS BIT) AS ada_pemilik,
                             CAST(CASE WHEN v.IDVehicle IS NULL THEN 0 ELSE 1 END AS BIT) AS terdaftar,
                             CAST(CASE WHEN r.FotoPath IS NULL THEN 0 ELSE 1 END AS BIT) AS ada_foto
                      {_DARI} WHERE {' AND '.join(where)} ORDER BY r.Waktu DESC""", *par)


def path_foto(id_deteksi, potongan_plat=False):
    kolom = "PlatPath" if potongan_plat else "FotoPath"          # konstanta, bukan input pengguna
    baris = _query(f"SELECT {kolom} AS p FROM dbo.RiwayatDeteksi WHERE DeteksiID = ?", id_deteksi)
    return baris[0]["p"] if baris else None