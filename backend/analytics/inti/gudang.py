"""Data laporan di memori, dan pemuatannya dari SQL Server di latar belakang.

Setiap data dan pekerjaan punya pemilik (sesi login); hanya pemilik yang bisa membacanya. Data yang masih segar (DATA_SEGAR_MENIT) bisa
dipakai sesi lain tanpa memuat ulang dari SQL; data tanpa pemilik disimpan selama masih segar, lalu dibuang.
Data yang diganti hasil muat ulang tetap bisa diminta dengan id lamanya (alias).
"""
import logging
import os
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
DATA_SEGAR_DETIK = konfigurasi.DATA_SEGAR_MENIT * 60
PESAN_BATAL = "Pemuatan dibatalkan."

# Pesan untuk pengguna saat pemuatan gagal. Rincian teknisnya tetap dicatat lengkap di log server.
# Sengaja "ERP", bukan nama produknya, karena ERP-nya bisa berganti. Istilah teknis lain (database, linked server) tidak dipakai.
PESAN_ERP = "Koneksi ke Ascend terputus. Coba lagi nanti."
PESAN_LOGIN_ERP = "Akses ke Ascend ditolak. Hubungi tim IT."
PESAN_DATABASE = "Server laporan tidak bisa dihubungi. Coba lagi nanti."
PESAN_AKSES = "Laporan ini belum bisa dibuka. Hubungi tim IT."
PESAN_LAMA = "Terlalu lama memuat. Coba rentang tanggal lebih pendek."
PESAN_KOSONG = "Tidak ada data di tanggal ini."
PESAN_UMUM = "Terjadi kesalahan. Coba lagi nanti."

_TANDA_JARINGAN = ("tcp provider", "login timeout", "network-related", "not accessible", "10060", "08001", "08s01",
                   "communication link failure", "physical connection is not usable", "unable to open a logical session")


def pesan_galat(e):
    """Satu kalimat yang bisa dipahami pengguna untuk galat pemuatan, menurut jenis galatnya."""
    t = str(e).lower()
    if isinstance(e, RuntimeError) and t.startswith("tidak ada data"):
        return PESAN_KOSONG
    if isinstance(e, RuntimeError) and t.startswith("belum ada rekening bank"):
        return str(e)                                   # pesan yang memang ditulis untuk pengguna (Kas & Bank)
    jaringan = any(k in t for k in _TANDA_JARINGAN)
    if jaringan and ("linked server" in t or "7412" in t or "7303" in t):
        return PESAN_ERP                                # SQL Server Main hidup, tapi server ERP (linked server) tidak terjangkau
    if "18456" in t or "login failed" in t:
        # Login yang ditolak bukan akun aplikasi (DB_USER) berarti akun linked server ke ERP, mis. password-nya diganti di ERP
        akun_app = os.environ.get("DB_USER", "").strip().lower()
        return PESAN_DATABASE if akun_app and f"'{akun_app}'" in t else PESAN_LOGIN_ERP
    if jaringan or "4060" in t:
        return PESAN_DATABASE
    if "permission" in t or "(229)" in t or "could not find stored procedure" in t or "belum ada di database main" in t:
        return PESAN_AKSES
    if "hyt00" in t or "query timeout" in t:
        return PESAN_LAMA
    return PESAN_UMUM


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
    def __init__(self, maks_dataset=MAKS_DATASET, segar_detik=DATA_SEGAR_DETIK):
        self.kunci = threading.Lock()
        self.maks_dataset = maks_dataset
        self.segar_detik = segar_detik
        self.tersimpan = set()         # kunci data yang ditinggal semua sesinya tapi disimpan selama masih segar
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

        Data yang ada dipakai ulang oleh sesi yang sudah memilikinya, dan oleh sesi lain (termasuk setelah login ulang) selama masih segar;
        selebihnya dimuat dari SQL, dan hasilnya menggantikan data lama periode itu. Pemuatan yang sama yang sedang berjalan dibagi, bukan diulang.
        segarkan=True selalu memuat dari SQL; data lama tetap dilayani sampai yang baru siap."""
        pemilik_baru = {pemilik} if pemilik is not None else set()
        with self.kunci:
            self._buang_basi()
            ada = self.dataset.get((laporan, mulai, akhir))
            if ada and not segarkan and (pemilik is None or pemilik in ada.pemilik or self._segar(ada)):
                ada.pemilik |= pemilik_baru
                self.dataset.move_to_end((laporan, mulai, akhir))
                self._lepas_periode_lain(laporan, (laporan, mulai, akhir), pemilik_baru)
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
                self._lepas_periode_lain(p.laporan, kunci_data, d.pemilik)
                while len(self.dataset) > self.maks_dataset:
                    self.dataset.popitem(last=False)
                self._rapikan_alias()
            p.data_id = d.id
            p.status = "selesai"
            log.info("Data %s %s..%s dimuat: %d baris dalam %.1f detik", p.laporan, p.mulai, p.akhir, len(df), time.time() - p.dibuat)
        except Dibatalkan:
            p.status, p.pesan = "dibatalkan", PESAN_BATAL
        except Exception as e:  # noqa: BLE001
            log.exception("Gagal memuat data %s", p.laporan)
            if p.kendali.dibatalkan:
                p.status, p.pesan = "dibatalkan", PESAN_BATAL
            else:
                p.status = "gagal"
                p.pesan = pesan_galat(e)
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

    def status_pemilik(self, pemilik):
        """{laporan: "memuat" | "siap"} untuk sesi ini: memuat = ada pemuatan berjalan, siap = ada data yang sudah dimuat."""
        with self.kunci:
            hasil = {d.laporan: "siap" for d in self.dataset.values() if pemilik in d.pemilik}
            for p in self.pekerjaan.values():
                if p.status == "berjalan" and pemilik in p.pemilik:
                    hasil[p.laporan] = "memuat"
            return hasil

    def lepas(self, pemilik):
        """Sesi berakhir: pemuatan yang tidak punya pemilik lagi dihentikan, data yang tidak punya pemilik lagi dibuang kecuali masih segar
        (disimpan untuk login berikutnya, dibuang setelah basi). Mengembalikan (data dihapus, pemuatan dihentikan)."""
        hentikan, dihapus = [], 0
        with self.kunci:
            for kunci in [k for k, d in self.dataset.items() if pemilik in d.pemilik]:
                d = self.dataset[kunci]
                d.pemilik.discard(pemilik)
                if not d.pemilik:
                    if self._segar(d):
                        self.tersimpan.add(kunci)
                    else:
                        del self.dataset[kunci]
                        dihapus += 1
            dihapus += self._buang_basi()
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

    def _lepas_periode_lain(self, laporan, kunci_baru, pemilik):
        """Di dalam kunci. Tiap sesi hanya menyimpan satu periode per laporan: setelah periode baru siap, periode lain laporan itu dilepas
        sesi-sesi ini, dan dibuang kalau tidak ada sesi lain yang memakainya. Kembali ke periode lama berarti memuat ulang dari SQL.
        Dilepas setelah data baru siap (bukan saat mulai memuat), supaya kalau pemuatan gagal atau dibatalkan tampilan lama tetap jalan."""
        if not pemilik:
            return
        for kunci in [k for k, d in self.dataset.items() if d.laporan == laporan and k != kunci_baru and d.pemilik & pemilik]:
            d = self.dataset[kunci]
            d.pemilik -= pemilik
            if not d.pemilik:
                del self.dataset[kunci]
                log.info("Data %s %s..%s dibuang: diganti periode lain", d.laporan, d.mulai, d.akhir)
        self._rapikan_alias()

    def _segar(self, d):
        """Di dalam kunci. Data boleh dipakai sesi lain tanpa memuat ulang dari SQL."""
        return self.segar_detik > 0 and (datetime.now() - d.dimuat_pada).total_seconds() < self.segar_detik

    def _buang_basi(self):
        """Di dalam kunci. Data yang ditinggal semua sesinya (lepas) dibuang setelah tidak segar lagi. Mengembalikan jumlahnya."""
        basi = []
        for k in list(self.tersimpan):
            d = self.dataset.get(k)
            if d is None or d.pemilik:          # sudah dibuang, atau dipakai sesi baru
                self.tersimpan.discard(k)
            elif not self._segar(d):
                basi.append(k)
        for k in basi:
            del self.dataset[k]
            self.tersimpan.discard(k)
        if basi:
            self._rapikan_alias()
        return len(basi)

    def _rapikan_alias(self):
        """Di dalam kunci."""
        ada = {d.id for d in self.dataset.values()}
        self.alias = {k: v for k, v in self.alias.items() if v in ada}

    def _bersihkan_pekerjaan(self):
        batas = time.time() - SIMPAN_PEKERJAAN_DETIK
        for pid in [k for k, v in self.pekerjaan.items() if v.selesai_pada and v.selesai_pada < batas]:
            del self.pekerjaan[pid]
