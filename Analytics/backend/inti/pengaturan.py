"""Pengaturan yang diubah admin dari aplikasi (saat ini batas idle), disimpan di berkas JSON supaya tetap setelah server dimulai ulang."""
import json
import logging
import threading
from pathlib import Path

log = logging.getLogger("dashboard")

IDLE_MAKS_MENIT = 24 * 60


class DataTidakValid(ValueError):
    pass


def periksa_idle(menit):
    if isinstance(menit, bool) or not isinstance(menit, (int, float)) or menit != int(menit) or not 0 <= menit <= IDLE_MAKS_MENIT:
        raise DataTidakValid(f"Batas idle harus bilangan bulat 0 sampai {IDLE_MAKS_MENIT} menit (0 = tidak ada batas).")
    return int(menit)


class Pengaturan:
    """bawaan: dipakai kalau berkas belum ada atau tidak terbaca."""

    def __init__(self, berkas, bawaan):
        self.berkas, self.bawaan = Path(berkas), dict(bawaan)
        self._kunci = threading.Lock()

    def baca(self):
        try:
            isi = json.loads(self.berkas.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return dict(self.bawaan)
        except (OSError, ValueError) as e:
            log.warning("Berkas pengaturan %s tidak terbaca, memakai nilai bawaan: %s", self.berkas, e)
            return dict(self.bawaan)
        return {**self.bawaan, **(isi if isinstance(isi, dict) else {})}

    def simpan(self, **ubah):
        """Ditulis lewat berkas sementara supaya tidak pernah setengah tertulis."""
        with self._kunci:
            isi = {**self.baca(), **ubah}
            self.berkas.parent.mkdir(parents=True, exist_ok=True)
            sementara = self.berkas.with_suffix(".tmp")
            sementara.write_text(json.dumps(isi, indent=2), encoding="utf-8")
            sementara.replace(self.berkas)
            return isi
