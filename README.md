# CPOS Platform

Satu repo untuk beberapa aplikasi yang tampil sebagai satu web:

| Bagian | Isi | Teknologi | Jalan di |
|---|---|---|---|
| **CPOS** | Timbangan, security, master, admin (login & hak akses pusat) | Flask + SQL Server | `/` (port 5000) |
| **RekapIn** | Dashboard RekapIn, Request Operator, Harga CPO & Kernel, Kategori Request, Pembelian TBS | modul di dalam CPOS | `/rekapin/...` (ikut CPOS) |
| **Analytics** | Laporan analitik (PR & PO, PO & PI, PVR/PV KPI, Weighbridge, TBS, PI-PVR, PI-GT, Outstanding, Kas & Bank) | React + FastAPI | `/analytics/` (backend port 8001) |
| **Deteksi Plat** | Baca plat dari kamera, foto bukti | Python | port internal 8000, videonya lewat CPOS |

Pengguna hanya login sekali di CPOS. Semua menu (termasuk RekapIn dan Analytics) ada di sidebar CPOS dan diatur di
**Admin › Kelola Menu** dan **Admin › Hak Akses**.

## Struktur folder

```
CPOS-Platform/
├─ backend/
│  ├─ .env                       SATU file pengaturan untuk semua aplikasi (tidak ikut git; contoh: .env.example)
│  ├─ cpos/                      Flask: app.py, serve.py, routes/, utils/, agen/, tools/
│  │  ├─ modules/rekapin/  item_request/  item_dashboard/   modul CPOS (kode Python + database/)
│  │  ├─ database/               schema.sql (database CPOS dari nol), perubahan/, keamanan/
│  │  └─ data/  logs/            upload privat dan log (dibuat saat berjalan)
│  ├─ analytics/                 FastAPI: api.py, inti/, laporan/
│  │  └─ database/               001_analytics.sql (hak menu) dan *_sp.sql (stored procedure laporan di Main)
│  └─ deteksi/                   server_web.py, anpr/, model, foto_bukti/
├─ frontend/
│  ├─ cpos/                      templates/ dan static/ (dirender Flask), termasuk templates|static/rekapin, item_*
│  │                             package.json + tailwind.config.js: membangun static/css/tailwind.css
│  └─ analytics/                 React + Vite: src/; hasil build di dist/ (dilayani di /analytics/)
├─ deploy/                       paket, pasang sebagai layanan, HTTPS (Caddy), buat_database.bat
├─ docs/                         dokumentasi CPOS dan Analytics
├─ jalankan.bat                  menjalankan semuanya di PC ini
├─ berhenti.bat                  menghentikan semuanya
└─ bangun-frontend.bat           membangun ulang frontend\analytics\dist dan CSS CPOS
```

`backend\` berisi semua kode Python; `frontend\` berisi semua tampilan. Halaman CPOS tetap dibuat oleh Flask dari
`frontend\cpos\templates`, jadi folder itu ikut dibawa ke server bersama `backend\`.

## Cara kerjanya

```
Browser ── http(s)://server/ ──────────────► CPOS (waitress :5000) ── SQL Server: database CPOS / Main
        └─ /analytics/          ─► CPOS menyajikan frontend\analytics\dist
        └─ /analytics/api/...   ─► CPOS meneruskan ke backend Analytics (uvicorn :8001) ── SP laporan di Main ── ERP
                                                     │
                                                     └─► tanya CPOS /api/analytics/saya: "cookie ini milik siapa,
                                                         laporan apa saja yang boleh dibuka?"
```

Karena CPOS sudah menyajikan `/analytics`, di depan cukup **satu** alamat: port CPOS. Reverse proxy (Caddy atau IIS) hanya perlu
meneruskan semua ke port CPOS.

- **RekapIn** adalah bagian kode CPOS, jadi otomatis memakai login, sidebar, hak akses, dan tampilan CPOS.
- **Analytics** aplikasi terpisah (FastAPI + React), tetapi tidak punya login sendiri: tiap permintaan diperiksa ke CPOS
  (alamatnya dibuat dari `PORT` di `backend\.env`). Menu laporan di CPOS beralamat `/an/<id laporan>`.

| Menu CPOS | Alamat | Laporan Analytics |
|---|---|---|
| Dashboard › Analytical Dashboard › PR & PO Outstanding | `/an/pr_po` | `pr_po` |
| … › PO & PI Outstanding | `/an/po_pi` | `po_pi` |
| … › PVR KPI | `/an/penilaian_pvr` | `penilaian_pvr` |
| … › PV KPI | `/an/penilaian_pv` | `penilaian_pv` |
| … › Weighbridge Fraud Analyst | `/an/palm_weighbridge` | `palm_weighbridge` |
| … › TBS Transaction Analyst | `/an/penerimaan_tbs` | `penerimaan_tbs` |
| Reports › Purchase Invoice | `/an/pi_pvr` | `pi_pvr` |
| Reports › Goods Transfer | `/an/pi_gt` | `pi_gt` |

Laporan Analytics baru: buat laporannya di `backend\analytics\laporan`, lalu di **Admin › Kelola Menu** tambah menu dengan alamat
`/an/<id laporan>` dan beri hak Lihat di Admin › Hak Akses. Kode CPOS tidak perlu diubah.

## 1. Pengaturan (.env)

```bat
copy backend\.env.example backend\.env
```

Satu file untuk semua aplikasi, dan cukup berisi yang berbeda dari bawaan. Daftar lengkap dengan nilai bawaannya ada di
`backend\.env.example`.

| Nama | Isi |
|---|---|
| `SECRET_KEY`, `HASH_SECRET_KEY` | kunci CPOS (pindah PC: salin dari PC lama, harus sama) |
| `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | database utama; dipakai CPOS, Deteksi, Analytics, dan modul RekapIn / Item Request |
| `ANALYTICS_DB_USER`, `ANALYTICS_DB_PASSWORD` | akun database khusus Analytics (mis. `pythonReport`); kosong = sama dengan `DB_USER` |
| `HARGA_TABEL` | tabel harga CPO & Kernel untuk Dashboard dan RekapIn (bawaan `Main.dbo.HARGA`) |
| `PORT` (5000) | port web CPOS; Analytics memeriksa login ke `http://127.0.0.1:<PORT>` |
| `DETEKTOR_PORT` (8000) | port internal Deteksi Plat |
| `FOLDER_FOTO` | folder foto plat (kosong = `backend\deteksi\foto_bukti`) |

Modul yang datanya di database lain cukup menulis yang berbeda, mis. `ITEM_REQUEST_SERVER=...`; isian yang kosong ikut `DB_*`
(`backend\cpos\utils\koneksi_lain.py`).

Penjelasan tiap nilai ada di `backend\.env.example`. Pengaturan khusus Analytics (nama SP, batas tanggal, dll) ada di
`backend\analytics\inti\konfigurasi.py`, semuanya punya nilai bawaan.

## 2. Menjalankan

```bat
jalankan.bat
```

Sekali klik: CPOS (port `PORT`), backend Analytics (8001), dan Deteksi Plat (`DETEKTOR_PORT`). Pertama kali, Python dan library
dipasang sendiri di `%LOCALAPPDATA%\cpos-platform` (bukan di folder ini). Tutup jendelanya untuk berhenti, atau `berhenti.bat`.

Setelah mengubah `frontend\analytics\src` atau memakai kelas Tailwind baru di `frontend\cpos`: `bangun-frontend.bat` (butuh Node.js).

Pengembangan frontend Analytics dengan hot reload:

```bat
cd frontend\analytics
npm install
set VITE_API_TARGET=http://127.0.0.1:8001
npm run dev
```

Lalu isi `ANALYTICS_URL=http://localhost:5173/analytics` di `backend\.env` dan buka CPOS di `http://localhost:5000`.

## 3. Database (SQL Server)

Database baru (kosong / server uji):

```bat
deploy\buat_database.bat localhost sa PasswordSa
```

Urutannya (bisa juga satu per satu di SSMS):

1. `backend\cpos\database\schema.sql`: membuat database **CPOS** (tabel, prosedur, menu, hak dasar, `dbo.SchemaLog`).
2. `backend\cpos\modules\rekapin\database\*.sql`: schema `rekap` + menu RekapIn + hak bawaan HO.
3. `backend\analytics\database\0*.sql`: hak bawaan menu laporan Analytics.

Stored procedure laporan Analytics (`backend\analytics\database\*_sp.sql`) dibuat sekali di database **Main**, terpisah dari langkah
di atas. Server yang sudah berisi data tidak dibuat ulang: perubahan ditulis sebagai skrip bernomor di
`backend\cpos\database\perubahan`, lalu dijalankan sekali.

## 4. Deploy ke server

Yang dibutuhkan server hanya:

```
backend\                         semua kode + backend\.env
frontend\cpos\templates, static  tampilan CPOS
frontend\analytics\dist          tampilan Analytics (hasil build)
deploy\, jalankan.*              skrip pasang dan jalankan
```

`deploy\buat_paket.bat` membuat zip berisi persis itu (frontend dibangun ulang dulu). Di server: ekstrak, lalu klik kanan
`deploy\pasang.bat` › Run as administrator. Rinciannya di `deploy\PASANG.txt`.

- **HTTPS dengan Caddy:** `deploy\pasang_https.ps1` (lihat PASANG.txt).
- **IIS:** buat satu situs dengan URL Rewrite + ARR yang meneruskan semua permintaan ke `http://127.0.0.1:<PORT>` (CPOS).
  `/analytics` sudah dilayani CPOS. Isi `BEHIND_PROXY=1`, `COOKIE_SECURE=1` (bila HTTPS), dan `HOST=127.0.0.1` di `backend\.env`.
  Kalau ingin IIS sendiri yang menyajikan file Analytics, arahkan `/analytics/*` ke folder `frontend\analytics\dist`
  (`frontend\analytics\public\web.config`) dan `/analytics/api/*` ke `127.0.0.1:8001/api/*`.

## 5. Hak akses

Semua di CPOS, **Admin › Hak Akses**, per menu (siapa: semua / jabatan / level / departemen / user; aksi: Lihat, Tambah, Ubah,
Hapus, Setujui, Tolak, Selesai):

- RekapIn: menu `RK_DASHBOARD`, `RK_REQUEST`, `RK_HARGA`, `RK_FITUR` (Kategori Request), `RK_TBS_DAILY/WEEKLY/MONTHLY`.
- Analytics: hak **Lihat** menu `/an/<id>` = boleh membuka laporan itu. Cakupan perusahaan per laporan diatur di Hak Akses › Cakupan data.

## 6. Kerja tim

Semua perubahan lewat git: `git pull` sebelum mulai, buat branch, lalu commit & push. Pembagian folder:

- tim CPOS: `backend\cpos`, `frontend\cpos` (selain bagian RekapIn)
- tim RekapIn: `backend\cpos\modules\rekapin`, `frontend\cpos\templates\rekapin`, `frontend\cpos\static\rekapin`
- tim Analytics: `backend\analytics`, `frontend\analytics`
