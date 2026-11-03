# CPOS Platform

Satu repo untuk tiga aplikasi yang tampil sebagai satu web:

| Bagian | Isi | Teknologi | Jalan di |
|---|---|---|---|
| **CPOS** | Timbangan, security, master, admin (login & hak akses pusat) | Flask + SQL Server | `/` (port 5000) |
| **RekapIn** | Dashboard RekapIn, Request Operator, Harga CPO & Kernel, Kategori Request, Pembelian TBS | modul di dalam CPOS | `/rekapin/...` (ikut CPOS) |
| **Analytics** | 8 laporan analitik (PR & PO, PO & PI, PVR/PV KPI, Weighbridge, TBS, PI-PVR, PI-GT) | React + FastAPI | `/analytics/` (backend port 8001) |

Pengguna hanya login sekali di CPOS. Semua menu (termasuk RekapIn dan Analytics) ada di sidebar CPOS dan diatur di
**Admin › Kelola Menu** dan **Admin › Hak Akses**.

## Struktur folder

```
CPOS-Platform/
├─ CPOS/                         aplikasi utama (Flask)
│  ├─ app.py, serve.py           jalankan: python serve.py
│  ├─ routes/  utils/  templates/  static/
│  ├─ routes/analytics.py        menu /an/<id> -> laporan Analytics dalam bingkai CPOS
│  ├─ modules/
│  │  └─ rekapin/                RekapIn sebagai modul CPOS
│  │     ├─ routes.py  db.py  laporan_tbs.py  erp.py
│  │     ├─ templates/rekapin/   static/rekapin/
│  │     └─ database/001_rekap.sql   schema "rekap" + hak bawaan
│  ├─ database/
│  │  ├─ schema.sql              database CPOS lengkap dari nol
│  │  ├─ demo_data.sql           data contoh (opsional)
│  │  └─ perubahan/              skrip perubahan untuk server yang sudah berjalan
│  └─ .env.example
├─ Analytics/
│  ├─ backend/                   FastAPI (uvicorn api:app), .env.example
│  ├─ frontend/                  React + Vite (dilayani di /analytics/)
│  └─ database/001_analytics.sql hak bawaan menu laporan Analytics
└─ deploy/
   ├─ buat_database.bat          membuat database CPOS lengkap dari nol
   └─ Caddyfile                  satu alamat HTTPS untuk CPOS + Analytics
```

## Cara kerjanya

```
Browser ── https://server/ ─────────────► Caddy ──► CPOS (waitress :5000)  ── SQL Server: database CPOS
        └─ https://server/analytics/ ────►   │  ──► file Analytics/frontend/dist
        └─ https://server/analytics/api/ ►   └────► Analytics backend (uvicorn :8001) ── SQL Server ERP (SP laporan)
                                                         │
                                                         └─► tanya CPOS /api/analytics/saya: "cookie ini milik siapa,
                                                             laporan apa saja yang boleh dibuka?"
```

- **RekapIn** sudah menjadi bagian kode CPOS, jadi otomatis memakai login, sidebar, hak akses, dan tampilan CPOS.
  Datanya di schema database `rekap` (dalam database CPOS); harga memakai tabel `dbo.DailyPrice` yang sama dengan Dashboard CPOS.
- **Analytics** tetap aplikasi terpisah (beda bahasa), tetapi:
  - menu laporan di CPOS beralamat `/an/<id laporan>` (mis. `/an/pr_po`), dan halamannya menampilkan Analytics di dalam bingkai,
    lengkap dengan sidebar & header CPOS;
  - backend Analytics tidak punya login sendiri bila `CPOS_URL` diisi: tiap permintaan diperiksa ke CPOS;
  - yang boleh membuka sebuah laporan = yang punya hak **Lihat** menu itu di Admin › Hak Akses;
  - font dan warna Analytics disamakan dengan CPOS.

Daftar menu laporan Analytics:

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

Laporan Analytics baru: buat laporannya di Analytics seperti biasa, lalu di **Admin › Kelola Menu** tambah menu dengan alamat
`/an/<id laporan>` dan beri hak Lihat di Admin › Hak Akses. Tidak perlu mengubah kode CPOS.

## 1. Clone

```bat
git clone https://github.com/<akun>/<repo>.git C:\CPOS-Platform
cd C:\CPOS-Platform
```

Yang tidak ikut di repo (dibuat sendiri di tiap PC/server): file `.env`, `venv`, `node_modules`, `Analytics/frontend/dist`, log.

## 2. Database (SQL Server)

Database baru (kosong / server uji):

```bat
deploy\buat_database.bat localhost sa PasswordSa
:: data contoh (opsional, hanya server uji):
sqlcmd -S localhost -U sa -P PasswordSa -C -d CPOS -i CPOS\database\demo_data.sql
```

Urutan yang dijalankan skrip itu (bisa juga satu per satu di SSMS):

1. `CPOS\database\schema.sql`: membuat database **CPOS** (tabel, prosedur, menu, hak dasar, `dbo.SchemaLog`).
2. `CPOS\modules\rekapin\database\*.sql`: schema `rekap` (request operator, kategori) + alamat menu RekapIn + hak bawaan HO.
3. `Analytics\database\*.sql`: hak bawaan menu laporan Analytics untuk HO.
4. (opsional) `CPOS\database\keamanan\01_user_aplikasi.sql` bila aplikasi login ke SQL Server dengan user khusus, bukan `sa`.
   Setelah itu jalankan ulang langkah 2–3, supaya user tersebut juga mendapat hak ke schema `rekap`.

Semua skrip aman dijalankan ulang dan mencatat dirinya di `dbo.SchemaLog`:

```sql
SELECT * FROM CPOS.dbo.SchemaLog ORDER BY RunDate;
```

Server yang **sudah berisi data** tidak dibuat ulang: perubahan baru ditulis sebagai skrip bernomor di
`CPOS\database\perubahan` (contoh: `_contoh.sql`), di folder `database` modul, atau di `Analytics\database`, lalu
dijalankan sekali. Ubahan yang sama juga dimasukkan ke `schema.sql` supaya server baru langsung lengkap.

Laporan Analytics dan laporan Pembelian TBS memanggil stored procedure ERP (database lain). Koneksinya diatur di `.env`
masing-masing (lihat langkah 3).

## 3. Pengaturan (.env)

```bat
copy CPOS\.env.example CPOS\.env
copy Analytics\backend\.env.example Analytics\backend\.env
```

`CPOS\.env` (yang terkait gabungan):

| Nama | Isi |
|---|---|
| `DB_SERVER`, `DB_NAME=CPOS`, `DB_USER`, `DB_PASSWORD` | database CPOS |
| `REKAPIN_ERP_CONNECTION_STRING` | connection string ODBC ke database ERP yang punya `dbo.tbsdetailybs2`, `dbo.tbsdetailybsweekly`, `dbo.tbsdetailmonthly` |
| `ANALYTICS_URL` | `/analytics` (satu alamat lewat Caddy). Saat pengembangan: `http://localhost:5173/analytics` |

`Analytics\backend\.env`:

| Nama | Isi |
|---|---|
| `CPOS_URL` | alamat CPOS yang bisa dihubungi server Analytics, mis. `http://127.0.0.1:5000`. Kosong = Analytics berdiri sendiri dengan login sendiri |
| `CPOS_COOKIE` | `wb_sesi` (nama cookie sesi CPOS) |
| `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | database ERP tempat stored procedure laporan (`SP_*` lain lihat `inti/konfigurasi.py`) |

## 4. Menjalankan saat pengembangan (satu PC)

Tiga jendela terminal:

```bat
:: 1) CPOS + RekapIn  -> http://localhost:5000
cd CPOS
python -m venv venv & venv\Scripts\activate
python -m pip install -r requirements.txt
python serve.py

:: 2) Backend Analytics -> port 8001
cd Analytics\backend
python -m venv venv & venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8001

:: 3) Frontend Analytics -> http://localhost:5173/analytics/
cd Analytics\frontend
npm install
set VITE_API_TARGET=http://127.0.0.1:8001
npm run dev
```

Buka **http://localhost:5000**, login, lalu buka menu Dashboard › Analytical Dashboard. Di `CPOS\.env` isi
`ANALYTICS_URL=http://localhost:5173/analytics`. Cookie login CPOS ikut terbaca di port 5173 karena alamatnya sama (`localhost`).
Pakai alamat yang sama di semua tempat (semua `localhost`, atau semua `127.0.0.1`), jangan dicampur.

## 5. Menjalankan di server

1. Langkah 1–3 di atas (`.env` server: `BEHIND_PROXY=1`, `COOKIE_SECURE=1`, `HOST=127.0.0.1`, `ANALYTICS_URL=/analytics`).
2. Build frontend Analytics sekali (dan setiap ada perubahan frontend):
   ```bat
   cd Analytics\frontend
   npm ci
   npm run build        :: hasil di Analytics\frontend\dist, alamatnya /analytics/
   ```
3. Jalankan CPOS (`python serve.py`) dan backend Analytics (`uvicorn api:app --host 127.0.0.1 --port 8001`, **satu** proses
   karena data laporan disimpan di memori) sebagai service Windows (mis. NSSM) atau Task Scheduler.
4. `deploy\Caddyfile`: ganti IP server dan lokasi repo, lalu `caddy run --config deploy\Caddyfile`. Semua PC membuka
   `https://<IP server>`.

Memakai IIS (bukan Caddy): satu situs dengan URL Rewrite + ARR. Aturannya sama dengan Caddyfile: `/analytics/api/*` ke
`127.0.0.1:8001/api/*`, `/analytics/*` ke folder `Analytics\frontend\dist` (lihat `Analytics\frontend\public\web.config`),
selain itu ke `127.0.0.1:5000`.

## 6. Hak akses

Semua di CPOS, **Admin › Hak Akses**, per menu (siapa: semua / jabatan / level / departemen / user; aksi: Lihat, Tambah, Ubah,
Hapus, Setujui, Tolak, Selesai):

- RekapIn: menu `RK_DASHBOARD`, `RK_REQUEST` (Setujui / Tolak / Selesai untuk menindaklanjuti request), `RK_HARGA`,
  `RK_FITUR` (Kategori Request), `RK_TBS_DAILY/WEEKLY/MONTHLY`. Operator timbangan (departemen TBG) yang hanya punya Tambah
  melihat request miliknya saja.
- Analytics: hak **Lihat** menu `/an/<id>` = boleh membuka laporan itu. Halaman Pengguna / Permission Control milik Analytics
  tidak dipakai lagi (tertutup saat `CPOS_URL` diisi).
- Hak bawaan setelah database dibuat: HO boleh semua menu RekapIn & Analytics; operator timbangan boleh membuat Request Operator.

## 7. Kerja tim

Disarankan semua perubahan lewat git (repo ini), bukan folder sharing: tiap orang `git pull` sebelum mulai, membuat branch,
lalu commit & push. Pembagian folder:

- tim CPOS: `CPOS/` (selain `modules/rekapin`)
- tim RekapIn: `CPOS/modules/rekapin/` (+ menu `RK_*` di schema)
- tim Analytics: `Analytics/`

Kalau tetap memakai folder sharing, cukup satu orang yang memindahkan perubahan dari folder sharing ke repo ini, supaya
riwayat dan versi server tetap satu.

## Yang berubah dari aplikasi lama

- **RekapIn**: tabel `USERS`, `PERMISSIONS`, `FEATURES`, `OPERATOR_REQUESTS` lama diganti akun & hak akses CPOS,
  `rekap.RequestCategory`, dan `rekap.OperatorRequest`. Harga dari `Main.dbo.HARGA` diganti `dbo.DailyPrice` CPOS
  (sama dengan Isi Harga di Dashboard). Laporan Pembelian TBS memakai stored procedure ERP yang sama dengan susunan tabel
  yang sama, dibaca lewat `REKAPIN_ERP_CONNECTION_STRING`. Ekspor Excel memakai tombol Excel / PDF CPOS di tiap tabel.
- **Analytics**: login, ganti password, dan halaman admin sendiri tidak dipakai saat `CPOS_URL` diisi; aplikasi dilayani di
  `/analytics/` (build dengan `VITE_BASE=/` bila ingin berdiri sendiri di root).
