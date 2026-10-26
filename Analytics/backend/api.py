"""API dashboard. Jalankan dari folder backend: uvicorn api:app --reload

SQL Server hanya dipanggil saat pengguna memuat laporan; hasilnya disimpan di memori milik sesi login itu. Karena itu jalankan satu proses
saja (tanpa banyak worker). Isi .env dijelaskan di README.
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from inti import cpos, ekspor, konfigurasi, sandi as kata_sandi
from inti.aktivitas import JENIS as JENIS_AKTIVITAS, LogAktivitas, ringkas_pengguna
from inti.db import get_connection_app
from inti.filter import FilterTidakValid
from inti.gudang import Gudang
from inti.laporan import MAKS_MINGGU, TampilanRentang
from inti.pengguna import (
    DataTidakValid, IzinTidakTerbaca, PenyimpanPengguna, PenyimpanTidakTersedia, TidakPunyaIzin,
    adalah_admin, kanonik_role, periksa_divisi_baru, periksa_pengguna_baru, periksa_role_baru, periksa_ubah_pengguna,
)
from inti.pengaturan import DataTidakValid as PengaturanTidakValid, Pengaturan, periksa_idle
from inti.sesi import PembatasLogin, Sesi
from laporan import SEMUA as LAPORAN

load_dotenv()
logging.basicConfig(level=logging.INFO)

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
]
MAKS_HARI = konfigurasi.MAKS_HARI
NAMA_COOKIE = "sesi"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
SESI_JAM = float(os.environ.get("SESI_JAM", "8"))
log = logging.getLogger("dashboard")

gudang = Gudang()
log_aktivitas = LogAktivitas(konfigurasi.AKTIVITAS_FOLDER, konfigurasi.AKTIVITAS_SIMPAN_HARI)


penyimpan_pengguna = PenyimpanPengguna(
    get_connection_app,
    tabel=konfigurasi.TABEL_PENGGUNA,
    tabel_role=konfigurasi.TABEL_ROLE,
    tabel_company=konfigurasi.TABEL_COMPANY,
    tabel_izin=konfigurasi.TABEL_IZIN,
    tabel_divisi=konfigurasi.TABEL_DIVISI,
    cache_detik=float(os.environ.get("PENGGUNA_CACHE_DETIK", "30")),
    role_disimpan=os.environ.get("ROLE_DISIMPAN", "auto").strip().lower(),
)


def _sesi_berakhir(kode, username):
    dihapus, dihentikan = gudang.lepas(kode)
    if dihapus or dihentikan:
        log.info("Sesi %s berakhir: %d data laporan dibuang, %d pemuatan dihentikan", username, dihapus, dihentikan)


# Batas idle diatur admin dari aplikasi; .env SESI_IDLE_MENIT hanya nilai awalnya (0 = tanpa batas)
pengaturan = Pengaturan(
    os.environ.get("PENGATURAN_BERKAS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pengaturan.json")),
    {"idle_menit": periksa_idle(float(os.environ.get("SESI_IDLE_MENIT", "30")))},
)


def buat_sesi():
    return Sesi(umur_detik=SESI_JAM * 3600, saat_berakhir=_sesi_berakhir, tunggal=konfigurasi.LOGIN_BERSAMAAN == "ganti",
                idle_detik=pengaturan.baca()["idle_menit"] * 60)


sesi_login = buat_sesi()
SAPU_SESI_DETIK = float(os.environ.get("SESI_SAPU_DETIK", "60"))
pembatas_login = PembatasLogin()
_algoritma = None   # hash akun baru, dipilih saat pertama dibutuhkan


def periksa_pengguna_awal():
    try:
        penyimpan_pengguna.periksa()
        jenis = penyimpan_pengguna.jenis_hash()
        n_admin = penyimpan_pengguna.jumlah_admin()
    except PenyimpanTidakTersedia as e:
        raise RuntimeError(
            f"Tidak bisa membaca tabel pengguna '{penyimpan_pengguna.tabel}'. Periksa DB_APP_* dan DB_APP_TABEL di .env, serta kolomnya "
            f"(id, username, password_hash, full_name, role, division, company, created_at). Detail: {e}"
        ) from e
    kata_sandi.pilih_algoritma(jenis, os.environ.get("PASSWORD_HASH", "auto"))     # gagal sejak awal kalau PASSWORD_HASH salah isi
    for j, n in jenis.items():
        if j is None:
            log.warning("%d akun memakai format hash yang tidak dikenal; akun itu tidak akan bisa masuk.", n)
        elif not kata_sandi.pustaka_tersedia(j):
            log.warning("%d akun memakai hash %s, tetapi pustaka %s belum terpasang; akun itu tidak akan bisa masuk.", n, j, kata_sandi.PUSTAKA[j])
    if n_admin == 0:
        log.warning("Belum ada akun System Administrator. Buat dengan: python -m inti.alat_pengguna buat-admin")
    try:
        penyimpan_pengguna.periksa_role()
    except PenyimpanTidakTersedia as e:     # login tetap jalan; hanya membuat akun yang butuh tabel role
        log.warning("Tabel role '%s' tidak bisa dibaca, sehingga akun baru belum bisa dibuat dari aplikasi. Periksa DB_APP_TABEL_ROLE dan kolomnya "
                    "(RoleId, RoleName, RoleDescription, Status). Detail: %s", penyimpan_pengguna.tabel_role, e)
    try:
        penyimpan_pengguna.periksa_company()
    except PenyimpanTidakTersedia as e:
        log.warning("Tabel company '%s' tidak bisa dibaca, sehingga akun baru belum bisa dibuat dari aplikasi. Periksa DB_APP_TABEL_COMPANY dan kolomnya "
                    "(CompName, Status). Detail: %s", penyimpan_pengguna.tabel_company, e)
    periksa_izin_awal()
    log.info("Tabel pengguna '%s' siap (%d akun, %d administrator).", penyimpan_pengguna.tabel, sum(jenis.values()), n_admin)


def periksa_izin_awal():
    try:
        penyimpan_pengguna.periksa_izin()
    except PenyimpanTidakTersedia as e:
        log.warning("Tabel izin '%s' tidak bisa dibaca, jadi akun selain %s belum bisa melihat laporan apa pun. Periksa DB_APP_TABEL_IZIN dan kolomnya "
                    "(role, page_key, can_access, can_edit, can_delete, can_approve, can_reject, can_done). Detail: %s", penyimpan_pengguna.tabel_izin, konfigurasi.ROLE_ADMIN, e)
        return
    try:
        tanpa = sorted({p.role for p in penyimpan_pengguna.daftar()
                        if p.role and not adalah_admin(p.role) and not _laporan_boleh(p)})
    except PenyimpanTidakTersedia as e:
        log.warning("Hak akses tidak bisa diperiksa saat server menyala: %s", e)
        return
    if tanpa:
        log.warning("Role ini punya akun tetapi belum punya akses ke laporan apa pun (atur di menu Permission Control): %s", ", ".join(tanpa))


# Mode CPOS: sesi dipegang CPOS, jadi data laporan milik sesi CPOS yang sudah lama tidak memanggil Analytics dibuang di sini
_cpos_terakhir = {}      # pemilik "cpos:<sid>" -> waktu terakhir terlihat (monotonic)


def _lepas_cpos_diam():
    batas = max(pengaturan.baca()["idle_menit"], 30) * 60
    sekarang = time.monotonic()
    for pemilik, waktu in list(_cpos_terakhir.items()):
        if sekarang - waktu > batas:
            _cpos_terakhir.pop(pemilik, None)
            _sesi_berakhir(pemilik, pemilik)


async def _sapu_sesi():
    """Membuang sesi kedaluwarsa (dan data laporannya) walau tidak ada yang mengaksesnya lagi."""
    while True:
        await asyncio.sleep(SAPU_SESI_DETIK)
        try:
            sesi_login.bersihkan()
            _lepas_cpos_diam()
        except Exception:  # noqa: BLE001 - penyapu harus tetap jalan
            log.exception("Gagal menyapu sesi kedaluwarsa")


def periksa_ekspor_awal():
    if not ekspor.tersedia():
        log.warning("%s", ekspor.PESAN_PUSTAKA_HILANG)


@asynccontextmanager
async def _siklus_hidup(_app):
    if cpos.aktif():
        log.info("Login dan hak akses laporan mengikuti CPOS di %s", konfigurasi.CPOS_URL)
    else:
        periksa_pengguna_awal()
    periksa_ekspor_awal()
    penyapu = asyncio.create_task(_sapu_sesi())
    try:
        yield
    finally:
        penyapu.cancel()


app = FastAPI(title="Dashboard API", lifespan=_siklus_hidup)
@app.middleware("http")
async def tanpa_cache(request, call_next):
    """Jawaban /api/ tidak boleh tertinggal di cache perangkat setelah keluar."""
    jawaban = await call_next(request)
    if request.url.path.startswith("/api/"):
        jawaban.headers["Cache-Control"] = "no-store"
    return jawaban


app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"]
)


def _laporan_boleh(p):
    """Admin: semua laporan. Lainnya menurut tabel izin; kalau tabel itu tidak terbaca, IzinTidakTerbaca dilempar."""
    if adalah_admin(p.role):
        return list(LAPORAN)
    izin = penyimpan_pengguna.izin_role(p.role)
    return [i for i in LAPORAN if i.casefold() in izin]


def _info_pengguna(p):
    return {"id": p.id, "username": p.username, "nama": p.nama, "role": p.role, "divisi": p.divisi, "company": p.company,
            "admin": adalah_admin(p.role), "laporan": _laporan_boleh(p)}


# Database tidak terbaca selalu dijawab 503, bukan 401/403: pengguna tidak boleh dikira salah password atau tidak punya akses.
_PESAN_503 = {
    "hak akses": "Pengaturan hak akses tidak dapat dibaca. Hubungi administrator.",
    "pengguna": "Database pengguna tidak dapat dihubungi. Coba lagi sebentar atau hubungi administrator.",
    "role": "Daftar role tidak bisa dibaca dari tabel role. Periksa DB_APP_TABEL_ROLE dan kolomnya, atau hubungi administrator.",
    "company": "Daftar company tidak bisa dibaca dari tabel company. Periksa DB_APP_TABEL_COMPANY dan kolomnya, atau hubungi administrator.",
    "divisi": "Daftar divisi tidak bisa dibaca dari tabel divisi. Periksa DB_APP_TABEL_DIVISI dan kolomnya, atau hubungi administrator.",
}


def _tak_terbaca(tabel, e):
    log.error("Tabel %s tidak terbaca: %s", tabel, e)
    raise HTTPException(503, _PESAN_503[tabel])


def _tanpa_izin_db(e, perintah, tabel="pengguna"):
    log.error("Tidak punya izin %s pada tabel %s: %s", perintah, tabel, e)
    raise HTTPException(503, f"Akun database yang dipakai server tidak punya izin {perintah} pada tabel {tabel}. Hubungi administrator database.")


def _pengguna_cpos(request):
    """Mode CPOS: pengguna & laporan yang boleh dibuka ditanyakan ke CPOS dengan cookie sesi CPOS dari browser."""
    try:
        data = cpos.pengguna(request.cookies.get(konfigurasi.CPOS_COOKIE) if request is not None else None,
                             request.headers.get("user-agent") if request is not None else None,
                             (request.headers.get("x-forwarded-for") if request is not None else None) or _ip(request))
    except cpos.CposTidakTersedia as e:
        log.error("CPOS tidak dapat dihubungi di %s: %s", konfigurasi.CPOS_URL, e)
        raise HTTPException(503, "CPOS tidak dapat dihubungi untuk memeriksa login. Coba lagi sebentar atau hubungi administrator.")
    if not data:
        raise HTTPException(401, "Sesi CPOS berakhir. Silakan masuk lagi di CPOS.")
    pemilik = f"cpos:{data.get('sid') or data['username']}"
    _cpos_terakhir[pemilik] = time.monotonic()
    company = data.get("company")
    return {"id": data["id"], "username": data["username"], "nama": data["nama"], "role": data["role"], "divisi": "",
            "company": ", ".join(company) if company else "Semua", "admin": False, "cpos": True,
            "laporan": [i for i in LAPORAN if i in set(data["laporan"])], "_sid": pemilik}


def pengguna_saat_ini(sesi_id: str | None = Cookie(default=None, alias=NAMA_COOKIE), request: Request = None):
    """Dibaca ulang dari tabel pengguna setiap permintaan (dengan cache singkat), jadi akun yang dihapus atau diganti role-nya langsung berlaku.
    Mode CPOS (CPOS_URL diisi): dari sesi CPOS."""
    if cpos.aktif():
        return _pengguna_cpos(request)
    username = sesi_login.ambil(sesi_id)
    if not username:     # sesi yang diakhiri paksa membawa alasannya sendiri
        raise HTTPException(401, sesi_login.alasan(sesi_id) or "Belum masuk atau sesi berakhir. Silakan masuk lagi.")
    try:
        p = penyimpan_pengguna.cari(username)
        if p is None:
            raise HTTPException(401, "Belum masuk atau sesi berakhir. Silakan masuk lagi.")
        return {**_info_pengguna(p), "_sid": sesi_id}       # _sid tidak pernah dikirim ke browser
    except IzinTidakTerbaca as e:
        _tak_terbaca("hak akses", e)
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)


def _pemilik(user):
    """Data laporan milik sesi login (username kalau tanpa sesi, mis. di tes)."""
    return user.get("_sid") or user["username"]


def _cari_pengguna(username):
    """Untuk catatan dan daftar saja: tabel pengguna yang tidak terbaca tidak boleh menggagalkan permintaannya."""
    try:
        return penyimpan_pengguna.cari(username)
    except PenyimpanTidakTersedia:
        return None


def wajib_admin(user=Depends(pengguna_saat_ini)):
    if not user["admin"]:
        raise HTTPException(403, "Hanya System Administrator yang boleh mengelola pengguna.")
    return user


def _ip(request):
    return request.client.host if request is not None and getattr(request, "client", None) else None


def _catat(jenis, user, request=None, laporan=None, keterangan=""):
    log_aktivitas.catat(jenis, user["username"], user.get("nama", ""), user.get("role", ""), laporan, keterangan, _ip(request))


def _izinkan(user, laporan_id):
    if laporan_id not in user["laporan"]:
        raise HTTPException(403, "Anda tidak punya akses ke laporan ini.")


class PermintaanLogin(BaseModel):
    username: str
    sandi: str


class PermintaanMuat(BaseModel):
    mulai: date
    akhir: date
    segarkan: bool = False   # jalankan SQL lagi walau periode ini sudah dimuat


def _laporan(laporan_id):
    lap = LAPORAN.get(laporan_id)
    if lap is None:
        raise HTTPException(404, f"Laporan '{laporan_id}' tidak ada")
    return lap


def _dataset(lap, data_id, user):
    ds = gudang.ambil(data_id, _pemilik(user))
    if ds is None or ds.laporan != lap.id:
        raise HTTPException(404, "Data laporan ini sudah tidak ada di server (misalnya server dimulai ulang). Muat ulang periodenya.")
    return ds


_PARAMETER_UMUM = {"data_id", "jenis", "jumlah_minggu", "minggu", "dari", "sampai", "cari", "urut", "arah", "halaman", "ukuran"}


def _rentang(lap, ds, jumlah_minggu, dari, sampai):
    """Rentang tampilan di dalam data yang sudah dimuat (tanpa SQL). Tanpa dari/sampai: seluruh periode yang dimuat."""
    if dari is None and sampai is None:
        return ds, jumlah_minggu
    if dari is None or sampai is None:
        raise HTTPException(422, "Isi tanggal dari dan sampai")
    if dari > sampai:
        raise HTTPException(422, "Tanggal dari tidak boleh setelah tanggal sampai")
    mulai, akhir = date.fromisoformat(str(ds.mulai)[:10]), date.fromisoformat(str(ds.akhir)[:10])
    if dari < mulai or sampai > akhir:
        raise HTTPException(422, f"Rentang harus di dalam data yang dimuat ({_tanggal(mulai)} sampai {_tanggal(akhir)}). Untuk tanggal lain, muat ulang periodenya.")
    return TampilanRentang(ds, dari.isoformat(), sampai.isoformat()), jumlah_minggu


def _filter(lap, request):
    """Filter dari URL (perusahaan=SUN&perusahaan=YBS). Namanya diambil dari lap.filter_didukung."""
    if request is None:
        return {}
    asing = sorted(set(request.query_params) - set(lap.filter_didukung) - _PARAMETER_UMUM)
    if asing:
        raise HTTPException(422, f"Filter '{asing[0]}' tidak tersedia untuk laporan ini")
    hasil = {}
    for nama in lap.filter_didukung:
        nilai = [v for v in request.query_params.getlist(nama) if v.strip()]
        if not nilai:
            continue
        if len(nilai) > 60 or any(len(v) > 120 for v in nilai):
            raise HTTPException(422, f"Filter {nama} terlalu banyak atau terlalu panjang")
        hasil[nama] = sorted(set(nilai))
    return hasil


def _ringkas(p):
    r = p.ringkas()
    ds = gudang.ambil(p.data_id) if p.data_id else None
    r["catatan"] = ds.catatan if ds else {}
    return r


@app.get("/api/status")
def status():
    """Tanpa login: dipakai halaman masuk."""
    return {"ok": True, "nama": konfigurasi.NAMA_APLIKASI, "cpos": cpos.aktif()}


@app.post("/api/auth/masuk")
def masuk(perm: PermintaanLogin, response: Response, request: Request = None):
    if cpos.aktif():
        raise HTTPException(400, "Masuk lewat CPOS, lalu buka laporan dari menu CPOS.")
    if len(perm.username) > 100 or len(perm.sandi) > 200:
        raise HTTPException(422, "Username atau password terlalu panjang")
    kunci = perm.username.strip().lower()
    tunggu = pembatas_login.sisa_tunggu(kunci)
    if tunggu > 0:
        raise HTTPException(429, f"Terlalu banyak percobaan masuk. Coba lagi dalam {tunggu} detik.")
    try:
        p = penyimpan_pengguna.cari(kunci)
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    # Hash palsu untuk username yang tidak ada, supaya waktu jawabannya sama
    try:
        sah = kata_sandi.cocok(perm.sandi, p.sandi if p else kata_sandi.HASH_PALSU)
    except kata_sandi.PustakaHilang as e:
        log.error("%s", e)
        raise HTTPException(503, "Login belum bisa dipakai: ada pustaka yang belum terpasang di server. Hubungi administrator.")
    if not (p and sah):
        pembatas_login.gagal(kunci)
        log.warning("Percobaan masuk gagal untuk '%s'", kunci[:50])
        log_aktivitas.catat("gagal_masuk", kunci[:50], ip=_ip(request))
        raise HTTPException(401, "Username atau password salah.")
    pembatas_login.berhasil(kunci)
    try:
        info = _info_pengguna(p)
    except IzinTidakTerbaca as e:
        _tak_terbaca("hak akses", e)
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    ip = _ip(request)     # di belakang proxy, ini alamat proxy-nya
    asal = f"IP {ip}" if ip else None
    response.set_cookie(
        NAMA_COOKIE, sesi_login.buat(p.username, asal=asal), httponly=True, samesite="strict", secure=COOKIE_SECURE,
        max_age=int(SESI_JAM * 3600), path="/",
    )
    log.info("Masuk: %s (role %s)%s", p.username, p.role, f" dari {asal}" if asal else "")
    _catat("masuk", info, request)
    return info


@app.post("/api/auth/keluar")
def keluar(response: Response, sesi_id: str | None = Cookie(default=None, alias=NAMA_COOKIE), request: Request = None):
    """Aman dipanggil walau sesi sudah berakhir."""
    username = sesi_login.ambil(sesi_id)
    sesi_login.hapus(sesi_id)
    if username:
        p = _cari_pengguna(username)
        log_aktivitas.catat("keluar", username, p.nama if p else "", p.role if p else "", ip=_ip(request))
    response.delete_cookie(NAMA_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/saya")
def saya(user=Depends(pengguna_saat_ini)):
    # Mode CPOS: batas idle dijaga CPOS sendiri, jadi frontend tidak mengeluarkan pengguna
    return {**{k: v for k, v in user.items() if not k.startswith("_")}, "batas_idle_detik": 0 if cpos.aktif() else sesi_login.idle}


class PermintaanGantiSandi(BaseModel):
    sandi_lama: str
    sandi_baru: str


@app.post("/api/auth/ganti-sandi")
def ganti_sandi(perm: PermintaanGantiSandi, request: Request = None, user=Depends(pengguna_saat_ini)):
    if cpos.aktif():
        raise HTTPException(400, "Password diganti di CPOS.")
    """Salah password lama dibatasi seperti login, supaya sesi yang tertinggal terbuka tidak bisa dipakai menebak password."""
    if len(perm.sandi_lama) > 200 or len(perm.sandi_baru) > 200:
        raise HTTPException(422, "Password terlalu panjang (maksimal 200 karakter).")
    kunci = f"ganti:{user['username'].lower()}"
    tunggu = pembatas_login.sisa_tunggu(kunci)
    if tunggu > 0:
        raise HTTPException(429, f"Terlalu banyak percobaan. Coba lagi dalam {tunggu} detik.")
    try:
        p = penyimpan_pengguna.cari(user["username"])
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    if p is None:
        raise HTTPException(401, "Belum masuk atau sesi berakhir. Silakan masuk lagi.")
    try:
        sah = kata_sandi.cocok(perm.sandi_lama, p.sandi)
    except kata_sandi.PustakaHilang as e:
        log.error("%s", e)
        raise HTTPException(503, "Password belum bisa diganti: ada pustaka yang belum terpasang di server. Hubungi administrator.")
    if not sah:
        pembatas_login.gagal(kunci)
        raise HTTPException(400, "Password lama salah.")
    pembatas_login.berhasil(kunci)
    if not 8 <= len(perm.sandi_baru) <= 200:
        raise HTTPException(422, "Password baru minimal 8 karakter.")
    if perm.sandi_baru == perm.sandi_lama:
        raise HTTPException(422, "Password baru harus berbeda dari password lama.")
    data = {"nama": p.nama, "role": p.role, "divisi": p.divisi, "company": p.company}     # hanya password yang berubah
    try:
        penyimpan_pengguna.ubah(p.id, data, kata_sandi.hash_sandi(perm.sandi_baru, _algoritma_hash()))
    except kata_sandi.PustakaHilang as e:
        log.error("%s", e)
        raise HTTPException(503, f"Password belum bisa diganti: {e}")
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "UPDATE")
    except (DataTidakValid, PenyimpanTidakTersedia) as e:
        _tak_terbaca("pengguna", e)
    log.info("Password diganti oleh pemiliknya: %s", p.username)
    _catat("ganti_sandi", user, request)
    return {"ok": True}


@app.post("/api/auth/aktif")
def tanda_aktif(user=Depends(pengguna_saat_ini)):
    """Pengguna masih aktif di halaman. pengguna_saat_ini sudah memperbarui waktu aktivitas terakhirnya."""
    return {"ok": True}


# ---------- Kelola pengguna (hanya System Administrator) ----------
class PermintaanPengguna(BaseModel):
    username: str
    sandi: str
    nama: str
    role: str
    divisi: str
    company: str | list[str]     # daftar, atau teks dipisah koma


class PermintaanUbahPengguna(BaseModel):
    nama: str
    role: str
    divisi: str
    company: str | list[str]
    sandi: str | None = None     # kosong = password tidak diganti


def _ringkas_pengguna(p):
    return {"id": p.id, "username": p.username, "nama": p.nama, "role": p.role, "divisi": p.divisi, "company": p.company, "dibuat": p.dibuat,
            "admin": adalah_admin(p.role)}


def _algoritma_hash():
    global _algoritma
    if _algoritma is None:
        _algoritma = kata_sandi.pilih_algoritma(penyimpan_pengguna.jenis_hash(), os.environ.get("PASSWORD_HASH", "auto"))
        log.info("Akun baru memakai hash %s.", _algoritma)
    return _algoritma


def _id_pengguna(teks):
    return int(teks) if teks.isdigit() else teks


@app.get("/api/admin/pengguna")
def daftar_pengguna(user=Depends(wajib_admin)):
    try:
        return [_ringkas_pengguna(p) for p in penyimpan_pengguna.daftar()]
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)


@app.get("/api/admin/opsi")
def opsi_pengguna(user=Depends(wajib_admin)):
    try:
        role = sorted(penyimpan_pengguna.role_aktif(), key=str.casefold)
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("role", e)
    try:
        company = penyimpan_pengguna.company_aktif()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("company", e)
    bawaan = kanonik_role(konfigurasi.ROLE_BAWAAN, role) or (role[0] if role else "")
    try:
        return {"role": role, "role_bawaan": bawaan, "divisi": penyimpan_pengguna.opsi()["divisi"], "company": company}
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)


@app.post("/api/admin/pengguna")
def tambah_pengguna(perm: PermintaanPengguna, request: Request = None, user=Depends(wajib_admin)):
    try:
        role_sah = penyimpan_pengguna.role_aktif()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("role", e)
    try:
        company_sah = penyimpan_pengguna.company_aktif()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("company", e)
    try:
        data = periksa_pengguna_baru(perm.username, perm.sandi, perm.nama, perm.role, perm.divisi, perm.company, role_sah, company_sah)
    except DataTidakValid as e:
        raise HTTPException(422, str(e))
    try:
        baru = penyimpan_pengguna.tambah(data, kata_sandi.hash_sandi(data["sandi"], _algoritma_hash()))
    except DataTidakValid as e:
        raise HTTPException(409, str(e))     # username sudah dipakai
    except kata_sandi.PustakaHilang as e:
        log.error("%s", e)
        raise HTTPException(503, f"Akun belum bisa dibuat: {e}")
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "INSERT")
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    log.info("Akun dibuat: %s (%s) oleh %s", baru.username, baru.role, user["username"])
    _catat("akun_tambah", user, request, keterangan=f"{baru.username} ({baru.role})")
    return _ringkas_pengguna(baru)


@app.put("/api/admin/pengguna/{pengguna_id}")
def ubah_pengguna(pengguna_id: str, perm: PermintaanUbahPengguna, request: Request = None, user=Depends(wajib_admin)):
    """Username tidak bisa diubah. Kalau password diganti admin, sesi akun itu dicabut (kecuali akun admin itu sendiri)."""
    id_ = _id_pengguna(pengguna_id)
    try:
        target = penyimpan_pengguna.cari_id(id_)
        if target is None:
            raise HTTPException(404, "Pengguna tidak ditemukan.")
        role_sah = penyimpan_pengguna.role_aktif()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    try:
        company_sah = penyimpan_pengguna.company_aktif()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("company", e)
    try:
        data = periksa_ubah_pengguna(perm.nama, perm.role, perm.divisi, perm.company, perm.sandi, role_sah, company_sah, target)
    except DataTidakValid as e:
        raise HTTPException(422, str(e))
    sendiri = str(target.id) == str(user["id"])
    role_berubah = data["role"].casefold() != target.role.casefold()
    if sendiri and role_berubah:
        raise HTTPException(400, "Anda tidak bisa mengubah role akun Anda sendiri.")
    try:
        if role_berubah and adalah_admin(target.role) and not adalah_admin(data["role"]) and penyimpan_pengguna.jumlah_admin() <= 1:
            raise HTTPException(400, "System Administrator terakhir tidak bisa diturunkan rolenya.")
        hash_baru = kata_sandi.hash_sandi(data["sandi"], _algoritma_hash()) if data["sandi"] else None
        baru = penyimpan_pengguna.ubah(id_, data, hash_baru)
    except DataTidakValid as e:
        raise HTTPException(404, str(e))
    except kata_sandi.PustakaHilang as e:
        log.error("%s", e)
        raise HTTPException(503, f"Akun belum bisa diubah: {e}")
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "UPDATE")
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    if data["sandi"] and not sendiri:
        sesi_login.cabut(baru.username, "Password akun Anda diganti oleh administrator. Masuk lagi dengan password yang baru.")
    perubahan = [k for k, a_, b_ in (("nama", target.nama, baru.nama), ("role", target.role, baru.role), ("divisi", target.divisi, baru.divisi),
                                     ("company", target.company, baru.company)) if a_ != b_] + (["password"] if data["sandi"] else [])
    log.info("Akun diubah: %s oleh %s (%s)", baru.username, user["username"], ", ".join(perubahan) or "tanpa perubahan")
    _catat("akun_ubah", user, request, keterangan=f"{baru.username}: {', '.join(perubahan) or 'tanpa perubahan'}")
    return _ringkas_pengguna(baru)


@app.delete("/api/admin/pengguna/{pengguna_id}")
def hapus_pengguna(pengguna_id: str, request: Request = None, user=Depends(wajib_admin)):
    id_ = _id_pengguna(pengguna_id)
    try:
        target = penyimpan_pengguna.cari_id(id_)
        if target is None:
            raise HTTPException(404, "Pengguna tidak ditemukan.")
        if str(target.id) == str(user["id"]):
            raise HTTPException(400, "Akun yang sedang Anda pakai tidak bisa dihapus.")
        if adalah_admin(target.role) and penyimpan_pengguna.jumlah_admin() <= 1:
            raise HTTPException(400, "System Administrator terakhir tidak bisa dihapus.")
        dihapus = penyimpan_pengguna.hapus(id_)
    except DataTidakValid as e:
        raise HTTPException(404, str(e))
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "DELETE")
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("pengguna", e)
    sesi_login.cabut(dihapus.username, "Akun ini sudah dihapus oleh administrator.")
    log.info("Akun dihapus: %s oleh %s", dihapus.username, user["username"])
    _catat("akun_hapus", user, request, keterangan=f"{dihapus.username} ({dihapus.role})")
    return {"ok": True}


# ---------- Permission Control (hanya System Administrator) ----------
class PermintaanDivisi(BaseModel):
    nama: str
    kode: str
    company_id: int | None = None


class PermintaanRole(BaseModel):
    nama: str
    deskripsi: str = ""
    divisi_id: int | None = None


@app.get("/api/admin/struktur")
def daftar_struktur(user=Depends(wajib_admin)):
    """Divisi, role per divisi, dan baris company untuk halaman Role & Divisi."""
    try:
        divisi = penyimpan_pengguna.daftar_divisi()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("divisi", e)
    try:
        role = penyimpan_pengguna.daftar_role_divisi()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("role", e)
    try:
        company = penyimpan_pengguna.daftar_baris_company()
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("company", e)
    return {"divisi": divisi, "role": role, "company": company}


@app.post("/api/admin/divisi")
def tambah_divisi(perm: PermintaanDivisi, request: Request = None, user=Depends(wajib_admin)):
    try:
        baru = penyimpan_pengguna.tambah_divisi(periksa_divisi_baru(perm.nama, perm.kode, perm.company_id))
    except DataTidakValid as e:
        raise HTTPException(422, str(e))
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "INSERT", "divisi")
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("divisi", e)
    log.info("Divisi dibuat: %s oleh %s", baru["nama"], user["username"])
    _catat("divisi_tambah", user, request, keterangan=f"{baru['nama']} ({baru['kode']})")
    return baru


@app.post("/api/admin/role")
def tambah_role(perm: PermintaanRole, request: Request = None, user=Depends(wajib_admin)):
    """Role baru belum punya akses laporan apa pun; aksesnya diatur di Permission Control."""
    try:
        baru = penyimpan_pengguna.tambah_role(periksa_role_baru(perm.nama, perm.deskripsi, perm.divisi_id))
    except DataTidakValid as e:
        raise HTTPException(422, str(e))
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "INSERT", "role")
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("role", e)
    log.info("Role dibuat: %s oleh %s", baru["nama"], user["username"])
    _catat("role_tambah", user, request, keterangan=baru["nama"])
    return baru


class PermintaanIzin(BaseModel):
    role: str
    laporan: str
    akses: bool


def _izin_halaman_gagal(e):
    log.error("Tabel izin tidak terbaca: %s", e)
    raise HTTPException(503, f"Tabel izin '{penyimpan_pengguna.tabel_izin}' tidak bisa dibaca. Periksa DB_APP_TABEL_IZIN di backend/.env, kolomnya "
                             "(role, page_key, can_access, ...), dan izin akun database server.")


@app.get("/api/admin/izin")
def daftar_izin(user=Depends(wajib_admin)):
    ids = list(LAPORAN)
    try:
        role = penyimpan_pengguna.izin_semua_role(ids)
    except PenyimpanTidakTersedia as e:
        _izin_halaman_gagal(e)
    hasil = []
    for r in sorted(role, key=lambda r: r["nama"].casefold()):
        if not r["aktif"] or not r["nama"]:
            continue
        admin = adalah_admin(r["nama"])
        hasil.append({"id": r["id"], "nama": r["nama"], "admin": admin,
                      "izin": {i: True for i in ids} if admin else r["izin"]})
    return {"laporan": [{"id": l.id, "nama": l.nama, "deskripsi": l.deskripsi} for l in LAPORAN.values()], "role": hasil}


@app.put("/api/admin/izin")
def atur_izin(perm: PermintaanIzin, request: Request = None, user=Depends(wajib_admin)):
    """Berlaku pada permintaan berikutnya, tanpa pengguna harus masuk lagi."""
    if perm.laporan not in LAPORAN:
        raise HTTPException(422, f"Laporan '{perm.laporan}' tidak dikenal.")
    try:
        nama = kanonik_role(perm.role, [r["nama"] for r in penyimpan_pengguna.daftar_role()])
    except PenyimpanTidakTersedia as e:
        _tak_terbaca("role", e)
    if nama is None:
        raise HTTPException(422, f"Role '{perm.role}' tidak ada di tabel role.")
    if adalah_admin(nama):
        raise HTTPException(400, f"Role {nama} selalu punya akses penuh dan tidak bisa dibatasi.")
    try:
        hasil = penyimpan_pengguna.atur_izin(nama, perm.laporan, perm.akses)
    except DataTidakValid as e:
        raise HTTPException(422, str(e))
    except TidakPunyaIzin as e:
        _tanpa_izin_db(e, "INSERT dan UPDATE", f"izin '{penyimpan_pengguna.tabel_izin}'")
    except PenyimpanTidakTersedia as e:
        _izin_halaman_gagal(e)
    log.info("Izin diubah: role %s, laporan %s, akses=%s, oleh %s", hasil["role"], hasil["laporan"], hasil["akses"], user["username"])
    _catat("izin", user, request, hasil["laporan"], f"Role {hasil['role']}: {'diberi akses' if hasil['akses'] else 'akses dicabut'}")
    return hasil


@app.get("/api/laporan")
def daftar_laporan(user=Depends(pengguna_saat_ini)):
    hari_ini = date.today()

    def mulai(l):
        if getattr(l, "awal_tahun", False):
            return date(hari_ini.year, 1, 1).isoformat()
        hari = getattr(l, "hari_bawaan", None)
        return (hari_ini - timedelta(days=hari - 1)).isoformat() if hari else l.mulai_bawaan

    return [
        {"id": l.id, "nama": l.nama, "grup": getattr(l, "grup", "Analytical Dashboard"), "deskripsi": l.deskripsi, "mulai_bawaan": mulai(l),
         "akhir_bawaan": hari_ini.isoformat(), "maks_hari": MAKS_HARI}
        for l in LAPORAN.values()
        if l.id in user["laporan"]
    ]


@app.post("/api/laporan/{laporan_id}/muat")
def muat_laporan(laporan_id: str, perm: PermintaanMuat, request: Request = None, user=Depends(pengguna_saat_ini)):
    """SQL berjalan di latar belakang. Periode yang sudah dimuat dipakai ulang, kecuali segarkan=true."""
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    if perm.mulai > perm.akhir:
        raise HTTPException(422, "Tanggal mulai tidak boleh setelah tanggal akhir")
    if (perm.akhir - perm.mulai).days > MAKS_HARI:
        raise HTTPException(422, f"Rentang tanggal terlalu panjang (maksimal {MAKS_HARI} hari)")
    p = gudang.mulai_muat(lap.id, perm.mulai.isoformat(), perm.akhir.isoformat(), lap.pemuat, _pemilik(user), segarkan=perm.segarkan)
    cara = "muat ulang dari SQL Server" if perm.segarkan else "memakai data yang sudah dimuat" if p.status == "selesai" else "dari SQL Server"
    _catat("muat", user, request, lap.id, f"{_tanggal(perm.mulai)} s/d {_tanggal(perm.akhir)}, {cara}")
    return _ringkas(p)


@app.get("/api/pekerjaan/{pekerjaan_id}")
def status_pekerjaan(pekerjaan_id: str, user=Depends(pengguna_saat_ini)):
    p = gudang.ambil_pekerjaan(pekerjaan_id, _pemilik(user))
    if p is None:
        raise HTTPException(404, "Pekerjaan tidak ditemukan")
    _izinkan(user, p.laporan)
    return _ringkas(p)


@app.post("/api/pekerjaan/{pekerjaan_id}/batal")
def batalkan_pekerjaan(pekerjaan_id: str, user=Depends(pengguna_saat_ini)):
    ada = gudang.ambil_pekerjaan(pekerjaan_id, _pemilik(user))
    if ada is None:
        raise HTTPException(404, "Pekerjaan tidak ditemukan")
    _izinkan(user, ada.laporan)
    return _ringkas(gudang.batalkan(pekerjaan_id, _pemilik(user)))


@app.get("/api/laporan/{laporan_id}/dashboard")
def dashboard(
    laporan_id: str,
    data_id: str = Query(..., max_length=40, description="id data dari hasil pemuatan"),
    jumlah_minggu: int = Query(5, ge=1, le=MAKS_MINGGU),
    minggu: int | None = Query(None, ge=0, le=MAKS_MINGGU - 1),
    dari: Annotated[date | None, Query(description="awal rentang tampilan, di dalam data yang dimuat (laporan mingguan)")] = None,
    sampai: Annotated[date | None, Query(description="akhir rentang tampilan")] = None,
    request: Request = None,
    user=Depends(pengguna_saat_ini),
):
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    ds = _dataset(lap, data_id, user)
    f = _filter(lap, request)
    lihat, jumlah_minggu = _rentang(lap, ds, jumlah_minggu, dari, sampai)
    kunci = ("dashboard", minggu, str(dari), str(sampai), tuple((k, tuple(v)) for k, v in sorted(f.items())))
    hasil = ds.hasil.get(kunci)
    if hasil is None:
        try:
            hasil = lap.bangun(lihat, jumlah_minggu, minggu, f)
        except FilterTidakValid as e:
            raise HTTPException(422, str(e))
        if len(ds.hasil) < 300:
            ds.hasil[kunci] = hasil
    return {**hasil, "dataset": {"mulai": ds.mulai, "akhir": ds.akhir,
                                  "dimuat_pada": ds.dimuat_pada.isoformat(timespec="seconds"), "catatan": ds.catatan}}


@app.get("/api/laporan/{laporan_id}/detail")
def detail(
    laporan_id: str,
    data_id: str = Query(..., max_length=40),
    jenis: str = Query(..., max_length=20, description="Tab tabel: outstanding, po (PR/PO), pi (PO/PI), semua atau berisiko (timbangan)"),
    jumlah_minggu: int = Query(5, ge=1, le=MAKS_MINGGU),
    minggu: int | None = Query(None, ge=0, le=MAKS_MINGGU - 1),
    cari: str | None = Query(None, max_length=100),
    urut: str | None = Query(None, max_length=30),
    arah: str | None = Query(None, max_length=4),
    halaman: int = Query(1, ge=1),
    ukuran: int = Query(50, ge=10, le=200),
    dari: Annotated[date | None, Query()] = None,
    sampai: Annotated[date | None, Query()] = None,
    request: Request = None,
    user=Depends(pengguna_saat_ini),
):
    """total_semua sama dengan angka di kartu yang bersangkutan."""
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    ds = _dataset(lap, data_id, user)
    f = _filter(lap, request)
    lihat, jumlah_minggu = _rentang(lap, ds, jumlah_minggu, dari, sampai)
    try:
        hasil = lap.detail(lihat, jenis, jumlah_minggu, minggu, f, cari, urut, arah, halaman, ukuran)
    except FilterTidakValid as e:
        raise HTTPException(422, str(e))
    return {**hasil, "maks_ekspor": ekspor.MAKS_BARIS,
            "dataset": {"mulai": ds.mulai, "akhir": ds.akhir, "dimuat_pada": ds.dimuat_pada.isoformat(timespec="seconds")}}


_LABEL_FILTER = {"perusahaan": "Perusahaan", "kategori": "Kategori", "buyer": "Buyer", "pembuat": "Buyer", "umur": "Aging", "supir": "Nama Supir", "produk": "Produk", "operator": "Operator"}


def _tanggal(teks):
    """'2026-10-15' -> '15/10/2026'; teks lain apa adanya."""
    try:
        return date.fromisoformat(str(teks)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(teks)


@app.get("/api/laporan/{laporan_id}/detail/export")
def ekspor_detail(
    laporan_id: str,
    data_id: str = Query(..., max_length=40),
    jenis: str = Query(..., max_length=20),
    jumlah_minggu: int = Query(5, ge=1, le=MAKS_MINGGU),
    minggu: int | None = Query(None, ge=0, le=MAKS_MINGGU - 1),
    cari: str | None = Query(None, max_length=100),
    urut: str | None = Query(None, max_length=30),
    arah: str | None = Query(None, max_length=4),
    dari: Annotated[date | None, Query()] = None,
    sampai: Annotated[date | None, Query()] = None,
    request: Request = None,
    user=Depends(pengguna_saat_ini),
):
    """Semua baris yang cocok dengan filter, pencarian, dan urutan di layar (bukan hanya satu halaman), paling banyak ekspor.MAKS_BARIS."""
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    if not ekspor.tersedia():
        log.error("%s", ekspor.PESAN_PUSTAKA_HILANG)
        raise HTTPException(503, ekspor.PESAN_PUSTAKA_HILANG)
    ds = _dataset(lap, data_id, user)
    f = _filter(lap, request)
    lihat, jumlah_minggu = _rentang(lap, ds, jumlah_minggu, dari, sampai)
    try:
        hasil = lap.detail(lihat, jenis, jumlah_minggu, minggu, f, cari, urut, arah, 1, ekspor.MAKS_BARIS)
    except FilterTidakValid as e:
        raise HTTPException(422, str(e))
    baris, total = hasil["baris"], hasil["total"]
    judul_kolom = {k["kunci"]: k["judul"] for k in hasil["kolom"]}
    periode = hasil.get("periode")
    label = {**_LABEL_FILTER, **getattr(lap, "label_filter", {})}
    info = [
        ("Laporan", lap.nama),
        ("Tabel", hasil.get("judul") or jenis),
        ("Data tanggal", f"{_tanggal(ds.mulai)} s/d {_tanggal(ds.akhir)}"),
        ("Dimuat pada", ds.dimuat_pada.strftime("%d/%m/%Y %H:%M")),
        ("Jendela tabel", f"{_tanggal(periode['mulai'])} s/d {_tanggal(periode['akhir'])}" if periode else None),
        ("Filter tanggal", f"{_tanggal(dari)} s/d {_tanggal(sampai)}" if dari else None),
        *[(label.get(n, n), ", ".join(v)) for n, v in f.items()],
        ("Filter", None if f else "Tidak ada (semua data)"),
        ("Pencarian", hasil.get("cari") or None),
        ("Urutan", f"{judul_kolom.get(hasil['urut'], hasil['urut'])} ({'naik' if hasil['arah'] == 'asc' else 'turun'})"),
        ("Baris diekspor", len(baris)),
        ("Baris sebelum pencarian", hasil["total_semua"] if hasil.get("cari") else None),
        ("Catatan", f"Dibatasi {ekspor.MAKS_BARIS:,} baris dari {total:,} baris yang cocok. Persempit dengan filter atau pencarian." if total > len(baris) else None),
        ("Diekspor oleh", f"{user['nama']} ({user['username']})"),
        ("Diekspor pada", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    isi = ekspor.buat_xlsx(hasil.get("judul") or jenis, hasil["kolom"], baris, info)
    nama = ekspor.nama_berkas(lap.id, jenis, ds.mulai, ds.akhir)
    log.info("Ekspor Excel %s/%s: %d baris oleh %s", lap.id, jenis, len(baris), user["username"])
    ket = [f"Tab {hasil.get('judul') or jenis}", f"{len(baris):,} baris".replace(",", "."),
           *[f"{label.get(n, n)}: {', '.join(v)}" for n, v in f.items()], *([f"cari \"{cari}\""] if cari else [])]
    _catat("ekspor", user, request, lap.id, "; ".join(ket))
    return Response(content=isi, media_type=ekspor.XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{nama}"', "Cache-Control": "no-store"})


# ---------- Log aktivitas (hanya System Administrator) ----------
@app.get("/api/admin/aktivitas")
def daftar_aktivitas(
    mulai: date | None = Query(None),
    akhir: date | None = Query(None),
    pengguna: str | None = Query(None, max_length=100),
    jenis: str | None = Query(None, max_length=30),
    laporan: str | None = Query(None, max_length=60),
    halaman: int = Query(1, ge=1),
    ukuran: int = Query(50, ge=10, le=200),
    user=Depends(wajib_admin),
):
    """Bawaan 7 hari terakhir. Ringkasan per pengguna mengabaikan filter pengguna, supaya tetap bisa dipakai memilih pengguna lain."""
    akhir = akhir or date.today()
    mulai = mulai or akhir - timedelta(days=6)
    if mulai > akhir:
        raise HTTPException(422, "Tanggal mulai tidak boleh setelah tanggal akhir")
    if (akhir - mulai).days >= konfigurasi.AKTIVITAS_SIMPAN_HARI:
        raise HTTPException(422, f"Log hanya disimpan {konfigurasi.AKTIVITAS_SIMPAN_HARI} hari terakhir")
    if jenis and jenis not in JENIS_AKTIVITAS:
        raise HTTPException(422, f"Jenis aktivitas '{jenis}' tidak dikenal")
    semua = log_aktivitas.baca(mulai, akhir)
    sesuai = [b for b in semua if (not jenis or b["jenis"] == jenis) and (not laporan or b.get("laporan") == laporan)]
    pilih = [b for b in sesuai if not pengguna or b["username"].casefold() == pengguna.casefold()]
    nama_laporan = lambda i: LAPORAN[i].nama if i in LAPORAN else i
    jumlah_halaman = max(1, -(-len(pilih) // ukuran))
    halaman = min(halaman, jumlah_halaman)
    baris = [{**b, "jenis_nama": JENIS_AKTIVITAS.get(b["jenis"], b["jenis"]), "laporan_nama": nama_laporan(b["laporan"]) if b.get("laporan") else None}
             for b in pilih[(halaman - 1) * ukuran:halaman * ukuran]]
    return {
        "mulai": mulai.isoformat(), "akhir": akhir.isoformat(), "simpan_hari": konfigurasi.AKTIVITAS_SIMPAN_HARI,
        "baris": baris, "total": len(pilih), "halaman": halaman, "jumlah_halaman": jumlah_halaman, "ukuran": ukuran,
        "per_pengguna": [{**r, "laporan": [nama_laporan(i) for i in r["laporan"]]} for r in ringkas_pengguna(sesuai)],
        "jumlah_gagal_masuk": sum(1 for b in pilih if b["jenis"] == "gagal_masuk"),
        "pilihan": {"jenis": [{"kunci": k, "nama": v} for k, v in JENIS_AKTIVITAS.items()],
                    "laporan": [{"id": l.id, "nama": l.nama} for l in LAPORAN.values()]},
    }


# ---------- Sesi aktif (hanya System Administrator) ----------
def _waktu_epoch(t):
    return datetime.fromtimestamp(t).isoformat(timespec="seconds") if t else None


@app.get("/api/admin/sesi")
def daftar_sesi(user=Depends(wajib_admin)):
    """Satu baris per sesi, jadi akun yang masuk di dua perangkat tampil dua kali."""
    sendiri = sesi_login.id_sesi(user.get("_sid")) if user.get("_sid") else None
    hasil = []
    for s in sesi_login.daftar():
        p = _cari_pengguna(s["username"])
        hasil.append({"id": s["id"], "username": s["username"], "nama": p.nama if p else "", "role": p.role if p else "",
                      "masuk": _waktu_epoch(s["masuk"]), "terakhir": _waktu_epoch(s["terakhir"]), "kedaluwarsa": _waktu_epoch(s["kedaluwarsa"]),
                      "asal": s["asal"], "sesi_ini": s["id"] == sendiri})
    return hasil


class PermintaanPengaturanSesi(BaseModel):
    idle_menit: float


@app.get("/api/admin/pengaturan/sesi")
def baca_pengaturan_sesi(user=Depends(wajib_admin)):
    return {"idle_menit": round(sesi_login.idle / 60), "sesi_jam": SESI_JAM}


@app.put("/api/admin/pengaturan/sesi")
def ubah_pengaturan_sesi(perm: PermintaanPengaturanSesi, request: Request = None, user=Depends(wajib_admin)):
    """Langsung berlaku untuk sesi yang sedang berjalan, dan tetap setelah server dimulai ulang."""
    try:
        menit = periksa_idle(perm.idle_menit)
    except PengaturanTidakValid as e:
        raise HTTPException(422, str(e))
    lama = round(sesi_login.idle / 60)
    try:
        pengaturan.simpan(idle_menit=menit)
    except OSError as e:
        log.error("Pengaturan tidak bisa disimpan ke %s: %s", pengaturan.berkas, e)
        raise HTTPException(500, "Pengaturan tidak bisa disimpan di server. Periksa izin tulis folder backend.")
    sesi_login.idle = menit * 60
    log.info("Batas idle sesi diubah oleh %s: %s -> %s menit", user["username"], lama, menit)
    _catat("pengaturan", user, request, keterangan=f"Batas idle: {lama or 'tanpa batas'} -> {menit or 'tanpa batas'}{' menit' if menit else ''}")
    return {"idle_menit": menit, "sesi_jam": SESI_JAM}


@app.delete("/api/admin/sesi/{id_sesi}")
def cabut_sesi(id_sesi: str, request: Request = None, user=Depends(wajib_admin)):
    if user.get("_sid") and sesi_login.id_sesi(user["_sid"]) == id_sesi:
        raise HTTPException(400, "Ini sesi Anda sendiri. Pakai tombol Keluar.")
    username = sesi_login.cabut_id(id_sesi, "Sesi Anda diakhiri oleh administrator. Masuk lagi untuk melanjutkan.")
    if username is None:
        raise HTTPException(404, "Sesi itu sudah berakhir.")
    log.info("Sesi %s dikeluarkan oleh %s", username, user["username"])
    _catat("sesi_cabut", user, request, keterangan=username)
    return {"ok": True, "username": username}
