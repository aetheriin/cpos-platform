"""Kumpulan (pool) koneksi database milik aplikasi: koneksi dipakai ulang, bolak-balik ke server dihemat.

Kenapa: server CPOS sering jauh dari SQL Server (cabang <-> HO lewat VPN), jadi yang membuat lambat bukan query yang
berat melainkan jumlah bolak-balik. Cara lama tiap fungsi: buka koneksi + set pengguna (sp_set_session_context) +
query + tutup (rollback & lepas cursor) = 3-4 bolak-balik, ditambah buka koneksi baru 150-300 ms bila pool driver
sudah melepasnya. Di sini:
- koneksi fisik disimpan & dipakai ulang (yang terakhir dikembalikan dipakai lebih dulu), dibuang bila menganggur
  terlalu lama atau putus (dicoba ulang otomatis sekali dengan koneksi baru);
- data pengguna untuk log perubahan (SESSION_CONTEXT, trigger migrasi 034) ditempel di depan query pertama,
  jadi ikut satu kali kirim, dan hanya dikirim bila berbeda dengan isi koneksi itu sekarang;
- transaksi baca yang tersisa ditutup (rollback) oleh petugas latar kolam, bukan oleh request;
- satu cursor per koneksi fisik dipakai ulang (membuat/menutup cursor berparameter = 1 bolak-balik tambahan).

Bagi kode lain tidak ada yang berubah: get_connection() / cursor() / execute / fetch* / commit / rollback / close
berperilaku seperti pyodbc. close() tetap menjamin perubahan yang belum di-commit dibatalkan:
- hanya membaca (SELECT): tidak ada yang perlu dibatalkan; transaksi bacanya ditutup petugas latar kolam
  (ROLLBACK tidak bisa ditempel di query berparameter: SQL Server menolak, error 266);
- sudah menulis tanpa commit (mis. jalur error): langsung di-rollback saat close(), seperti cara lama."""
import logging
import re
import threading
import time

import pyodbc

log = logging.getLogger(__name__)

MAKS_DIAM = 16                  # koneksi menganggur yang disimpan
BATAS_DIAM_DETIK = 300          # menganggur lebih lama -> dibuang (VPN / firewall sering memutus koneksi diam)
UMUR_MAKS_DETIK = 1800          # koneksi fisik diganti setelah 30 menit
KODE_PUTUS = ("08S01", "08S02", "08003", "08007", "08001", "HYT00", "01000")

_POLA_BACA = re.compile(r"^\s*(SET\s+NOCOUNT\s+ON\s*;\s*)?(SELECT|WITH)\b", re.I)
_POLA_TULIS = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|EXEC|EXECUTE|TRUNCATE|DROP|ALTER|CREATE)\b", re.I)
_POLA_IP = re.compile(r"[^0-9A-Fa-f.:]")


def _hanya_baca(sql):
    return bool(_POLA_BACA.match(sql)) and not _POLA_TULIS.search(sql)


def _awalan_konteks(konteks):
    """Teks SQL pengisi SESSION_CONTEXT (id_user, ip). Nilai disaring jadi angka / karakter IP, aman ditempel."""
    if konteks is None:
        return "EXEC sp_set_session_context N'id_user', NULL; EXEC sp_set_session_context N'ip', NULL; "
    id_user, ip = konteks
    ip = _POLA_IP.sub("", ip or "")[:45]
    return (f"EXEC sp_set_session_context N'id_user', {int(id_user)}; "
            f"EXEC sp_set_session_context N'ip', {f'N{chr(39)}{ip}{chr(39)}' if ip else 'NULL'}; ")


class _Fisik:
    """Satu koneksi pyodbc sungguhan + cursor yang dipakai ulang + status yang perlu ditempel di query berikutnya."""
    __slots__ = ("conn", "cur", "konteks", "perlu_rollback", "lahir", "terakhir")

    def __init__(self, conn):
        self.conn = conn
        self.cur = None
        self.konteks = None             # isi SESSION_CONTEXT saat ini di server (None = kosong)
        self.perlu_rollback = False     # transaksi baca yang belum ditutup -> ditutup petugas latar saat menganggur
        self.lahir = self.terakhir = time.monotonic()

    def cursor(self):
        if self.cur is None:
            self.cur = self.conn.cursor()
        return self.cur

    def kuras(self):
        """Sisa baris / hasil yang belum dibaca dibuang, supaya koneksi siap untuk perintah berikutnya."""
        if self.cur is None:
            return
        try:
            for _ in range(100):        # batas jaga-jaga (mis. objek tiruan di unit test)
                try:
                    self.cur.fetchall()
                except pyodbc.ProgrammingError:
                    pass            # perintah tanpa hasil baris
                if self.cur.nextset() is not True:
                    break
        except pyodbc.Error:
            self.cur = None         # cursor bermasalah: dibuat baru saat dipakai lagi
        if self.cur is not None and self.cur.fast_executemany:
            self.cur.fast_executemany = False

    def tutup(self):
        try:
            self.conn.close()
        except pyodbc.Error:
            pass


JEDA_PETUGAS_DETIK = 2


class Kolam:
    def __init__(self, buat_koneksi):
        self._buat = buat_koneksi
        self._diam = []
        self._kunci = threading.Lock()
        self._petugas = None

    def _mulai_petugas(self):
        if self._petugas is None:
            self._petugas = threading.Thread(target=self._rapikan_terus, name="kolam-db", daemon=True)
            self._petugas.start()

    def _rapikan_terus(self):
        while True:
            time.sleep(JEDA_PETUGAS_DETIK)
            try:
                self.rapikan()
            except Exception:           # noqa: BLE001 - petugas latar tidak boleh mati
                log.exception("Gagal merapikan kolam koneksi")

    def rapikan(self):
        """Koneksi menganggur: transaksi bacanya ditutup (tidak ada transaksi terbuka lama di server),
        yang terlalu lama menganggur / terlalu tua dibuang."""
        sekarang = time.monotonic()
        with self._kunci:
            ambil = [f for f in self._diam if f.perlu_rollback or sekarang - f.terakhir > BATAS_DIAM_DETIK
                     or sekarang - f.lahir > UMUR_MAKS_DETIK]
            self._diam = [f for f in self._diam if f not in ambil]
        for f in ambil:
            if sekarang - f.terakhir > BATAS_DIAM_DETIK or sekarang - f.lahir > UMUR_MAKS_DETIK:
                f.tutup()
                continue
            try:
                f.conn.rollback()
                f.perlu_rollback = False
            except pyodbc.Error:
                f.tutup()
                continue
            with self._kunci:
                if len(self._diam) < MAKS_DIAM:
                    self._diam.insert(0, f)     # paling belakang dipakai: yang baru dikembalikan tetap duluan
                    continue
            f.tutup()

    def ambil(self):
        """(koneksi fisik, baru?) - yang terakhir dikembalikan lebih dulu (paling mungkin masih hidup)."""
        sekarang = time.monotonic()
        with self._kunci:
            while self._diam:
                f = self._diam.pop()
                if sekarang - f.terakhir <= BATAS_DIAM_DETIK and sekarang - f.lahir <= UMUR_MAKS_DETIK:
                    return f, False
                threading.Thread(target=f.tutup, daemon=True).start()
        return _Fisik(self._buat()), True

    def kembalikan(self, f):
        self._mulai_petugas()
        f.terakhir = time.monotonic()
        with self._kunci:
            if len(self._diam) < MAKS_DIAM:
                self._diam.append(f)
                return
        f.tutup()

    def buang(self, f):
        f.tutup()

    def kosongkan(self):
        with self._kunci:
            semua, self._diam = self._diam, []
        for f in semua:
            f.tutup()

    def jumlah_diam(self):
        return len(self._diam)


class Kursor:
    """Cursor pinjaman. Cursor pertama per pinjaman memakai cursor fisik bersama; cursor tambahan dalam pinjaman
    yang sama (jarang) mendapat cursor sendiri seperti biasa."""

    def __init__(self, pinjam, cur, bersama):
        self._p = pinjam
        self._cur = cur
        self._bersama = bersama

    def execute(self, sql, *params):
        self._p._jalankan(self._cur, sql, params)
        return self

    def executemany(self, sql, params):
        self._p._siapkan(self._cur)
        self._p._ditulis = True
        self._cur.executemany(sql, params)
        return self

    def close(self):
        if not self._bersama:
            self._cur.close()

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __getattr__(self, nama):            # fetchone, fetchall, description, rowcount, nextset, ...
        return getattr(self._cur, nama)

    def __setattr__(self, nama, nilai):
        if nama.startswith("_"):
            object.__setattr__(self, nama, nilai)
        else:
            setattr(self._cur, nama, nilai)


class Koneksi:
    """Koneksi pinjaman dari Kolam; perilakunya sama dengan pyodbc.Connection bagi pemakainya."""

    def __init__(self, kolam, fisik, konteks):
        self._kolam = kolam
        self._f = fisik
        self._konteks = konteks             # isi SESSION_CONTEXT yang diminta pinjaman ini
        self._kursor_bersama = False
        self._kursor_aktif = None
        self._ditulis = False               # ada perintah tulis yang belum di-commit / rollback
        self._pertama = True
        self._ditutup = False

    # ----- dipakai Kursor -----
    def _awalan(self):
        return _awalan_konteks(self._konteks) if self._konteks != self._f.konteks else ""

    def _sesudah_awalan(self):
        self._f.konteks = self._konteks

    def _siapkan(self, cur):
        """Awalan dijalankan sendiri (untuk executemany)."""
        awalan = self._awalan()
        if awalan:
            cur.execute(awalan)
            self._sesudah_awalan()

    def _jalankan(self, cur, sql, params):
        awalan = self._awalan()
        if not _hanya_baca(sql):
            self._ditulis = True
        try:
            cur.execute(awalan + sql, *params)
        except pyodbc.Error as e:
            # Koneksi diam yang ternyata sudah putus: perintah pertama pinjaman ini diulang dengan koneksi baru
            if not (self._pertama and getattr(e, "args", None) and str(e.args[0]) in KODE_PUTUS):
                raise
            log.warning("Koneksi database terputus, membuka ulang: %s", e)
            self._kolam.buang(self._f)
            self._f = _Fisik(self._kolam._buat())
            cur = self._f.cursor()
            if self._kursor_aktif is not None:
                self._kursor_aktif._cur = cur
            cur.execute(self._awalan() + sql, *params)
        self._sesudah_awalan()
        self._pertama = False

    # ----- antarmuka seperti pyodbc.Connection -----
    def cursor(self):
        if not self._kursor_bersama:
            self._kursor_bersama = True
            self._kursor_aktif = Kursor(self, self._f.cursor(), True)
            return self._kursor_aktif
        return Kursor(self, self._f.conn.cursor(), False)

    def execute(self, sql, *params):
        return self.cursor().execute(sql, *params)

    def commit(self):
        self._f.conn.commit()
        self._ditulis = self._f.perlu_rollback = False

    def rollback(self):
        self._f.conn.rollback()
        self._ditulis = self._f.perlu_rollback = False

    def close(self):
        if self._ditutup:
            return
        self._ditutup = True
        f = self._f
        try:
            f.kuras()
            if self._ditulis:
                f.conn.rollback()           # perubahan tanpa commit dibatalkan sekarang (kunci data dilepas)
            elif not self._pertama:
                f.perlu_rollback = True     # hanya membaca: transaksi bacanya ditutup petugas latar kolam
            if f.conn.autocommit:
                f.conn.autocommit = False
            self._kolam.kembalikan(f)
        except pyodbc.Error:
            self._kolam.buang(f)

    def __enter__(self):
        return self

    def __exit__(self, jenis, *_):
        # Sama dengan pyodbc: commit bila tanpa error, rollback bila error; koneksi tidak ditutup
        if jenis is None:
            self.commit()
        else:
            self.rollback()

    def __del__(self):
        if not getattr(self, "_ditutup", True):
            try:
                self.close()
            except Exception:           # noqa: BLE001 - dipanggil saat garbage collection
                pass

    def __getattr__(self, nama):            # timeout, autocommit, getinfo, ...
        return getattr(self._f.conn, nama)

    def __setattr__(self, nama, nilai):
        if nama.startswith("_"):
            object.__setattr__(self, nama, nilai)
        else:
            setattr(self._f.conn, nama, nilai)
