"""Aturan tampilan personel (tanpa database, bisa di-unit-test)."""
import re
KATEGORI_VALID = ("KARYAWAN", "DRIVER", "TAMU")     # utils/jenis_orang.py
WAJIB_SIM = ("DRIVER",)

# kolom audit -> label yang ditampilkan di menu Log Audit
KOLOM_AUDIT = (
    ("nik", "nik_lama", "nik_baru"),
    ("nama", "nama_lama", "nama_baru"),
    ("no_sim", "no_sim_lama", "no_sim_baru"),
)


def format_id(id_personel):
    return f"{int(id_personel):03d}"


def format_nama_personel(id_personel, nama):
    """`ID 014 · Nama`."""
    return f"ID {format_id(id_personel)} · {nama}"


def nik_valid(nik):
    """NIK Personel: 5-16 karakter, boleh berisi huruf, angka, dan strip."""
    return bool(nik) and re.fullmatch(r"[A-Za-z0-9-]{5,16}", nik) is not None


def nik_akun_valid(nik):
    """NIK akun pengguna: 5-16 karakter, boleh berisi huruf, angka, dan strip."""
    return bool(nik) and re.fullmatch(r"[A-Za-z0-9-]{5,16}", nik) is not None

def validasi_personel(nik, nama, kategori, no_sim, kategori_valid=KATEGORI_VALID, wajib_sim=WAJIB_SIM):
    """Kembalikan pesan error, atau None kalau data valid. kategori = jenis orang (utils/jenis_orang.py)."""
    if not nik or not nama:
        return "NIK dan nama wajib diisi"
    if not nik_valid(nik):
        return "NIK harus 5-16 karakter: huruf, angka, atau strip"
    if kategori not in kategori_valid:
        return "Jenis orang tidak valid"
    if kategori in wajib_sim and not no_sim:
        return f"No. SIM wajib untuk {kategori}"
    return None


def daftar_perubahan(row):
    """Kolom yang berubah pada satu baris personel_audit_logs -> [(kolom, lama, baru)]."""
    hasil = []
    for kolom, lama, baru in KOLOM_AUDIT:
        v_lama, v_baru = row.get(lama), row.get(baru)
        if (v_lama or None) != (v_baru or None):
            hasil.append((kolom, v_lama, v_baru))
    return hasil
