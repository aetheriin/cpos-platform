"""Visitor & Staff Logs: semua aktivitas scan wajah di satu tabel (FaceActivity).

- karyawan (termasuk security & BHL): absensi MASUK / KELUAR (pulang) dengan status waktu dari jadwal kerja area;
- driver & tamu: kunjungan MASUK (keperluan, orang yang dituju, plat) lalu KELUAR;
- scan yang tidak dikenali / ditolak blacklist juga dicatat. Foto wajah saat scan disimpan di FaceRecog (bukti).
"Masih di dalam" = aktivitas berhasil terakhir orang itu (24 jam terakhir) adalah MASUK."""
import json

from datetime import date, datetime, timedelta
from utils import jenis_orang
from utils.area_filter import sql_area
from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

BERHASIL, TIDAK_DIKENALI, DITOLAK = "WAJAH_BERHASIL", "WAJAH_TIDAK_DIKENALI", "WAJAH_DITOLAK"
STATUS = (BERHASIL, TIDAK_DIKENALI, DITOLAK)


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


@cache_ttl(300)
def id_status():
    """{kode: StatusID} hasil scan wajah (tabel Status)."""
    return {r["StatusCode"]: r["StatusID"] for r in _query(
        "SELECT StatusCode, StatusID FROM Status WHERE StatusCode IN (?, ?, ?)", *STATUS)}


def catat(id_user, jenis, status, id_area, user_id, *, nama_wajah=None, embedding=None, foto_path=None, id_blacklist=None,
          keterangan=None, id_dituju=None, no_plat=None, status_waktu=None, selisih=None, jarak=None, perangkat=None, ip=None,
          waktu=None):
    """Satu aktivitas scan (+ foto wajah saat scan bila ada). Kembalikan ActivityID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        id_face = None
        if foto_path or embedding is not None:
            cursor.execute("""INSERT INTO FaceRecog (FaceName, FaceDet, Blacklist, PhotoPath) OUTPUT INSERTED.FaceID
                              VALUES (?, ?, ?, ?)""", nama_wajah, embedding, id_blacklist, foto_path)
            id_face = cursor.fetchone()[0]
        cursor.execute("""INSERT INTO FaceActivity (UserID, FaceID, ActivityType, StatusID, LogDate, Description, VisitToID, NoVehicle,
                                                    CompAreaID, TimeStatus, DiffMinutes, FaceDistance, Device, IPAddress, CreateBy)
                          OUTPUT INSERTED.ActivityID VALUES (?, ?, ?, ?, COALESCE(?, GETDATE()), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       id_user, id_face, jenis, id_status()[status], waktu, keterangan, id_dituju, no_plat, id_area,
                       status_waktu, selisih, jarak, (perangkat or "Web")[:50], ip, user_id)
        id_baru = cursor.fetchone()[0]
        conn.commit()
        return id_baru
    finally:
        conn.close()

def simpan_bukti_wajah(nama_wajah, embedding, foto_path):
    """Simpan bukti scan wajah tanpa membuat baris FaceActivity baru."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO FaceRecog (FaceName, FaceDet, PhotoPath)
            OUTPUT INSERTED.FaceID
            VALUES (?, ?, ?)
            """,
            nama_wajah,
            embedding,
            foto_path,
        )
        face_id = int(cursor.fetchone()[0])
        conn.commit()
        return face_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bukti_wajah_milik(face_id, nama_wajah):
    """Pastikan bukti scan yang dikirim memang tersimpan untuk nama orang tersebut."""
    baris = _query(
        """
        SELECT FaceID
        FROM FaceRecog
        WHERE FaceID = ? AND FaceName = ?
        """,
        face_id,
        nama_wajah,
    )
    return bool(baris)

def _id_status_kunjungan():
    kode = (
        "KUNJUNGAN_MENUNGGU",
        "KUNJUNGAN_DALAM",
        "KUNJUNGAN_SELESAI",
    )
    baris = _query(
        "SELECT StatusCode, StatusID FROM Status "
        "WHERE StatusCode IN (?, ?, ?)",
        *kode,
    )
    hasil = {r["StatusCode"]: r["StatusID"] for r in baris}

    if len(hasil) != len(kode):
        raise RuntimeError("Status kunjungan belum lengkap di tabel Status.")

    return hasil


def buat_kunjungan_menunggu(
    no_plat,
    id_area,
    *,
    entry_id=None,
    waktu=None,
    perangkat="Kamera",
    ip=None,
):
    """Buat satu catatan awal kunjungan. entry_id boleh kosong untuk input manual."""
    status_id = _id_status_kunjungan()["KUNJUNGAN_MENUNGGU"]

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Mencegah kejadian kamera yang sama membuat catatan ganda.
        if entry_id is not None:
            cursor.execute(
                """
                SELECT TOP 1 ActivityID
                FROM FaceActivity WITH (UPDLOCK, HOLDLOCK)
                WHERE EntryKejadianID = ?
                """,
                entry_id,
            )
            lama = cursor.fetchone()
            if lama:
                conn.commit()
                return int(lama[0])

        cursor.execute(
            """
            INSERT INTO FaceActivity (
                ActivityType, StatusID, LogDate, LogDay,
                NoVehicle, CompAreaID, Device, IPAddress,
                VisitData, EntryKejadianID
            )
            OUTPUT INSERTED.ActivityID
            VALUES (
                'MASUK', ?, COALESCE(?, GETDATE()),
                CONVERT(date, COALESCE(?, GETDATE())),
                ?, ?, ?, ?, N'{}', ?
            )
            """,
            status_id,
            waktu,
            waktu,
            no_plat,
            id_area,
            (perangkat or "Kamera")[:50],
            ip,
            entry_id,
        )

        activity_id = int(cursor.fetchone()[0])
        conn.commit()
        return activity_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lengkapi_kunjungan(
    activity_id,
    id_personel,
    id_face,
    visit_group,
    data_kunjungan,
    *,
    id_dituju=None,
    tujuan=None,
    no_plat=None,
    id_area=None,
    user_id=None,
    perangkat="Web",
    ip=None,
):
    """Lengkapi catatan menunggu dan ubah statusnya menjadi masih di dalam."""
    if visit_group not in ("VISITOR", "EMPLOYEE"):
        raise ValueError("Jenis log kunjungan tidak valid.")

    data_json = json.dumps(data_kunjungan or {}, ensure_ascii=False)
    status = _id_status_kunjungan()
    status_menunggu = status["KUNJUNGAN_MENUNGGU"]
    status_dalam = status["KUNJUNGAN_DALAM"]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE FaceActivity
            SET UserID = ?,
                FaceID = ?,
                VisitGroup = ?,
                VisitData = ?,
                VisitToID = ?,
                Description = ?,
                NoVehicle = COALESCE(NULLIF(?, ''), NoVehicle),
                CompAreaID = COALESCE(?, CompAreaID),
                StatusID = ?,
                Device = ?,
                IPAddress = ?,
                CreateBy = COALESCE(?, CreateBy)
            OUTPUT INSERTED.ActivityID
            WHERE ActivityID = ?
              AND StatusID = ?
              AND DateTimeOut IS NULL
              AND CompAreaID = ?
            """,
            id_personel,
            id_face,
            visit_group,
            data_json,
            id_dituju,
            tujuan,
            no_plat,
            id_area,
            status_dalam,
            (perangkat or "Web")[:50],
            ip,
            user_id,
            activity_id,
            status_menunggu,
            id_area,
        )

        baris = cursor.fetchone()
        if not baris:
            raise ValueError(
                "Catatan kunjungan tidak ditemukan, sudah dilengkapi, atau sudah selesai."
            )

        conn.commit()
        return int(baris[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def tutup_kunjungan(activity_id, *, exit_id=None, waktu_keluar=None):
    """Tutup catatan kunjungan yang sama saat kendaraan/orang keluar."""
    status = _id_status_kunjungan()
    status_dalam = status["KUNJUNGAN_DALAM"]
    status_selesai = status["KUNJUNGAN_SELESAI"]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE FaceActivity
            SET DateTimeOut = COALESCE(?, GETDATE()),
                ExitKejadianID = ?,
                StatusID = ?
            OUTPUT INSERTED.ActivityID
            WHERE ActivityID = ?
              AND StatusID = ?
              AND DateTimeOut IS NULL
            """,
            waktu_keluar,
            exit_id,
            status_selesai,
            activity_id,
            status_dalam,
        )

        baris = cursor.fetchone()
        if not baris:
            raise ValueError("Kunjungan tidak ditemukan atau sudah selesai.")

        conn.commit()
        return int(baris[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def kunjungan_aktif(id_personel):
    """Kunjungan yang statusnya masih di dalam untuk orang tersebut."""
    status_id = _id_status_kunjungan()["KUNJUNGAN_DALAM"]

    baris = _query(
        """
        SELECT TOP 1
            ActivityID AS id_aktivitas,
            LogDate AS waktu,
            NoVehicle AS no_plat,
            CompAreaID AS id_area
        FROM FaceActivity
        WHERE UserID = ?
          AND StatusID = ?
          AND DateTimeOut IS NULL
        ORDER BY LogDate DESC, ActivityID DESC
        """,
        id_personel,
        status_id,
    )
    return baris[0] if baris else None

def terakhir(id_user):
    """Aktivitas berhasil terakhir orang ini dalam 24 jam: {jenis, waktu} atau None."""
    rows = _query("""SELECT TOP 1 a.ActivityType AS jenis, a.LogDate AS waktu FROM FaceActivity a
                     WHERE a.UserID = ? AND a.StatusID = ? AND a.ActivityType IS NOT NULL
                       AND a.LogDate >= DATEADD(HOUR, -24, GETDATE())
                     ORDER BY a.LogDate DESC, a.ActivityID DESC""", id_user, id_status()[BERHASIL])
    return rows[0] if rows else None


def sudah_masuk_hari_ini(id_user, tanggal):
    """Absensi karyawan: (waktu scan terakhir hari itu, sudah ada MASUK)."""
    rows = _query("""SELECT MAX(LogDate) AS terakhir, SUM(CASE WHEN ActivityType = 'MASUK' THEN 1 ELSE 0 END) AS masuk
                     FROM FaceActivity WHERE UserID = ? AND LogDay = ? AND StatusID = ?""",
                  id_user, tanggal, id_status()[BERHASIL])
    r = rows[0] if rows else {"terakhir": None, "masuk": 0}
    return r["terakhir"], bool(r["masuk"])


_KOLOM = f"""a.ActivityID AS id_aktivitas, a.LogDate AS waktu, a.ActivityType AS jenis, s.StatusCode AS status, s.StatusName AS nama_status,
             s.StatusColor AS warna_status, a.Description AS keterangan, a.NoVehicle AS no_plat, a.TimeStatus AS status_waktu,
             a.DiffMinutes AS selisih_menit, a.FaceDistance AS jarak_wajah, a.Device AS perangkat, f.PhotoPath AS foto_scan,
             p.UserID AS id_personel, p.Nama AS nama_personel, p.PersonType AS kategori,
             {jenis_orang.sql_nama('p.PersonType')} AS nama_kategori, p.IsBlacklisted AS is_blacklisted, p.PhotoPath AS foto_path,
             p.CompanyFrom AS asal_perusahaan, d.Nama AS nama_dituju, ar.CompID + ' · ' + ar.AreaName AS area, u.Nama AS dicatat_oleh"""
_FROM = """FROM FaceActivity a
           JOIN Status s ON s.StatusID = a.StatusID
           LEFT JOIN FaceRecog f ON f.FaceID = a.FaceID
           LEFT JOIN UserProfile p ON p.UserID = a.UserID
           LEFT JOIN Users d ON d.UserID = a.VisitToID
           LEFT JOIN Users u ON u.UserID = a.CreateBy
           LEFT JOIN CompanyArea ar ON ar.CompAreaID = a.CompAreaID"""


def _rapikan(rows):
    for r in rows:
        r["is_blacklisted"] = bool(r.get("is_blacklisted"))
        if isinstance(r.get("waktu"), datetime):
            r["jam"] = r["waktu"].strftime("%H:%M")
            r["waktu"] = r["waktu"].strftime("%Y-%m-%d %H:%M")
    return rows


def logs(tanggal, id_area, jenis=None, status=None, cari=None, batas=500):
    """Semua aktivitas satu hari dalam cakupan area, terbaru dulu. jenis = jenis orang, status = kode status scan."""
    f_area, a_area = sql_area("a.CompAreaID", id_area)
    awal = datetime.combine(tanggal, datetime.min.time())
    sql = f"SELECT TOP (?) {_KOLOM} {_FROM} WHERE a.LogDate >= ? AND a.LogDate < ?{f_area}"
    params = [batas, awal, awal + timedelta(days=1), *a_area]
    if jenis in jenis_orang.JENIS:
        sql += " AND p.PersonType = ?"
        params.append(jenis)
    if status in STATUS:
        sql += " AND s.StatusCode = ?"
        params.append(status)
    if cari:
        pola = f"%{cari}%"
        sql += " AND (p.Nama LIKE ? OR p.NoKTP LIKE ? OR a.NoVehicle LIKE ?)"
        params += [pola] * 3
    return _rapikan(_query(sql + " ORDER BY a.LogDate DESC, a.ActivityID DESC", *params))


def di_dalam(id_area):
    """Orang yang masih di dalam: aktivitas berhasil terakhirnya (24 jam) MASUK, dalam cakupan area."""
    f_area, a_area = sql_area("a.CompAreaID", id_area)
    return _rapikan(_query(f"""WITH akhir AS (
                                  SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.UserID ORDER BY a.LogDate DESC, a.ActivityID DESC) AS n
                                  FROM FaceActivity a
                                  WHERE a.UserID IS NOT NULL AND a.StatusID = ? AND a.ActivityType IS NOT NULL
                                    AND a.LogDate >= DATEADD(HOUR, -24, GETDATE()))
                              SELECT {_KOLOM} FROM akhir a
                              JOIN Status s ON s.StatusID = a.StatusID
                              LEFT JOIN FaceRecog f ON f.FaceID = a.FaceID
                              LEFT JOIN UserProfile p ON p.UserID = a.UserID
                              LEFT JOIN Users d ON d.UserID = a.VisitToID
                              LEFT JOIN Users u ON u.UserID = a.CreateBy
                              LEFT JOIN CompanyArea ar ON ar.CompAreaID = a.CompAreaID
                              WHERE a.n = 1 AND a.ActivityType = 'MASUK'{f_area}
                              ORDER BY a.LogDate DESC""", id_status()[BERHASIL], *a_area))


def ringkasan(tanggal, id_area):
    """Angka kartu: masuk hari ini per jenis, masih di dalam, tidak dikenali, ditolak."""
    f_area, a_area = sql_area("a.CompAreaID", id_area)
    st = id_status()
    r = _query(f"""SELECT SUM(CASE WHEN a.StatusID = ? AND a.ActivityType = 'MASUK' AND p.PersonType = 'KARYAWAN' THEN 1 ELSE 0 END) AS karyawan,
                          SUM(CASE WHEN a.StatusID = ? AND a.ActivityType = 'MASUK' AND p.PersonType = 'DRIVER' THEN 1 ELSE 0 END) AS driver,
                          SUM(CASE WHEN a.StatusID = ? AND a.ActivityType = 'MASUK' AND p.PersonType = 'TAMU' THEN 1 ELSE 0 END) AS tamu,
                          SUM(CASE WHEN a.StatusID = ? THEN 1 ELSE 0 END) AS tidak_dikenali,
                          SUM(CASE WHEN a.StatusID = ? THEN 1 ELSE 0 END) AS ditolak
                   FROM FaceActivity a LEFT JOIN UserProfile p ON p.UserID = a.UserID
                   WHERE a.LogDay = ?{f_area}""",
               st[BERHASIL], st[BERHASIL], st[BERHASIL], st[TIDAK_DIKENALI], st[DITOLAK], tanggal, *a_area)[0]
    return {k: int(v or 0) for k, v in r.items()} | {"di_dalam": len(di_dalam(id_area))}


def daftar_dituju():
    """Orang yang bisa ditemui tamu: karyawan aktif."""
    return _query("""SELECT p.UserID AS id_personel, p.Nama AS nama_personel, ld.LevelDetName AS peran
                     FROM Users p LEFT JOIN LevelDetails ld ON ld.LevelDetID = p.UserLevelID
                     WHERE p.Active = 1 AND p.UserLevelID IS NOT NULL ORDER BY p.Nama""")


def saran_keperluan(batas=12):
    """Keperluan yang pernah diketik (isian cepat di form kunjungan)."""
    return [r["teks"] for r in _query("""SELECT TOP (?) x.teks FROM (
                                            SELECT VisitorNeeds AS teks FROM Guest WHERE VisitorNeeds IS NOT NULL
                                            UNION ALL
                                            SELECT LEFT(Description, CHARINDEX(N' · ', Description + N' · ') - 1) FROM FaceActivity
                                            WHERE Description IS NOT NULL AND LogDate >= DATEADD(DAY, -90, GETDATE())) x
                                         GROUP BY x.teks ORDER BY COUNT(*) DESC, x.teks""", batas)]


def rekap_harian(tanggal, id_area):
    """Absensi karyawan aktif satu hari: masuk pertama & keluar terakhir."""
    f_area, a_area = sql_area("p.CompAreaID", id_area)
    st = id_status()[BERHASIL]
    rows = _query(f"""
        SELECT p.UserID AS id_personel, p.Nama AS nama_personel, ld.LevelDetName AS peran,
               p.IsBlacklisted AS is_blacklisted,
               m.waktu AS jam_masuk, m.status_waktu AS status_masuk, m.selisih AS selisih_masuk,
               k.waktu AS jam_pulang, k.status_waktu AS status_pulang, k.selisih AS selisih_pulang
        FROM UserProfile p
        LEFT JOIN LevelDetails ld ON ld.LevelDetID = p.UserLevelID
        LEFT JOIN Level lv ON lv.LevelID = ld.LevelID
        OUTER APPLY (SELECT TOP 1 a.LogDate AS waktu, a.TimeStatus AS status_waktu, a.DiffMinutes AS selisih FROM FaceActivity a
                     WHERE a.UserID = p.UserID AND a.LogDay = ? AND a.StatusID = ? AND a.ActivityType = 'MASUK' ORDER BY a.LogDate) m
        OUTER APPLY (SELECT TOP 1 a.LogDate AS waktu, a.TimeStatus AS status_waktu, a.DiffMinutes AS selisih FROM FaceActivity a
                     WHERE a.UserID = p.UserID AND a.LogDay = ? AND a.StatusID = ? AND a.ActivityType = 'KELUAR' ORDER BY a.LogDate DESC) k
        WHERE p.Active = 1 AND p.PersonType = 'KARYAWAN' AND ISNULL(lv.IsAdmin, 0) = 0{f_area}
        ORDER BY CASE WHEN m.waktu IS NULL THEN 1 ELSE 0 END, p.Nama""", tanggal, st, tanggal, st, *a_area)
    for r in rows:
        for k in ("jam_masuk", "jam_pulang"):
            r[k] = r[k].strftime("%H:%M") if isinstance(r[k], datetime) else None
        r["is_blacklisted"] = bool(r["is_blacklisted"])
    return rows


def rekap_bulanan(tahun, bulan, id_area):
    awal = date(tahun, bulan, 1)
    akhir = date(tahun + (bulan == 12), bulan % 12 + 1, 1)
    f_area, a_area = sql_area("p.CompAreaID", id_area)
    return _query(f"""
        SELECT p.UserID AS id_personel, p.Nama AS nama_personel, ld.LevelDetName AS peran,
               COUNT(DISTINCT CASE WHEN a.ActivityType = 'MASUK' THEN a.LogDay END) AS hari_hadir,
               SUM(CASE WHEN a.ActivityType = 'MASUK' AND a.TimeStatus = 'TERLAMBAT' THEN 1 ELSE 0 END) AS jml_terlambat,
               SUM(CASE WHEN a.ActivityType = 'MASUK' AND a.TimeStatus = 'TERLAMBAT' THEN a.DiffMinutes ELSE 0 END) AS menit_terlambat,
               SUM(CASE WHEN a.ActivityType = 'KELUAR' AND a.TimeStatus = 'PULANG_AWAL' THEN 1 ELSE 0 END) AS jml_pulang_awal
        FROM UserProfile p
        LEFT JOIN LevelDetails ld ON ld.LevelDetID = p.UserLevelID
        LEFT JOIN FaceActivity a ON a.UserID = p.UserID AND a.StatusID = ? AND a.LogDay >= ? AND a.LogDay < ?
        WHERE p.Active = 1 AND p.PersonType = 'KARYAWAN'{f_area}
        GROUP BY p.UserID, p.Nama, ld.LevelDetName
        HAVING COUNT(a.ActivityID) > 0
        ORDER BY p.Nama""", id_status()[BERHASIL], awal, akhir, *a_area)


def area_akun(id_user):
    """Area akun yang sedang login (pengaturan per area: ambang wajah, tantangan, jadwal)."""
    rows = _query("SELECT CompAreaID AS id_comp_area FROM Users WHERE UserID = ?", id_user)
    return rows[0]["id_comp_area"] if rows else None
