import ahli  # noqa: F401
import os

from inti import db
from inti.pengguna import PenyimpanPengguna, PenyimpanTidakTersedia

SEMUA = ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_APP_SERVER", "DB_APP_NAME", "DB_APP_USER", "DB_APP_PASSWORD")


class Lingkungan:
    """Atur variabel lingkungan sementara (yang tidak disebut dihapus), lalu kembalikan seperti semula."""

    def __init__(self, **isi):
        self.isi = isi

    def __enter__(self):
        self.asli = {k: os.environ.get(k) for k in SEMUA}
        for k in SEMUA:
            os.environ.pop(k, None)
        os.environ.update(self.isi)

    def __exit__(self, *a):
        for k in SEMUA:
            os.environ.pop(k, None)
            if self.asli[k] is not None:
                os.environ[k] = self.asli[k]


def pesan_dari(fn):
    try:
        fn()
    except db.KonfigurasiKurang as e:
        return str(e)
    raise AssertionError("seharusnya melempar KonfigurasiKurang")


def test_tanpa_env_semua_yang_kurang_disebut_sekaligus_dan_dijelaskan_penyebabnya():
    with Lingkungan():
        for fn in (db.get_connection, db.get_connection_app):
            p = pesan_dari(fn)
            assert all(n in p for n in ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD")), p
            assert "backend/.env" in p and ".env.contoh" in p and "tidak ikut di zip" in p


def test_hanya_yang_benar_benar_kurang_yang_disebut():
    with Lingkungan(DB_SERVER="srv", DB_NAME="data"):
        p = pesan_dari(db.get_connection_app)
        assert "DB_USER, DB_PASSWORD belum diisi" in p and "DB_SERVER" not in p.split("belum diisi")[0] and "DB_NAME" not in p.split("belum diisi")[0]
    with Lingkungan(DB_SERVER="", DB_NAME="data", DB_USER="u", DB_PASSWORD="p"):       # server kosong sama dengan tidak diisi
        assert "DB_SERVER belum diisi" in pesan_dari(db.get_connection)


def test_pengaturan_khusus_tabel_pengguna_menggantikan_yang_umum():
    with Lingkungan(DB_APP_SERVER="srv", DB_APP_NAME="peng", DB_APP_USER="", DB_APP_PASSWORD=""):   # kosong = akun Windows, sah
        try:
            db.get_connection_app()
        except db.KonfigurasiKurang as e:
            raise AssertionError("pengaturan DB_APP_* lengkap tidak boleh dianggap kurang: " + str(e))
        except Exception:
            pass                                                   # gagal menyambung ke server sungguhan adalah wajar di uji
    with Lingkungan(DB_APP_SERVER="srv"):
        assert "DB_NAME, DB_USER, DB_PASSWORD" in pesan_dari(db.get_connection_app)        # DB_APP_NAME dan akun tidak diisi, DB_NAME jadi cadangan


def test_galat_pengaturan_sampai_ke_pesan_tabel_pengguna_bukan_keyerror():
    with Lingkungan():
        t = PenyimpanPengguna(db.get_connection_app)
        try:
            t.periksa()
        except PenyimpanTidakTersedia as e:
            pesan = str(e)
        else:
            raise AssertionError("seharusnya gagal")
    assert "KonfigurasiKurang" in pesan and "backend/.env" in pesan and "KeyError" not in pesan
