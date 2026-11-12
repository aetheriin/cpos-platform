"""Koneksi SQL Server: database data (SP laporan, DB_*) dan database pengguna (DB_APP_*, bawaannya sama dengan database data).

DB_USER atau DB_APP_USER yang kosong berarti memakai akun Windows yang menjalankan server.
"""
import os

import pyodbc


class KonfigurasiKurang(RuntimeError):
    pass


def _periksa(wajib_isi=(), wajib_ada=()):
    """Sebutkan semua yang kurang sekaligus. wajib_ada boleh kosong, tapi harus ada."""
    kurang = [n for n in wajib_isi if not os.environ.get(n)] + [n for n in wajib_ada if os.environ.get(n) is None]
    if kurang:
        raise KonfigurasiKurang(
            f"Pengaturan database belum lengkap: {', '.join(kurang)}. Isi di backend\\.env."
        )


def _sambungkan(server, database, user, password, timeout_detik, login_detik=None):
    bagian = ["DRIVER={ODBC Driver 18 for SQL Server}", f"SERVER={server}", f"DATABASE={database}"]
    if user:
        # Kurung kurawal melindungi karakter khusus di password
        bagian += [f"UID={user}", "PWD={" + (password or "").replace("}", "}}") + "}"]
    else:
        bagian.append("Trusted_Connection=yes")
    bagian.append("TrustServerCertificate=yes")
    conn = pyodbc.connect(";".join(bagian), **({"timeout": login_detik} if login_detik else {}))
    conn.timeout = timeout_detik  # per query
    return conn


def get_connection(timeout_detik=300):
    _periksa(wajib_isi=("DB_SERVER", "DB_NAME"), wajib_ada=("DB_USER", "DB_PASSWORD"))
    return _sambungkan(os.environ["DB_SERVER"], os.environ["DB_NAME"], os.environ["DB_USER"], os.environ["DB_PASSWORD"], timeout_detik)


def get_connection_app(timeout_detik=15):
    """Gagal dalam 10 detik kalau server tidak terjangkau."""
    pakai_app = "DB_APP_USER" in os.environ
    _periksa(
        wajib_isi=tuple(n for n, ganti in (("DB_SERVER", "DB_APP_SERVER"), ("DB_NAME", "DB_APP_NAME")) if not os.environ.get(ganti)),
        wajib_ada=() if pakai_app else ("DB_USER", "DB_PASSWORD"),
    )
    if pakai_app:   # kosong = akun Windows
        user, password = os.environ["DB_APP_USER"], os.environ.get("DB_APP_PASSWORD", "")
    else:
        user, password = os.environ["DB_USER"], os.environ["DB_PASSWORD"]
    return _sambungkan(
        os.environ.get("DB_APP_SERVER") or os.environ["DB_SERVER"],
        os.environ.get("DB_APP_NAME") or os.environ["DB_NAME"],
        user,
        password,
        timeout_detik,
        login_detik=10,
    )
