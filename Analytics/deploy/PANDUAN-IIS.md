# Hosting di IIS (Windows 10 Pro)

Cara kerjanya:

```
Browser ──► IIS (port 80) ──┬─ /laporan/..., /login, file js/css  → folder web (hasil build frontend)
                            └─ /api/...                            → backend FastAPI (127.0.0.1:8001, hanya bisa diakses dari server itu)
```

Backend berjalan sebagai tugas Windows yang otomatis menyala saat komputer server dinyalakan. Pengguna hanya membuka satu alamat,
misalnya `http://192.168.1.20`.

---

## 1. Di komputer developer: buat paket

Buka PowerShell di folder proyek:

```bash
powershell -ExecutionPolicy Bypass -File deploy\buat-paket.ps1
```

Hasilnya `deploy\paket\dashboard-analytics.zip`. Isinya tidak memuat `.env`, karena file itu berisi password database. File `.env`
disalin terpisah di langkah 4.

## 2. Di server (lewat AnyDesk): pasang prasyarat

Cukup sekali saja. Kalau sudah terpasang, lewati.

1. **IIS.** Buka *Turn Windows features on or off* → centang **Internet Information Services** → OK.
2. **URL Rewrite** untuk IIS: unduh dari situs resmi Microsoft (iis.net, cari "URL Rewrite") lalu pasang.
3. **Application Request Routing (ARR) 3.0**: unduh dari iis.net (cari "Application Request Routing") lalu pasang.
4. **ODBC Driver 18 for SQL Server**: unduh dari learn.microsoft.com (cari "Download ODBC Driver for SQL Server") lalu pasang.
5. **Python 3.14** dari python.org. Saat memasang, **centang "Add python.exe to PATH"**.
   Jangan pakai versi terbaru (3.15 ke atas). Pustaka `pyodbc` belum mendukungnya, sehingga pemasangan gagal dengan pesan
   "Microsoft Visual C++ 14.0 or greater is required". Python 3.14 boleh dipasang berdampingan dengan versi lain; skrip pasang
   otomatis memilih versi yang didukung (3.14, 3.13, 3.12, atau 3.11).

Setelah memasang semuanya, tutup lalu buka lagi PowerShell supaya PATH yang baru terbaca.

## 3. Salin paket ke server

1. Di AnyDesk, buka **File Transfer** (ikon dua panah di toolbar), lalu kirim `dashboard-analytics.zip` ke server.
2. Ekstrak ke **`C:\inetpub\dashboard-analytics`**. Hindari folder di dalam `C:\Users\...`, karena IIS sering tidak boleh membacanya.

Isi foldernya:

```
C:\inetpub\dashboard-analytics\
  web\       ← dibaca IIS
  backend\
  deploy\
```

## 4. Salin `.env`

Kirim `backend\.env` dari komputer developer ke `C:\inetpub\dashboard-analytics\backend\.env` lewat File Transfer AnyDesk.
Periksa isinya kalau server memakai database atau akun yang berbeda (`DB_SERVER`, `DB_USER`, dan seterusnya).

Kalau situs nanti dibuka lewat HTTPS, tambahkan `COOKIE_SECURE=1`. Untuk HTTP biasa, biarkan.

## 5. Jalankan skrip pasang

Buka **PowerShell sebagai Administrator** (klik kanan → *Run as administrator*):

```bash
cd C:\inetpub\dashboard-analytics
powershell -ExecutionPolicy Bypass -File deploy\pasang-server.ps1
```

Skrip ini:
- memasang pustaka Python;
- memeriksa koneksi ke tabel pengguna;
- mendaftarkan backend;
- membuat situs IIS;
- membuka port 80 di firewall.

Di akhir, skrip menampilkan alamat yang bisa dibuka.

Kalau muncul **"Port 80 sudah dipakai situs IIS 'Default Web Site'"**, pilih salah satu:
- Buka *IIS Manager* → *Sites* → klik kanan **Default Web Site** → *Manage Website* → **Stop**, lalu jalankan skrip lagi; atau
- Pakai port lain: `powershell -ExecutionPolicy Bypass -File deploy\pasang-server.ps1 -PortWeb 8080`.

## 6. Coba

1. Di server, buka `http://localhost`.
2. Dari komputer lain di jaringan yang sama, buka `http://<IP server>` (alamatnya ditampilkan di akhir skrip).
3. Login, buka satu laporan, lalu tekan **F5** di alamat `/laporan/...`. Halaman harus tetap tampil, bukan 404.

---

## Update ke versi baru

1. Di komputer developer, jalankan lagi `deploy\buat-paket.ps1`.
2. Di server, ekstrak zip baru ke folder yang sama dan timpa isinya. Folder `backend\venv`, `.env`, dan `pengaturan.json` tidak ikut tertimpa karena tidak ada di zip.
3. Jalankan lagi `deploy\pasang-server.ps1` sebagai Administrator.

Saat backend dinyalakan ulang, semua pengguna akan logout, karena sesi disimpan di memori.

## Kalau ada masalah

| Gejala | Periksa |
| --- | --- |
| pip gagal: "Microsoft Visual C++ 14.0 or greater is required" saat memasang pyodbc | Versi Python terlalu baru; pasang Python 3.14 lalu jalankan skrip lagi |
| Halaman putih atau error 500.19 | URL Rewrite belum terpasang |
| Login gagal dengan pesan "Terjadi kesalahan (502)" | Backend mati: lihat `backend\server.log`, atau ARR proxy belum aktif (jalankan skrip lagi) |
| "Tidak bisa membaca tabel pengguna" | Isi `.env`, ODBC Driver 18, dan apakah server bisa menjangkau SQL Server (port 1433) |
| Bisa dibuka di server tapi tidak dari komputer lain | Firewall Windows, atau alamat IP yang dipakai salah |
| Export Excel lama lalu gagal | Batas waktu proxy 10 menit; data yang sangat besar perlu difilter dulu |

Menyalakan, mematikan, atau melihat backend: buka *Task Scheduler* → **DashboardAnalytics-Backend**, lalu klik *Run* atau *End*.

## Catatan

- Log Aktivitas akan mencatat IP semua pengguna sebagai `127.0.0.1`. Ini karena permintaan ke backend selalu lewat IIS di mesin yang sama.
- Peringatan "unduhan tidak aman" saat Export Excel muncul karena situs memakai HTTP, bukan HTTPS. Peringatan ini hilang kalau IIS
  dipasangi sertifikat HTTPS. Setelah itu, atur `COOKIE_SECURE=1` di `.env`.
