# Panduan Tampilan, Cakupan Data & Data Orang

Dokumen ini menjelaskan:
- cara mengubah tampilan CPOS (warna, lebar menu samping);
- cara kerja cakupan data per PT;
- struktur data orang dan Visitor & Staff Logs setelah normalisasi mengikuti ERD Blueprint CPOS.

---

## 1. Mengubah tampilan

Setelah mengubah file CSS / konfigurasi di bawah, **build ulang** `tailwind.css` dari folder `CPOS`:

```
node node_modules/tailwindcss/lib/cli.js -i ./static/css/tailwind-source.css -o ./static/css/tailwind.css --minify
```

Lalu muat ulang halaman di browser (Ctrl + F5).

### 1.1 Warna utama (biru)

| Yang diubah | File | Baris |
|---|---|---|
| Nilai warna (angka R G B) | `CPOS/static/css/tailwind-source.css` | blok `:root` paling atas, variabel `--utama-50` s/d `--utama-800` |
| Nama warna untuk class (`bg-utama-600`, dll.) | `CPOS/tailwind.config.js` | `colors.utama` (cukup dibiarkan, membaca variabel di atas) |

Contoh: ubah ke hijau dengan mengganti angka di `:root`. Contoh angka hijau sudah ditulis di komentar tepat di atasnya.

```css
:root {
  --utama-50: 236 246 253;  --utama-100: 212 236 251; --utama-200: 168 214 245; --utama-300: 125 190 236; --utama-400: 80 170 225;
  --utama-500: 41 151 214;  --utama-600: 18 124 191;  --utama-700: 13 102 160; --utama-800: 14 84 130;
}
```

Kegunaan tiap angka warna:
- **600:** tombol utama, menu aktif;
- **50 / 100:** latar terang (sorotan);
- **700:** teks pada latar terang.

Warna lain (merah = bahaya, hijau = berhasil, kuning = peringatan) sengaja tidak ikut warna utama.

### 1.2 Lebar menu samping (sidebar)

| Yang diubah | File | Baris |
|---|---|---|
| Lebar sidebar | `CPOS/static/css/tailwind-source.css` | `--lebar-sidebar: 19rem;` di blok `:root` |

Nama menu tidak turun ke baris kedua. Kalau nanti ada nama menu yang lebih panjang, besarkan angkanya (mis. `20rem`) lalu build ulang.

### 1.3 Tombol kembali ke atas

- Tombol bulat di kanan bawah muncul setelah halaman digulir lebih dari 300 px, sama seperti di Analytics.
- **Kode:** `CPOS/templates/base.html` (tombol `#tombolKeAtas`) dan `CPOS/static/js/base.js` (bagian "Tombol kembali ke atas").
- **Jarak munculnya:** ubah angka `300` di `base.js`.

### 1.4 Tabel rapi

- **Perataan judul kolom:** otomatis mengikuti isinya, dikerjakan oleh `samakanPerataanTabel` di `base.js`. Angka rata kanan, status di tengah, teks rata kiri.
- **Judul kolom:** tidak turun baris.
- **Isi sel:** sejajar di tengah secara vertikal (`.table-cell` di `tailwind-source.css`).
- **Membuat kolom angka baru:** cukup beri `text-right` pada sel isinya (`<td>`). Judul kolomnya ikut sendiri.

---

## 2. Hak Akses & cakupan data

### 2.1 Hak per menu

- Kolom hak (Lihat, Tambah, Ubah, Hapus, Setujui, …) di **Admin › Hak Akses** hanya menampilkan aksi yang memang ada di menu itu.
- Laporan **Analytics** hanya punya **Lihat**, karena laporannya hanya menarik data, bukan mengisi.
- Aksi per menu diatur di tabel `MenuAction`.

### 2.2 Cakupan data (pengganti "PT dikelola" / tabel UserCompany)

Setiap aturan **Izinkan** di Hak Akses punya kolom **Cakupan data**:

| Pilihan | Artinya |
|---|---|
| Area sendiri (bawaan) | Data area pengguna. Akun kantor pusat (HO) tetap melihat semua PT |
| PT sendiri | Semua area milik PT pengguna |
| Semua PT | Semua PT, termasuk PT baru nanti |
| PT tertentu | Pilih PT-nya (mis. YBS + SJN) |

Aturan pemakaian:
- **Diatur per menu.** Contoh: staf Pembelian YBS boleh melihat SJN di *Pembelian TBS Daily*, tetapi tidak di menu lain.
- **Digabung.** Kalau seseorang kena beberapa aturan, PT yang terlihat adalah gabungan semuanya.
- **Penyimpanan:** `AccessMenu.MenuDetails` (JSON), contoh `{"cakupan":"PT_TERTENTU","pt":["YBS","SJN"]}`.
- **Fungsi database:** `dbo.fn_UserMenuScope(@UserID, @MenuCode)` dan `dbo.sp_UserScope @UserID, @MenuCode`.
- **Berlaku di CPOS, RekapIn, dan Analytics.** Di Analytics, tampilan laporan tetap sama; baris PT di luar cakupan tidak ikut dihitung dan tidak muncul di pilihan perusahaan.

---

## 3. Data orang (normalisasi mengikuti ERD)

### 3.1 Jenis orang dibaca dari relasi (tabel UserCategory dihapus)

| Jenis | Ciri di data |
|---|---|
| Karyawan | `Users.UserLevelID` terisi (jabatan = departemen + level). Security = departemen Security; **BHL = jabatan "BHL"** (mis. "Sortasi · BHL"), tanpa akun |
| Driver | `Users.GuestID` terisi (profil visitor) **dan** punya SIM aktif (`LicenseDetail`) |
| Tamu | `Users.GuestID` terisi, tanpa SIM |
| Punya akun | `Users.UserName` terisi; menu dari `AccessMenu` |

- Jenis orang dibaca di view `dbo.UserProfile.PersonType`. Di kode: `utils/jenis_orang.py`.
- Blacklist dan Alur Persetujuan memakai jenis yang sama: Karyawan / Driver / Tamu, ditambah Kendaraan / Supplier.

### 3.2 Tabel yang berubah

| Tabel / kolom | Sekarang |
|---|---|
| `UserCategory`, `Users.CategoryCode` | **Dihapus**: jenis orang dari relasi (lihat 3.1) |
| `VisitPurpose` | **Dihapus**: keperluan disimpan sebagai teks: `Guest.VisitorNeeds` (keperluan biasa) dan `FaceActivity.Description` (keperluan kunjungan itu) |
| `UserCompany` | **Dihapus**: diganti Cakupan data (bagian 2.2) |
| `Guest` | Profil visitor, satu baris per orang (asal perusahaan, keperluan biasa, NIK). Ditunjuk oleh `Users.GuestID` |
| `Users.FaceEmbeddingData`, `Users.UploadPath` | **Tetap**: wajah terdaftar, **satu per orang**. Bisa dari kamera atau upload; perubahan tercatat di Log |
| `FaceRecog` | **Tetap, fungsinya berubah**: foto wajah yang **tertangkap kamera setiap scan** (bukti), termasuk wajah tak dikenal. Kolom: FaceName (nama yang dikenali), FaceDet (embedding saat scan), Blacklist |
| `FaceActivity` | **Semua aktivitas scan**: absensi karyawan masuk / keluar, kunjungan driver / tamu masuk / keluar, scan tak dikenali / ditolak. `StatusID` → tabel Status (`WAJAH_BERHASIL`, `WAJAH_TIDAK_DIKENALI`, `WAJAH_DITOLAK`), `FaceID` → FaceRecog |
| Trigger `TR_FaceRecog_Utama` | **Dihapus**: tidak ada lagi salinan dobel |

### 3.3 FaceRecog vs FaceEmbeddingData: tidak dobel

- **`Users.FaceEmbeddingData` / `UploadPath`** = wajah **acuan** orang itu (siapa dia).
- **`FaceRecog`** = foto **setiap kali** kamera menangkap wajah (bukti scan).
- **Alur scan:**
  1. Foto dari kamera disimpan di FaceRecog.
  2. Foto itu dicocokkan dengan wajah acuan di Users.
  3. Hasilnya dicatat di FaceActivity, yang menunjuk orangnya (`UserID`) dan fotonya (`FaceID`).

---

## 4. Visitor & Staff Logs (Forms › Visitor & Staff Logs, `/visitor-logs`)

Satu halaman untuk semua scan wajah. Menu lama **Pengenalan Wajah** dan **Tamu** dialihkan ke sini.

| Tab | Isi | Hak (Admin › Hak Akses) |
|---|---|---|
| Scan Wajah | Kamera, ringkasan hari ini, daftar "Masih di dalam" | `VSL_SCAN`: Tambah = scan & catat masuk, Ubah = catat keluar |
| Logs | Aktivitas scan, absensi karyawan harian, rekap bulanan | `VSL_LOGS`: Lihat |
| Data Orang | Daftar orang, tambah / ubah / hapus, persetujuan pendaftaran | `PERSONEL`: Tambah / Ubah / Hapus / Setujui |

Hasil scan:
- **Karyawan** (termasuk security & BHL): absensi langsung tercatat MASUK / KELUAR, dengan status tepat waktu / terlambat dari Jadwal Kerja area.
- **Driver / tamu:** muncul form kunjungan (keperluan, orang yang dituju, plat), lalu **Catat Masuk**. Kalau masih di dalam, tombolnya **Catat Keluar**.
- **Tidak dikenali:** tetap dicatat sebagai bukti. Tombol **Daftarkan Orang** membuka form Tambah Orang dengan foto hasil scan. Jenis orang dipilih dari dropdown, dan isian form menyesuaikan:
  - Karyawan → area, departemen, jabatan;
  - Driver → asal perusahaan + SIM;
  - Tamu → asal perusahaan, keperluan.
- **Diblacklist:** ditolak, dicatat di Logs dan Log Validasi Blacklist.

Persetujuan pendaftaran (opsional):
- **Cara mengaktifkan:** Admin › Alur Persetujuan › **Data orang · Tambah**, bisa dibedakan per jenis orang.
- **Selama menunggu:** orangnya belum aktif (wajahnya belum dikenali).
- **Tanpa alur:** langsung aktif.

---

## 5. Memperbarui database yang sudah berjalan

Jalankan **sekali** di SSMS, setelah backup:

```
CPOS/database/perubahan/004_normalisasi_orang.sql
```

Isi skrip ini:
- memindahkan data lama:
  - kategori → jabatan / profil visitor;
  - kunjungan lama & absensi lama → FaceActivity;
  - wajah utama → Users;
- menghapus tabel lama;
- menyusun menu Visitor & Staff Logs dan menyalin hak lamanya.

Skrip aman bila tidak sengaja dijalankan dua kali. Database baru cukup dibuat dari `schema.sql`.

> Catatan: akun kantor pusat yang sebelumnya dibatasi "PT dikelola" kembali melihat semua PT. Batasi lagi lewat Admin › Hak Akses › Cakupan data.
