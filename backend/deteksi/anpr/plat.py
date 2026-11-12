"""Aturan plat nomor Indonesia: merapikan hasil OCR jadi format baku 'BM 1455 JJ'.

KODE_WILAYAH dan normalisasi_plat() disalin dari timbangan_sawit_v2 (utils/plat_utils.py) supaya hasil
di sini sama persis dengan yang diterima website. Kalau aturan di website berubah, salin ulang ke sini.
"""
import re

# Kode wilayah plat Indonesia (1-2 huruf depan)
KODE_WILAYAH = {
    # Sumatera
    "BL", "BB", "BK", "BA", "BM", "BH", "BD", "BG", "BN", "BE", "BP",
    # Jawa, Bali, Nusa Tenggara
    "A", "B", "D", "E", "F", "T", "Z", "G", "H", "K", "R", "AA", "AB", "AD",
    "L", "M", "N", "P", "S", "W", "AE", "AG", "DK", "DR", "EA", "DH", "EB", "ED",
    # Kalimantan
    "KB", "DA", "KH", "KT", "KU",
    # Sulawesi
    "DB", "DL", "DM", "DN", "DT", "DD", "DC", "DW",
    # Maluku & Papua
    "DE", "DG", "PA", "PB", "PG", "PS", "PT", "PY",
}

# Huruf depan 1-2, angka 1-4 (tidak diawali 0), huruf belakang 0-3.
_POLA_PLAT = re.compile(r"^([A-Z]{1,2})[\s.\-]*([1-9][0-9]{0,3})[\s.\-]*([A-Z]{0,3})$")


def normalisasi_plat(raw):
    """Ubah input bebas jadi format baku 'BM 1455 JJ'.

    Return (plat_baku, None) kalau valid, atau (None, pesan_error) kalau tidak.
    """
    teks = (raw or "").strip().upper()
    if not teks:
        return None, "Nomor plat kosong"

    m = _POLA_PLAT.match(teks)
    if not m:
        return None, (f"Format plat '{teks}' tidak valid. "
                      "Contoh: BM 1455 JJ, A 1234 JJ, AA 456 SJU")

    wilayah, angka, akhiran = m.groups()
    if wilayah not in KODE_WILAYAH:
        return None, f"Kode wilayah '{wilayah}' tidak dikenal (plat '{teks}')"

    return " ".join(p for p in (wilayah, angka, akhiran) if p), None


# Karakter yang sering tertukar oleh OCR, dipakai sesuai posisi:
# di bagian huruf, angka diubah ke huruf yang mirip; di bagian angka, huruf diubah ke angka yang mirip.
_ANGKA_KE_HURUF = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"}
_HURUF_KE_ANGKA = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2",
                   "A": "4", "S": "5", "G": "6", "T": "7", "B": "8"}

MAKS_KOREKSI = 2


def _ke_huruf(bagian):
    hasil, koreksi = [], 0
    for c in bagian:
        if c.isalpha():
            hasil.append(c)
        elif c in _ANGKA_KE_HURUF:
            hasil.append(_ANGKA_KE_HURUF[c])
            koreksi += 1
        else:
            return None, 0
    return "".join(hasil), koreksi


def _ke_angka(bagian):
    hasil, koreksi = [], 0
    for c in bagian:
        if c.isdigit():
            hasil.append(c)
        elif c in _HURUF_KE_ANGKA:
            hasil.append(_HURUF_KE_ANGKA[c])
            koreksi += 1
        else:
            return None, 0
    return "".join(hasil), koreksi


def rapikan_bacaan(teks_ocr):
    """Rapikan teks mentah OCR jadi plat baku.

    Mencoba semua pembagian huruf depan (1-2) / angka (1-4) / huruf belakang (0-3), membetulkan karakter
    yang mirip sesuai posisinya, dan membuang baris masa berlaku (mis. '0627') yang ikut terbaca di belakang.
    Dipilih pembagian dengan koreksi paling sedikit.

    Return (plat_baku, jumlah_koreksi) atau (None, alasan).
    """
    teks = re.sub(r"[^A-Z0-9]", "", (teks_ocr or "").upper())
    if not teks:
        return None, "kosong"

    terbaik = None  # (skor, plat, koreksi)
    for p in (1, 2):
        for d in range(1, 5):
            for s in range(0, 4):
                n = p + d + s
                if n > len(teks):
                    continue
                sisa = teks[n:]
                # Sisa hanya boleh berupa masa berlaku (2-4 angka) di bawah nomor plat. Plat tanpa huruf
                # belakang tidak boleh punya sisa: angka nomor dan masa berlaku tidak bisa dibedakan.
                if sisa and not (s > 0 and 2 <= len(sisa) <= 4 and sisa.isdigit()):
                    continue
                depan, k1 = _ke_huruf(teks[:p])
                angka, k2 = _ke_angka(teks[p:p + d])
                belakang, k3 = _ke_huruf(teks[p + d:n])
                if depan is None or angka is None or belakang is None:
                    continue
                koreksi = k1 + k2 + k3
                if koreksi > MAKS_KOREKSI:
                    continue
                plat, salah = normalisasi_plat(f"{depan} {angka} {belakang}".strip())
                if salah:
                    continue
                skor = (koreksi, bool(sisa), -n)
                if terbaik is None or skor < terbaik[0]:
                    terbaik = (skor, plat, koreksi)

    if terbaik is None:
        return None, f"bukan format plat ({teks})"
    return terbaik[1], terbaik[2]
