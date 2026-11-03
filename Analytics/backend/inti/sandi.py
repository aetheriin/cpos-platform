"""Hash kata sandi. Tabel pengguna bisa berisi hash dari pustaka berbeda; jenisnya dikenali dari awalan:

    scrypt$N$r$p$garam$hash       buatan aplikasi ini (hashlib.scrypt, tanpa pustaka tambahan)
    scrypt:N:r:p$garam$hash       Werkzeug / Flask (hashlib.scrypt)
    pbkdf2:sha256:N$garam$hash    Werkzeug / Flask (hashlib.pbkdf2_hmac)
    pbkdf2_sha256$N$garam$hash    Django (hashlib.pbkdf2_hmac)
    $argon2id$...                 argon2-cffi      (pip install argon2-cffi)
    $2a$ / $2b$ / $2y$ ...        bcrypt           (pip install bcrypt)

Akun baru mengikuti algoritma akun yang sudah ada (pilih_algoritma), supaya aplikasi lain yang memakai tabel yang sama tetap bisa
memeriksanya. Format Werkzeug sudah diuji silang dengan pustaka Werkzeug asli.
"""
import base64
import hashlib
import hmac
import os
import secrets
import string
from collections import Counter

N, R, P = 2 ** 14, 8, 1          # scrypt aplikasi ini, sekitar 16 MB per pemeriksaan
ITERASI_PBKDF2 = 600_000         # akun baru berformat Django
WERKZEUG_SCRYPT = (32768, 8, 1)  # bawaan Werkzeug, sekitar 34 MB per pemeriksaan
WERKZEUG_PBKDF2 = 1_000_000      # bawaan Werkzeug 3.1
_HURUF_GARAM = string.ascii_letters + string.digits

JENIS = ("scrypt", "werkzeug-scrypt", "werkzeug-pbkdf2", "django-pbkdf2", "argon2", "bcrypt")
BISA_DIBUAT = JENIS
PUSTAKA = {"argon2": "argon2-cffi", "bcrypt": "bcrypt"}         # jenis yang butuh pustaka tambahan


class PustakaHilang(Exception):
    def __init__(self, paket):
        super().__init__(f"Pustaka {paket} belum terpasang di server (jalankan: pip install {paket})")
        self.paket = paket


def _impor(jenis):
    """Modul pustaka tambahan untuk jenis ini (argon2 atau bcrypt), atau PustakaHilang."""
    try:
        return __import__(jenis)
    except ImportError:
        raise PustakaHilang(PUSTAKA[jenis]) from None


def _teks(h):
    if isinstance(h, (bytes, bytearray)):
        return bytes(h).decode("utf-8", "ignore").strip()
    return h.strip() if isinstance(h, str) else ""


def jenis_hash(tersimpan):
    """Salah satu isi JENIS, atau None kalau formatnya tidak dikenal."""
    t = _teks(tersimpan)
    if t.startswith("scrypt$"):
        return "scrypt"
    if t.startswith("scrypt:"):
        return "werkzeug-scrypt"
    if t.startswith("pbkdf2:"):
        return "werkzeug-pbkdf2"
    if t.startswith("pbkdf2_sha256$"):
        return "django-pbkdf2"
    if t.startswith("$argon2"):
        return "argon2"
    if t[:4] in ("$2a$", "$2b$", "$2y$", "$2x$"):
        return "bcrypt"
    return None


def pustaka_tersedia(jenis):
    if jenis not in PUSTAKA:
        return True
    try:
        _impor(jenis)
        return True
    except PustakaHilang:
        return False


def _b64(b):
    return base64.b64encode(b).decode("ascii")


def _periksa_scrypt(sandi, t):
    _, n, r, p, garam, h = t.split("$")
    target = base64.b64decode(h)
    hitung = hashlib.scrypt(sandi.encode("utf-8"), salt=base64.b64decode(garam), n=int(n), r=int(r), p=int(p), dklen=len(target))
    return hmac.compare_digest(hitung, target)


def _periksa_werkzeug_scrypt(sandi, t):
    metode, garam, h = t.split("$", 2)
    _, n, r, p = metode.split(":")
    target = bytes.fromhex(h)
    n, r, p = int(n), int(r), int(p)
    hitung = hashlib.scrypt(sandi.encode("utf-8"), salt=garam.encode("utf-8"), n=n, r=r, p=p, maxmem=132 * n * r * p, dklen=len(target))
    return hmac.compare_digest(hitung, target)


def _periksa_werkzeug_pbkdf2(sandi, t):
    metode, garam, h = t.split("$", 2)
    _, algoritma, iterasi = metode.split(":")
    target = bytes.fromhex(h)
    hitung = hashlib.pbkdf2_hmac(algoritma, sandi.encode("utf-8"), garam.encode("utf-8"), int(iterasi), dklen=len(target))
    return hmac.compare_digest(hitung, target)


def _periksa_django_pbkdf2(sandi, t):
    _, iterasi, garam, h = t.split("$")
    target = base64.b64decode(h)
    hitung = hashlib.pbkdf2_hmac("sha256", sandi.encode("utf-8"), garam.encode("utf-8"), int(iterasi), dklen=len(target))
    return hmac.compare_digest(hitung, target)


def _periksa_argon2(sandi, t):
    argon2 = _impor("argon2")
    from argon2 import exceptions as galat
    try:
        return bool(argon2.PasswordHasher().verify(t, sandi))
    except (galat.VerificationError, galat.InvalidHashError):
        return False


def _periksa_bcrypt(sandi, t):
    return bool(_impor("bcrypt").checkpw(sandi.encode("utf-8"), t.encode("utf-8")))


_PERIKSA = {
    "scrypt": _periksa_scrypt, "werkzeug-scrypt": _periksa_werkzeug_scrypt, "werkzeug-pbkdf2": _periksa_werkzeug_pbkdf2,
    "django-pbkdf2": _periksa_django_pbkdf2, "argon2": _periksa_argon2, "bcrypt": _periksa_bcrypt,
}


def cocok(sandi, tersimpan):
    """Hash rusak atau tidak dikenal = tidak cocok. Pustaka yang belum terpasang = PustakaHilang, supaya bisa dibedakan dari sandi salah."""
    jenis = jenis_hash(tersimpan)
    if jenis is None:
        return False
    try:
        return _PERIKSA[jenis](sandi, _teks(tersimpan))
    except (ValueError, TypeError, AttributeError, IndexError, OverflowError):
        return False


def hash_sandi(sandi, algoritma="scrypt"):
    if algoritma == "scrypt":
        garam = os.urandom(16)
        h = hashlib.scrypt(sandi.encode("utf-8"), salt=garam, n=N, r=R, p=P, dklen=32)
        return f"scrypt${N}${R}${P}${_b64(garam)}${_b64(h)}"
    if algoritma == "werkzeug-scrypt":
        n, r, p = WERKZEUG_SCRYPT
        garam = "".join(secrets.choice(_HURUF_GARAM) for _ in range(16))
        h = hashlib.scrypt(sandi.encode("utf-8"), salt=garam.encode("utf-8"), n=n, r=r, p=p, maxmem=132 * n * r * p).hex()
        return f"scrypt:{n}:{r}:{p}${garam}${h}"
    if algoritma == "werkzeug-pbkdf2":
        garam = "".join(secrets.choice(_HURUF_GARAM) for _ in range(16))
        h = hashlib.pbkdf2_hmac("sha256", sandi.encode("utf-8"), garam.encode("utf-8"), WERKZEUG_PBKDF2).hex()
        return f"pbkdf2:sha256:{WERKZEUG_PBKDF2}${garam}${h}"
    if algoritma == "django-pbkdf2":
        garam = secrets.token_urlsafe(12)
        h = hashlib.pbkdf2_hmac("sha256", sandi.encode("utf-8"), garam.encode("utf-8"), ITERASI_PBKDF2)
        return f"pbkdf2_sha256${ITERASI_PBKDF2}${garam}${_b64(h)}"
    if algoritma == "argon2":
        return _impor("argon2").PasswordHasher().hash(sandi)
    if algoritma == "bcrypt":
        bcrypt = _impor("bcrypt")
        return bcrypt.hashpw(sandi.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    raise ValueError(f"Algoritma hash tidak dikenal: {algoritma}. Pilihan: {', '.join(BISA_DIBUAT)}")


def pilih_algoritma(jenis_di_tabel, pilihan="auto"):
    """'auto': jenis yang paling banyak dipakai di tabel, atau scrypt kalau tidak ada. jenis_di_tabel: Counter dari jenis_hash."""
    pilihan = (pilihan or "auto").strip().lower()
    if pilihan != "auto":
        if pilihan not in BISA_DIBUAT:
            raise ValueError(f"PASSWORD_HASH harus 'auto' atau salah satu dari: {', '.join(BISA_DIBUAT)}")
        return pilihan
    umum = Counter({j: n for j, n in (jenis_di_tabel or {}).items() if j in BISA_DIBUAT})
    return umum.most_common(1)[0][0] if umum else "scrypt"


# Untuk username yang tidak ada, supaya username tidak bisa ditebak dari kecepatan jawaban
HASH_PALSU = hash_sandi("sandi-yang-tidak-pernah-dipakai")
