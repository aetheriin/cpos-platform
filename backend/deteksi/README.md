# Deteksi Plat Sawit

Membaca plat nomor kendaraan langsung dari CCTV (UNV IPC2324SB-DZK-I0) untuk pos security PKS.
Tahap sekarang: **uji coba mandiri** di HO dengan satu kamera. Belum tersambung ke web timbangan v2;
integrasi ke info bar Form Security menyusul setelah akurasinya terbukti.

## Cara kerja

```
CCTV ──RTSP──> ambil frame terbaru ──> deteksi plat (YOLOv9-tiny) ──> baca huruf (OCR)
                                                    │
         rapikan ke format baku "BM 1455 JJ" (aturan sama dengan web timbangan)
                                                    │
         voting beberapa frame ──> plat pasti ──> konsol + hasil/plat_*.csv + gambar bukti
```

- Model AI: [fast-alpr](https://github.com/ankandrew/fast-alpr) (MIT). Model jadi, **tanpa training**,
  format ONNX, jalan di CPU. Model OCR `cct-s-v2-global-model` dilatih dengan plat banyak negara
  termasuk Indonesia.
- Hasil OCR disaring dengan aturan plat Indonesia (kode wilayah, huruf-angka-huruf). Karakter yang sering
  tertukar dibetulkan sesuai posisinya (`8`↔`B`, `5`↔`S`, `1`↔`I`, `0`↔`O`), baris masa berlaku
  (mis. `06.27`) dibuang, dan bacaan yang tidak masuk akal ditolak.
- Plat baru dilaporkan setelah terbaca sama di beberapa frame. Kendaraan yang berhenti lama tidak
  tercatat berkali-kali.

## 1. Siapkan kamera

Buka web kamera di browser (`http://<IP kamera>`), lalu:

| Menu | Pengaturan |
|---|---|
| Video (main stream) | Encoding **H.264** (lebih ringan didekode PC lama daripada H.265), resolusi 2560x1440 atau 1920x1080, **15 fps** |
| Image / Exposure | Shutter tetap sekitar 1/250 s (malam: cegah blur), WDR aktif, Smart IR aktif |
| Network › Port | RTSP port 554 (bawaan) |
| User | Buat user khusus yang hanya bisa melihat (jangan pakai admin) |

Posisi & zoom: sudut ke plat sebaiknya di bawah 30°. Zoom (lensa motorized 2.8–12 mm) sampai **lebar plat
di layar minimal sekitar 130–150 px**. Angka `lebar ...px` tampil di bawah kotak plat pada preview.

## 2. Pasang dan jalankan

Deteksi Plat dijalankan bersama CPOS oleh `jalankan.bat` di akar repo (Python dan library dipasang sendiri di
`%LOCALAPPDATA%\deteksi-plat`). Pengaturannya di `backend\.env` (satu file untuk semua aplikasi): `KAMERA_IP`, `KAMERA_USER`,
`KAMERA_PASS`, `DETEKTOR_PORT`, `FOLDER_FOTO`, dll. Kamera juga bisa ditambah dari web tanpa mengubah `.env`.

Menjalankan sendiri (uji): `python server_web.py --port 8000` dari folder ini.

Di jendela preview: **Q / Esc** = keluar, **S** = simpan snapshot.

Warna kotak: **hijau** = plat terbaca dan format valid, **kuning** = plat yang sama sudah dilaporkan,
**merah** = ditolak (alasan tertulis di sampingnya).

Uji dari rekaman atau foto (mis. rekaman dari NVR / HP):

```
venv\Scripts\python baca_plat.py --video rekaman.mp4
venv\Scripts\python baca_plat.py --video foto_plat.jpg
```

## 4. Hasil

Semua di folder `hasil/`:

| File | Isi |
|---|---|
| `plat_YYYY-MM-DD.csv` | Satu baris per plat yang pasti terbaca: waktu, plat, jumlah frame, keyakinan, lebar plat, gambar |
| `bacaan_YYYY-MM-DD.csv` | Semua bacaan per frame termasuk yang ditolak, untuk mencari pola salah baca |
| `YYYY-MM-DD/*.jpg` | Gambar frame (dengan kotak) + crop plat untuk tiap plat, juga snapshot tombol S |

CSV memakai pemisah `;` supaya langsung rapi di Excel. Gambar dan CSV ini juga menjadi bahan dataset bila
nanti model perlu dilatih ulang.

## 5. Yang dicatat selama uji coba

Untuk memutuskan apakah model jadi ini cukup atau perlu dilatih ulang:

1. Bandingkan `plat_*.csv` dengan plat sebenarnya: berapa persen benar seluruh karakternya?
2. Pisahkan siang / malam / hujan / silau.
3. `proses AI ... ms/frame` di konsol: kecepatan PC. Di bawah sekitar 500 ms masih nyaman karena truk berhenti.
4. Kesalahan yang berulang di `bacaan_*.csv` (mis. huruf tertentu selalu salah).

Bila OCR terlalu lambat, ganti `OCR_MODEL=cct-xs-v2-global-model` di `.env`.

## Masalah umum

| Gejala | Penyebab / solusi |
|---|---|
| `Gagal tersambung` terus | IP salah / beda jaringan (coba `ping <IP>`), user/password salah, port 554 diblok. Coba buka `rtsp://...` di VLC |
| Tersambung tapi gambar patah / lambat | Ganti main stream ke H.264 dan 15 fps, atau resolusi 1920x1080 |
| Plat terdeteksi tapi selalu merah `OCR kurang yakin` | Plat terlalu kecil (lihat `lebar ...px`), perbesar zoom; atau turunkan `MIN_CONF_OCR` sedikit |
| Error DLL saat memuat model | Pasang [Visual C++ Redistributable x64](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| Jendela preview tidak muncul | Jalankan ulang `pasang.bat` (mengganti OpenCV tanpa-jendela) |

## Pengembangan

```
baca_plat.py          program utama (kamera / video / foto, preview, konsol)
anpr/kamera.py        stream RTSP di thread, selalu frame terbaru, sambung ulang otomatis
anpr/pembaca.py       deteksi plat + OCR (fast-alpr)
anpr/plat.py          aturan plat Indonesia (disalin dari web timbangan) + koreksi karakter
anpr/penstabil.py     voting beberapa frame, redam laporan ganda
anpr/penyimpan.py     CSV + gambar bukti
tests/                python -m pytest
```

Rencana berikutnya: dua kamera (depan & belakang) dalam satu sesi, lalu API ke web timbangan v2 untuk
mengisi No. Plat di info bar Form Security, dengan konfirmasi security tetap wajib.
