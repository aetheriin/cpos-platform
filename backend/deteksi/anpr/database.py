"""Menulis hasil deteksi ke SQL Server (dbo.RiwayatDeteksi); pemilik dicari lewat DetailVehicle -> UserC."""
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from anpr import gerbang

FOLDER_PROYEK = Path(__file__).resolve().parent.parent
load_dotenv(FOLDER_PROYEK.parent / ".env")   # backend\.env, sama dengan CPOS

try:
    import pyodbc
except ImportError:
    pyodbc = None

TIDAK_DIKETAHUI = "Tidak Diketahui"


def get_koneksi(timeout=10):
    if pyodbc is None:
        raise RuntimeError("Library pyodbc belum terinstall.")

    driver = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}").strip()
    if not (driver.startswith("{") and driver.endswith("}")):
        driver = "{" + driver + "}"

    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME", "Main")
    user = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASSWORD", "")
    trust = os.getenv("DB_TRUST_CERT", "yes")

    if not server:
        raise RuntimeError("DB_SERVER belum diisi pada .env CPOS.")

    bagian = [
        f"DRIVER={driver}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"TrustServerCertificate={trust}",
        "APP=CPOS-Deteksi",
    ]

    if user:
        password = password.replace("}", "}}")
        bagian.extend([f"UID={user}", f"PWD={{{password}}}"])
    else:
        bagian.append("Trusted_Connection=yes")

    return pyodbc.connect(";".join(bagian), timeout=timeout)


def simpan_riwayat(waktu, kamera, jenis, plat, conf_ocr, foto_rel, plat_rel):
    """Simpan satu baris ke dbo.RiwayatDeteksi dan gabungkan ke kejadian gerbang (bila kamera punya gerbang).
    Return nama pemilik (dbo.UserC) atau 'Tidak Diketahui'."""
    for percobaan in range(1, 4):
        try:
            conn = get_koneksi()
            try:
                cur = conn.cursor()
                cur.execute("SELECT IDVehicle FROM dbo.DetailVehicle WHERE NoVehicle = ?", plat)
                baris = cur.fetchone()
                id_vehicle = baris[0] if baris else None            # NULL = plat belum terdaftar
                waktu_dt = datetime.fromtimestamp(waktu)
                conf = float(conf_ocr) if conf_ocr is not None else None
                cur.execute("""SET NOCOUNT ON;
                               INSERT INTO dbo.RiwayatDeteksi (Waktu, Kamera, IDVehicle, PlatNomor, JenisTerdeteksi, ConfOCR, FotoPath, PlatPath)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                               SELECT CAST(SCOPE_IDENTITY() AS BIGINT);""",
                            waktu_dt, kamera, id_vehicle, plat, jenis, conf, foto_rel, plat_rel)
                id_deteksi = cur.fetchone()[0]
                try:
                    gerbang.pasangkan(cur, id_deteksi, waktu_dt, kamera, plat, conf, id_vehicle)
                except Exception as e:  
                    print(f"[GERBANG] gagal menggabungkan bacaan: {e}")
                pemilik = TIDAK_DIKETAHUI
                if id_vehicle is not None:
                    cur.execute("SELECT TOP 1 Nama FROM dbo.UserC WHERE IDVehicle = ? AND Active = 1", id_vehicle)
                    p = cur.fetchone()
                    if p:
                        pemilik = p[0]
                conn.commit()
                return pemilik
            finally:
                conn.close()
        except Exception as e: 
            print(f"[SQL] gagal simpan (percobaan {percobaan}/3): {e}")
            time.sleep(2)
    return TIDAK_DIKETAHUI


def ambil_laporan_excel(rentang):
    """rentang: 'hari_ini', 'minggu_ini', 'bulan_ini'"""
    kolom = ["Waktu", "Kamera", "JenisKendaraan", "PlatNomor", "NamaPemilik"]
    try:
        if rentang == "hari_ini":
            filter_sql = "CAST(r.Waktu AS DATE) = CAST(GETDATE() AS DATE)"
        elif rentang == "minggu_ini":
            filter_sql = "r.Waktu >= DATEADD(day, -7, GETDATE())"
        elif rentang == "bulan_ini":
            filter_sql = "MONTH(r.Waktu) = MONTH(GETDATE()) AND YEAR(r.Waktu) = YEAR(GETDATE())"
        else:
            filter_sql = "1=1"
        conn = get_koneksi()
        try:
            return pd.read_sql(f"""
                SELECT r.Waktu, r.Kamera, COALESCE(t.NameType, r.JenisTerdeteksi, '-') AS JenisKendaraan, r.PlatNomor,
                       ISNULL(u.Nama, '{TIDAK_DIKETAHUI}') AS NamaPemilik
                FROM dbo.RiwayatDeteksi r
                LEFT JOIN dbo.DetailVehicle v ON v.IDVehicle = r.IDVehicle
                LEFT JOIN dbo.VehicleType t ON t.VehicleTypeID = v.VehicleType
                LEFT JOIN dbo.UserC u ON u.IDVehicle = r.IDVehicle AND u.Active = 1
                WHERE {filter_sql} ORDER BY r.Waktu DESC""", conn)
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"Error ambil laporan Excel: {e}")
        return pd.DataFrame(columns=kolom)