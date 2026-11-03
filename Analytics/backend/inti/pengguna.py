"""Pengguna, role, company, dan hak akses laporan, dibaca dari tabel yang sudah ada di SQL Server (nama tabel dan kolomnya ada di README).

users.role boleh berisi nama role atau RoleId; keduanya dibaca sebagai nama role. Tabel izin dipakai bersama aplikasi lain: program ini hanya
menyentuh baris yang page_key-nya id laporan, dan hanya kolom can_access.
"""
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from . import konfigurasi, sandi as kata_sandi

ROLE_ADMIN = konfigurasi.ROLE_ADMIN

KOLOM = ("id", "username", "password_hash", "full_name", "role", "division", "company", "created_at")
KOLOM_ROLE = ("RoleId", "RoleName", "RoleDescription", "Status")
KOLOM_COMPANY = ("CompID", "CompName", "CompType", "Status")
KOLOM_DIVISI = ("DivisionID", "CompID", "DivisionName", "DivisionCode", "Status")
MAKS_NAMA_ROLE = 30        # users.role nvarchar(30)
MAKS_NAMA_DIVISI = 50      # DIVISION.DivisionName nchar(50)
MAKS_KODE_DIVISI = 20
MAKS_DESKRIPSI_ROLE = 255
KOLOM_IZIN = ("role", "page_key", "can_access", "can_edit", "can_delete", "can_approve", "can_reject", "can_done")
_NONAKTIF = {"0", "false", "n", "no", "off", "inactive", "nonaktif", "non-aktif", "tidak aktif", "disabled"}
_NAMA_TABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")
_USERNAME = re.compile(r"^[A-Za-z0-9._@-]{3,50}$")


class PenyimpanTidakTersedia(Exception):
    """Database tidak terjangkau atau query gagal (bukan kesalahan masukan)."""


class TidakPunyaIzin(PenyimpanTidakTersedia):
    pass


class IzinTidakTerbaca(PenyimpanTidakTersedia):
    """Saat ini terjadi, akun non-admin tidak boleh dianggap punya akses."""


class DataTidakValid(ValueError):
    """Pesannya aman ditampilkan ke pengguna."""


@dataclass(frozen=True)
class Pengguna:
    id: object
    username: str
    nama: str            # full_name
    role: str            # selalu nama role, walau users.role berisi RoleId
    divisi: str          # division
    company: str
    sandi: str           # password_hash
    dibuat: str          # created_at


def _kunci_role(nama):
    """Spasi dan huruf besar-kecil diabaikan: "Software Engineer" sama dengan "SoftwareEngineer"."""
    return "".join(str(nama or "").split()).casefold()


def kanonik_role(role, sah):
    """Nama role persis seperti di daftar `sah`, atau None."""
    kunci = _kunci_role(role)
    return next((r for r in sah if _kunci_role(r) == kunci), None) if kunci else None


def adalah_admin(role):
    return _kunci_role(role) == _kunci_role(ROLE_ADMIN)


def _aktif(status):
    return status is None or str(status).strip().casefold() not in _NONAKTIF


def _urut_compid(baris):
    i = _teks(baris[0]).strip()
    return (0, int(i), "") if i.isdigit() else (1, 0, i)


PEMISAH_COMPANY = ", "


def daftar_company_akun(nilai):
    """Satu akun boleh punya beberapa company, dipisah koma di kolom yang sama: "ORI, RCM" -> ["ORI", "RCM"]."""
    return [c.strip() for c in str(nilai or "").split(",") if c.strip()]


def _rapikan_company(company, company_sah):
    """Teks untuk kolom company, urut seperti company_sah dan tanpa duplikat."""
    dipilih = daftar_company_akun(company) if isinstance(company, str) or company is None else [str(c).strip() for c in company if str(c).strip()]
    sah = {c.casefold(): c for c in reversed(company_sah)}
    asing = [c for c in dipilih if c.casefold() not in sah]
    if not dipilih or asing:
        raise DataTidakValid(f"Company harus dipilih minimal satu, dari: {', '.join(dict.fromkeys(company_sah)) or '(tabel company kosong)'}.")
    terpilih = {c.casefold() for c in dipilih}
    teks = PEMISAH_COMPANY.join(dict.fromkeys(c for c in company_sah if c.casefold() in terpilih))
    if len(teks) > 100:
        raise DataTidakValid("Terlalu banyak company dipilih (kolom company maksimal 100 karakter).")
    return teks


def _periksa_profil(nama, role, divisi, role_sah, role_lama=None):
    """Bagian yang sama untuk akun baru dan perubahan akun: (nama, role resmi, divisi)."""
    nama, divisi = (str(x or "").strip() for x in (nama, divisi))
    if not nama or len(nama) > 150:
        raise DataTidakValid("Nama lengkap wajib diisi (maksimal 150 karakter).")
    resmi = kanonik_role(role, role_sah) or (kanonik_role(role, [role_lama]) if role_lama else None)
    if resmi is None:
        raise DataTidakValid(f"Role harus salah satu dari: {', '.join(role_sah) or '(tabel role kosong)'}.")
    if not divisi or len(divisi) > 100:
        raise DataTidakValid("Divisi wajib diisi (maksimal 100 karakter).")
    return nama, resmi, divisi


def periksa_pengguna_baru(username, sandi, nama, role, divisi, company, role_sah, company_sah):
    username = str(username or "").strip()
    if not _USERNAME.match(username):
        raise DataTidakValid("Username 3 sampai 50 karakter: huruf, angka, titik, garis bawah, strip, atau @.")
    if not 8 <= len(sandi or "") <= 200:
        raise DataTidakValid("Password minimal 8 karakter (maksimal 200).")
    nama, resmi, divisi = _periksa_profil(nama, role, divisi, role_sah)
    comp = _rapikan_company(company, company_sah)
    return {"username": username, "sandi": sandi, "nama": nama, "role": resmi, "divisi": divisi, "company": comp}


def _isian(nilai, judul, maks, wajib=True):
    teks = " ".join(str(nilai or "").split())
    if wajib and not teks:
        raise DataTidakValid(f"{judul} wajib diisi.")
    if len(teks) > maks:
        raise DataTidakValid(f"{judul} paling panjang {maks} karakter.")
    return teks


def periksa_divisi_baru(nama, kode, comp_id):
    if not isinstance(comp_id, int):
        raise DataTidakValid("Company wajib dipilih.")
    return {"nama": _isian(nama, "Nama divisi", MAKS_NAMA_DIVISI), "kode": _isian(kode, "Kode divisi", MAKS_KODE_DIVISI).upper(), "comp_id": comp_id}


def periksa_role_baru(nama, deskripsi, divisi_id):
    if not isinstance(divisi_id, int):
        raise DataTidakValid("Divisi wajib dipilih.")
    return {"nama": _isian(nama, "Nama role", MAKS_NAMA_ROLE), "deskripsi": _isian(deskripsi, "Deskripsi", MAKS_DESKRIPSI_ROLE, wajib=False),
            "divisi_id": divisi_id}


def periksa_ubah_pengguna(nama, role, divisi, company, sandi, role_sah, company_sah, lama):
    """Role dan company lama boleh tetap walau sudah tidak ada di pilihan (mis. role dinonaktifkan). sandi kosong = tidak diganti."""
    nama, resmi, divisi = _periksa_profil(nama, role, divisi, role_sah, lama.role)
    comp = _rapikan_company(company, [*company_sah, *daftar_company_akun(lama.company)])
    sandi = sandi or None
    if sandi is not None and not 8 <= len(sandi) <= 200:
        raise DataTidakValid("Password baru minimal 8 karakter (maksimal 200), atau kosongkan kalau tidak diganti.")
    return {"nama": nama, "role": resmi, "divisi": divisi, "company": comp, "sandi": sandi}


def _benar(v):
    return str(v).strip().lower() in ("1", "true", "y", "ya", "yes")


def _teks(v):
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ", timespec="seconds")
    return str(v)


def _kutip(tabel):
    """dbo.users -> [dbo].[users]"""
    return ".".join(f"[{b}]" for b in tabel.split("."))


class PenyimpanPengguna:
    """buka_koneksi: fungsi tanpa argumen yang mengembalikan koneksi pyodbc.

    Pengguna, peta role, dan tabel izin dicache cache_detik detik karena dibaca di setiap permintaan. Perubahan lewat aplikasi ini berlaku
    langsung; perubahan langsung di database paling lambat cache_detik kemudian."""

    def __init__(self, buka_koneksi, tabel="users", tabel_role="role", cache_detik=30, jam=time.time, role_disimpan="auto", tabel_company="company",
                 tabel_izin="PERMISSIONS", tabel_divisi="DIVISION"):
        for nama in (tabel, tabel_role, tabel_company, tabel_izin, tabel_divisi):
            if not _NAMA_TABEL.match(nama or ""):
                raise ValueError(f"Nama tabel tidak valid: {nama!r}")
        if role_disimpan not in ("auto", "nama", "id"):
            raise ValueError("ROLE_DISIMPAN harus auto, nama, atau id")
        self._buka, self.tabel, self.tabel_role = buka_koneksi, tabel, tabel_role
        self.tabel_company, self.tabel_izin = tabel_company, tabel_izin
        self._t, self._tr, self._tc, self._ti = _kutip(tabel), _kutip(tabel_role), _kutip(tabel_company), _kutip(tabel_izin)
        self.tabel_divisi, self._td = tabel_divisi, _kutip(tabel_divisi)
        self._cache_izin = None   # (waktu, [(role, page_key, akses)])
        self._cache_detik, self._jam = cache_detik, jam
        self._kunci = threading.Lock()
        self._cache = {}          # username huruf kecil -> (waktu, Pengguna)
        self._peta = None         # (waktu, {str(RoleId): RoleName})
        self._role_disimpan = role_disimpan
        self._kolom = ", ".join(f"[{k}]" for k in KOLOM)
        self._kolom_role = ", ".join(f"[{k}]" for k in KOLOM_ROLE)

    def _kerja(self, fungsi):
        """fungsi(kursor) dalam satu transaksi. ValueError diteruskan; kegagalan lain menjadi PenyimpanTidakTersedia."""
        try:
            conn = self._buka()
            try:
                hasil = fungsi(conn.cursor())
                conn.commit()
                return hasil
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except ValueError:
            raise
        except Exception as e:
            pesan = f"{type(e).__name__}: {e}"
            if "permission" in pesan.lower() and "denied" in pesan.lower():
                raise TidakPunyaIzin(pesan) from e
            raise PenyimpanTidakTersedia(pesan) from e

    def _baca(self, sql, params=()):
        def f(cur):
            cur.execute(sql, params)
            return [tuple(r) for r in cur.fetchall()]
        return self._kerja(f)

    def bersihkan_cache(self):
        with self._kunci:
            self._cache.clear()
            self._peta = None
            self._cache_izin = None

    def _peta_role(self):
        """{str(RoleId): RoleName}. Kosong (dan tidak dicache) kalau tabel role tidak terbaca; users.role lalu dipakai apa adanya."""
        if self._cache_detik > 0:
            with self._kunci:
                item = self._peta
            if item and self._jam() - item[0] < self._cache_detik:
                return item[1]
        try:
            peta = {_teks(r[0]).strip(): _teks(r[1]).strip() for r in self._baca(f"SELECT [RoleId], [RoleName] FROM {self._tr}")}
        except PenyimpanTidakTersedia:
            return {}
        if self._cache_detik > 0:
            with self._kunci:
                self._peta = (self._jam(), peta)
        return peta

    def _ke_pengguna(self, b, peta):
        mentah = _teks(b[4]).strip()
        return Pengguna(b[0], _teks(b[1]), _teks(b[3]), peta.get(mentah, mentah), _teks(b[5]), _teks(b[6]), _teks(b[2]), _teks(b[7]))

    def periksa_role(self):
        self._baca(f"SELECT {self._kolom_role} FROM {self._tr} WHERE 1 = 0")

    def daftar_role(self):
        return [{"id": r[0], "nama": _teks(r[1]).strip(), "deskripsi": _teks(r[2]), "aktif": _aktif(r[3])}
                for r in self._baca(f"SELECT {self._kolom_role} FROM {self._tr} ORDER BY [RoleId]")]

    def daftar_role_divisi(self):
        """Role beserta DivisionID-nya, untuk halaman Role & Divisi."""
        return [{"id": r[0], "divisi_id": r[1], "nama": _teks(r[2]).strip(), "deskripsi": _teks(r[3]).strip(), "aktif": _aktif(r[4])}
                for r in self._baca(f"SELECT [RoleId], [DivisionID], [RoleName], [RoleDescription], [Status] FROM {self._tr} ORDER BY [RoleId]")]

    def daftar_divisi(self):
        return [{"id": r[0], "comp_id": r[1], "nama": _teks(r[2]).strip(), "kode": _teks(r[3]).strip(), "aktif": _aktif(r[4])}
                for r in self._baca(f"SELECT {', '.join(f'[{k}]' for k in KOLOM_DIVISI)} FROM {self._td} ORDER BY [DivisionID]")]

    def daftar_baris_company(self):
        """Semua baris company aktif (satu nama bisa beberapa CompType), untuk memilih company sebuah divisi."""
        return [{"id": r[0], "nama": _teks(r[1]).strip(), "jenis": _teks(r[2]).strip()}
                for r in sorted(self._baca(f"SELECT [CompID], [CompName], [CompType], [Status] FROM {self._tc}"), key=_urut_compid) if _aktif(r[3])]

    def tambah_divisi(self, data):
        """data: hasil periksa_divisi_baru. Nama atau kode yang sudah dipakai: DataTidakValid."""
        if data["comp_id"] not in {c["id"] for c in self.daftar_baris_company()}:
            raise DataTidakValid("Company tidak ditemukan atau tidak aktif.")
        for d in self.daftar_divisi():
            if d["nama"].casefold() == data["nama"].casefold():
                raise DataTidakValid(f"Divisi '{d['nama']}' sudah ada.")
            if d["kode"].casefold() == data["kode"].casefold():
                raise DataTidakValid(f"Kode '{d['kode']}' sudah dipakai divisi {d['nama']}.")

        def f(cur):
            cur.execute(f"INSERT INTO {self._td} ([CompID], [DivisionName], [DivisionCode], [Status], [CreatedAt]) VALUES (?, ?, ?, 1, ?)",
                        (data["comp_id"], data["nama"], data["kode"], datetime.now()))
        self._kerja(f)
        return next(d for d in self.daftar_divisi() if d["nama"].casefold() == data["nama"].casefold())

    def tambah_role(self, data):
        """data: hasil periksa_role_baru. Nama yang sudah dipakai (spasi dan huruf besar-kecil diabaikan): DataTidakValid."""
        if data["divisi_id"] not in {d["id"] for d in self.daftar_divisi() if d["aktif"]}:
            raise DataTidakValid("Divisi tidak ditemukan atau tidak aktif.")
        kunci = _kunci_role(data["nama"])
        sama = next((r["nama"] for r in self.daftar_role() if _kunci_role(r["nama"]) == kunci), None)
        if sama:
            raise DataTidakValid(f"Role '{sama}' sudah ada.")

        def f(cur):
            cur.execute(f"INSERT INTO {self._tr} ([DivisionID], [RoleName], [RoleDescription], [Status], [CreatedAt]) VALUES (?, ?, ?, 1, ?)",
                        (data["divisi_id"], data["nama"], data["deskripsi"] or None, datetime.now()))
        self._kerja(f)
        self.bersihkan_cache()
        return next(r for r in self.daftar_role_divisi() if _kunci_role(r["nama"]) == kunci)

    def role_aktif(self):
        return [r["nama"] for r in self.daftar_role() if r["aktif"] and r["nama"]]

    def role_disimpan(self):
        """'id' atau 'nama'. auto: 'id' kalau semua users.role yang ada berupa angka."""
        if self._role_disimpan != "auto":
            return self._role_disimpan
        nilai = {_teks(b[0]).strip() for b in self._baca(f"SELECT DISTINCT [role] FROM {self._t}")} - {""}
        return "id" if nilai and all(v.isdigit() for v in nilai) else "nama"

    def _nilai_role(self, nama):
        """Isi kolom users.role untuk role ini, mengikuti role_disimpan()."""
        if self.role_disimpan() != "id":
            return nama
        nilai = next((r["id"] for r in self.daftar_role() if r["nama"] == nama), None)
        if nilai is None:
            raise DataTidakValid(f"Role '{nama}' tidak ditemukan di tabel role.")
        return nilai

    def periksa_company(self):
        self._baca(f"SELECT {', '.join(f'[{k}]' for k in KOLOM_COMPANY)} FROM {self._tc} WHERE 1 = 0")

    def daftar_company(self):
        """Nama unik, urut abjad. Satu nama bisa punya beberapa baris (CLOUD, TRAINING, ...); aktif kalau salah satunya aktif."""
        status = {}
        for nama, st in self._baca(f"SELECT [CompName], [Status] FROM {self._tc}"):
            n = _teks(nama).strip()
            if n:
                status[n] = status.get(n, False) or _aktif(st)
        return [{"nama": n, "aktif": a} for n, a in sorted(status.items(), key=lambda x: x[0].casefold())]

    def company_aktif(self):
        return [c["nama"] for c in self.daftar_company() if c["aktif"]]

    def company_menurut_jenis(self, jenis):
        """Company aktif dengan CompType = jenis, urut CompID. Ini perusahaan yang dipanggil SP laporan."""
        kunci = str(jenis or "").strip().casefold()
        hasil = []
        for r in sorted(self._baca(f"SELECT [CompID], [CompName], [CompType], [Status] FROM {self._tc}"), key=_urut_compid):
            nama = _teks(r[1]).strip()
            if nama and _teks(r[2]).strip().casefold() == kunci and _aktif(r[3]) and nama not in hasil:
                hasil.append(nama)
        return hasil

    def lokasi_menurut_jenis(self, jenis):
        """[(nama, server tertaut, database)] company aktif dengan CompType = jenis, urut CompID, dari kolom CompAddr dan CompDataBase."""
        kunci = str(jenis or "").strip().casefold()
        baris = self._baca(f"SELECT [CompID], [CompName], [CompType], [Status], [CompAddr], [CompDataBase] FROM {self._tc}")
        hasil = []
        for r in sorted(baris, key=_urut_compid):
            nama = _teks(r[1]).strip()
            if nama and _teks(r[2]).strip().casefold() == kunci and _aktif(r[3]) and nama not in [h[0] for h in hasil]:
                hasil.append((nama, _teks(r[4]).strip(), _teks(r[5]).strip()))
        return hasil

    def periksa_izin(self):
        self._baca(f"SELECT {', '.join(f'[{k}]' for k in KOLOM_IZIN)} FROM {self._ti} WHERE 1 = 0")

    def _baris_izin(self, segar=False):
        """[(role, page_key, akses)]. segar=True melewati cache."""
        if segar:
            with self._kunci:
                self._cache_izin = None
        elif self._cache_detik > 0:
            with self._kunci:
                item = self._cache_izin
            if item and self._jam() - item[0] < self._cache_detik:
                return item[1]
        baris = [(_teks(r), _teks(p), _benar(a)) for r, p, a in self._baca(f"SELECT [role], [page_key], [can_access] FROM {self._ti}")]
        if self._cache_detik > 0:
            with self._kunci:
                self._cache_izin = (self._jam(), baris)
        return baris

    @staticmethod
    def _akses_role(baris, kunci):
        """{page_key: boleh}. Baris ganda yang bertentangan hanya mengizinkan kalau semuanya mengizinkan."""
        hasil = {}
        for r, p, a in baris:
            if _kunci_role(r) == kunci:
                k = p.strip().casefold()
                hasil[k] = hasil.get(k, True) and a
        return hasil

    def izin_role(self, nama_role):
        """page_key (huruf kecil) yang boleh dibuka role ini. Tabel tidak terbaca: IzinTidakTerbaca, jangan dianggap terbuka."""
        kunci = _kunci_role(nama_role)
        if not kunci:
            return set()
        try:
            baris = self._baris_izin()
        except PenyimpanTidakTersedia as e:
            raise IzinTidakTerbaca(str(e)) from e
        return {k for k, a in self._akses_role(baris, kunci).items() if a}

    def izin_semua_role(self, laporan_ids):
        """Untuk Permission Control, tanpa cache. Laporan tanpa baris dianggap tidak boleh."""
        role, baris = self.daftar_role(), self._baris_izin(segar=True)
        return [{"id": r["id"], "nama": r["nama"], "aktif": r["aktif"],
                 "izin": {i: self._akses_role(baris, _kunci_role(r["nama"])).get(i.casefold(), False) for i in laporan_ids}} for r in role]

    def hitung_baris_izin(self, laporan_ids):
        """(baris laporan program ini, baris halaman aplikasi lain)."""
        kunci = {i.casefold() for i in laporan_ids}
        baris = self._baris_izin(segar=True)
        ini = sum(1 for _, p, _ in baris if p.strip().casefold() in kunci)
        return ini, len(baris) - ini

    def role_izin_asing(self):
        """{role di tabel izin yang tidak ada di tabel role: jumlah barisnya}."""
        dikenal = {_kunci_role(r["nama"]) for r in self.daftar_role()}
        hasil = {}
        for r, _, _ in self._baris_izin(segar=True):
            if _kunci_role(r) not in dikenal:
                hasil[r.strip()] = hasil.get(r.strip(), 0) + 1
        return hasil

    def atur_izin(self, nama_role, laporan_id, akses):
        """Baris yang ada hanya diubah can_access-nya; baris baru diisi 0 untuk kolom izin lain."""
        kunci = _kunci_role(nama_role)
        role = next((r for r in self.daftar_role() if _kunci_role(r["nama"]) == kunci), None) if kunci else None
        if role is None:
            raise DataTidakValid(f"Role '{nama_role}' tidak ada di tabel role.")
        nilai = int(bool(akses))
        ada = {(r, p) for r, p, _ in self._baris_izin(segar=True) if _kunci_role(r) == kunci and p.strip().casefold() == laporan_id.casefold()}

        def f(cur):
            for r, p in ada:
                cur.execute(f"UPDATE {self._ti} SET [can_access] = ? WHERE [role] = ? AND [page_key] = ?", (nilai, r, p))
            if not ada:
                cur.execute(f"INSERT INTO {self._ti} ({', '.join(f'[{k}]' for k in KOLOM_IZIN)}) VALUES (?, ?, ?, 0, 0, 0, 0, 0)", (role["nama"], laporan_id, nilai))
        self._kerja(f)
        self.bersihkan_cache()
        return {"role": role["nama"], "laporan": laporan_id, "akses": bool(nilai)}

    def periksa(self):
        self._baca(f"SELECT {self._kolom} FROM {self._t} WHERE 1 = 0")

    def cari(self, username):
        kunci = str(username).strip().lower()
        if self._cache_detik > 0:
            with self._kunci:
                item = self._cache.get(kunci)
            if item and self._jam() - item[0] < self._cache_detik:
                return item[1]
        baris = self._baca(f"SELECT {self._kolom} FROM {self._t} WHERE LOWER([username]) = ?", (kunci,))
        if not baris:
            with self._kunci:
                self._cache.pop(kunci, None)
            return None
        p = self._ke_pengguna(baris[0], self._peta_role())
        if self._cache_detik > 0:
            with self._kunci:
                self._cache[kunci] = (self._jam(), p)
        return p

    def cari_id(self, id_):
        baris = self._baca(f"SELECT {self._kolom} FROM {self._t} WHERE [id] = ?", (id_,))
        return self._ke_pengguna(baris[0], self._peta_role()) if baris else None

    def daftar(self):
        peta = self._peta_role()
        return [self._ke_pengguna(b, peta) for b in self._baca(f"SELECT {self._kolom} FROM {self._t} ORDER BY [username]")]

    def opsi(self):
        """Divisi untuk pilihan di formulir akun: yang aktif di tabel divisi ditambah yang sudah dipakai akun.
        Tabel divisi yang tidak terbaca tidak menggagalkan formulir akun."""
        dipakai = {_teks(b[0]).strip() for b in self._baca(f"SELECT DISTINCT [division] FROM {self._t}")}
        try:
            terdaftar = {d["nama"] for d in self.daftar_divisi() if d["aktif"]}
        except PenyimpanTidakTersedia:
            terdaftar = set()
        return {"divisi": sorted((dipakai | terdaftar) - {""}, key=str.casefold)}

    def jumlah_admin(self):
        return sum(1 for p in self.daftar() if adalah_admin(p.role))

    def jenis_hash(self):
        """Counter jenis hash di tabel; kunci None = format tidak dikenal."""
        return Counter(kata_sandi.jenis_hash(b[0]) for b in self._baca(f"SELECT [password_hash] FROM {self._t}"))

    def izin_tulis(self, tabel=None, aksi=("INSERT", "UPDATE", "DELETE")):
        """{"INSERT": bool, ...} untuk akun database ini, atau None kalau bukan SQL Server."""
        try:
            hasil = {}
            for aksi in aksi:
                v = self._baca("SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', ?)", (tabel or self.tabel, aksi))[0][0]
                hasil[aksi] = None if v is None else bool(v)
            return hasil
        except PenyimpanTidakTersedia:
            return None

    def id_otomatis(self):
        """Apakah kolom id IDENTITY. None kalau bukan SQL Server."""
        try:
            v = self._baca("SELECT COLUMNPROPERTY(OBJECT_ID(?), 'id', 'IsIdentity')", (self.tabel,))[0][0]
            return None if v is None else bool(v)
        except PenyimpanTidakTersedia:
            return None

    def tambah(self, data, hash_sandi):
        """data: hasil periksa_pengguna_baru. Username yang sudah dipakai: DataTidakValid."""
        sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nilai_role = self._nilai_role(data["role"])

        def f(cur):
            cur.execute(f"SELECT 1 FROM {self._t} WHERE LOWER([username]) = ?", (data["username"].lower(),))
            if cur.fetchall():
                raise DataTidakValid(f"Username '{data['username']}' sudah dipakai.")
            cur.execute(
                f"INSERT INTO {self._t} ([username], [password_hash], [full_name], [role], [division], [company], [created_at]) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data["username"], hash_sandi, data["nama"], nilai_role, data["divisi"], data["company"], sekarang),
            )
        self._kerja(f)
        self.bersihkan_cache()
        return self.cari(data["username"])

    def ubah(self, id_, data, hash_sandi=None):
        """data: hasil periksa_ubah_pengguna. Role hanya ditulis kalau berubah, supaya isi aslinya (nama atau RoleId) tidak tertimpa."""
        ada = self.cari_id(id_)
        if ada is None:
            raise DataTidakValid("Pengguna tidak ditemukan.")
        kolom = [("full_name", data["nama"]), ("division", data["divisi"]), ("company", data["company"])]
        if data["role"].casefold() != ada.role.casefold():
            kolom.append(("role", self._nilai_role(data["role"])))
        if hash_sandi is not None:
            kolom.append(("password_hash", hash_sandi))

        def f(cur):
            cur.execute(f"UPDATE {self._t} SET " + ", ".join(f"[{k}] = ?" for k, _ in kolom) + " WHERE [id] = ?", [v for _, v in kolom] + [id_])
        self._kerja(f)
        self.bersihkan_cache()
        return self.cari_id(id_)

    def hapus(self, id_):
        ada = self.cari_id(id_)
        if ada is None:
            raise DataTidakValid("Pengguna tidak ditemukan.")

        def f(cur):
            cur.execute(f"DELETE FROM {self._t} WHERE [id] = ?", (id_,))
        self._kerja(f)
        self.bersihkan_cache()
        return ada
