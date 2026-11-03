"""Sesi login (di memori, hilang saat server dimulai ulang) dan pembatas percobaan login."""
import hashlib
import logging
import secrets
import threading
import time
from datetime import datetime

log = logging.getLogger("dashboard")


class Sesi:
    """Cookie hanya berisi kode acak; pemiliknya hanya diketahui server.

    saat_berakhir(kode, username) dipanggil di luar kunci setiap kali sesi dibuang (keluar, kedaluwarsa, dicabut).
    tunggal=True: login baru mengakhiri sesi lama akun yang sama, dan perangkat lama diberi tahu sebabnya lewat alasan(kode).
    idle_detik (atribut idle, bisa diubah saat berjalan): sesi berakhir kalau tidak ada permintaan selama itu; 0 = tanpa batas."""

    def __init__(self, umur_detik=8 * 3600, jam=time.time, saat_berakhir=None, tunggal=False, idle_detik=0):
        self.umur = umur_detik
        self.idle = idle_detik
        self._jam = jam
        self._saat_berakhir = saat_berakhir
        self._tunggal = tunggal
        self._kunci = threading.Lock()
        self._data = {}   # kode -> (username, waktu_kedaluwarsa)
        self._alasan = {}  # kode sesi yang diakhiri paksa -> (waktu, pesan)
        self._info = {}    # kode -> {masuk, terakhir, asal}

    def _umumkan(self, berakhir):
        if not self._saat_berakhir:
            return
        for kode, username in berakhir:
            try:
                self._saat_berakhir(kode, username)
            except Exception:  # noqa: BLE001 - tidak boleh menggagalkan login atau logout
                log.exception("Gagal membersihkan data sesi %s", username)

    def _milik(self, username):
        """Di dalam kunci: [(kode, username)] semua sesi akun ini."""
        kecil = str(username).lower()
        return [(k, u) for k, (u, _) in self._data.items() if str(u).lower() == kecil]

    def buat(self, username, asal=None):
        """asal (mis. "IP 172.20.1.5") ikut dalam pesan untuk perangkat yang digantikan."""
        kode = secrets.token_urlsafe(32)
        with self._kunci:
            lama = self._buang_kedaluwarsa()
            diganti = []
            if self._tunggal:
                diganti = self._milik(username)
                sekarang = self._jam()
                pesan = (f"Akun ini baru saja masuk di perangkat lain{f' ({asal})' if asal else ''} pukul "
                         f"{datetime.fromtimestamp(sekarang).strftime('%H:%M')}, jadi sesi di perangkat ini diakhiri. Masuk lagi untuk memakainya di sini.")
                for k, _ in diganti:
                    del self._data[k]
                    self._alasan[k] = (sekarang, pesan)
                self._rapikan_alasan()
            self._data[kode] = (username, self._jam() + self.umur)
            self._info[kode] = {"masuk": self._jam(), "terakhir": self._jam(), "asal": asal}
            self._rapikan_info()
        self._umumkan(lama + diganti)
        return kode

    def alasan(self, kode):
        """Kenapa sesi ini diakhiri paksa, atau None."""
        with self._kunci:
            item = self._alasan.get(kode)
            return item[1] if item else None

    def _rapikan_alasan(self):
        """Di dalam kunci: alasan disimpan paling lama sehari, paling banyak 1000."""
        batas = self._jam() - 24 * 3600
        for k in [k for k, (w, _) in self._alasan.items() if w < batas]:
            del self._alasan[k]
        while len(self._alasan) > 1000:
            del self._alasan[next(iter(self._alasan))]

    def ambil(self, kode):
        """Username pemilik sesi (sekaligus mencatat aktivitas terakhirnya), atau None."""
        if not kode:
            return None
        with self._kunci:
            item = self._data.get(kode)
            if item is None:
                return None
            if item[1] > self._jam() and not self._idle_habis(kode):
                if kode in self._info:
                    self._info[kode]["terakhir"] = self._jam()
                return item[0]
            if self._idle_habis(kode):
                self._alasan[kode] = (self._jam(), self._pesan_idle())
            del self._data[kode]
        self._umumkan([(kode, item[0])])
        return None

    def masih_ada(self, kode):
        """Seperti ambil, tetapi tidak mencatat aktivitas (untuk pekerjaan latar belakang) dan tidak mengakhiri sesi."""
        with self._kunci:
            item = self._data.get(kode)
            return item[0] if item and item[1] > self._jam() and not self._idle_habis(kode) else None

    def _idle_habis(self, kode):
        info = self._info.get(kode)
        return bool(self.idle and info and self._jam() - info["terakhir"] >= self.idle)

    def _pesan_idle(self):
        menit = round(self.idle / 60)
        return f"Anda keluar otomatis karena tidak ada aktivitas selama {menit} menit. Masuk lagi untuk melanjutkan."

    def hapus(self, kode):
        if not kode:
            return
        with self._kunci:
            item = self._data.pop(kode, None)
        if item is not None:
            self._umumkan([(kode, item[0])])

    def cabut(self, username, alasan=None):
        """Akhiri semua sesi akun ini (mis. akunnya dihapus). alasan ditampilkan di perangkat yang dikeluarkan."""
        with self._kunci:
            kena = self._milik(username)
            for kode, _ in kena:
                del self._data[kode]
                if alasan:
                    self._alasan[kode] = (self._jam(), alasan)
            self._rapikan_alasan()
        self._umumkan(kena)

    def bersihkan(self):
        """Buang sesi kedaluwarsa, termasuk yang tidak pernah diakses lagi. Mengembalikan jumlahnya."""
        with self._kunci:
            lama = self._buang_kedaluwarsa()
        self._umumkan(lama)
        return len(lama)

    def _buang_kedaluwarsa(self):
        """Di dalam kunci. Mengembalikan [(kode, username)] yang dibuang."""
        sekarang = self._jam()
        kena = [(k, u) for k, (u, e) in self._data.items() if e <= sekarang or self._idle_habis(k)]
        for k, _ in kena:
            if self._idle_habis(k):
                self._alasan[k] = (sekarang, self._pesan_idle())
            del self._data[k]
        return kena

    @staticmethod
    def id_sesi(kode):
        """Pengenal untuk tampilan admin; kode sesi asli tidak pernah dikirim ke browser."""
        return hashlib.sha256(str(kode).encode()).hexdigest()[:16]

    def _rapikan_info(self):
        for k in [k for k in self._info if k not in self._data]:
            del self._info[k]

    def daftar(self):
        """Sesi yang masih berlaku, yang terakhir masuk lebih dulu. Waktu dalam detik epoch."""
        with self._kunci:
            lama = self._buang_kedaluwarsa()
            self._rapikan_info()
            hasil = [{"id": self.id_sesi(k), "username": u, "kedaluwarsa": e, **self._info.get(k, {"masuk": None, "terakhir": None, "asal": None})}
                     for k, (u, e) in self._data.items()]
        self._umumkan(lama)
        return sorted(hasil, key=lambda s: s["masuk"] or 0, reverse=True)

    def cabut_id(self, id_sesi, alasan=None):
        """id dari daftar(). Mengembalikan username pemiliknya, atau None kalau sesi itu sudah tidak ada."""
        with self._kunci:
            kode = next((k for k in self._data if self.id_sesi(k) == id_sesi), None)
            if kode is None:
                return None
            username, _ = self._data.pop(kode)
            self._info.pop(kode, None)
            if alasan:
                self._alasan[kode] = (self._jam(), alasan)
                self._rapikan_alasan()
        self._umumkan([(kode, username)])
        return username


class PembatasLogin:
    """Setelah `maks` kali gagal dalam `jendela` detik, kunci itu ditahan sementara."""

    def __init__(self, maks=5, jendela=300, jam=time.time):
        self.maks, self.jendela, self._jam = maks, jendela, jam
        self._kunci = threading.Lock()
        self._gagal = {}   # username -> [waktu gagal]

    def _segar(self, kunci):
        batas = self._jam() - self.jendela
        daftar = [t for t in self._gagal.get(kunci, []) if t > batas]
        if daftar:
            self._gagal[kunci] = daftar
        else:
            self._gagal.pop(kunci, None)
        return daftar

    def sisa_tunggu(self, kunci):
        """Detik yang harus ditunggu; 0 kalau tidak sedang ditahan."""
        with self._kunci:
            daftar = self._segar(kunci)
            if len(daftar) < self.maks:
                return 0
            return max(1, int(round(daftar[0] + self.jendela - self._jam())))

    def gagal(self, kunci):
        with self._kunci:
            if len(self._gagal) > 5000:     # username acak tidak boleh membengkakkan memori
                for k in list(self._gagal):
                    self._segar(k)
            self._gagal.setdefault(kunci, []).append(self._jam())

    def berhasil(self, kunci):
        with self._kunci:
            self._gagal.pop(kunci, None)
