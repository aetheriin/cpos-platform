# Panduan Menarik Branch ke Main & Cara Mundur Bila Error

Untuk `desain-sidebar` (tampilan, CCTV, normalisasi data orang) dan `optimasi-kecepatan` (kecepatan database).
Semua perintah diketik di **Git Bash** atau **Command Prompt**, di folder proyek (mis. `C:\cpos-platform`).

---

## 1. Gambaran

```
main ── desain-sidebar ── optimasi-kecepatan
```

- **`optimasi-kecepatan` dibuat dari `desain-sidebar`**, jadi isinya = desain-sidebar + optimasi.
- **Disarankan bertahap:** masukkan `desain-sidebar` dulu, pakai beberapa hari; bila aman, baru `optimasi-kecepatan`.
- **Setiap tahap diberi tanda versi (tag)**, supaya mudah kembali ke versi tertentu.

---

## 2. Sebelum mulai (wajib)

1. **Backup database** di SSMS: klik kanan database CPOS › Tasks › Back Up…
2. Catat versi yang sedang jalan, mis. `git log --oneline -1` (contoh hasil: `391bbcb Analytics: ...`).
3. Beri tanda versi lama supaya bisa kembali:
   ```
   git checkout main
   git pull origin main
   git tag sebelum-sidebar
   git push origin sebelum-sidebar
   ```

---

## 3. Tahap 1: masukkan `desain-sidebar` ke main

```
git fetch origin
git checkout main
git pull origin main
git merge --no-ff origin/desain-sidebar -m "Gabung desain-sidebar"
git push origin main
git tag rilis-sidebar
git push origin rilis-sidebar
```

Arti per baris:

| Perintah | Arti |
|---|---|
| `git fetch origin` | Ambil info terbaru dari GitHub (belum mengubah file) |
| `git checkout main` | Pindah ke branch main |
| `git pull origin main` | Samakan main di komputer dengan GitHub |
| `git merge --no-ff origin/desain-sidebar -m "..."` | Gabungkan desain-sidebar ke main. `--no-ff` membuat satu "titik gabung" yang nanti mudah dibatalkan sekaligus |
| `git push origin main` | Kirim main yang baru ke GitHub |
| `git tag rilis-sidebar` + `git push origin rilis-sidebar` | Beri tanda versi |

**Setelah kode masuk ke server CPOS:**
1. Di SSMS jalankan sekali, berurutan:
   1. `database/perubahan/004_normalisasi_orang.sql` (bila belum);
   2. `database/perubahan/005_cctv.sql`.
2. Restart CPOS. Di browser tekan Ctrl + F5.

---

## 4. Tahap 2: masukkan `optimasi-kecepatan` ke main

```
git fetch origin
git checkout main
git pull origin main
git merge --no-ff origin/optimasi-kecepatan -m "Gabung optimasi-kecepatan"
git push origin main
git tag rilis-optimasi
git push origin rilis-optimasi
```

- Tidak ada skrip database untuk tahap ini.
- Cukup restart CPOS.

---

## 5. Mengambil versi terbaru di server CPOS

Di folder CPOS pada server:

```
git checkout main
git pull origin main
```

Lalu restart CPOS (service / jendela `serve.py`).

---

## 6. Bila ada error: cara mundur (dari yang paling ringan)

### 6.1 Optimasi bermasalah → matikan tanpa ubah kode (paling cepat)

1. Buka file `.env` di folder CPOS, tambahkan:
   ```
   DB_KOLAM=0
   ```
2. Restart CPOS.

CPOS kembali memakai cara koneksi lama, sementara tampilan baru tetap ada.

### 6.2 Server kembali ke versi sebelumnya sebentar (tanpa mengubah GitHub)

Di server:

```
git fetch origin --tags
git checkout rilis-sidebar
```

- Restart CPOS. Server sekarang memakai versi bertanda `rilis-sidebar` (tanpa optimasi).
- Contoh versi lain: `git checkout sebelum-sidebar` (lihat peringatan database di 6.4).
- **Kembali ke versi terbaru:**
  ```
  git checkout main
  git pull origin main
  ```

### 6.3 Batalkan gabungan di main (permanen, rapi di riwayat)

1. Cari titik gabungnya:
   ```
   git log --oneline --merges -5
   ```
   Contoh hasil: `a1b2c3d Gabung optimasi-kecepatan`.
2. Batalkan:
   ```
   git checkout main
   git pull origin main
   git revert -m 1 a1b2c3d
   git push origin main
   ```
   - `-m 1` = "pertahankan sisi main, buang isi branch yang digabung".
   - Riwayat tidak dihapus; Git membuat commit baru yang membalik perubahannya.
3. Di server: `git pull origin main`, lalu restart CPOS.

**Ingin memasukkan lagi setelah diperbaiki?** Batalkan dulu pembatalannya (revert dari commit revert), lalu merge perbaikannya:

```
git log --oneline -5                 # cari commit "Revert "Gabung optimasi-kecepatan""
git revert <kode commit revert itu>
git merge --no-ff origin/optimasi-kecepatan -m "Gabung optimasi-kecepatan (perbaikan)"
git push origin main
```

### 6.4 Peringatan database

- Skrip `004_normalisasi_orang.sql` **mengubah struktur tabel orang**: tabel lama dihapus, data dipindah. Kode main sebelum `desain-sidebar` memakai tabel lama.
- Jadi bila ingin kembali ke `sebelum-sidebar` **setelah 004 dijalankan**, database juga harus dikembalikan dari backup (bagian 2). Kembali ke `rilis-sidebar` tidak perlu restore.
- `005_cctv.sql` hanya menambah tabel & menu, aman dibiarkan untuk versi mana pun.
- `optimasi-kecepatan` tidak mengubah database.

---

## 7. Perintah bantu

| Perintah | Kegunaan |
|---|---|
| `git status` | Branch aktif & file yang berubah |
| `git log --oneline -10` | 10 commit terakhir |
| `git branch -a` | Semua branch (lokal & GitHub) |
| `git tag` | Semua tanda versi |
| `git diff main origin/optimasi-kecepatan --stat` | File yang akan berubah bila branch itu digabung |
| `git checkout -- .` | Buang perubahan file di komputer yang belum di-commit (hati-hati) |

**Bila `git merge` berhenti karena "CONFLICT"** (bentrok; saat ini tidak akan terjadi karena main belum berubah):
- jalankan `git merge --abort` untuk membatalkan;
- tanyakan ke programmer.
