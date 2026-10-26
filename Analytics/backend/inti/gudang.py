"""Data laporan di memori, dan pemuatannya dari SQL Server di latar belakang.

Setiap data dan pekerjaan punya pemilik (sesi login); hanya pemilik yang bisa membacanya. Saat sesi berakhir, lepas(pemilik) membuang data
yang tidak punya pemilik lagi. Data yang diganti hasil muat ulang tetap bisa diminta dengan id lamanya (alias).
"""
import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import datetime

from . import konfigurasi

log = logging.getLogger("dashboard")

MAKS_DATASET = konfigurasi.MAKS_DATASET
SIMPAN_PEKERJAAN_DETIK = konfigurasi.SIMPAN_PEKERJAAN_DETIK
PESAN_BATAL = "Pemuatan dibatalkan."


class Dibatalkan(Exception):
    pass


class KendaliBatal:
    """Menghubungkan tombol Batalkan dengan query SQL yang sedang berjalan."""

    def __init__(self):
        self._batal = threading.Event()
        self._kunci = threading.Lock()
        self._kursor = []

    @property
    def dibatalkan(self):
        return self._batal.is_set()

    def periksa(self):
        if self._batal.is_set():
            raise Dibatalkan()

    def daftarkan(self, kursor):
        """Kursor yang terdaftar bisa dihentikan dari thread lain."""
        with self._kunci:
            self._kursor.append(kursor)
        if self._batal.is_set():
            self._hentikan(kursor)
            raise Dibatalkan()

    @staticmethod
    def _hentikan(kursor):
        try:
            cancel = getattr(kursor, "cancel", None)
            if cancel:
                cancel()
        except Exception:  # noqa: BLE001
            log.warning("Kursor tidak bisa dibatalkan, hasilnya akan dibuang saja", exc_info=True)

    def batalkan(self):
        self._batal.set()
        with self._kunci:
            kursor = list(self._kursor)
        for k in kursor:
            self._hentikan(k)


@dataclass
class Dataset:
    id: str
    laporan: str
    mulai: str      # YYYY-MM-DD
    akhir: str
    df: object
    dimuat_pada: datetime
    catatan: dict = field(default_factory=dict)
    terakhir_dipakai: float = field(default_factory=time.time)
    hasil: dict = field(default_factory=dict)   # cache hasil per kombinasi filter
    pemilik: set = field(default_factory=set)


@dataclass
class Pekerjaan:
    id: str
    laporan: str
    mulai: str
    akhir: str
    status: str = "berjalan"   # berjalan, selesai, gagal, dibatalkan
    pesan: str = ""
    data_id: str | None = None
    dibuat: float = field(default_factory=time.time)
    selesai_pada: float | None = None
    kendali: KendaliBatal = field(default_factory=KendaliBatal)
    pemilik: set = field(default_factory=set)   # sesi yang menunggu hasilnya
    berpemilik: bool = False                    # False hanya di tes tanpa pemilik

    def ringkas(self):
        akhir = self.selesai_pada or time.time()
        return {
            "id": self.id,
            "laporan": self.laporan,
            "mulai": self.mulai,
            "akhir": self.akhir,
            "status": self.status,
            "pesan": self.pesan,
            "data_id": self.data_id,
            "detik": round(akhir - self.dibuat, 1),
        }


class Gudang:
    def __init__(self, maks_dataset=MAKS_DATASET):
        self.kunci = threading.Lock()
        self.maks_dataset = maks_dataset
        self.dataset = OrderedDict()   # (laporan, mulai, akhir) -> Dataset
        self.pekerjaan = {}            # id -> Pekerjaan
        self.alias = {}                # id data lama -> id data yang menggantikannya

    def cari_dataset(self, laporan, mulai, akhir):
        with self.kunci:
            d = self.dataset.get((laporan, mulai, akhir))
            if d:
                d.terakhir_dipakai = time.time()
                self.dataset.move_to_end((laporan, mulai, akhir))
            return d

    def ambil(self, data_id, pemilik=None):
        """None kalau tidak ada, atau kalau pemilik diberikan dan bukan pemiliknya."""
        with self.kunci:
            data_id = self.alias.get(data_id, data_id)
            for d in self.dataset.values():
                if d.id == data_id:
                    if pemilik is not None and pemilik not in d.pemilik:
                        return None
                    d.terakhir_dipakai = time.time()
                    return d
        return None

    def ambil_pekerjaan(self, pid, pemilik=None):
        with self.kunci:
            p = self.pekerjaan.get(pid)
            if p is not None and pemilik is not None and pemilik not in p.pemilik:
                return None
            return p

    def mulai_muat(self, laporan, mulai, akhir, pemuat, pemilik=None, segarkan=False):
        """pemuat(mulai, akhir, kendali) -> (DataFrame, catatan).

        Data yang ada hanya dipakai ulang oleh sesi yang sudah memilikinya; sesi lain (termasuk setelah login ulang) selalu memuat dari SQL,
        dan hasilnya menggantikan data lama periode itu. Pemuatan yang sama yang sedang berjalan dibagi, bukan diulang.
        segarkan=True selalu memuat dari SQL; data lama tetap dilayani sampai yang baru siap."""
        pemilik_baru = {pemilik} if pemilik is not None else set()
        with self.kunci:
            ada = self.dataset.get((laporan, mulai, akhir))
            if ada and not segarkan and (pemilik is None or pemilik in ada.pemilik):
                self.dataset.move_to_end((laporan, mulai, akhir))
                p = Pekerjaan(uuid.uuid4().hex[:12], laporan, mulai, akhir, "selesai", "Memakai data yang sudah dimuat", ada.id, pemilik=set(pemilik_baru))
                p.selesai_pada = p.dibuat
                self.pekerjaan[p.id] = p
                return p
            for p in self.pekerjaan.values():
                if p.status == "berjalan" and (p.laporan, p.mulai, p.akhir) == (laporan, mulai, akhir):
                    p.pemilik |= pemilik_baru
                    return p
            p = Pekerjaan(uuid.uuid4().hex[:12], laporan, mulai, akhir, pemilik=set(pemilik_baru), berpemilik=pemilik is not None)
            self.pekerjaan[p.id] = p
            self._bersihkan_pekerjaan()
        threading.Thread(target=self._jalankan, args=(p, pemuat), daemon=True).start()
        return p

    def _jalankan(self, p, pemuat):
        try:
            df, catatan = pemuat(p.mulai, p.akhir, p.kendali)
            p.kendali.periksa()
            d = Dataset(uuid.uuid4().hex[:12], p.laporan, p.mulai, p.akhir, df, datetime.now(), catatan or {})
            with self.kunci:
                if p.berpemilik and not p.pemilik:
                    raise Dibatalkan()                  # semua yang menunggu sudah keluar
                d.pemilik = set(p.pemilik)
                kunci_data = (p.laporan, p.mulai, p.akhir)
                lama = self.dataset.get(kunci_data)
                if lama is not None:
                    d.pemilik |= lama.pemilik
                    for k, v in self.alias.items():
                        if v == lama.id:
                            self.alias[k] = d.id        # alias tidak pernah berantai
                    self.alias[lama.id] = d.id
                self.dataset[kunci_data] = d
                self.dataset.move_to_end(kunci_data)
                while len(self.dataset) > self.maks_dataset:
                    self.dataset.popitem(last=False)
                self._rapikan_alias()
            p.data_id = d.id
            p.status = "selesai"
            log.info("Data %s %s..%s dimuat: %d baris dalam %.1f detik", p.laporan, p.mulai, p.akhir, len(df), time.time() - p.dibuat)
        except Dibatalkan:
            p.status, p.pesan = "dibatalkan", PESAN_BATAL
        except Exception:  # noqa: BLE001
            log.exception("Gagal memuat data %s", p.laporan)
            if p.kendali.dibatalkan:
                p.status, p.pesan = "dibatalkan", PESAN_BATAL
            else:
                p.status = "gagal"
                p.pesan = "Gagal mengambil data dari SQL Server. Rincian ada di terminal server."
        finally:
            p.selesai_pada = time.time()

    def batalkan(self, pid, pemilik=None):
        """Dengan pemilik, hanya sesi itu yang berhenti menunggu; query baru dihentikan kalau tidak ada lagi yang menunggu.
        Kalau pemuatan berlanjut untuk sesi lain, yang dikembalikan salinan berstatus dibatalkan."""
        with self.kunci:
            p = self.pekerjaan.get(pid)
            if p is None or (pemilik is not None and pemilik not in p.pemilik):
                return None
            masih = p.status == "berjalan"
            sisa = p.pemilik - {pemilik} if pemilik is not None else set()
            berhenti = not sisa
            if masih and berhenti:
                p.status, p.pesan, p.selesai_pada = "dibatalkan", PESAN_BATAL, time.time()
            elif masih:
                p.pemilik = sisa
        if masih and berhenti:
            p.kendali.batalkan()                            # di luar kunci
        elif masih:
            return replace(p, status="dibatalkan", pesan=PESAN_BATAL, selesai_pada=time.time(), pemilik=set())
        return p

    def lepas(self, pemilik):
        """Sesi berakhir: data dan pemuatan yang tidak punya pemilik lagi dibuang. Mengembalikan (data dihapus, pemuatan dihentikan)."""
        hentikan, dihapus = [], 0
        with self.kunci:
            for kunci in [k for k, d in self.dataset.items() if pemilik in d.pemilik]:
                d = self.dataset[kunci]
                d.pemilik.discard(pemilik)
                if not d.pemilik:
                    del self.dataset[kunci]
                    dihapus += 1
            for pid in [k for k, p in self.pekerjaan.items() if pemilik in p.pemilik]:
                p = self.pekerjaan[pid]
                p.pemilik.discard(pemilik)
                if not p.pemilik:
                    if p.status == "berjalan":
                        p.status, p.pesan, p.selesai_pada = "dibatalkan", PESAN_BATAL, time.time()
                        hentikan.append(p)
                    del self.pekerjaan[pid]
            self._rapikan_alias()
        for p in hentikan:
            p.kendali.batalkan()
        return dihapus, len(hentikan)

    def _rapikan_alias(self):
        """Di dalam kunci."""
        ada = {d.id for d in self.dataset.values()}
        self.alias = {k: v for k, v in self.alias.items() if v in ada}

    def _bersihkan_pekerjaan(self):
        batas = time.time() - SIMPAN_PEKERJAAN_DETIK
        for pid in [k for k, v in self.pekerjaan.items() if v.selesai_pada and v.selesai_pada < batas]:
            del self.pekerjaan[pid]
