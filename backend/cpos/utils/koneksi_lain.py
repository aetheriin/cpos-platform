"""Koneksi ODBC ke database lain: laporan & tiket ERP RekapIn, tabel harga, Item Request.

Tiap bagian punya awalan sendiri di .env (mis. ITEM_REQUEST_SERVER). Yang tidak diisi memakai database utama (DB_SERVER, DB_NAME,
DB_USER, DB_PASSWORD), jadi .env cukup berisi yang memang berbeda. <AWALAN>_CONNECTION_STRING lengkap menggantikan semuanya."""
import os


def _isi(nama):
    nilai = os.getenv(nama)
    return nilai if nilai not in (None, "") else None


def connection_string(awalan, aplikasi, nama=None, db_bawaan=None):
    """nama: nama kolom lain untuk awalan lama, mis. {"DB": "DATABASE", "USER": "UID", "PASSWORD": "PWD"}.
    db_bawaan: database bila <AWALAN>_DB kosong (sebelum DB_NAME)."""
    teks = (os.getenv(f"{awalan}_CONNECTION_STRING") or "").strip()
    if teks:
        return teks
    n = {"SERVER": "SERVER", "DB": "DB", "USER": "USER", "PASSWORD": "PASSWORD", **(nama or {})}
    server = (_isi(f"{awalan}_{n['SERVER']}") or os.getenv("DB_SERVER") or "").strip()
    database = (_isi(f"{awalan}_{n['DB']}") or db_bawaan or os.getenv("DB_NAME") or "").strip()
    user = (_isi(f"{awalan}_{n['USER']}") or os.getenv("DB_USER") or "").strip()
    sandi = _isi(f"{awalan}_{n['PASSWORD']}") or os.getenv("DB_PASSWORD") or ""
    login = f"UID={user};PWD={{{sandi.replace('}', '}}')}}};" if user else "Trusted_Connection=yes;"
    driver = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
    # Encrypt=no: ODBC Driver 18 memakai enkripsi bawaan dan gagal ke SQL Server lama tanpa TLS
    enkripsi = (os.getenv(f"{awalan}_ENCRYPT") or "no").strip()
    return (f"DRIVER={driver};SERVER={server};DATABASE={database};{login}"
            f"Encrypt={enkripsi};TrustServerCertificate=yes;APP={aplikasi};")
