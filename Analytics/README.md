# Dashboard Analytics

Dashboard laporan procurement (React + Tailwind + Recharts di depan, FastAPI + SQL Server di belakang).

## Susunan folder

```
backend/
  api.py                  endpoint (tipis, tidak berisi rumus)
  inti/                   dipakai SEMUA laporan: db, gudang (cache + pemuatan + batal), kategori, filter, tabel,
                          pengguna + sandi + sesi (login), alat_pengguna (alat bantu tabel pengguna)
  laporan/
    __init__.py           daftar laporan (satu elemen per laporan)
    pr_po/                sumber.py (SP + pembersihan), ukuran.py (rumus), dashboard.py (grafik + tabel)
    po_pi/                sama
    palm/                 laporan Deteksi Kecurangan Timbangan (sama)
  database/               users.sql (tabel pengguna) dan permission.sql (izin untuk tabel PERMISSIONS)
frontend/src/
  App.jsx  api.js         kerangka (menu samping, login, daftar laporan)
  komponen/               umum: Sidebar, PanelPeriode, LaporanView, FilterMulti, Kartu, TabelBaris, TabelDetail, Login, HalamanPengguna, HalamanIzin
  grafik/                 umum: WeeklyChart, GarisSeri, DonatKategori, KategoriOutstandingChart, BatangPembuat,
                          BatangRisiko, BatangKendaraan, BatangRisikoSupplier, SebaranTara (laporan timbangan)
  laporan/                index.js (daftar dashboard) + satu folder per laporan
  lib/data.js            fungsi kecil (tanggal, pilihan, format)
```

## Menjalankan

```
cd backend
pip install -r requirements.txt
python -m inti.alat_pengguna cek  # periksa tabel pengguna (lihat bagian Login dan pengguna)
uvicorn api:app --reload          # satu proses saja, jangan pakai banyak worker

cd frontend
npm run dev
```

Isi `backend/.env` (lihat `.env.contoh`).

**Setelah memperbarui kode dari zip baru, jalankan `pip install -r requirements.txt` lagi** (di venv yang sama). Daftar pustaka bisa bertambah,
mis. `openpyxl` untuk Export Excel dan `argon2-cffi`/`bcrypt` untuk hash kata sandi tertentu. Kalau `openpyxl` belum terpasang, server tetap menyala
(dengan peringatan di terminal) dan hanya tombol Export Excel yang gagal, dengan pesan yang menyebut apa yang harus dipasang.

## Login dan pengguna

Semua halaman dan endpoint (kecuali halaman masuk) membutuhkan login. Pengecekan dilakukan di server pada setiap permintaan.
Akun dibaca dari **tabel pengguna yang sudah ada** di SQL Server dengan kolom `id, username, password_hash, full_name, role, division,
company, created_at` (nama tabel: `DB_APP_TABEL` di `.env`, bawaan `users`), dan role dari **tabel role** dengan kolom `RoleId, DivisionId,
RoleName, RoleDescription, Status, CreatedAt` (nama tabel: `DB_APP_TABEL_ROLE`, bawaan `role`), dan pilihan company dari **tabel company** dengan
kolom `CompID, CompName, CompType, CompAddr, CompDataBase, Status` (nama tabel: `DB_APP_TABEL_COMPANY`, bawaan `company`). Server, database, dan akun database bawaannya sama dengan
database data (`DB_SERVER`, `DB_NAME`, `DB_USER`); kalau tabelnya di tempat lain, isi `DB_APP_SERVER`, `DB_APP_NAME`, `DB_APP_USER`,
`DB_APP_PASSWORD` (lihat `backend/inti/db.py`).

**Role.** Daftar role (dan pilihan di formulir akun baru) diambil dari tabel role; hanya role berstatus aktif yang ditawarkan (Status 0,
false, no, nonaktif, inactive dianggap nonaktif; kosong dianggap aktif). Kolom `users.role` boleh berisi **nama role** atau **RoleId**:
keduanya dikenali, dan akun baru disimpan dengan cara yang sama dengan akun yang sudah ada (`ROLE_DISIMPAN=auto`; boleh dipaksa `nama` atau
`id`). Huruf besar-kecil dan spasi pada nama role diabaikan ("Software Engineer" sama dengan "SoftwareEngineer").

**Hak akses halaman (menu Permission Control).** Siapa boleh membuka laporan **tidak tertulis di kode**, tetapi dibaca dari tabel izin yang sudah ada dan dipakai
bersama aplikasi lain (`DB_APP_TABEL_IZIN`, bawaan `PERMISSIONS`; kolom `role, page_key, can_access, can_edit, can_delete, can_approve, can_reject, can_done`).
Untuk laporan, `page_key` berisi id laporan (mis. `pr_po`) dan hanya kolom `can_access` yang dipakai; baris halaman lain tidak pernah disentuh. System Administrator
mengaturnya lewat menu **Administrasi → Permission Control**: pilih role, lalu nyalakan saklar **Akses** untuk tiap laporan. Perubahan berlaku **langsung** pada
permintaan berikutnya (akun yang sedang masuk tidak perlu masuk ulang).

- **Role admin** (`ROLE_ADMIN` di `.env`, bawaan System Administrator) selalu punya akses penuh ke semua laporan, kelola pengguna, dan Permission Control. Hak ini
  tidak disimpan di tabel dan tidak bisa dibatasi, supaya tidak ada yang bisa mengunci dirinya sendiri.
- **Role lain tanpa baris di tabel izin tidak melihat laporan apa pun.** Begitu juga laporan baru yang ditambahkan di program: tertutup bagi semua role selain admin
  sampai diberi akses di Permission Control. Saat akses dicabut, barisnya tetap ada dengan `can_access = 0`; baris baru diisi 0 pada kolom lainnya.
- **Struktur tabel izin tidak dibuat atau diubah oleh program ini.** Akun database server butuh `SELECT, INSERT, UPDATE` di tabel itu (contoh GRANT dan seed opsional
  ada di `backend/database/permission.sql`). Kalau tabel izin tidak terbaca, akun non-admin mendapat pesan 503 (bukan akses terbuka), dan admin tetap bisa masuk untuk memperbaikinya.
- **Export Excel tidak punya izin terpisah**: siapa yang boleh membuka laporan boleh meng-export tabel detailnya (tabel izin bersama tidak punya kolom export).
- `python -m inti.alat_pengguna cek` menampilkan hak tiap role dan menandai role yang punya akun tetapi belum punya akses ke laporan apa pun.

Kolom `division` dan `company` dicatat dan ditampilkan, tetapi belum membatasi data yang terlihat.

**Memeriksa tabel (lakukan sekali sebelum dipakai):**

```
cd backend
python -m inti.alat_pengguna cek          # koneksi, kolom, tabel role, akun per role, cara role disimpan, jenis hash, izin tulis (tanpa menampilkan hash)
python -m inti.alat_pengguna buat-admin   # hanya kalau belum ada System Administrator
```

**Format hash.** Kata sandi lama di tabel diperiksa sesuai jenis hash-nya, dikenali dari awalan: argon2 (`$argon2...`), bcrypt (`$2b$...`),
scrypt dan PBKDF2 gaya Werkzeug/Flask, PBKDF2 gaya Django, serta scrypt buatan aplikasi ini. Argon2 dan bcrypt membutuhkan pustaka
`argon2-cffi` dan `bcrypt` (ada di `requirements.txt`). Akun yang formatnya tidak dikenal tidak bisa masuk; `cek` menyebutkannya.
Akun baru dibuat dengan jenis hash yang sama dengan akun yang sudah ada (`PASSWORD_HASH=auto`), supaya aplikasi lain yang memakai tabel
yang sama tetap bisa memeriksanya. Boleh dipaksa lewat `PASSWORD_HASH=scrypt|werkzeug-scrypt|werkzeug-pbkdf2|django-pbkdf2|argon2|bcrypt`. Format Werkzeug (yang dipakai
akun Flask) sudah diuji silang dengan pustaka Werkzeug asli: hash buatan Werkzeug dibaca aplikasi ini, dan akun baru buatan aplikasi ini
dibaca Werkzeug.

**Izin database.** Akun database yang dipakai server harus boleh membaca, menambah, dan menghapus di tabel pengguna, dan membaca tabel role
(`GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.users TO ...`, lihat `backend/database/users.sql`). Kolom `id` harus terisi otomatis (IDENTITY atau nilai
bawaan), karena aplikasi tidak mengisi `id`.

**Kelola pengguna (menu Administrasi, hanya System Administrator):** daftar akun (dengan pencarian), tambah akun lewat popup **Tambah User**,
edit akun lewat tombol **Edit**, dan hapus akun yang tidak terpakai (dengan konfirmasi). Akun sendiri dan System Administrator terakhir tidak bisa dihapus. Akun yang dihapus
langsung keluar dari sesinya. Password minimal 8 karakter, disimpan sebagai hash, dan tidak pernah dikirim kembali ke layar.

Popup Tambah User berisi Username, Password (ada ikon mata untuk melihatnya), Nama lengkap, Role, Division, dan Company. Isian Role, Division,
dan Company berupa dropdown dengan nilai bawaan: role dari `ROLE_BAWAAN` di `.env` (bawaan Operator; kalau tidak ada di tabel role, role pertama), division
dan company yang pertama menurut abjad. Pilihannya:

- **Role:** dari tabel role, yang Status-nya aktif.
- **Company:** nama unik dari tabel company (satu nama bisa punya beberapa baris: CLOUD, TRAINING, PKS_LOKAL, ...; spasi di ujung nama dibuang).
  Sebuah company ditawarkan kalau minimal satu barisnya aktif. Server menolak company yang tidak ada di tabel itu.
- **Division:** nama division yang sudah dipakai di tabel pengguna. Kalau tabel pengguna belum punya satu pun, isian berupa teks biasa.

**Edit akun.** Tombol **Edit** di tiap baris membuka popup untuk mengubah nama lengkap, role, division, company, dan (opsional) password baru. Username tidak
bisa diubah. Aturannya:

- Role atau company yang **tidak diubah** boleh tetap walau sekarang sudah tidak ada di pilihan (mis. role dinonaktifkan), supaya akun lama tetap bisa
  disunting; yang baru harus dari pilihan. Hanya kolom yang benar-benar berubah yang ditulis, jadi nilai role aslinya di database (nama atau RoleId) tidak rusak.
- Admin **tidak bisa mengubah role akunnya sendiri**, dan System Administrator terakhir tidak bisa diturunkan rolenya. Admin boleh menaikkan akun lain jadi admin.
- Perubahan role langsung berlaku pada sesi yang sedang berjalan. **Password yang diganti** mencabut semua sesi akun itu (beserta data laporannya) dan perangkatnya
  diberi tahu sebabnya; kalau yang diganti adalah akun admin sendiri, sesinya tetap hidup.
- Akun database server butuh izin `UPDATE` di tabel pengguna (`cek` memeriksanya).

- Sesi disimpan di memori server (hilang saat server dimulai ulang), berlaku 8 jam (`SESI_JAM`), dan dikenali lewat cookie
  httpOnly dengan SameSite=Strict. Setelah memakai HTTPS, atur `COOKIE_SECURE=1`.
- **Keluar otomatis saat idle.** Pengguna dikeluarkan kalau tidak menggerakkan mouse atau mengetik selama batas idle (bawaan 30 menit,
  `SESI_IDLE_MENIT`; 0 = mati). Administrator mengubahnya di menu **Log Aktivitas → Keluar otomatis saat idle**; nilainya disimpan di
  `backend/pengaturan.json` (lokasi lain: `PENGATURAN_BERKAS`) dan langsung berlaku. Tabel "Sedang masuk" di menu yang sama menampilkan
  lama masuk dan lama idle tiap sesi.
- **Laporan tidak tersisa setelah keluar atau sesi berakhir.** Data laporan yang dimuat disimpan di memori server dan dimiliki oleh sesi login
  yang memuatnya; hanya sesi itu yang bisa membacanya. Saat sesi berakhir (menekan Keluar, sesi habis, atau akunnya dihapus), data itu
  dibuang dan pemuatan yang sedang berjalan dihentikan, jadi setelah masuk lagi pengguna harus memilih tanggal dan menekan Muat data lagi.
  Sesi yang habis disapu tiap `SESI_SAPU_DETIK` (bawaan 60 detik), walau tidak ada yang mengaksesnya lagi. Kalau dua pengguna meminta periode yang
  sama pada saat yang sama, data dipakai bersama tanpa SQL kedua; data baru dibuang setelah keduanya berakhir. Di layar, semua yang sudah
  ditampilkan ikut dihapus saat keluar.
- **Satu akun, satu sesi aktif.** Login baru mengakhiri sesi lama akun itu di perangkat atau IP lain (beserta data laporannya), sehingga satu akun hanya bisa
  dipakai di satu tempat pada satu waktu. Perangkat lama mendapat pesan sebabnya pada permintaan berikutnya, mis. "Akun ini baru saja masuk di perangkat lain
  (IP ...) pukul 14.05 ...". Di belakang proxy (mis. IIS) alamat yang tampil adalah alamat proxy-nya. `LOGIN_BERSAMAAN=izinkan` mematikan aturan ini.
- Lima kali salah sandi dalam 5 menit mengunci username itu sementara.
- Perubahan yang dibuat langsung di database (bukan lewat aplikasi) berlaku paling lambat 30 detik kemudian (`PENGGUNA_CACHE_DETIK`).
- Kalau tabel pengguna tidak terbaca saat server dinyalakan, server berhenti dengan pesan yang menyebut tabel dan kolomnya. Kalau
  database mati saat server berjalan, pengguna mendapat pesan 503 (bukan dikira salah sandi).

## Konfigurasi (.env) dan hard code

**Hard code** adalah nilai yang ditulis langsung di dalam kode padahal bisa berubah (alamat server, kata sandi, nama stored procedure, daftar perusahaan, daftar
role dan hak aksesnya, batas-batas), sehingga mengubahnya berarti mengedit program. Di proyek ini nilai seperti itu diletakkan di luar kode:

| Jenis | Disimpan di |
|---|---|
| Kata sandi, server, dan database | `backend/.env` (tidak ikut di zip) |
| Perusahaan yang dipanggil SP laporan | tabel company (kolom CompName, CompType, Status; jenis dipilih `LAPORAN_SUMBER`) |
| Daftar role dan role bawaan | tabel role; `ROLE_ADMIN` dan `ROLE_BAWAAN` di `.env` |
| Hak akses role per laporan | tabel izin, diatur lewat Permission Control |
| Nama stored procedure dan parameternya | `.env`: `SP_PR_PO`, `SP_PO_PI`, `LAPORAN_SUMBER`, `SP_STATUS` |
| Batas dan bawaan | `.env`, dibaca di satu tempat (`backend/inti/konfigurasi.py`) |

Frontend tidak memegang angka atau nama itu: batas rentang hari, role bawaan, nama aplikasi, dan daftar laporan yang boleh dibuka dikirim server. Alamat backend untuk `npm run dev`
diatur `VITE_API_TARGET` di `frontend/.env.local` (bawaan `http://localhost:8001`). Semua variabel di `.env` bersifat opsional kecuali `DB_*`; nilai bawaannya
sama dengan perilaku sebelumnya, dan isian yang salah (mis. angka berisi huruf) menghentikan server dengan pesan yang menyebut nama variabelnya.

| Variabel | Bawaan | Arti |
|---|---|---|
| `LAPORAN_SUMBER` | `cloud` | parameter sumber SP, dan jenis perusahaan (CompType) yang dipilih dari tabel company |
| `SP_PR_PO`, `SP_PO_PI` | `R_PR_OUT_YBS_2`, `R_PO_OUT_YBS` | nama stored procedure laporan |
| `SP_STATUS` | `4` | parameter status SP (4 = semua status) |
| `TABEL_KATEGORI` | `dbo.MappingCategory` | pemetaan kategori PR/PO dan PO/PI (kolom `Company`, `OldCategory`, `Category`) di database data; dibaca setiap data dimuat, perusahaan tanpa baris memakai kategori apa adanya |
| `LAPORAN_MULAI_BAWAAN` | `2025-10-01` | tanggal mulai yang terisi lebih dulu di pilihan periode |
| `MAKS_HARI_PERIODE` | `1100` | rentang tanggal terpanjang yang boleh dimuat |
| `MAKS_DATASET`, `SIMPAN_PEKERJAAN_DETIK` | `6`, `3600` | jumlah data laporan di memori server; lama catatan pekerjaan disimpan |
| `MAKS_BARIS_EKSPOR` | `100000` | batas baris sekali Export Excel |
| `AKTIVITAS_FOLDER` | `backend/log_aktivitas` | folder file log aktivitas (satu file per hari) |
| `AKTIVITAS_SIMPAN_HARI` | `180` | file log aktivitas yang lebih tua dihapus otomatis |
| `SP_PALM_WEIGHBRIDGE` | `dbo.PalmWeighbridge` | stored procedure laporan timbangan; parameternya (urut): perusahaan, tanggal awal; selalu sampai data terakhir |
| `PALM_SUMBER` | sama dengan `LAPORAN_SUMBER` | jenis perusahaan (CompType di tabel company) yang dipanggil SP timbangan |
| `PALM_AMBANG_TARA_KG` | `150` | selisih tara (kg) di atas batas ini, naik atau turun, ditandai WARNING |
| `PALM_AMBANG_DURASI_MENIT` | `180` | durasi timbang (menit) di atas batas ini ditandai WARNING |
| `PALM_TOP_KENDARAAN` | `12` | jumlah kendaraan di grafik selisih tara |
| `PALM_TOP_SUPPLIER` | `15` | jumlah supplier di grafik risiko per supplier |
| `PALM_MAKS_TITIK` | `1500` | titik terbanyak di grafik sebaran (lebih sedikit = lebih ringan di browser) |
| `SP_TBS` | `dbo.tbsdetailybs` | stored procedure laporan Penerimaan TBS; parameter: perusahaan, tanggal awal, tanggal akhir |
| `TBS_SUMBER` | sama dengan `LAPORAN_SUMBER` | CompType perusahaan yang dipanggil SP TBS |
| `TBS_FORMAT_TANGGAL` | `%Y%m%d` | bentuk tanggal yang dikirim ke SP TBS |
| `TBS_HARI_FORECAST` | `7` | panjang forecast (hari) dan jendela uji ketepatannya |
| `TBS_HARI_TREN` | `30` | hari aktual terakhir di grafik tren |
| `TBS_HARI_SKALA` | `14` | skala forecast: total netto sekian hari terakhir (dibagi 2 untuk forecast 7 hari) |
| `TBS_SIMULASI` | `Turun 5%:0.95,Normal:1,Naik 10%:1.1` | skenario forecast (nama:pengali) |
| `TBS_TOP_SUPPLIER` | `10` | baris di peringkat supplier dan business group |
| `TBS_TOP_TIPE` | `10` | baris di grafik netto per tipe supplier |
| `TBS_TOP_TIPE_HARGA` | `10` | tipe di grafik Harga per Tipe |
| `PALM_HARI_TREN` | `30` | tren harian: sekian hari terakhir dari periode yang dimuat |
| `PALM_TOP_PELANGGAR` | `10` | baris di Pelanggar Berulang (kendaraan, supir, supplier) |
| `PALM_MIN_TRANSAKSI_PERSEN` | `10` | supplier di bawah jumlah transaksi ini tidak ikut urutan persentase berisiko |
| `PALM_TOP_OPERATOR` | `12` | operator dengan transaksi terbanyak di peta Operator per Jam Masuk |
| `PALM_TITIK_EKSTREM` | `100` | titik ekstrem (durasi terlama, selisih terbesar) yang selalu ikut saat disampel |
| `ROLE_ADMIN`, `ROLE_BAWAAN` | `System Administrator`, `Operator` | role yang selalu penuh; role yang terpilih lebih dulu di akun baru |
| `LOGIN_BERSAMAAN` | `ganti` | `ganti` = login baru mengakhiri sesi lama; `izinkan` = boleh banyak perangkat |
| `DB_APP_TABEL`, `DB_APP_TABEL_ROLE`, `DB_APP_TABEL_COMPANY`, `DB_APP_TABEL_IZIN` | `users`, `role`, `company`, `PERMISSIONS` | nama tabel (boleh `Main.dbo.PERMISSIONS` kalau di database lain) |
| `NAMA_APLIKASI` | `Dashboard Analytics` | nama di halaman masuk, menu samping, dan judul tab browser |

**Yang sengaja tetap di kode**, di satu tempat masing-masing: aturan bisnis laporan (batas kategori aging di `inti/umur.py`, status aktif, rumus, definisi kolom tabel),
teks tampilan, biaya hash kata sandi, dan nama cookie. Aturan-aturan itu jarang berubah;
memindahkannya ke tabel masuk akal hanya kalau pengguna bisnis perlu mengubahnya sendiri.

## Log aktivitas

Menu **Log Aktivitas** (hanya System Administrator) menampilkan siapa yang masuk, gagal masuk, keluar, membuka laporan (periode dan apakah
SQL Server dijalankan), Export Excel (tab, jumlah baris, filter, pencarian), serta pembuatan, perubahan, dan penghapusan akun dan hak akses.
Tiap catatan memuat waktu, pengguna, laporan, keterangan, dan alamat IP. Filter: periode, jenis aktivitas, laporan, dan pengguna (klik nama di
tabel Per pengguna). Log disimpan sebagai file JSON Lines di `AKTIVITAS_FOLDER`, bukan di database, jadi tidak perlu tabel baru.
Gagal menulis log tidak menggagalkan permintaan pengguna; penyebabnya dicatat di log server.

## Periode, muat ulang, export, dan navigasi

SQL Server hanya dijalankan ketika pengguna memilih tanggal dan menekan **Muat data**, atau menekan **Muat ulang data**. Tidak ada
pembaruan otomatis.

- **Ganti periode.** Setelah dashboard tampil, tombol Ganti periode di bar atas membuka **popup** (bukan halaman baru). Dashboard yang
  lama tetap terlihat di belakangnya dan baru diganti setelah data baru selesai dimuat. Selama memuat, popup menampilkan detik berjalan dan
  tombol Batalkan (tidak bisa tertutup tak sengaja oleh Esc atau klik di luar). Kalau gagal, pesannya muncul di popup dan dashboard lama
  tetap ada. Filter kembali ke awal karena datanya berbeda. Kartu satu halaman hanya dipakai untuk pemilihan tanggal pertama kali.
- **Muat ulang data.** Tombol di bar atas mengambil ulang periode yang **sedang tampil** dari SQL Server, jadi pembaruan di database bisa
  didapat tanpa menunggu. Dashboard tetap terlihat selama menunggu (bar atas menampilkan detik dan tombol Batalkan), **filter, tab, pencarian,
  urutan, dan halaman tabel tidak berubah**, dan jam "dimuat jam" ikut diperbarui. Kalau gagal atau dibatalkan, data lama tetap dipakai dan
  pesannya muncul di bar atas dengan tombol Coba lagi. Di server ini berarti permintaan muat dengan `segarkan=true`: data lama tetap
  dilayani sampai yang baru siap, lalu id lamanya dialihkan ke yang baru (`Gudang.alias`), jadi sesi lain yang membuka periode yang sama
  tidak mendapat galat.
- **Export Excel.** Tombol di tabel detail mengunduh **semua baris** yang cocok dengan tab, filter, pencarian, dan urutan yang sedang
  tampil, bukan hanya halaman yang terlihat (`GET /api/laporan/{id}/detail/export`, `backend/inti/ekspor.py`). Berkasnya berisi lembar
  Data dan lembar Info (laporan, periode, filter, jumlah baris, pengekspor, waktu). Paling banyak 100.000 baris; kalau lebih, tampil
  peringatan di atas tabel dan lembar Info mencatatnya. Teks yang diawali `=` disimpan sebagai teks, bukan rumus, supaya isi database tidak
  bisa dijalankan Excel. Export memakai data yang sudah dimuat (tanpa SQL).
- **Laporan pertama langsung dimuat.** Setelah masuk, laporan paling atas di daftar yang boleh dibuka akun itu langsung dibuka dan dimuat
  dengan tanggal bawaan, tanpa memilih tanggal dulu. Laporan lain tetap meminta periode seperti biasa. Hanya sekali per sesi masuk.
- **Sapaan di bilah atas.** "Selamat Pagi/Siang/Sore/Malam, nama pengguna" menurut jam di perangkat pengguna saat halaman dibuka
  (pagi 05.00-10.59, siang 11.00-14.59, sore 15.00-17.59, selain itu malam). Bilah atas tidak memuat nama laporan; itu ada di menu samping.
- **Akun tanpa akses laporan.** Akun non-admin yang belum diberi akses ke laporan mana pun tetap bisa masuk. Ia melihat pesan "Tidak dapat
  mengakses laporan", dan menu samping hanya berisi menu akun untuk keluar.
- **Kembali ke atas.** Tombol bundar di pojok kanan bawah muncul setelah halaman digulir lebih dari 300 px dan menggulir kembali ke atas
  (tanpa animasi kalau pengguna meminta mengurangi animasi di sistemnya).

## Filter

Filter ada di panel kanan yang dibuka lewat tombol berikon corong di pojok kanan atas dashboard (lencana angka =
jumlah filter aktif). Filter yang sedang aktif tetap tampil sebagai chip di atas kartu, jadi bisa dilepas tanpa membuka panel.

## Kualitas data

- Stored procedure dipanggil SATU PER PERUSAHAAN (paralel). Memanggil SP dengan beberapa perusahaan
  sekaligus ('ybs, sun, sjn, ...') bisa menautkan PO milik perusahaan lain ke sebuah PR.
- Sebagai pengaman, nomor PO (PR/PO) atau PI (PO/PI) yang awalannya bukan perusahaan barisnya diabaikan dan dilaporkan sebagai
  "Peringatan data" di atas dashboard; pada data normal peringatan ini tidak muncul.

## New PO, PO partial, dan PI partial

**New PO (PR/PO)** = jumlah PO pada baris PR yang sudah selesai di-PO (QTYOUT = 0), PO dibuat dalam periode, status Open atau Completed.
Satuannya PO per baris PR: PR yang di-PO dua kali (dua nomor PO
berbeda) dihitung dua. PO dengan nomor dan tanggal yang sama pada satu baris PR bukan split dan dihitung sekali. Setiap PO dihitung di
periode (minggu) tanggal POnya sendiri, tepat sekali.

**Tabel detail "Sudah PO"** satu baris per PO (PR yang di-PO dua kali tampil dua baris, nomor PO tidak digabung), kecuali PO dengan nomor dan
tanggal yang sama. Jumlah barisnya (dan angka di label tab) selalu sama dengan kartu New PO. Kolom **Partial** menandai PO yang partial (Y/N)
dengan aturan yang sama dengan kartu, sehingga jumlah baris berstatus Y sama dengan angka di kartu PO partial. Keterangan di atas tabel
sengaja singkat (mis. "PO yang dibuat 11/09/2026 sampai 15/10/2026.").

**PO partial** = persen dari New PO yang berasal dari PR yang di-PO lebih dari satu nomor berbeda (PARTIAL = Y). Status partial adalah sifat PR-nya:
kedua PO tetap partial walau jatuh di minggu berbeda, dan tiap PO dihitung di minggu tanggal POnya sendiri. Karena itu jumlah PO partial per minggu
dijumlahkan selalu sama dengan jumlah seluruh periode. Status partial tidak bergantung pada filter buyer. Penyebutnya selalu sama dengan kartu New PO.

**PI partial** (PO/PI) = persen dari New PI yang PO-nya punya lebih dari satu PI. Masih memakai penilaian per PO keseluruhan, belum menurut periode.

## Kecepatan penyelesaian

Dua kartu di kisi kartu ringkasan, untuk PR (atau PO) yang DIBUAT pada periode, yaitu minggu terpilih atau seluruh minggu yang tampil.
Penjelasan singkatnya ada di dalam kartu (mis. "tanpa Void, Closed, tanggal janggal"); aturan lengkapnya di bawah.

- **Kecepatan Penyelesaian:** rata-rata hari dari PR dibuat sampai PO terakhir (PO/PI: dari tanggal dokumen PO sampai PI terakhir),
  untuk yang sudah selesai, kapan pun selesainya sampai hari ini. Ditampilkan sebagai bilangan bulat (dibulatkan ke terdekat).
- **Completion Rate per Period:** persen dari PR yang dibuat pada periode itu yang sudah selesai (PO terakhirnya terbit) pada atau sebelum
  akhir periode itu. Catatan kartu menyebut jumlahnya, mis. "1.541 dari 1.729 PR dibuat pada periode ini".

Yang TIDAK diikutkan (ringkasannya tertulis di kartu "Completion Rate per Period"):

- PR/PO berstatus **Void atau Closed**, karena tidak akan selesai lewat PO/PI.
- PR/PO berstatus Completed yang **tidak punya tanggal PO/PI yang sah** (kosong atau di masa depan), karena waktunya tidak bisa diukur.
- Data **janggal**: tanggal PO/PI lebih awal dari tanggal PR dibuat / tanggal dokumen PO (selisih negatif).
- Yang masih Open ikut di penyebut persen "Completion Rate per Period", tetapi tidak ikut di rata-rata kecepatan (belum selesai).

Lainnya:

- Titik awal sama dengan yang dipakai kolom Aging dari SP (PR: tanggal PR dibuat; PO: tanggal dokumen PO).
- Semuanya mengikuti minggu terpilih dan semua filter. Tabel detail punya kolom "Lama selesai (hari)".
- Periode yang masih baru punya waktu lebih sedikit untuk selesai: persen "Completion Rate per Period" tampak rendah, sedangkan kecepatan
  tampak sangat cepat (hanya yang cepat yang sudah selesai). Bandingkan periode yang sudah cukup lama berlalu.
- PR yang sudah selesai berumur "COMPLETED", jadi memilih filter Aging selain COMPLETED hanya menyisakan PR yang masih berjalan.

## Filter Aging (kategori umur)

Laporan PR/PO dan PO/PI sama-sama punya filter Aging (kategori aging: Tepat Waktu 0-8 hari, Perlu Perhatian 9-15, Telat 16-30,
Perlu Tindakan >30, serta COMPLETED/CLOSED/VOID). Aturannya ada di satu tempat, `backend/inti/umur.py`. Aging yang dipakai adalah umur saat data dimuat dari SP.

## Buyer dan pembuat yang tampil

Di menu filter dan grafik, buyer (PR/PO) atau pembuat (PO/PI) yang TIDAK membuat PO baru pada periode yang tampil
(minggu yang dipilih, atau seluruh minggu yang ditampilkan) disembunyikan; hitungannya ikut filter lain. Yang sedang dipilih
tetap tampil supaya bisa dilepas. Grafik Outstanding by Creator memuat pembuat yang punya outstanding. Warna tiap nama
tetap karena ditentukan oleh daftar seluruh nama (`pilihan.buyer_semua` dan `pilihan.pembuat_semua`).

## Nama buyer dan pembuat

Tidak ada nama yang disembunyikan; semua yang ada di SP tampil.

## Deteksi Kecurangan Timbangan

Transaksi timbang sawit dari stored procedure `SP_PALM_WEIGHBRIDGE`, dipanggil SATU PER PERUSAHAAN (paralel) dengan parameter perusahaan dan tanggal awal.
 Perusahaan yang dipanggil dibaca dari tabel company menurut jenis `PALM_SUMBER`. Kolom wajib di hasil SP: TicketNo, Ticket Date,
DurationMinutes, VehicleNo, ProductName, Bruto, ActualTara, MaxHistoricalTara, TaraDeviation, Deduction, Netto, Operator, NamaSupir, SupplierCode,
SupplierName (nama kolom tidak peduli huruf besar-kecil, spasi, dan garis bawah). Kolom RiskIndicator dari SP **tidak dipakai**: indikator dihitung program.
MaxHistoricalTara adalah tara historis tertinggi kendaraan (dulu median, kolom AvgHistoricalTara; nama lama masih dibaca). Kolom opsional `Splitted`
(1 = tiket hasil split) tampil sebagai kolom dan filter Splitted; tiket pecahannya sudah tidak dikirim SP.
Kolom opsional `TicketType` menjadi Jenis Transaksi: TBS Luar = Pembelian, Produk = Penjualan. Kalau jenis dipilih di panel filter, menu filter lain
(Produk, Supplier, dan seterusnya) hanya berisi nilai dari jenis itu.

**Indikator risiko** (satu per transaksi; selisih tara dinilai lebih dulu):

- `WARNING: Kenaikan Tara Tidak Wajar (>150kg atau <-150kg)`: selisih tara (TaraDeviation) lebih dari +150 atau kurang dari -150, walau durasinya juga lama.
- `WARNING: Durasi Timbang Lama (>3 Jam)`: selisih tara wajar, tetapi durasi lebih dari 180 menit.
- `NORMAL`: selain itu. Batas tepat (150 kg atau 180 menit) masih NORMAL. Angka 150 dan 180 diatur `PALM_AMBANG_TARA_KG` dan `PALM_AMBANG_DURASI_MENIT`,
  dan tulisan labelnya mengikutinya.

**Tampilan.** Ringkasan transaksi berisiko (termasuk total kg tara yang lebih ringan dari historisnya pada transaksi WARNING tara), empat kartu, grafik
jumlah per indikator, kendaraan dengan WARNING tara terbanyak (`PALM_TOP_KENDARAAN`), sebaran durasi lawan selisih tara (`PALM_MAKS_TITIK`; kalau lebih,
disampel dan titik ekstrem serta yang dipilih tetap ikut), indikator risiko per nama supplier (`PALM_TOP_SUPPLIER`), dan tabel detail dengan tab Semua
transaksi dan Berisiko. Laporan ini tidak memakai pilihan minggu.

**Cross filter.** Klik batang atau titik memfilter semua kartu, grafik, dan tabel (Ctrl/Shift + klik menambah pilihan). Klik satu titik di grafik sebaran
memfilter satu transaksi itu (filter No. Tiket). Panel filter: Perusahaan, Jenis Transaksi, Indikator Risiko, Operator, No. Kendaraan, Supplier, Nama Supir, Produk, Splitted.
Seperti laporan lain, laporan ini tertutup bagi semua role selain admin sampai diberi akses di Permission Control.

## Penerimaan TBS

Detail pembelian TBS dari stored procedure `SP_TBS` (bawaan `dbo.tbsdetailybs`), dipanggil satu per perusahaan (paralel) dengan parameter
perusahaan, tanggal awal, dan tanggal akhir; perusahaan dibaca dari tabel company menurut `TBS_SUMBER`. Periode sepanjang periode yang dipilih
tepat sebelumnya ikut diambil, untuk perbandingan kartu KPI dan sebagai riwayat forecast.

**Rumus** (sama dengan measure Power Pivot di Excel "Forecast TBS YBS db"):
- Total Netto, Total Nilai (Total Spend = SUM LINETOTAL), Supplier Aktif.
- Harga Rata-rata **tertimbang** (total nilai ÷ total kg). Excel memakai rata-rata PRICEPERKG, yang membuat pembelian 50 kg berbobot sama
  dengan 12 ton; ini satu-satunya rumus yang sengaja berbeda.
- Rata-rata per Truk: rata-rata dari rata-rata netto per baris tiap hari (AVERAGEX atas tanggal).
- Rata-rata per Hari (Senin..Minggu): rata-rata total netto harian; hari tanpa pembelian tidak dihitung (AVERAGEX melewati tanggal kosong).

**Forecast** `TBS_HARI_FORECAST` (bawaan 7) hari setelah hari aktual terakhir (MAX tanggal seluruh data; hari ini tidak dipakai karena belum
selesai): forecast(t) = Skala x Proporsi Tahun Lalu(t) x Multiplier.
- Skala (Skala Mingguan Aktual): total netto `TBS_HARI_SKALA` (14) hari terakhir ÷ 2.
- Proporsi Tahun Lalu: netto tanggal t - 364 hari (hari dalam seminggu sama) ÷ total netto blok 7 hari tahun lalu yang dimulai 364 hari
  sebelum hari pertama forecast. Kalau blok itu tidak ada di data, forecast kosong (seperti BLANK di Excel).
- Multiplier: skenario `TBS_SIMULASI` (bawaan Turun 5%, Normal, Naik 10%), dipilih di layar.
- Titik sambung: di hari aktual terakhir forecast = aktual, supaya garis menyambung.
- Nilai (Rp) forecast = netto forecast x harga tertimbang `TBS_HARI_SKALA` hari terakhir (tambahan, tidak ada di Excel).
- Uji ketepatan (tambahan): metode yang sama dijalankan seolah-olah 7 hari lalu; layar menampilkan rata-rata meleset harian (ditimbang volume)
  dan selisih totalnya terhadap aktual.
Hasilnya sama persis dengan kolom Netto Forecast di Excel (dicek 19-25/10/2026). Forecast mengikuti filter perusahaan, tipe, grup, supplier,
dan kategori, tetapi tidak filter tanggal dan hari.

**Grafik.** Netto & Forecast: garis, `TBS_HARI_TREN` (30) hari terakhir ditambah forecast, dengan pilihan Netto/Nilai (Total Spend digabung ke
sini karena sumbu waktunya sama). Harga per Tipe: satu baris per tipe berisi garis kecil harga tertimbang harian pada 30 hari yang sama, harga
terakhir, dan perubahannya; menggantikan banyak garis bertumpuk di Excel yang sulit dibaca. Netto per Tipe, Supplier Teratas, dan Business
Group: peringkat batang, masing-masing paling banyak 10 baris (yang sedang dipilih tetap tampil).

## Menambah laporan baru

Backend: buat `backend/laporan/<nama>/` berisi `sumber.py`, `ukuran.py`, `dashboard.py`, dan `__init__.py` yang membuat satu
objek `LAPORAN` (contoh: `laporan/pr_po/__init__.py`), lalu daftarkan di `backend/laporan/__init__.py`.

Frontend: buat `frontend/src/laporan/<nama>/Dashboard<Nama>.jsx` memakai komponen di `komponen/` dan `grafik/`,
lalu tambahkan satu baris di `frontend/src/laporan/index.js`. Kuncinya harus sama dengan `id` laporan di backend.

Pencarian, urutan, halaman tabel, filter pilihan banyak, cache, dan pembatalan sudah ada di `inti/`; tidak perlu ditulis ulang.
