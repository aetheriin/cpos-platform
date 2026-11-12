"""Data orang (Visitor & Staff Logs › Data Orang, Data Master › Driver): karyawan, driver, tamu.
Jenis orang dibaca dari relasi (utils/jenis_orang.py): karyawan = punya jabatan (peran + departemen + area),
driver / tamu = punya profil visitor (Guest), driver = punya SIM aktif. Satu wajah terdaftar per orang (Users)."""
from datetime import datetime

from utils.db_utils import get_connection, _rows_to_dicts, hitung_hash_driver, user_id_baru
from utils import jenis_orang
from utils.face_cache import invalidate as reset_cache_wajah
from utils import log_aktivitas

KOLOM_PERSONEL = """p.UserID AS id_personel, p.NoKTP AS nik, p.Nama AS nama_personel, p.LicenseNumber AS no_sim, p.PersonType AS kategori,
                    p.LicenseID AS id_jenis_sim, p.LicenseCode AS kode_jenis_sim, p.ExpiredSIM AS sim_berlaku_sampai,
                    p.IsBlacklisted AS is_blacklisted, p.BlacklistID AS id_blacklist, p.PhotoPath AS foto_path, p.IsUpload AS is_updated, p.Active AS is_active, p.UpdateDate AS updated_at,
                    p.CompanyFrom AS asal_perusahaan, p.VisitorNeeds AS keperluan, p.UserName AS akun, p.CompAreaID AS id_comp_area,
                    ld.DeptID AS id_department, ld.LevelID AS id_jabatan, ld.LevelDetName AS peran, ar.CompID + ' · ' + ar.AreaName AS area"""
FROM_PERSONEL = """FROM UserProfile p LEFT JOIN LevelDetails ld ON ld.LevelDetID = p.UserLevelID
                   LEFT JOIN CompanyArea ar ON ar.CompAreaID = p.CompAreaID"""


def _normalisasi(r):
    for k in ("is_blacklisted", "is_updated", "is_active"):
        if k in r:
            r[k] = bool(r[k])
    if isinstance(r.get("updated_at"), datetime):
        r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M")
    if r.get("sim_berlaku_sampai") is not None:
        r["sim_berlaku_sampai"] = r["sim_berlaku_sampai"].isoformat()
    return r


def get_daftar_personel(kategori=None, cari=None, hanya_blacklist=False, batas=200):
    sql = f"SELECT TOP (?) {KOLOM_PERSONEL} {FROM_PERSONEL} WHERE p.Active = 1"
    params = [batas]
    if kategori:
        sql += " AND p.PersonType = ?"
        params.append(kategori)
    if hanya_blacklist:
        sql += " AND p.IsBlacklisted = 1"
    if cari:
        sql += " AND (p.NoKTP LIKE ? OR p.Nama LIKE ? OR CAST(p.UserID AS VARCHAR) = ?)"
        pola = f"%{cari}%"
        params += [pola, pola, cari.lstrip("0") or "0"]
    sql += " ORDER BY p.UserID"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_normalisasi(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_personel(id_personel):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {KOLOM_PERSONEL} {FROM_PERSONEL} WHERE p.UserID = ?", id_personel)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _normalisasi(data[0]) if data else None


def _catat_audit(cursor, id_personel, aksi, lama, baru, user_id):
    """lama / baru: dict {nik, nama, no_sim} (lama None untuk TAMBAH). Dicatat di log_aktivitas."""
    log_aktivitas.catat("PERSONEL", aksi, tabel="Users", id_baris=id_personel, lama=lama, baru=baru,
                        user_id=user_id, cursor=cursor)


# ===== SIM & WAJAH (dipakai juga oleh driver dari Form Security, utils/db_utils.py) =====
def sim_dipakai(no_sim, exclude_id=None):
    """No. SIM aktif milik personel lain."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("""SELECT TOP 1 UserID AS id_personel FROM LicenseDetail
                                       WHERE LicenseNumber = ? AND Active = 1 AND UserID <> ?""",
                                    no_sim, exclude_id or 0).fetchone()
        return row is not None
    finally:
        conn.close()


def simpan_sim(cursor, id_personel, no_sim, id_jenis_sim=None, berlaku_sampai=None, user_id=None):
    """SIM aktif personel. Kosong -> SIM aktif dinonaktifkan. Nomor sama -> jenis & masa berlaku diperbarui bila diisi.
    Nomor berbeda -> SIM lama nonaktif (riwayat tetap), SIM baru ditambah. Jenis kosong = BELUM_DIISI (data cepat dari pos)."""
    cursor.execute("SELECT DetailLicenseID AS id_sim, LicenseNumber AS no_sim FROM LicenseDetail WHERE UserID = ? AND Active = 1", id_personel)
    aktif = cursor.fetchall()
    sama = next((x for x in aktif if no_sim and x.no_sim == no_sim), None)
    for x in aktif:
        if x is not sama:
            cursor.execute("UPDATE LicenseDetail SET Active = 0 WHERE DetailLicenseID = ?", x.id_sim)
    if not no_sim:
        return
    if sama:
        if id_jenis_sim:
            cursor.execute("UPDATE LicenseDetail SET SIMType = ?, ExpiredSIM = ? WHERE DetailLicenseID = ?",
                           id_jenis_sim, berlaku_sampai, sama.id_sim)
        return
    cursor.execute("""INSERT INTO LicenseDetail (UserID, SIMType, LicenseNumber, ExpiredSIM, CreateBy)
                      VALUES (?, COALESCE(?, (SELECT LicenseID FROM License WHERE LicenseCode = 'BELUM_DIISI')), ?, ?, ?)""",
                   id_personel, id_jenis_sim, no_sim, berlaku_sampai, user_id)


def simpan_wajah(cursor, id_personel, embedding_binary, foto_path, sumber, user_id=None):
    """Wajah terdaftar orang ini (satu per orang) diganti; perubahan dicatat di Log (foto lama tetap ada di disk)."""
    cursor.execute("SELECT UploadPath FROM Users WHERE UserID = ?", id_personel)
    lama = cursor.fetchone()
    cursor.execute("UPDATE Users SET FaceEmbeddingData = ?, UploadPath = ?, UpdateDate = GETDATE() WHERE UserID = ?",
                   embedding_binary, foto_path, id_personel)
    log_aktivitas.catat("PERSONEL", "WAJAH", tabel="Users", id_baris=id_personel, user_id=user_id, cursor=cursor,
                        lama={"foto": lama[0] if lama else None}, baru={"foto": foto_path, "sumber": sumber})


def simpan_profil(cursor, id_personel, kategori, profil):
    """Jenis orang lewat relasinya. profil: KARYAWAN {id_level, id_dept_detail, id_comp_area};
    DRIVER / TAMU {asal_perusahaan, keperluan} (profil visitor di Guest)."""
    profil = profil or {}
    if profil.get("tetap"):
        return
    cursor.execute("SELECT GuestID, NoKTP, UserName FROM Users WHERE UserID = ?", id_personel)
    r = cursor.fetchone()
    if kategori == "KARYAWAN":
        if not profil.get("id_level"):
            raise ValueError("Karyawan: pilih departemen dan jabatan")
        cursor.execute("UPDATE Users SET UserLevelID = ?, UserDeptID = ?, CompAreaID = ? WHERE UserID = ?",
                       profil["id_level"], profil.get("id_dept_detail"), profil.get("id_comp_area"), id_personel)
        return
    if r.UserName:
        raise ValueError("Orang ini punya akun login, jadi tetap Karyawan. Ubah lewat Admin › Kelola Pengguna")
    cursor.execute("UPDATE Users SET UserLevelID = NULL, UserDeptID = NULL WHERE UserID = ?", id_personel)
    asal, perlu = (profil.get("asal_perusahaan") or None), (profil.get("keperluan") or None)
    if r.GuestID:
        cursor.execute("UPDATE Guest SET CompanyFrom = ?, VisitorNeeds = ?, NoKTP = ?, Active = 1 WHERE GuestID = ?",
                       asal, perlu, r.NoKTP, r.GuestID)
    else:
        cursor.execute("""INSERT INTO Guest (CompanyFrom, VisitorNeeds, NoKTP) OUTPUT INSERTED.GuestID VALUES (?, ?, ?)""",
                       asal, perlu, r.NoKTP)
        cursor.execute("UPDATE Users SET GuestID = ? WHERE UserID = ?", cursor.fetchone()[0], id_personel)


def _data_lama(cursor, id_personel):
    cursor.execute("SELECT NoKTP AS nik, Nama AS nama_personel, LicenseNumber AS no_sim FROM UserProfile WHERE UserID = ?", id_personel)
    r = cursor.fetchone()
    return {"nik": r.nik, "nama": r.nama_personel, "no_sim": r.no_sim}


def insert_personel(nik, nama, no_sim, kategori, embedding_binary, foto_path, foto_sumber, user_id,
                    id_jenis_sim=None, sim_berlaku=None, profil=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        id_personel = user_id_baru(cursor)
        cursor.execute("""INSERT INTO Users (UserID, NoKTP, Nama, CurrentHash) VALUES (?, ?, ?, ?)""",
                       id_personel, nik, nama, hitung_hash_driver(nik, nama, no_sim, datetime.now()))
        simpan_profil(cursor, id_personel, kategori, profil)
        simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
        if embedding_binary is not None:
            simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
        if user_id:
            _catat_audit(cursor, id_personel, "TAMBAH", None,
                         {"nik": nik, "nama": nama, "no_sim": no_sim or None}, user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    reset_cache_wajah()
    return id_personel


def update_personel(id_personel, nik, nama, no_sim, kategori, user_id,
                    embedding_binary=None, foto_path=None, foto_sumber=None, id_jenis_sim=None, sim_berlaku=None, profil=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        lama = _data_lama(cursor, id_personel)
        baru = {"nik": nik, "nama": nama, "no_sim": no_sim or None}
        hash_baru = hitung_hash_driver(nik, nama, no_sim, datetime.now())
        cursor.execute("""UPDATE Users SET NoKTP = ?, Nama = ?, IsUpload = 1, CurrentHash = ?, UpdateDate = GETDATE()
                          WHERE UserID = ?""", nik, nama, hash_baru, id_personel)
        simpan_profil(cursor, id_personel, kategori, profil)
        simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
        if embedding_binary is not None:
            simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
        _catat_audit(cursor, id_personel, "UPDATE", lama, baru, user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if embedding_binary is not None:
        reset_cache_wajah()


def akun_personel(id_personel):
    """username akun aktif milik personel ini, atau None."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT UserName FROM Users WHERE UserID = ? AND Active = 1", id_personel).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def hapus_personel(id_personel, user_id):
    """Soft delete: wajah tidak dikenali lagi & dilepas dari truk; riwayat tiket/absensi tetap."""
    conn = get_connection()
    cursor = conn.cursor()
    data = _data_lama(cursor, id_personel)
    cursor.execute("UPDATE Users SET Active = 0, UpdateDate = GETDATE() WHERE UserID = ?", id_personel)
    cursor.execute("""UPDATE VehicleDriver SET Active = 0, IsMain = 0, UpdateDate = GETDATE()
                      WHERE UserID = ?""", id_personel)
    _catat_audit(cursor, id_personel, "HAPUS", data, data, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()


def get_riwayat_perubahan_personel(hari=7, batas=300):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP (?) l.LogID AS id_log, p.UserID AS id_personel, l.LogActionType AS aksi,
               JSON_VALUE(l.OldValue, '$.nik') AS nik_lama, JSON_VALUE(l.NewValue, '$.nik') AS nik_baru,
               JSON_VALUE(l.OldValue, '$.nama') AS nama_lama, JSON_VALUE(l.NewValue, '$.nama') AS nama_baru,
               JSON_VALUE(l.OldValue, '$.no_sim') AS no_sim_lama, JSON_VALUE(l.NewValue, '$.no_sim') AS no_sim_baru,
               CAST(l.LogDate AS DATETIME) AS updated_at, u.Nama AS oleh, lv.LevelDetCode AS role_oleh,
               p.Nama AS nama_personel
        FROM Log l
        JOIN Users p ON p.UserID = TRY_CAST(l.RowID AS BIGINT)
        LEFT JOIN Users u ON l.CreateBy = u.UserID
        LEFT JOIN LevelDetails lv ON lv.LevelDetID = u.UserLevelID
        WHERE l.Category = 'PERSONEL' AND l.LogDate >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
        ORDER BY l.LogID DESC
    """, batas, -(hari - 1))
    data = _rows_to_dicts(cursor)
    conn.close()
    return data


# ===== JENIS ORANG & JENIS SIM =====
def daftar_kategori(semua=False):  # noqa: ARG001 - jenis orang tetap (utils/jenis_orang.py)
    """{kode: {kode, nama, wajib_sim, boleh_akun, prefix_kode, is_active}} untuk pilihan Jenis di form."""
    return {k: {**v, "is_active": True} for k, v in jenis_orang.JENIS.items()}


def daftar_jenis_sim():
    """Pilihan jenis SIM di form (tanpa penanda BELUM_DIISI)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT LicenseID AS id_jenis_sim, LicenseCode AS kode, LicenseType AS nama FROM License WHERE Active = 1 ORDER BY LicenseID")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()
