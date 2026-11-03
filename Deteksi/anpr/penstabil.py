from collections import defaultdict
from dataclasses import dataclass, field


def jarak_edit(a, b):
    sebelum = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        sekarang = [i]
        for j, cb in enumerate(b, 1):
            sekarang.append(min(sebelum[j] + 1, sekarang[j - 1] + 1, sebelum[j - 1] + (ca != cb)))
        sebelum = sekarang
    return sebelum[-1]


@dataclass
class PlatTerbaca:
    plat: str
    waktu: float
    jumlah_frame: int
    conf_ocr: float
    kandidat_lain: dict = field(default_factory=dict)  # plat lain di jendela yang sama -> jumlah
    bacaan_terbaik: object = None                     # Bacaan dengan conf_ocr tertinggi
    frame_terbaik: object = None


class PenstabilPlat:
    MAKS_BEDA_MIRIP = 2

    def __init__(self, min_frame=3, jendela_detik=5.0, jeda_ulang_detik=60.0):
        self.min_frame = min_frame
        self.jendela_detik = jendela_detik
        self.jeda_ulang_detik = jeda_ulang_detik
        self._riwayat = []    # (waktu, plat, conf) bacaan diterima dalam jendela
        self._terbaik = {}    # plat -> (conf, bacaan, frame): hanya frame terbaik yang disimpan (hemat RAM)
        self._diredam = {}    # plat yang sudah dilaporkan -> waktu terakhir terlihat

    def _plat_redam(self, plat):
        """Plat yang sudah dilaporkan dan mirip dengan `plat`, atau None."""
        for p in self._diredam:
            if jarak_edit(p, plat) <= self.MAKS_BEDA_MIRIP:
                return p
        return None

    def sudah_dilaporkan(self, plat):
        return self._plat_redam(plat) is not None

    def tambah(self, waktu, bacaan_list, frame):
        """Masukkan bacaan satu frame. Return daftar PlatTerbaca yang baru saja pasti."""
        self._diredam = {p: t for p, t in self._diredam.items() if waktu - t < self.jeda_ulang_detik}
        for b in bacaan_list:
            if not b.diterima:
                continue
            redam = self._plat_redam(b.plat)
            if redam:
                self._diredam[redam] = waktu  # kendaraan masih di tempat: perpanjang redaman
            else:
                self._riwayat.append((waktu, b.plat, b.conf_ocr))
                if b.conf_ocr > self._terbaik.get(b.plat, (-1,))[0]:
                    self._terbaik[b.plat] = (b.conf_ocr, b, frame.copy())
        self._riwayat = [r for r in self._riwayat
                         if waktu - r[0] <= self.jendela_detik and not self._plat_redam(r[1])]
        ada = {r[1] for r in self._riwayat}
        self._terbaik = {p: v for p, v in self._terbaik.items() if p in ada}

        hitung = defaultdict(list)
        for r in self._riwayat:
            hitung[r[1]].append(r)
        if not hitung:
            return []

        plat, daftar = max(hitung.items(), key=lambda x: len(x[1]))
        if len(daftar) < self.min_frame:
            return []
        _, bacaan, frame_terbaik = self._terbaik[plat]
        mirip = {p: len(d) for p, d in hitung.items()
                 if p != plat and jarak_edit(p, plat) <= self.MAKS_BEDA_MIRIP}
        self._diredam[plat] = waktu
        self._riwayat = [r for r in self._riwayat if r[1] != plat and r[1] not in mirip]
        return [PlatTerbaca(plat, waktu, len(daftar), sum(r[2] for r in daftar) / len(daftar),
                            mirip, bacaan, frame_terbaik)]
