"""Jenis orang (pengganti tabel kategori): dibaca dari relasi data, tidak disimpan di Users.

- KARYAWAN: punya jabatan (Users.UserLevelID), termasuk Security & BHL lewat departemen / jabatannya;
- DRIVER:   visitor (Users.GuestID) yang punya SIM aktif (LicenseDetail);
- TAMU:     visitor tanpa SIM.
Di database: view dbo.UserProfile.PersonType. Blacklist & Alur Persetujuan menyimpan kodenya sebagai jenis target."""

JENIS = {
    "KARYAWAN": {"kode": "KARYAWAN", "nama": "Karyawan", "wajib_sim": False, "prefix_kode": "KRY", "boleh_akun": True},
    "DRIVER": {"kode": "DRIVER", "nama": "Supir", "wajib_sim": True, "prefix_kode": "DRV", "boleh_akun": False},
    "TAMU": {"kode": "TAMU", "nama": "Tamu", "wajib_sim": False, "prefix_kode": "TMU", "boleh_akun": False},
}
VISITOR = ("DRIVER", "TAMU")


def nama(kode):
    return (JENIS.get(kode or "") or {}).get("nama", kode or "-")


def sql_nama(kolom):
    """Ekspresi SQL nama jenis dari kolom kode, mis. sql_nama('p.PersonType')."""
    return "CASE " + kolom + "".join(f" WHEN '{k}' THEN N'{v['nama']}'" for k, v in JENIS.items()) + " END"
