import os
import pyodbc
import hashlib
import time
from datetime import datetime, timedelta, date
import extensions  # noqa: F401  (memuat backend\.env)
from config import get_connection_string
from utils.cache import cache_ttl


# Connection pooling ODBC: koneksi yang di-close() dikembalikan ke pool, bukan diputus.
# Harus di-set sebelum koneksi pertama dibuat.
pyodbc.pooling = True

QUERY_TIMEOUT_DETIK = int(os.getenv("DB_QUERY_TIMEOUT", "15"))


def get_connection():
    """Koneksi baru (dari pool ODBC). Waktu buka koneksi dicatat per request untuk log LAMBAT."""
    mulai = time.perf_counter()
    conn = pyodbc.connect(get_connection_string(), timeout=10)
    conn.timeout = QUERY_TIMEOUT_DETIK          # query tertahan (lock / server sibuk) -> error, bukan menunggu lama
    try:
        from flask import g, has_request_context
        if has_request_context():
            g.db_koneksi = getattr(g, "db_koneksi", 0) + 1
            g.db_buka_ms = getattr(g, "db_buka_ms", 0) + (time.perf_counter() - mulai) * 1000
            _isi_konteks(conn)
    except ImportError:
        pass
    return conn

def _isi_konteks(conn):
    """Pengguna & IP request ini untuk trigger log perubahan data (migrasi 034). Gagal -> dicatat tanpa pengguna."""
    # Hanya user yang sudah dimuat flask-login (g._login_user): memanggil current_user di sini bisa berulang
    # karena memuat user juga membuka koneksi.
    from flask import g, request
    user = g.get("_login_user")
    id_user = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    if id_user is None:
        return
    try:
        conn.cursor().execute("EXEC sp_set_session_context N'id_user', ?; EXEC sp_set_session_context N'ip', ?",
                              id_user, (request.remote_addr or "")[:45] or None)
    except pyodbc.Error:
        pass

def cek_koneksi_db():
    """Dipakai /health: True bila database bisa dijangkau."""
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1").fetchone()
        return True
    finally:
        conn.close()

# ===== USERS (ERD Ladder Desk: Users + LevelDetails = peran + PasswordManager) =====
_KOLOM_USER = """u.UserID AS id_user, u.UserName AS username, u.Nama AS nama, ld.LevelDetCode AS role,
                 ld.LevelDetName AS nama_level, u.UserLevelID AS id_level, lv.IsAdmin AS is_admin, ld.HomeUrl AS halaman_awal,
                 u.SessionVersion AS sesi_versi"""
_DARI_USER = """FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID JOIN Level lv ON lv.LevelID = ld.LevelID"""


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""SELECT TOP 1 {_KOLOM_USER}, pm.UserPasswd AS password,
                              CASE WHEN pm.MustChange = 1 THEN NULL ELSE pm.CreateDate END AS password_changed_at
                       {_DARI_USER} JOIN PasswordManager pm ON pm.UserID = u.UserID
                       WHERE (u.UserName = ? OR u.NoKTP = ?) AND u.Active = 1 AND ld.Active = 1
                       ORDER BY CASE WHEN u.UserName = ? THEN 0 ELSE 1 END""", username, username, username)
    row = cursor.fetchone()
    conn.close()
    return row

@cache_ttl(15)
def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    # User yang dinonaktifkan langsung kehilangan sesi (flask-login memanggil ini setiap request)
    cursor.execute(f"SELECT {_KOLOM_USER} {_DARI_USER} WHERE u.UserID = ? AND u.Active = 1 AND ld.Active = 1", user_id)
    row = cursor.fetchone()
    conn.close()
    return row

def get_password_hash(user_id):
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT UserPasswd FROM PasswordManager WHERE UserID = ?", user_id).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def ganti_password_sendiri(user_id, password_hash):
    """Password baru oleh user sendiri. Sesi lain user ini dicabut; kembalikan sesi_versi baru untuk sesi sekarang."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        simpan_password(cursor, user_id, password_hash, wajib_ganti=False)
        cursor.execute("""SET NOCOUNT ON; DECLARE @o TABLE (v INT);
                          UPDATE Users SET SessionVersion = SessionVersion + 1, UpdateDate = GETDATE()
                          OUTPUT INSERTED.SessionVersion INTO @o WHERE UserID = ?; SELECT v FROM @o""", user_id)
        versi = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    get_user_by_id.hapus()
    return versi

RIWAYAT_PASSWORD_MAKS = 12


def simpan_password(cursor, user_id, password_hash, wajib_ganti):
    """Isi / ganti password di PasswordManager; hash baru masuk paling depan History (disimpan secukupnya)."""
    import json
    row = cursor.execute("SELECT History FROM PasswordManager WITH (UPDLOCK) WHERE UserID = ?", user_id).fetchone()
    riwayat = [password_hash] + (json.loads(row[0] or "[]") if row else [])
    riwayat = json.dumps(riwayat[:RIWAYAT_PASSWORD_MAKS])
    if row:
        cursor.execute("""UPDATE PasswordManager SET UserPasswd = ?, CreateDate = GETDATE(), MustChange = ?, History = ?
                          WHERE UserID = ?""", password_hash, 1 if wajib_ganti else 0, riwayat, user_id)
    else:
        cursor.execute("INSERT INTO PasswordManager (UserID, UserPasswd, MustChange, History) VALUES (?, ?, ?, ?)",
                       user_id, password_hash, 1 if wajib_ganti else 0, riwayat)

def password_pernah_dipakai(user_id, password):
    """True bila password sama dengan salah satu dari N password terakhir (Pengaturan › PASSWORD_RIWAYAT)."""
    import json
    from werkzeug.security import check_password_hash
    from utils import pengaturan
    n = pengaturan.nilai("PASSWORD_RIWAYAT")
    if not n:
        return False
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT History FROM PasswordManager WHERE UserID = ?", user_id).fetchone()
    finally:
        conn.close()
    return any(check_password_hash(h, password) for h in (json.loads(row[0] or "[]") if row else [])[:n])

def pesan_riwayat_password():
    from utils import pengaturan
    n = pengaturan.nilai("PASSWORD_RIWAYAT")
    return (f"Password baru tidak boleh sama dengan {n} password terakhir." if n and n > 1
            else "Password baru tidak boleh sama dengan password lama.")

def naikkan_sesi_versi(user_id):
    """Cabut semua sesi lain user ini (login di perangkat baru); kembalikan sesi_versi baru."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SET NOCOUNT ON; DECLARE @o TABLE (v INT);
                          UPDATE Users SET SessionVersion = SessionVersion + 1 OUTPUT INSERTED.SessionVersion INTO @o
                          WHERE UserID = ?; SELECT v FROM @o""", user_id)
        versi = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    get_user_by_id.hapus()
    return versi

def catat_login_terakhir(user_id):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE Users SET LastLogin = GETDATE() WHERE UserID = ?", user_id)
        conn.commit()
    finally:
        conn.close()

def user_id_baru(cursor):
    """UserID format Ladder Desk: YYMMDD + urutan 4 digit (mis. 2601010001)."""
    cursor.execute("""SET NOCOUNT ON; DECLARE @p BIGINT = CAST(FORMAT(GETDATE(), 'yyMMdd') AS BIGINT) * 10000;
                      SELECT ISNULL(MAX(UserID), @p) + 1 FROM Users WITH (UPDLOCK, HOLDLOCK)
                      WHERE UserID > @p AND UserID < @p + 10000""")
    return cursor.fetchone()[0]

# ===== SUPPLIER / PRODUK =====

@cache_ttl(300)
def get_semua_supplier():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT s.SupplierID AS id_supplier, s.SupplierName AS nama_supplier,
                             CAST(CASE WHEN EXISTS (SELECT 1 FROM SupplierTypeDetails p WHERE p.SupplierID = s.SupplierID
                                                    AND p.TypeCode = 'CUSTOMER') THEN 1 ELSE 0 END AS BIT) AS is_customer,
                             CAST(CASE WHEN EXISTS (SELECT 1 FROM SupplierTypeDetails p WHERE p.SupplierID = s.SupplierID
                                                    AND p.TypeCode = 'PENGANGKUTAN') THEN 1 ELSE 0 END AS BIT) AS is_angkutan,
                             CAST(CASE WHEN s.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted
                      FROM Supplier s WHERE s.Active = 1 ORDER BY s.SupplierName""")
    rows = cursor.fetchall()
    conn.close()
    return rows

@cache_ttl(300)
def get_semua_produk():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ProductID AS id_produk, ProductName AS nama_produk, Category AS kategori, FlowID AS id_alur FROM Product WHERE Active = 1 ORDER BY ProductName")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ===== KENDARAAN =====

def get_or_create_kendaraan(no_plat, no_stnk=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDVehicle AS id_kendaraan FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
    row = cursor.fetchone()
    if row:
        if no_stnk:
            cursor.execute("UPDATE DetailVehicle SET NoSTNK = ? WHERE IDVehicle = ?", no_stnk, row.id_kendaraan)
            conn.commit()
        conn.close()
        return row.id_kendaraan
    cursor.execute("INSERT INTO DetailVehicle (NoVehicle, NoSTNK) VALUES (?, ?)", no_plat, no_stnk)
    conn.commit()
    cursor.execute("SELECT IDVehicle AS id_kendaraan FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
    kendaraan_id = cursor.fetchone().id_kendaraan
    conn.close()
    return kendaraan_id

def get_kendaraan_by_plat(no_plat):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDVehicle AS id_kendaraan, NoVehicle AS no_plat, NoSTNK AS no_stnk, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted, Active AS is_active FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def _rows_to_dicts(cursor):
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query(sql, *params):
    """Jalankan SELECT / EXEC, kembalikan result set pertama yang berkolom sebagai list dict ([] bila tidak ada)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        while cursor.description is None:
            if not cursor.nextset():
                return []
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def ubah(sql, *params, pesan_kosong=None):
    """Jalankan INSERT / UPDATE / DELETE lalu commit; kembalikan jumlah baris yang kena.
    pesan_kosong: ValueError dengan pesan itu (tanpa commit) bila tidak ada baris yang kena."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        n = cursor.rowcount
        if n == 0 and pesan_kosong:
            raise ValueError(pesan_kosong)
        conn.commit()
        return n
    finally:
        conn.close()

# ----- Truk <-> Supir (tabel kendaraan_driver) -----

def get_supir_kendaraan(id_kendaraan):
    """Supir terdaftar untuk truk ini, supir utama paling atas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.UserID AS id_driver, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
               d.PhotoPath AS foto_path, d.IsUpload AS is_updated, d.IsBlacklisted AS is_blacklisted, kd.IsMain AS is_utama
        FROM VehicleDriver kd
        JOIN UserProfile d ON kd.UserID = d.UserID
        WHERE kd.IDVehicle = ? AND kd.Active = 1 AND d.Active = 1
        ORDER BY kd.IsMain DESC, d.Nama
    """, id_kendaraan)
    data = _rows_to_dicts(cursor)
    conn.close()
    for r in data:
        r["is_utama"], r["is_updated"] = bool(r["is_utama"]), bool(r["is_updated"])
        r["is_blacklisted"] = bool(r["is_blacklisted"])
    return data

def _daftarkan_supir(cursor, id_kendaraan, id_driver, is_utama, user_id):
    """Tambah / aktifkan ulang relasi truk-supir. Kalau is_utama, supir lain di truk ini jadi bukan utama."""
    if is_utama:
        cursor.execute("UPDATE VehicleDriver SET IsMain = 0, UpdateDate = GETDATE() WHERE IDVehicle = ?",
                       id_kendaraan)
    cursor.execute("SELECT VehicleDriverID AS id_kendaraan_driver FROM VehicleDriver WHERE IDVehicle = ? AND UserID = ?",
                   id_kendaraan, id_driver)
    if cursor.fetchone():
        cursor.execute("""UPDATE VehicleDriver SET Active = 1, IsMain = ?, UpdateDate = GETDATE()
                          WHERE IDVehicle = ? AND UserID = ?""", 1 if is_utama else 0, id_kendaraan, id_driver)
    else:
        cursor.execute("""INSERT INTO VehicleDriver (IDVehicle, UserID, IsMain, CreateBy)
                          VALUES (?, ?, ?, ?)""", id_kendaraan, id_driver, 1 if is_utama else 0, user_id)

def tambah_supir_kendaraan(id_kendaraan, id_driver, is_utama, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    _daftarkan_supir(cursor, id_kendaraan, id_driver, is_utama, user_id)
    conn.commit()
    conn.close()

def nonaktifkan_supir_kendaraan(id_kendaraan, id_driver):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""UPDATE VehicleDriver SET Active = 0, IsMain = 0, UpdateDate = GETDATE()
                      WHERE IDVehicle = ? AND UserID = ?""", id_kendaraan, id_driver)
    conn.commit()
    conn.close()

# ----- Truk <-> Supplier (tabel kontrak_kendaraan) -----

def _status_kontrak(k, hari_ini):
    if not k["is_active"]:
        return "NONAKTIF"
    if k["tanggal_mulai"] > hari_ini:
        return "BELUM_MULAI"
    if k["tanggal_selesai"] is not None and k["tanggal_selesai"] < hari_ini:
        return "BERAKHIR"
    return "AKTIF"

def _ke_tanggal(v):
    """Kolom DATE dari pyodbc sudah berupa date; jaga-jaga kalau driver mengembalikan datetime / string."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])

def get_kontrak_kendaraan(id_kendaraan, hanya_aktif=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kk.VehicleContractID AS id_kontrak, kk.ContractNumber AS no_kontrak, kk.SupplierID AS id_supplier, s.SupplierName AS nama_supplier, kk.ProductID AS id_produk, p.ProductName AS nama_produk,
               kk.TransactionType AS jenis_transaksi, kk.StartDate AS tanggal_mulai, kk.EndDate AS tanggal_selesai, kk.Active AS is_active, kk.Description AS keterangan
        FROM VehicleContract kk
        JOIN Supplier s ON kk.SupplierID = s.SupplierID
        LEFT JOIN Product p ON kk.ProductID = p.ProductID
        WHERE kk.IDVehicle = ?
        ORDER BY kk.Active DESC, kk.StartDate DESC
    """, id_kendaraan)
    data = _rows_to_dicts(cursor)
    conn.close()
    hari_ini = date.today()
    for k in data:
        k["tanggal_mulai"], k["tanggal_selesai"] = _ke_tanggal(k["tanggal_mulai"]), _ke_tanggal(k["tanggal_selesai"])
        k["status"] = _status_kontrak(k, hari_ini)
        k["is_active"] = bool(k["is_active"])
        k["tanggal_mulai"] = k["tanggal_mulai"].isoformat()
        k["tanggal_selesai"] = k["tanggal_selesai"].isoformat() if k["tanggal_selesai"] else None
    if hanya_aktif:
        data = [k for k in data if k["status"] == "AKTIF"]
    return data

def _sql_kontrak_berlaku():
    return "Active = 1 AND StartDate <= ? AND (EndDate IS NULL OR EndDate >= ?)"

def cari_kontrak_aktif(id_kendaraan, id_supplier, cursor=None):
    """id_kontrak yang berlaku hari ini untuk pasangan truk + supplier, atau None."""
    tutup = cursor is None
    if tutup:
        conn = get_connection()
        cursor = conn.cursor()
    hari_ini = date.today()
    cursor.execute(f"""SELECT TOP 1 VehicleContractID AS id_kontrak FROM VehicleContract
                       WHERE IDVehicle = ? AND SupplierID = ? AND {_sql_kontrak_berlaku()}
                       ORDER BY StartDate DESC""", id_kendaraan, id_supplier, hari_ini, hari_ini)
    row = cursor.fetchone()
    if tutup:
        conn.close()
    return row.id_kontrak if row else None

def tambah_kontrak(id_kendaraan, id_supplier, id_produk, jenis_transaksi, no_kontrak,
                   tanggal_mulai, tanggal_selesai, keterangan, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO VehicleContract
                      (ContractNumber, IDVehicle, SupplierID, ProductID, TransactionType,
                       StartDate, EndDate, Description, CreateBy)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   no_kontrak, id_kendaraan, id_supplier, id_produk, jenis_transaksi,
                   tanggal_mulai, tanggal_selesai, keterangan, user_id)
    conn.commit()
    conn.close()

def akhiri_kontrak(id_kontrak):
    """Nonaktifkan kontrak. Tanggal selesai diisi hari ini kalau masih kosong / lebih lambat."""
    conn = get_connection()
    cursor = conn.cursor()
    hari_ini = date.today()
    cursor.execute("""UPDATE VehicleContract SET Active = 0,
                      EndDate = CASE WHEN EndDate IS NULL OR EndDate > ? THEN ?
                                             ELSE EndDate END
                      WHERE VehicleContractID = ? AND StartDate <= ?""", hari_ini, hari_ini, id_kontrak, hari_ini)
    if cursor.rowcount == 0:   # kontrak yang belum mulai: cukup dinonaktifkan
        cursor.execute("UPDATE VehicleContract SET Active = 0 WHERE VehicleContractID = ?", id_kontrak)
    conn.commit()
    conn.close()

# ===== DRIVER (tabel personel, migrasi 002) =====
# Supir adalah orang berjenis DRIVER (visitor dengan SIM). Kolom dialias ke nama lama (id_driver, nama_driver)
# supaya kode & JSON tab Security / Timbangan / Sortasi / Lab tidak perlu berubah.

SQL_KOLOM_DRIVER = """d.UserID AS id_driver, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
                      d.LicenseID AS id_jenis_sim, d.LicenseCode AS kode_jenis_sim, d.ExpiredSIM AS sim_berlaku_sampai,
                      d.PersonType AS kategori, d.IsBlacklisted AS is_blacklisted, d.IsUpload AS is_updated, d.PhotoPath AS foto_path"""

def get_all_driver_embeddings():
    """Wajah terdaftar semua orang aktif (bukan hanya DRIVER), supaya wajah security/karyawan tidak terbaca sebagai supir lain.
    Satu wajah per orang: Users.FaceEmbeddingData."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT UserID AS id_personel, Nama AS nama_personel, FaceEmbeddingData AS embedding FROM Users
                      WHERE Active = 1 AND FaceEmbeddingData IS NOT NULL""")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_driver_by_id(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM UserProfile d WHERE d.UserID = ?", driver_id)
    row = cursor.fetchone()
    conn.close()
    return row

def cek_nik_ada(nik, exclude_id=None):
    """NIK unik untuk semua personel, termasuk yang sudah dihapus (is_active = 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT UserID AS id_personel FROM Users WHERE NoKTP = ? AND UserID != ?", nik, exclude_id)
    else:
        cursor.execute("SELECT UserID AS id_personel FROM Users WHERE NoKTP = ?", nik)
    row = cursor.fetchone()
    conn.close()
    return row is not None

def cari_wajah_mirip_driver(embedding_baru, threshold=None, exclude_id=None):
    """Personel aktif paling mirip (dari cache embedding di memori), atau None."""
    from utils.face_cache import cari_terdekat
    if threshold is None:
        from utils import pengaturan          # import di sini: pengaturan juga memakai db_utils
        threshold = pengaturan.nilai("AMBANG_WAJAH")
    id_personel, nama, _ = cari_terdekat(embedding_baru, threshold, exclude_id)
    return (id_personel, nama) if id_personel is not None else None

def insert_driver(nik, nama, no_sim, embedding_binary, foto_path=None, user_id=None, foto_sumber='KAMERA'):
    """Supir baru dari modal Tambah di Form Create Ticket = orang berjenis DRIVER. Kembalikan id_personel."""
    from utils.db_personel import insert_personel
    return insert_personel(nik, nama, no_sim, 'DRIVER', embedding_binary, foto_path, foto_sumber, user_id)

def hitung_hash_driver(nik, nama, no_sim, timestamp, secret_key=None):
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{nik}{nama}{no_sim}{timestamp}{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def update_driver_dengan_audit(driver_id, nik_baru, nama_baru, sim_baru, updated_by, embedding_binary=None, foto_path=None):
    """Ubah identitas supir dari Form Security (modal Update). SIM & wajah lewat personel_sim / personel_wajah."""
    from utils.db_personel import simpan_sim, simpan_wajah
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT NoKTP AS nik, Nama AS nama_personel, LicenseNumber AS no_sim FROM UserProfile WHERE UserID = ?", driver_id)
    lama = cursor.fetchone()

    timestamp = datetime.now()
    hash_baru = hitung_hash_driver(nik_baru, nama_baru, sim_baru, timestamp)
    cursor.execute("UPDATE Users SET NoKTP=?, Nama=?, IsUpload=1, CurrentHash=?, UpdateDate=GETDATE() WHERE UserID=?",
                   nik_baru, nama_baru, hash_baru, driver_id)
    simpan_sim(cursor, driver_id, sim_baru, user_id=updated_by)
    if embedding_binary is not None:
        simpan_wajah(cursor, driver_id, embedding_binary, foto_path, "KAMERA", updated_by)
    from utils import log_aktivitas
    log_aktivitas.catat("PERSONEL", "UPDATE", tabel="Users", id_baris=driver_id, user_id=updated_by, cursor=cursor,
                        lama={"nik": lama.nik, "nama": lama.nama_personel,
                              "no_sim": lama.no_sim},
                        baru={"nik": nik_baru, "nama": nama_baru, "no_sim": sim_baru})
    conn.commit()
    conn.close()
    if embedding_binary is not None:
        from utils.face_cache import invalidate
        invalidate()

def cari_riwayat_driver_by_plat(no_plat):
    """Cari transaksi TERAKHIR untuk plat ini (apapun statusnya) untuk menyarankan supir & foto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP 1 {SQL_KOLOM_DRIVER}, k.IDVehicle AS id_kendaraan, k.NoSTNK AS no_stnk
        FROM WeightBridge t
        JOIN DetailVehicle k ON t.IDVehicle = k.IDVehicle
        JOIN UserProfile d ON t.DriverID = d.UserID
        WHERE k.NoVehicle = ?
        ORDER BY t.TicketDate DESC
    """, no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def cari_driver_by_nik(nik):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM UserProfile d WHERE d.NoKTP = ? AND d.Active = 1", nik)
    row = cursor.fetchone()
    conn.close()
    return row

# ===== TRANSAKSI (INTI) =====

def generate_no_tiket(no_plat):
    plat_bersih = no_plat.replace(" ", "").upper()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"TKT-{plat_bersih}-{timestamp}"

def cari_transaksi_aktif(no_plat=None, no_tiket=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.TicketNumber AS no_tiket, t.WeightTypeCode AS jenis_transaksi, t.DONumber AS no_do, t.StatusCode AS status_alur, t.QRExpiredDate AS qr_expired_at,
               t.TicketDate AS created_at, t.QRReprintCount AS qr_reprint_count, t.SupplierID AS id_supplier, t.ProductID AS id_produk, s.SupplierName AS nama_supplier, p.ProductName AS nama_produk, p.Category AS kategori,
               t.CompAreaID AS id_comp_area, t.FlowID AS id_alur, t.TransportMode AS cara_angkut, t.TransportID AS id_pengangkutan, k.NoVehicle AS no_plat, k.NoSTNK AS no_stnk,
               d.UserID AS id_driver, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
               d.IsUpload AS is_updated, d.IsBlacklisted AS is_blacklisted, d.PhotoPath AS foto_path
        FROM WeightBridge t
        JOIN DetailVehicle k ON t.IDVehicle = k.IDVehicle
        JOIN Supplier s ON t.SupplierID = s.SupplierID
        JOIN Product p ON t.ProductID = p.ProductID
        JOIN UserProfile d ON t.DriverID = d.UserID
        WHERE t.StatusCode NOT IN ('SELESAI', 'REJECTED', 'VOID')
          AND (k.NoVehicle = ? OR t.TicketNumber = ?)
        ORDER BY t.TicketDate DESC
    """, no_plat or '', no_tiket or '')
    row = cursor.fetchone()
    conn.close()
    return row

def cari_transaksi_aktif_by_plat(no_plat):
    return cari_transaksi_aktif(no_plat=no_plat)

def buat_transaksi_full(no_tiket, no_plat, no_stnk, jenis_transaksi, id_supplier, id_produk, id_driver, no_do, security_id,
                        id_pengangkutan=None, id_comp_area=None, id_alur=None, id_do=None, cara_angkut="PENGIRIM"):
    """INSERT sungguhan, dipanggil saat 'Mulai Validasi Awal' diklik (bukan saat Tab di base bar)."""
    kendaraan_id = get_or_create_kendaraan(no_plat, no_stnk)
    qr_expired = datetime.now() + timedelta(hours=24)

    conn = get_connection()
    cursor = conn.cursor()
    id_kontrak = cari_kontrak_aktif(kendaraan_id, id_supplier, cursor)
    cursor.execute(
        """INSERT INTO WeightBridge
           (TicketNumber, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID, DONumber, QRExpiredDate,
            CreateBy, VehicleContractID, TransportID, CompAreaID, FlowID, DeliveryOrderID, TransportMode)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        no_tiket, jenis_transaksi, id_supplier, id_produk, kendaraan_id, id_driver, no_do, qr_expired,
        security_id, id_kontrak, id_pengangkutan, id_comp_area, id_alur, id_do, cara_angkut
    )
    # Supir yang membawa truk ini otomatis tercatat di daftar supir truk.
    # Kalau truk belum punya supir sama sekali, supir ini jadi supir utama.
    cursor.execute("SELECT UserID AS id_driver FROM VehicleDriver WHERE IDVehicle = ? AND UserID = ? AND Active = 1",
                   kendaraan_id, id_driver)
    if not cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM VehicleDriver WHERE IDVehicle = ? AND Active = 1", kendaraan_id)
        _daftarkan_supir(cursor, kendaraan_id, id_driver, cursor.fetchone()[0] == 0, security_id)
    # Alur dinamis: tahap alur disalin ke tiket (Security langsung selesai); status awal mengikuti tahap pertama yang ditunggu
    # (mis. Lab dulu -> Inspeksi). Alur yang hanya Security (Pos Security saja) tetap memakai cara lama (selesai saat keluar).
    from utils import alur
    if id_alur and len(alur.peta_alur().get(id_alur, {}).get("kelompok", [])) > 1:
        alur.buat_tahap_tiket(cursor, no_tiket, id_alur, security_id)
        cursor.execute("UPDATE WeightBridge SET StatusCode = ? WHERE TicketNumber = ?",
                       alur.status_dari_tahap(alur.tahap_tiket(cursor, no_tiket)), no_tiket)
    from utils import log_aktivitas
    log_aktivitas.catat("TIMELINE", "SECURITY_INIT", tabel="WeightBridge", id_baris=no_tiket, user_id=security_id, cursor=cursor)
    conn.commit()
    conn.close()
    return no_tiket

def get_history_driver(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP {int(limit)} k.NoVehicle AS no_plat, d.UserID AS id_driver, d.Nama AS nama_driver, d.NoKTP AS nik, d.LicenseNumber AS no_sim, d.IsBlacklisted AS is_blacklisted
        FROM WeightBridge t
        JOIN DetailVehicle k ON t.IDVehicle = k.IDVehicle
        JOIN UserProfile d ON t.DriverID = d.UserID
        ORDER BY t.TicketDate DESC
    """)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

def get_standar_mutu(id_produk):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SQL_STANDAR, id_produk)
    row = cursor.fetchone()
    conn.close()
    return row

def update_standar_mutu(id_produk, maks_ffa, maks_air, maks_kotoran, user_id=None):
    """Simpan standar mutu produk + catat riwayatnya di log_aktivitas (STANDAR_MUTU)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Product SET StandardFFA = ?, StandardMoist = ?, StandardDirt = ? WHERE ProductID = ?",
                       maks_ffa, maks_air, maks_kotoran, id_produk)
        if cursor.rowcount == 0:
            raise ValueError("Produk tidak ditemukan")
        from utils import log_aktivitas
        log_aktivitas.catat("STANDAR_MUTU", "STANDAR_UBAH", tabel="Product", id_baris=id_produk, user_id=user_id,
                            baru={"maks_ffa": maks_ffa, "maks_air": maks_air, "maks_kotoran": maks_kotoran}, cursor=cursor)
        conn.commit()
    finally:
        conn.close()
    get_standar_mutu.hapus()

def get_history_standar(hari=2):
    """Perubahan standar mutu N hari terakhir (tab Laboratorium)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT CAST(l.LogDate AS DATETIME) AS updated_at, p.ProductName AS nama_produk,
                                 CAST(JSON_VALUE(l.NewValue, '$.maks_ffa') AS FLOAT) AS maks_ffa,
                                 CAST(JSON_VALUE(l.NewValue, '$.maks_air') AS FLOAT) AS maks_air,
                                 CAST(JSON_VALUE(l.NewValue, '$.maks_kotoran') AS FLOAT) AS maks_kotoran, u.Nama AS oleh
                          FROM Log l JOIN Product p ON p.ProductID = TRY_CAST(l.RowID AS INT)
                          LEFT JOIN Users u ON u.UserID = l.CreateBy
                          WHERE l.Category = 'STANDAR_MUTU' AND l.LogDate >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
                          ORDER BY l.LogID DESC""", -(int(hari) - 1))
        return _rows_to_dicts(cursor)
    finally:
        conn.close()

def _filter_area(id_area):
    from utils.area_filter import sql_area
    return sql_area(AREA_TIKET, id_area)


def get_history_umum(tabel, limit=10, id_area=None):
    conn = get_connection()
    cursor = conn.cursor()
    if tabel not in ("lab_hasil", "sortasi"):          # nama tabel disisipkan ke SQL -> hanya daftar tetap
        raise ValueError(f"Tabel tidak diizinkan: {tabel}")
    kolom_status = "sr.Decision" if tabel == 'lab_hasil' else "t.StatusCode"
    tabel = "LabResult" if tabel == "lab_hasil" else "Grading"
    cursor.execute(f"""
        SELECT TOP {int(limit)} k.NoVehicle AS no_plat, p.ProductName AS nama_produk, s.SupplierName AS nama_supplier, {kolom_status} AS status_val
        FROM {tabel} sr
        JOIN WeightBridge t ON sr.TicketNumber = t.TicketNumber
        JOIN DetailVehicle k ON t.IDVehicle = k.IDVehicle
        JOIN Product p ON t.ProductID = p.ProductID
        JOIN Supplier s ON t.SupplierID = s.SupplierID
        WHERE 1 = 1{_filter_area(id_area)[0]}
        ORDER BY t.TicketDate DESC
    """, *_filter_area(id_area)[1])
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data