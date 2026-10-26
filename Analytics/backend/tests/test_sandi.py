import ahli  # noqa: F401
import base64
import hashlib
import sys
import types
from collections import Counter

from inti import sandi as ks

# Vektor uji RFC 7914 (nilai standar, bukan hasil kode ini)
RFC_PBKDF2 = "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc49ca9cccf179b645991664b39d77ef317c71b845b1e30bd509112041d3a19783"
RFC_SCRYPT = "fdbabe1c9d3472007856e7190d01e9fe7c6ad7cbc8237830e77376634b3731622eaf30d92e22a3886ff109279d9830dac727afb94a83ee6d8360cbdfa2cc0640"


class pustaka_palsu:
    """Pasang pustaka palsu di sys.modules selama blok with, lalu kembalikan keadaan semula."""

    def __init__(self, **modul):
        self.modul, self.simpan = modul, {}

    def __enter__(self):
        for nama, m in self.modul.items():
            self.simpan[nama] = sys.modules.get(nama, "tidak-ada")
            sys.modules[nama] = m

    def __exit__(self, *a):
        for nama, lama in self.simpan.items():
            if lama == "tidak-ada":
                sys.modules.pop(nama, None)
            else:
                sys.modules[nama] = lama


def argon2_palsu():
    """Pengganti argon2-cffi: hanya menguji sambungan ke pustakanya, bukan kriptografinya."""
    galat = types.ModuleType("argon2.exceptions")

    class VerificationError(Exception):
        pass

    class VerifyMismatchError(VerificationError):
        pass

    class InvalidHashError(ValueError):
        pass
    galat.VerificationError, galat.VerifyMismatchError, galat.InvalidHashError = VerificationError, VerifyMismatchError, InvalidHashError
    m = types.ModuleType("argon2")
    m.exceptions = galat

    class PasswordHasher:
        def hash(self, sandi):
            return "$argon2id$v=19$m=65536,t=3,p=4$palsu$" + base64.b64encode(sandi.encode()).decode()

        def verify(self, hash_, sandi):
            if not hash_.startswith("$argon2id$"):
                raise InvalidHashError("bukan argon2")
            if hash_.rsplit("$", 1)[1] != base64.b64encode(sandi.encode()).decode():
                raise VerifyMismatchError("salah")
            return True
    m.PasswordHasher = PasswordHasher
    return {"argon2": m, "argon2.exceptions": galat}


def bcrypt_palsu():
    m = types.ModuleType("bcrypt")
    m.gensalt = lambda: b"$2b$12$garampalsugarampalsuga"
    m.hashpw = lambda pw, salt: b"$2b$12$palsu" + base64.b64encode(pw)
    m.checkpw = lambda pw, h: h == b"$2b$12$palsu" + base64.b64encode(pw)
    return {"bcrypt": m}


def test_hash_buatan_sendiri_dan_hash_rusak():
    h = ks.hash_sandi("rahasia")
    assert h.startswith("scrypt$") and "rahasia" not in h and ks.jenis_hash(h) == "scrypt"
    assert ks.cocok("rahasia", h) and not ks.cocok("Rahasia", h) and not ks.cocok("", h)
    assert ks.hash_sandi("rahasia") != h                                       # garam acak
    for rusak in ["", "bukan-hash", "scrypt$1$2", "scrypt$x$y$z$AA==$AA==", "pbkdf2:sha256$a$b", "pbkdf2_sha256$x$y", None, 123, b"\xff\xfe"]:
        assert ks.cocok("rahasia", rusak) is False                              # hash rusak tidak membuat server error


def test_jenis_hash_dikenali_dari_awalan():
    contoh = {"scrypt$16384$8$1$AA==$AA==": "scrypt", "scrypt:32768:8:1$g$ab": "werkzeug-scrypt", "pbkdf2:sha256:600000$g$ab": "werkzeug-pbkdf2",
              "pbkdf2_sha256$600000$g$AA==": "django-pbkdf2", "$argon2id$v=19$m=1,t=1,p=1$a$b": "argon2", "$argon2i$v=19$a$b": "argon2",
              "$2b$12$abcdefghijklmnopqrstuv": "bcrypt", "$2a$10$x": "bcrypt", "$2y$10$x": "bcrypt", b"$2b$12$x": "bcrypt"}
    for h, j in contoh.items():
        assert ks.jenis_hash(h) == j, h
    for lain in ["plaintext", "5f4dcc3b5aa765d61d8327deb882cf99", "", None, "$1$md5crypt$x"]:
        assert ks.jenis_hash(lain) is None


def test_format_werkzeug_dengan_vektor_rfc_7914():
    assert ks.cocok("passwd", f"pbkdf2:sha256:1$salt${RFC_PBKDF2}")
    assert not ks.cocok("salah", f"pbkdf2:sha256:1$salt${RFC_PBKDF2}")
    assert ks.cocok("password", f"scrypt:1024:8:16$NaCl${RFC_SCRYPT}")
    assert not ks.cocok("Password", f"scrypt:1024:8:16$NaCl${RFC_SCRYPT}")


def test_format_django_pbkdf2():
    h = hashlib.pbkdf2_hmac("sha256", b"passwd", b"salt", 1, 32)
    assert ks.cocok("passwd", "pbkdf2_sha256$1$salt$" + base64.b64encode(h).decode())
    assert not ks.cocok("passwD", "pbkdf2_sha256$1$salt$" + base64.b64encode(h).decode())
    baru = ks.hash_sandi("rahasia123", "django-pbkdf2")                       # buatan aplikasi, dalam format Django
    assert baru.startswith("pbkdf2_sha256$600000$") and ks.cocok("rahasia123", baru) and not ks.cocok("rahasia124", baru)


def test_argon2_dan_bcrypt_lewat_pustaka_dengan_pustaka_palsu():
    with pustaka_palsu(**argon2_palsu()):
        h = ks.hash_sandi("rahasia", "argon2")
        assert ks.jenis_hash(h) == "argon2" and ks.cocok("rahasia", h) and not ks.cocok("salah", h)
        assert ks.cocok("rahasia", "$argon2id$v=19$m=1,t=1,p=1$a$b") is False       # hash rusak: ditolak, bukan error
        assert ks.pustaka_tersedia("argon2")
    with pustaka_palsu(**bcrypt_palsu()):
        h = ks.hash_sandi("rahasia", "bcrypt")
        assert ks.jenis_hash(h) == "bcrypt" and ks.cocok("rahasia", h) and not ks.cocok("salah", h)


def test_pustaka_belum_terpasang_dibedakan_dari_sandi_salah():
    with pustaka_palsu(argon2=None, bcrypt=None):                              # None di sys.modules membuat impor gagal
        assert not ks.pustaka_tersedia("argon2") and not ks.pustaka_tersedia("bcrypt") and ks.pustaka_tersedia("scrypt")
        for h in ("$argon2id$v=19$m=1,t=1,p=1$a$b", "$2b$12$abcdefghijklmnopqrstuv"):
            try:
                ks.cocok("apa-saja", h)
                raise AssertionError("seharusnya melempar PustakaHilang")
            except ks.PustakaHilang as e:
                assert e.paket in ("argon2-cffi", "bcrypt") and "pip install" in str(e)
        for algo in ("argon2", "bcrypt"):
            try:
                ks.hash_sandi("x", algo)
                raise AssertionError("seharusnya melempar PustakaHilang")
            except ks.PustakaHilang:
                pass


def test_pilih_algoritma_mengikuti_hash_yang_sudah_ada():
    pilih = ks.pilih_algoritma
    assert pilih(Counter({"argon2": 5, "scrypt": 1})) == "argon2"
    assert pilih(Counter({"bcrypt": 2, "django-pbkdf2": 7, None: 9})) == "django-pbkdf2"           # format tak dikenal diabaikan
    assert pilih(Counter({"werkzeug-scrypt": 4})) == "werkzeug-scrypt"                      # tabel berisi hash Werkzeug: akun baru juga Werkzeug
    assert pilih(Counter({"werkzeug-scrypt": 4, "scrypt": 1})) == "werkzeug-scrypt" and pilih(Counter({"werkzeug-pbkdf2": 2})) == "werkzeug-pbkdf2"
    assert pilih(Counter()) == "scrypt" and pilih(None) == "scrypt"
    assert pilih(Counter({"argon2": 5}), "werkzeug-scrypt") == "werkzeug-scrypt" and pilih(Counter({"argon2": 5}), "bcrypt") == "bcrypt" and pilih(Counter({"argon2": 5}), " SCRYPT ") == "scrypt"
    for salah in ("md5", "sha1", "plaintext"):
        try:
            pilih(Counter(), salah)
            raise AssertionError("seharusnya ditolak")
        except ValueError as e:
            assert "PASSWORD_HASH" in str(e)
    assert ks.cocok("x", ks.HASH_PALSU) is False and ks.jenis_hash(ks.HASH_PALSU) == "scrypt"


def test_hash_werkzeug_buatan_aplikasi_sesuai_algoritma_yang_didokumentasikan():
    """Dihitung ulang dengan hashlib mengikuti algoritma Werkzeug (garam 16 huruf-angka, hex), tanpa memakai kode aplikasi."""
    h = ks.hash_sandi("rahasia123", "werkzeug-scrypt")
    metode, garam, hex_ = h.split("$")
    assert metode == "scrypt:32768:8:1" and len(garam) == 16 and garam.isalnum() and len(hex_) == 128
    assert hashlib.scrypt(b"rahasia123", salt=garam.encode(), n=32768, r=8, p=1, maxmem=132 * 32768 * 8).hex() == hex_
    h = ks.hash_sandi("rahasia123", "werkzeug-pbkdf2")
    metode, garam, hex_ = h.split("$")
    assert metode == "pbkdf2:sha256:1000000" and len(garam) == 16 and garam.isalnum() and len(hex_) == 64
    assert hashlib.pbkdf2_hmac("sha256", b"rahasia123", garam.encode(), 1000000).hex() == hex_
    assert ks.hash_sandi("rahasia123", "werkzeug-scrypt") != ks.hash_sandi("rahasia123", "werkzeug-scrypt")        # garam acak


def test_hash_werkzeug_diuji_silang_dengan_pustaka_werkzeug_asli():
    try:
        from werkzeug.security import check_password_hash, generate_password_hash
    except ImportError:
        ahli.lewati("pustaka werkzeug tidak terpasang")
        return
    for algo in ("werkzeug-scrypt", "werkzeug-pbkdf2"):                         # dibuat aplikasi, dibaca Werkzeug
        h = ks.hash_sandi("rahasia123", algo)
        assert check_password_hash(h, "rahasia123") and not check_password_hash(h, "rahasia124"), algo
    for metode in ("scrypt", "pbkdf2"):                                          # dibuat Werkzeug, dibaca aplikasi
        h = generate_password_hash("rahasia123", method=metode)
        assert ks.jenis_hash(h) == "werkzeug-" + metode and ks.cocok("rahasia123", h) and not ks.cocok("rahasia124", h), metode
    assert not check_password_hash(ks.hash_sandi("rahasia123", "scrypt"), "rahasia123")   # format scrypt lama buatan sendiri TIDAK dibaca Werkzeug
