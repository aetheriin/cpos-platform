# Dashboard Analytics

> Letak folder sekarang: backend di `backend\analytics`, frontend di `frontend\analytics`, pengaturan di `backend\.env`
> (satu untuk semua aplikasi). Path `backend/...` dan `frontend/...` di bawah dibaca relatif ke folder itu.

Dashboard laporan procurement (React + Tailwind + Recharts di depan, FastAPI + SQL Server di belakang).

## Susunan folder

```
backend/
  api.py                  endpoint (tipis, tidak berisi rumus)
  inti/                   dipakai SEMUA laporan: db, gudang (cache + pemuatan + batal), kategori, filter, tabel,
                          cpos (login & hak akses dari CPOS), perusahaan (tabel company)
  laporan/
    __init__.py           daftar laporan (satu elemen per laporan)
    pr_po/                sumber.py (SP + pembersihan), ukuran.py (rumus), dashboard.py (grafik + tabel)
    po_pi/                sama
    palm/                 laporan Deteksi Kecurangan Timbangan (sama)
  database/               sumber SQL stored procedure laporan di database Main (dijalankan manual, bukan oleh program)
frontend/analytics/src/
  App.jsx  api.js         kerangka (menu samping, daftar laporan)
  komponen/               umum: Sidebar, PanelPeriode, LaporanView, FilterMulti, Kartu, TabelBaris, TabelDetail
  grafik/                 umum: WeeklyChart, GarisSeri, DonatKategori, KategoriOutstandingChart, BatangPembuat,
                          BatangRisiko, BatangKendaraan, BatangRisikoSupplier, SebaranTara (laporan timbangan)
  laporan/                index.js (daftar dashboard) + satu folder per laporan
  lib/data.js            fungsi kecil (tanggal, pilihan, format)
```

## Menjalankan

```
cd backend\analytics
pip install -r requirements.txt
uvicorn api:app --reload          # satu proses saja, jangan pakai banyak worker

cd frontend
npm run dev
```

Isi `backend\.env` di akar repo (satu file untuk semua aplikasi, contoh: `backend\.env.example`).

**Setelah memperbarui kode dari zip baru, jalankan `pip install -r requirements.txt` lagi** (di venv yang sama). Daftar pustaka bisa bertambah,
mis. `openpyxl` untuk Export Excel. Kalau `openpyxl` belum terpasang, server tetap menyala
(dengan peringatan di terminal) dan hanya tombol Export Excel yang gagal, dengan pesan yang menyebut apa yang harus dipasang.

## Login dan hak akses (CPOS)

Analytics tidak punya login sendiri. Alamat CPOS dibuat otomatis dari `PORT` di `backend\.env` (bisa ditimpa dengan `CPOS_URL`).

- **Login.** Laporan dibuka dari menu CPOS (`/an/<id laporan>`). Setiap permintaan, backend meneruskan cookie sesi CPOS milik browser ke
  `CPOS_URL/api/analytics/saya` (`backend/inti/cpos.py`). Sesi CPOS yang berakhir dijawab 401, dan layar menampilkan tombol Masuk ke CPOS.
- **Laporan yang boleh dibuka** mengikuti hak **Lihat** menu laporan itu di Hak Akses CPOS.
- **Cakupan perusahaan.** Kalau di CPOS (Admin › Hak Akses › Cakupan data) seorang pengguna dibatasi ke perusahaan tertentu untuk sebuah laporan,
  semua kartu, grafik, tabel, dan Export Excel hanya berisi baris perusahaan itu (`_pt_boleh` dan `_saring_pt` di `api.py`, menurut kolom `comp`).
- **Data laporan per sesi.** Data yang dimuat disimpan di memori server milik sesi CPOS yang memuatnya. Sesi yang tidak memanggil Analytics selama
  `SESI_IDLE_MENIT` (paling cepat 30 menit) dibuang datanya; penyapu berjalan tiap `SESI_SAPU_DETIK` (bawaan 60 detik).
- **Pramuat.** Sidebar CPOS memanggil `POST /api/laporan/pramuat` sekali setelah login, sehingga semua laporan yang boleh dibuka mulai dimuat di latar.

Kode login mandiri yang lama (tabel users, role, PERMISSIONS, halaman admin) sudah dibuang dan disimpan di `X:\lama\Analytics\`.

## Konfigurasi (.env) dan hard code

**Hard code** adalah nilai yang ditulis langsung di dalam kode padahal bisa berubah (alamat server, kata sandi, nama stored procedure, daftar perusahaan, daftar
role dan hak aksesnya, batas-batas), sehingga mengubahnya berarti mengedit program. Di proyek ini nilai seperti itu diletakkan di luar kode:

| Jenis | Disimpan di |
|---|---|
| Kata sandi, server, dan database | `backend\.env` (tidak ikut di zip) |
| Perusahaan yang dipanggil SP laporan | tabel company (kolom CompID, CompType, Status, CompAddr, CompDataBase; jenis dipilih `LAPORAN_SUMBER`) |
| Login, laporan yang boleh dibuka, dan cakupan perusahaan | CPOS (Hak Akses) |
| Nama stored procedure dan parameternya | `.env`: `SP_PR_PO`, `SP_PO_PI`, `LAPORAN_SUMBER`, `SP_STATUS` |
| Batas dan bawaan | `.env`, dibaca di satu tempat (`backend/inti/konfigurasi.py`) |

Frontend tidak memegang angka atau nama itu: batas rentang hari, nama aplikasi, dan daftar laporan yang boleh dibuka dikirim server. Alamat backend untuk `npm run dev`
diatur `VITE_API_TARGET` di `frontend/analytics/.env.local` (bawaan `http://localhost:8001`). Semua variabel di `.env` bersifat opsional kecuali `DB_*`; nilai bawaannya
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
| `CPOS_URL` | (wajib) | alamat CPOS untuk memeriksa sesi dan hak akses |
| `DB_APP_TABEL_COMPANY` | `company` | nama tabel company (boleh di database lain lewat `DB_APP_*`) |
| `NAMA_APLIKASI` | `Dashboard Analytics` | nama di menu samping dan judul tab browser |

**Yang sengaja tetap di kode**, di satu tempat masing-masing: aturan bisnis laporan (batas kategori aging di `inti/umur.py`, status aktif, rumus, definisi kolom tabel),
dan teks tampilan. Aturan-aturan itu jarang berubah;
memindahkannya ke tabel masuk akal hanya kalau pengguna bisnis perlu mengubahnya sendiri.

## Log

Muat laporan dan Export Excel dicatat satu baris di log server (keluaran uvicorn, mis. analytics.log), dengan laporan, periode, dan pengguna CPOS. Riwayat aktivitas pengguna ada di CPOS.

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
- **Dibuka langsung (bukan dari CPOS).** Kalau `/analytics` dibuka langsung dengan sesi CPOS yang masih berlaku, tampil menu samping berisi
  laporan dan bilah atas dengan sapaan "Selamat Pagi/Siang/Sore/Malam, nama pengguna". Di dalam CPOS keduanya disembunyikan.
- **Akun tanpa akses laporan** melihat pesan "Tidak dapat mengakses laporan"; aksesnya diberikan di Hak Akses CPOS.
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
Seperti laporan lain, siapa yang boleh membukanya diatur di Hak Akses CPOS.

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

Frontend: buat `frontend/analytics/src/laporan/<nama>/Dashboard<Nama>.jsx` memakai komponen di `komponen/` dan `grafik/`,
lalu tambahkan satu baris di `frontend/analytics/src/laporan/index.js`. Kuncinya harus sama dengan `id` laporan di backend.

Pencarian, urutan, halaman tabel, filter pilihan banyak, cache, dan pembatalan sudah ada di `inti/`; tidak perlu ditulis ulang.
