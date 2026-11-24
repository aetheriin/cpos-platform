"""API dashboard. Jalankan dari folder backend\\analytics: uvicorn api:app --reload

Login dan hak akses mengikuti CPOS (alamatnya dari PORT di backend\\.env): tiap permintaan, sesi CPOS milik browser diperiksa ke CPOS.
SQL Server hanya dipanggil saat pengguna memuat laporan; hasilnya disimpan di memori milik sesi itu. Karena itu jalankan satu proses
saja (tanpa banyak worker). Isi .env dijelaskan di README.
"""
import asyncio
import logging
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from inti import cpos, ekspor, konfigurasi
import pandas as pd
from inti.filter import FilterTidakValid, saring
from inti.gudang import Gudang
from inti.laporan import MAKS_MINGGU, TampilanRentang
from laporan import SEMUA as LAPORAN

logging.basicConfig(level=logging.INFO)

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
]
MAKS_HARI = konfigurasi.MAKS_HARI
# Data laporan milik sesi CPOS yang tidak memanggil Analytics selama ini dibuang (paling cepat 30 menit)
DIAM_MENIT = max(float(os.environ.get("SESI_IDLE_MENIT", "30")), 30)
SAPU_SESI_DETIK = float(os.environ.get("SESI_SAPU_DETIK", "60"))
log = logging.getLogger("dashboard")

gudang = Gudang()


def _sesi_berakhir(kode, username):
    _sudah_pramuat.discard(kode)
    dihapus, dihentikan = gudang.lepas(kode)
    if dihapus or dihentikan:
        log.info("Sesi %s berakhir: %d data laporan dibuang, %d pemuatan dihentikan", username, dihapus, dihentikan)


# Sesi dipegang CPOS, jadi data laporan milik sesi CPOS yang sudah lama tidak memanggil Analytics dibuang di sini
_cpos_terakhir = {}      # pemilik "cpos:<sid>" -> waktu terakhir terlihat (monotonic)


def _lepas_cpos_diam():
    batas = DIAM_MENIT * 60
    sekarang = time.monotonic()
    for pemilik, waktu in list(_cpos_terakhir.items()):
        if sekarang - waktu > batas:
            _cpos_terakhir.pop(pemilik, None)
            _sesi_berakhir(pemilik, pemilik)


async def _sapu_sesi():
    """Membuang data laporan sesi CPOS yang sudah diam, walau tidak ada yang mengaksesnya lagi."""
    while True:
        await asyncio.sleep(SAPU_SESI_DETIK)
        try:
            _lepas_cpos_diam()
        except Exception:  # noqa: BLE001 - penyapu harus tetap jalan
            log.exception("Gagal menyapu sesi kedaluwarsa")


def periksa_ekspor_awal():
    if not ekspor.tersedia():
        log.warning("%s", ekspor.PESAN_PUSTAKA_HILANG)


@asynccontextmanager
async def _siklus_hidup(_app):
    if not cpos.aktif():
        raise RuntimeError("CPOS_URL di backend/.env wajib diisi: login dan hak akses Analytics mengikuti CPOS.")
    log.info("Login dan hak akses laporan mengikuti CPOS di %s", konfigurasi.CPOS_URL)
    periksa_ekspor_awal()
    penyapu = asyncio.create_task(_sapu_sesi())
    try:
        yield
    finally:
        penyapu.cancel()


# Tanpa /docs, /redoc, /openapi.json: peta API tidak boleh terbuka untuk yang belum login
app = FastAPI(title="Dashboard API", lifespan=_siklus_hidup, docs_url=None, redoc_url=None, openapi_url=None)
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


def pengguna_saat_ini(request: Request = None):
    """Pengguna & laporan yang boleh dibuka ditanyakan ke CPOS dengan cookie sesi CPOS dari browser."""
    try:
        data = cpos.pengguna(request.cookies.get(konfigurasi.CPOS_COOKIE) if request is not None else None,
                             request.headers.get("user-agent") if request is not None else None,
                             (request.headers.get("x-forwarded-for") if request is not None else None) or _ip(request))
    except cpos.CposTidakTersedia as e:
        log.error("CPOS tidak dapat dihubungi di %s: %s", konfigurasi.CPOS_URL, e)
        raise HTTPException(503, "CPOS tidak dapat dihubungi untuk memeriksa login. Coba lagi sebentar atau hubungi administrator.")
    if not data:
        raise HTTPException(401, "Sesi CPOS berakhir. Silakan masuk lagi di CPOS.")
    if "_ditolak" in data:
        if data["_ditolak"] == "KHUSUS_ADMIN":
            raise HTTPException(403, "Akun Super Admin hanya untuk mengelola sistem, jadi tidak membuka laporan. "
                                     "Masuk dengan akun yang punya akses laporan.")
        raise HTTPException(403, data["_pesan"] or "Akun ini tidak bisa membuka laporan Analytics saat ini.")
    pemilik = f"cpos:{data.get('sid') or data['username']}"
    _cpos_terakhir[pemilik] = time.monotonic()
    company = data.get("company")
    return {"id": data["id"], "username": data["username"], "nama": data["nama"], "role": data["role"], "divisi": "",
            "company": ", ".join(company) if company else "Semua", "admin": False, "cpos": True,
            "laporan": [i for i in LAPORAN if i in set(data["laporan"])], "_sid": pemilik,
            "_pt_laporan": data.get("company_laporan") or {}}


def _pemilik(user):
    """Data laporan milik sesi CPOS (username kalau tanpa sesi, mis. di tes)."""
    return user.get("_sid") or user["username"]


def _ip(request):
    return request.client.host if request is not None and getattr(request, "client", None) else None


def _izinkan(user, laporan_id):
    if laporan_id not in user["laporan"]:
        raise HTTPException(403, "Anda tidak punya akses ke laporan ini.")


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
    return _batasi_pt(ds, _pt_boleh(user, lap.id))


def _pt_boleh(user, laporan_id):
    """PT yang boleh dilihat di laporan ini (Admin › Hak Akses › Cakupan data CPOS), huruf kecil. None = semua."""
    daftar = (user.get("_pt_laporan") or {}).get(laporan_id)
    return None if daftar is None else frozenset(str(x).strip().casefold() for x in daftar)


def _saring_pt(df, boleh):
    """Buang baris perusahaan di luar cakupan (kolom comp). Data lain (dict / list DataFrame) disaring per bagian."""
    if isinstance(df, dict):
        return {k: _saring_pt(v, boleh) for k, v in df.items()}
    if isinstance(df, (list, tuple)):
        return type(df)(_saring_pt(v, boleh) for v in df)
    if hasattr(df, "columns") and "comp" in df.columns:
        return df[df["comp"].astype(str).str.strip().str.casefold().isin(boleh)]
    return df


class _DatasetPT:
    """Dataset yang sama, hanya baris PT dalam cakupan pengguna; hasil olahan disimpan terpisah per cakupan."""

    def __init__(self, ds, boleh):
        self._ds, self.boleh = ds, boleh
        simpan = ds.hasil.setdefault(("_pt", boleh), {})
        if "df" not in simpan:
            simpan["df"] = _saring_pt(ds.df, boleh)
        self.df, self.hasil = simpan["df"], simpan.setdefault("hasil", {})

    def __getattr__(self, nama):
        return getattr(self._ds, nama)


def _batasi_pt(ds, boleh):
    return ds if boleh is None else _DatasetPT(ds, boleh)


_PARAMETER_UMUM = {"data_id", "jenis", "jumlah_minggu", "minggu", "dari", "sampai", "cari", "urut", "arah", "halaman", "ukuran", "kunci"}


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
    r["dimuat_pada"] = ds.dimuat_pada.isoformat(timespec="seconds") if ds else None
    return r


@app.get("/api/status")
def status():
    """Tanpa login: nama aplikasi untuk halaman."""
    return {"ok": True, "nama": konfigurasi.NAMA_APLIKASI, "cpos": True}


@app.get("/api/auth/saya")
def saya(user=Depends(pengguna_saat_ini)):
    # Batas idle dijaga CPOS sendiri, jadi frontend tidak mengeluarkan pengguna
    return {**{k: v for k, v in user.items() if not k.startswith("_")}, "batas_idle_detik": 0}


def _periode_bawaan(l):
    """(mulai, akhir) ISO yang dimuat saat laporan dibuka; sama untuk menu dan pramuat, supaya pramuat bisa dipakai ulang."""
    hari_ini = date.today()
    if getattr(l, "awal_tahun", False):
        mulai = date(hari_ini.year, 1, 1).isoformat()
    else:
        hari = getattr(l, "hari_bawaan", None)
        mulai = (hari_ini - timedelta(days=hari - 1)).isoformat() if hari else l.mulai_bawaan
    return mulai, hari_ini.isoformat()


@app.get("/api/laporan")
def daftar_laporan(user=Depends(pengguna_saat_ini)):
    hasil = [
        {"id": l.id, "nama": l.nama, "grup": getattr(l, "grup", "Analytical Dashboard"), "deskripsi": l.deskripsi, "mulai_bawaan": _periode_bawaan(l)[0],
         "akhir_bawaan": _periode_bawaan(l)[1], "maks_hari": l.maks_hari or MAKS_HARI}
        for l in LAPORAN.values()
        if l.id in user["laporan"]
    ]
    return hasil


_sudah_pramuat = set()   # pemilik sesi yang pramuatnya sudah dimulai


@app.post("/api/laporan/pramuat")
def pramuat_laporan(user=Depends(pengguna_saat_ini)):
    """Dipanggil sidebar CPOS (static/js/analytics/status_menu.js) di halaman pertama setelah login: semua laporan yang boleh dibuka mulai
    dimuat bersamaan di latar dengan periode bawaannya.
    Hanya sekali per sesi; data yang masih segar dari sesi lain langsung dipakai tanpa SQL."""
    pemilik = _pemilik(user)
    if not konfigurasi.PRAMUAT or pemilik in _sudah_pramuat:
        return {"dimulai": 0}
    _sudah_pramuat.add(pemilik)
    ids = [i for i in user["laporan"] if i in LAPORAN]
    for i in ids:
        lap = LAPORAN[i]
        gudang.mulai_muat(lap.id, *_periode_bawaan(lap), lap.pemuat, pemilik)
    log.info("Pramuat %s: %d laporan mulai dimuat bersamaan", user["username"], len(ids))
    return {"dimulai": len(ids)}


@app.get("/api/laporan/status")
def status_laporan(user=Depends(pengguna_saat_ini)):
    """Tanda di menu laporan (sidebar CPOS): laporan mana yang sedang dimuat atau datanya sudah siap untuk sesi ini."""
    return {k: v for k, v in gudang.status_pemilik(_pemilik(user)).items() if k in user["laporan"]}


@app.post("/api/laporan/{laporan_id}/muat")
def muat_laporan(laporan_id: str, perm: PermintaanMuat, request: Request = None, user=Depends(pengguna_saat_ini)):
    """SQL berjalan di latar belakang. Periode yang sudah dimuat dipakai ulang, kecuali segarkan=true."""
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    if perm.mulai > perm.akhir:
        raise HTTPException(422, "Tanggal mulai tidak boleh setelah tanggal akhir")
    if (perm.akhir - perm.mulai).days > (lap.maks_hari or MAKS_HARI):
        raise HTTPException(422, f"Rentang tanggal terlalu panjang (maksimal {lap.maks_hari or MAKS_HARI} hari)")
    p = gudang.mulai_muat(lap.id, perm.mulai.isoformat(), perm.akhir.isoformat(), lap.pemuat, _pemilik(user), segarkan=perm.segarkan)
    cara = "muat ulang dari SQL Server" if perm.segarkan else "memakai data yang sudah dimuat" if p.status == "selesai" else "dari SQL Server"
    log.info("Muat %s %s s/d %s (%s) oleh %s", lap.id, _tanggal(perm.mulai), _tanggal(perm.akhir), cara, user["username"])
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


@app.get("/api/laporan/{laporan_id}/rincian")
def rincian(
    laporan_id: str,
    data_id: str = Query(..., max_length=40),
    jenis: str = Query(..., max_length=20),
    kunci: str = Query(..., max_length=600, description="JSON identitas baris, mis. {comp, no_dok} atau {comp, mitra}"),
    dari: Annotated[date | None, Query()] = None,
    sampai: Annotated[date | None, Query()] = None,
    request: Request = None,
    user=Depends(pengguna_saat_ini),
):
    """Isi jendela rincian satu baris tabel detail."""
    lap = _laporan(laporan_id)
    _izinkan(user, lap.id)
    if lap.rincian is None:
        raise HTTPException(404, "Laporan ini belum punya rincian per baris.")
    try:
        k = json.loads(kunci)
    except ValueError:
        raise HTTPException(422, "kunci bukan JSON yang sah")
    if not isinstance(k, dict):
        raise HTTPException(422, "kunci harus objek JSON")
    ds = _dataset(lap, data_id, user)
    f = _filter(lap, request)
    lihat, _ = _rentang(lap, ds, 5, dari, sampai)
    try:
        return lap.rincian(lihat, jenis, k, f)
    except FilterTidakValid as e:
        raise HTTPException(422, str(e))


_LABEL_FILTER = {"perusahaan": "Perusahaan", "kategori": "Kategori", "buyer": "Buyer", "pembuat": "Buyer", "umur": "Aging", "supir": "Nama Supir", "produk": "Produk", "operator": "Operator"}


def _tanggal(teks):
    """'2026-10-15' -> '15/10/2026'; teks lain apa adanya."""
    try:
        return date.fromisoformat(str(teks)[:10]).strftime("%d-%m-%Y")
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
        raise HTTPException(503, ekspor.PESAN_EKSPOR_TIDAK_BISA)
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
        ("Dimuat pada", ds.dimuat_pada.strftime("%d-%m-%Y %H:%M")),
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
        ("Diekspor pada", datetime.now().strftime("%d-%m-%Y %H:%M")),
    ]
    if lap.id == "cash_flow" and jenis == "rekap_giro":
        awal, akhir = periode["mulai"][:7].replace("-", ""), periode["akhir"][:7].replace("-", "")
        isi = ekspor.buat_xlsx_giro(hasil.get("judul") or jenis, baris, awal if awal == akhir else f"{awal}-{akhir}", info)
    else:
        isi = ekspor.buat_xlsx(hasil.get("judul") or jenis, hasil["kolom"], baris, info)
    nama = ekspor.nama_berkas(lap.id, jenis, ds.mulai, ds.akhir)
    log.info("Ekspor Excel %s/%s: %d baris oleh %s", lap.id, jenis, len(baris), user["username"])
    return Response(content=isi, media_type=ekspor.XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{nama}"', "Cache-Control": "no-store"})


# ---------- Asisten: tanya jawab data laporan dengan kalimat biasa (backend/analytics/asisten) ----------
import asisten  # noqa: E402

_perusahaan_asisten = []


def _perusahaan_dikenal():
    """Kode perusahaan yang dikenali di kalimat; dibaca sekali dari tabel company."""
    global _perusahaan_asisten
    if not _perusahaan_asisten:
        try:
            from inti.perusahaan import daftar_perusahaan
            _perusahaan_asisten = daftar_perusahaan()
        except Exception:  # noqa: BLE001 - tanpa daftar, kode perusahaan tidak dikenali tapi pertanyaan lain tetap jalan
            log.exception("Asisten: daftar perusahaan tidak bisa dibaca")
    return _perusahaan_asisten


class PertanyaanAsisten(BaseModel):
    teks: str
    lalu: dict | None = None   # permintaan sebelumnya, untuk kalimat lanjutan
    menu: str | None = None    # id laporan yang sedang dibuka: rekomendasi dan prioritas jawaban
    tampilan: dict | None = None   # data_id, periode, dan filter yang sedang tampil di laporan itu (dari halaman)


class NilaiAsisten(BaseModel):
    id: str
    suka: bool
    komentar: str | None = None


class IngatAsisten(BaseModel):
    asal: str
    ke: str


@app.post("/api/asisten/tanya")
def tanya_asisten(perm: PertanyaanAsisten, user=Depends(pengguna_saat_ini)):
    """Data diambil dari periode bawaan tiap laporan atas nama sesi ini + ':asisten', supaya periode yang sedang dibuka di halaman
    laporan tidak dilepas. Data yang masih segar dari sesi lain dipakai tanpa SQL."""
    pemilik = f"{_pemilik(user)}:asisten"
    _cpos_terakhir[pemilik] = time.monotonic()
    menu = perm.menu if perm.menu in LAPORAN else None
    tamp = _tampilan_asisten(menu, perm.tampilan, user)   # None: pakai periode bawaan

    def ambil(sumber):
        if menu in _BARIS_MENU and _BARIS_MENU[menu][0] == sumber:
            return _baris_menu(menu, tamp, pemilik, sumber, user)
        lap = LAPORAN[asisten.kamus.SUMBER[sumber]["laporan"]]
        if lap.id not in user["laporan"]:
            raise asisten.TanpaAkses(sumber)
        if tamp:
            # data laporan yang sedang dibuka, atau data pendukungnya (mis. PR & PO memakai baris Purchase Request) disaring perusahaan yang sama
            ds = tamp["ds"] if lap.id == menu else _muat_asisten(lap, pemilik, sumber, user)
            df = ds.df
            pt = tamp["filter"].get("perusahaan")
            if pt and hasattr(df, "columns") and "comp" in df.columns:
                df = df[df["comp"].astype(str).str.upper().isin([x.upper() for x in pt])]
            return df, {"mulai": ds.mulai, "akhir": ds.akhir, "dimuat_pada": ds.dimuat_pada.isoformat(timespec="seconds")}
        p = gudang.mulai_muat(lap.id, *_periode_bawaan(lap), lap.pemuat, pemilik)
        if p.status == "gagal":
            raise HTTPException(503, f"Data laporan {lap.nama} gagal dimuat: {p.pesan}")
        if p.status != "selesai":
            raise asisten.Memuat(sumber)
        ds = gudang.ambil(p.data_id)
        if ds is None:
            raise asisten.Memuat(sumber)
        ds = _batasi_pt(ds, _pt_boleh(user, lap.id))
        return ds.df, {"mulai": ds.mulai, "akhir": ds.akhir, "dimuat_pada": ds.dimuat_pada.isoformat(timespec="seconds")}

    def dasbor(laporan_id, **filt):
        """Ringkasan dashboard laporan dengan periode bawaan, sama dengan yang tampil di halaman (dipakai ulang dari cache data itu)."""
        lap = LAPORAN[laporan_id]
        if lap.id not in user["laporan"]:
            raise asisten.TanpaAkses(lap.id)
        if tamp and lap.id == menu:
            # sama dengan yang tampil di halaman: periode, rentang, dan filter halaman; filter dari insight (mis. transaksi) didahulukan
            f = {**tamp["filter"], **{k: sorted(set(v)) for k, v in filt.items() if k in lap.filter_didukung and v}}
            kunci = ("dashboard", tamp["minggu"], str(tamp["dari"]), str(tamp["sampai"]), tuple((k, tuple(v)) for k, v in sorted(f.items())))
            hasil = tamp["ds"].hasil.get(kunci)
            if hasil is None:
                try:
                    hasil = lap.bangun(tamp["lihat"], tamp["jumlah_minggu"], tamp["minggu"], f)
                except FilterTidakValid:
                    hasil = lap.bangun(tamp["lihat"], tamp["jumlah_minggu"], tamp["minggu"], {k: v for k, v in f.items() if k in filt})
                if len(tamp["ds"].hasil) < 300:
                    tamp["ds"].hasil[kunci] = hasil
            return hasil
        p = gudang.mulai_muat(lap.id, *_periode_bawaan(lap), lap.pemuat, pemilik)
        if p.status == "gagal":
            raise HTTPException(503, f"Data laporan {lap.nama} gagal dimuat: {p.pesan}")
        ds = gudang.ambil(p.data_id) if p.status == "selesai" else None
        if ds is None:
            raise asisten.Memuat(lap.id)
        ds = _batasi_pt(ds, _pt_boleh(user, lap.id))
        f = {k: sorted(set(v)) for k, v in filt.items() if k in lap.filter_didukung and v}
        kunci = ("dashboard", None, "None", "None", tuple((k, tuple(v)) for k, v in sorted(f.items())))
        hasil = ds.hasil.get(kunci)
        if hasil is None:
            hasil = lap.bangun(ds, 5, None, f)
            if len(ds.hasil) < 300:
                ds.hasil[kunci] = hasil
        return hasil

    dasbor.lingkup = tamp["teks"] if tamp else None
    hasil = asisten.tanya(perm.teks, perm.lalu, ambil, _perusahaan_dikenal(), user["username"], (user.get("nama") or user["username"]).split()[0].title(),
                          menu, LAPORAN[menu].nama if menu else None, dasbor)
    if hasil.get("jenis") != "memuat":
        log.info("Asisten %s: %r -> %s", user["username"], perm.teks[:120], hasil.get("jenis"))
    return hasil


def _susun_pr(df):
    from laporan.purchase_request.sumber import susun
    return susun(df)


def _susun_po(df):
    from laporan.purchase_order.sumber import susun
    return susun(df)


# Menu outstanding yang baris insight-nya dihitung dari datanya sendiri: (sumber asisten, kolom tanggal dokumen, dimensi filter, penyusun baris)
_BARIS_MENU = {
    "pr_po": ("pr", "pr_date", {"perusahaan": "comp", "kategori": "category", "buyer": "buyer", "umur": "umur"}, _susun_pr),
    "po_pi": ("po", "cd", {"perusahaan": "comp", "kategori": "category", "pembuat": "creator", "umur": "umur"}, _susun_po),
}


def _baris_menu(menu, tamp, pemilik, sumber, user):
    """Baris PR atau PO dari data menu itu sendiri (bentuknya sama dengan laporan Purchase Request / Purchase Order),
    dengan periode, rentang tanggal, dan filter yang sedang tampil di halaman."""
    lap = LAPORAN[menu]
    if lap.id not in user["laporan"]:
        raise asisten.TanpaAkses(sumber)
    ds = tamp["ds"] if tamp else _muat_asisten(lap, pemilik, sumber, user)
    _, kol_tgl, dimensi, susun = _BARIS_MENU[menu]
    filt = tamp["filter"] if tamp else {}
    dari, sampai = (tamp["dari"], tamp["sampai"]) if tamp else (None, None)
    kunci = ("asisten_baris", str(dari), str(sampai), tuple((k, tuple(v)) for k, v in sorted(filt.items())))
    df = ds.hasil.get(kunci)
    if df is None:
        mentah = ds.df
        if "lalu" in mentah.columns:
            mentah = mentah[~mentah["lalu"].astype(bool)]   # periode pembanding KPI tidak ikut
        if dari and sampai:
            t = pd.to_datetime(mentah[kol_tgl], errors="coerce")
            mentah = mentah[(t >= pd.Timestamp(dari)) & (t < pd.Timestamp(sampai) + pd.Timedelta(days=1))]
        mentah = saring(mentah, filt, dimensi)
        df = susun(mentah)
        if len(ds.hasil) < 300:
            ds.hasil[kunci] = df
    return df, {"mulai": ds.mulai, "akhir": ds.akhir, "dimuat_pada": ds.dimuat_pada.isoformat(timespec="seconds")}


def _muat_asisten(lap, pemilik, sumber, user):
    """Data laporan dengan periode bawaan untuk AkasaBot. Belum siap: Memuat."""
    p = gudang.mulai_muat(lap.id, *_periode_bawaan(lap), lap.pemuat, pemilik)
    if p.status == "gagal":
        raise HTTPException(503, f"Data laporan {lap.nama} gagal dimuat: {p.pesan}")
    ds = gudang.ambil(p.data_id) if p.status == "selesai" else None
    if ds is None:
        raise asisten.Memuat(sumber)
    return _batasi_pt(ds, _pt_boleh(user, lap.id))


def _tampilan_asisten(menu, t, user):
    """Periode dan filter yang sedang tampil di halaman laporan `menu`, supaya AkasaBot membaca data yang sama.
    None kalau tidak dikirim atau datanya sudah tidak ada (AkasaBot kembali memakai periode bawaan)."""
    if not menu or not isinstance(t, dict) or not isinstance(t.get("data_id"), str) or menu not in user["laporan"]:
        return None
    lap = LAPORAN[menu]
    try:
        ds = _dataset(lap, t["data_id"][:40], user)
        dari = date.fromisoformat(t["dari"]) if t.get("dari") else None
        sampai = date.fromisoformat(t["sampai"]) if t.get("sampai") else None
        jm = int(t.get("jumlah_minggu") or 5)
        jm = min(max(jm, 1), MAKS_MINGGU)
        minggu = t.get("minggu")
        minggu = None if minggu is None else min(max(int(minggu), 0), MAKS_MINGGU - 1)
        lihat, jm = _rentang(lap, ds, jm, dari, sampai)
    except (HTTPException, ValueError, TypeError):
        return None
    f = {}
    for nama, nilai in (t.get("filter") or {}).items():
        if nama in lap.filter_didukung and isinstance(nilai, list):
            v = sorted({str(x)[:120] for x in nilai if str(x).strip()})[:60]
            if v:
                f[nama] = v
    awal, akhir = (dari, sampai) if dari and sampai else (ds.mulai, ds.akhir)
    teks = f"Dihitung dari tampilan laporan saat ini: {_tanggal(awal)} sampai {_tanggal(akhir)}"
    if f:
        teks += ", filter " + "; ".join(f"{_LABEL_FILTER.get(k, k.replace('_', ' ').capitalize())} {', '.join(v[:3])}{' dan lainnya' if len(v) > 3 else ''}"
                                       for k, v in f.items())
    return {"ds": ds, "lihat": lihat, "dari": dari, "sampai": sampai, "jumlah_minggu": jm, "minggu": minggu, "filter": f, "teks": teks + "."}


@app.get("/api/asisten/saran")
def saran_asisten(menu: str | None = Query(None, max_length=40), user=Depends(pengguna_saat_ini)):
    """Rekomendasi pertanyaan untuk menu yang sedang dibuka (panel kosong)."""
    info = asisten.kamus.MENU.get(menu or "", {})
    return {"menu": LAPORAN[menu].nama if menu in LAPORAN else None, "saran": info.get("saran") or asisten.kamus.CONTOH[:6],
            "ada_data": bool(info.get("sumber"))}


@app.post("/api/asisten/nilai")
def nilai_asisten(n: NilaiAsisten, user=Depends(pengguna_saat_ini)):
    asisten.nilai(n.id[:20], n.suka, user["username"], n.komentar)
    return {"ok": True}


@app.post("/api/asisten/ingat")
def ingat_asisten(i: IngatAsisten, user=Depends(pengguna_saat_ini)):
    asisten.ingat(i.asal[:300], i.ke, user["username"])
    return {"ok": True}
