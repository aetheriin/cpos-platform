# Panduan Monitoring CCTV (Tahap 1: live per area)

Dokumen ini untuk dipelajari dari nol:
- **Bagian A:** cara kerja secara sederhana.
- **Bagian B:** kamus istilah (RTSP, go2rtc, VLC, port, NVR, dll.).
- **Bagian C:** langkah pemasangan lengkap, dari meminta data ke IT sampai kamera tampil di CPOS.
- **Bagian D:** masalah yang sering terjadi dan cara mengatasinya.
- **Bagian E:** pengaturan, database, dan tahap berikutnya.

---

## A. Cara kerja (gambaran sederhana)

```
Kamera / NVR  ──RTSP──►  Gateway video (go2rtc)  ──HTTP──►  Server CPOS  ──►  Browser pengguna
 (LAN cabang)            (PC/server di cabang/HO)           (cek hak akses)     (cabang / HO)
```

Bayangkan seperti ini:
- **Kamera** = sumber siaran. Ia "menyiarkan" video lewat jaringan memakai bahasa bernama **RTSP**.
- **Browser** (Chrome, Edge) **tidak mengerti RTSP**. Jadi perlu "penerjemah".
- **go2rtc** = penerjemah. Ia mengambil video RTSP dari kamera, lalu mengubahnya menjadi gambar JPEG / video MJPEG yang bisa ditampilkan browser.
- **Server CPOS** = penjaga pintu. Sebelum gambar dikirim ke browser, CPOS mengecek: apakah pengguna ini punya hak melihat, dan apakah kamera ini ada di area cakupannya?

Akibatnya:
- **Browser tidak pernah terhubung langsung ke kamera.** Alamat dan password kamera tidak pernah sampai ke komputer pengguna.
- **Hak akses tetap berlaku.** Orang yang tidak diberi hak tidak bisa membuka kamera, walaupun tahu alamatnya.
- **Rekaman tetap di NVR.** CPOS hanya untuk memantau secara langsung (live), bukan merekam.
- **Merk kamera bebas** (Hikvision, Dahua, Uniview, EZVIZ, dll.), asalkan kamera bisa mengirim RTSP. Hampir semua kamera IP bisa.

Di CPOS:
- **Grid:** gambar diperbarui tiap 2 detik dari sub-stream (ringan, cocok dilihat dari HO).
- **Layar penuh:** video kualitas penuh (MJPEG). Siapa yang membuka kamera tercatat di Log.

---

## B. Kamus istilah

### B.1 Jaringan

| Istilah | Penjelasan sederhana | Contoh |
|---|---|---|
| **Alamat IP** | "Nomor rumah" sebuah perangkat di jaringan. Setiap kamera, PC, dan server punya satu | `192.168.10.31` |
| **IP statis** | Alamat IP yang dikunci, tidak berubah-ubah. **Kamera dan gateway wajib IP statis**, kalau tidak, alamat yang didaftarkan di CPOS bisa tiba-tiba salah | diatur di kamera atau router oleh IT |
| **LAN** (Local Area Network) | Jaringan lokal di dalam satu kantor / cabang. Cepat dan tidak lewat internet | jaringan kabel di PKS YBS |
| **WAN** (Wide Area Network) | Jaringan yang menghubungkan kantor-kantor yang berjauhan | HO ↔ cabang |
| **VPN** | "Terowongan" aman lewat internet supaya jaringan HO dan cabang seolah-olah satu LAN. Dipakai agar HO bisa menjangkau gateway cabang | VPN kantor yang dipasang IT |
| **Port** | "Nomor pintu" pada sebuah alamat IP. Satu perangkat bisa punya banyak layanan, masing-masing di pintu berbeda | lihat B.2 |
| **Firewall** | "Satpam jaringan" yang memutuskan pintu (port) mana yang boleh dilewati. Kalau port diblokir, koneksi gagal walaupun alamatnya benar | Windows Defender Firewall, firewall router |
| **VLAN** | Jaringan yang dipisah-pisah secara logika walau kabelnya sama. Sering kamera dibuat di VLAN sendiri. Server gateway harus diizinkan menjangkau VLAN kamera | VLAN CCTV, VLAN kantor |
| **ping** | Perintah untuk mengecek apakah sebuah alamat IP "menjawab" | `ping 192.168.10.31` |
| **Bandwidth** | Kapasitas jalur jaringan, seperti lebar jalan. Video besar butuh jalan lebar | sub-stream ±0,3–0,5 Mbps per kamera |
| **Latency / delay** | Jeda antara kejadian nyata dan yang tampil di layar | 1–3 detik itu normal |

### B.2 Port yang dipakai

| Port | Milik | Untuk apa | Perlu dibuka dari mana ke mana |
|---|---|---|---|
| **554** | Kamera / NVR | **RTSP**: pintu untuk mengambil video | dari PC gateway → ke kamera |
| **80 / 443** | Kamera / NVR | Halaman web pengaturan kamera (dibuka di browser) | hanya untuk IT saat mengatur kamera |
| **8000** | Kamera Hikvision | Aplikasi Hikvision (iVMS, SADP). **Tidak dipakai CPOS** | – |
| **1984** | go2rtc | API & halaman web go2rtc. CPOS meminta gambar lewat pintu ini | dari server CPOS → ke PC gateway |
| **8554, 8555** | go2rtc | Fitur tambahan go2rtc (RTSP ulang, WebRTC). **Tidak dipakai CPOS**, boleh tetap tertutup | – |
| **5000 / 80** | Server CPOS | Halaman CPOS yang dibuka pengguna | dari PC pengguna → server CPOS |

### B.3 Kamera & perekam

| Istilah | Penjelasan |
|---|---|
| **Kamera IP** | Kamera CCTV yang tersambung ke jaringan (kabel LAN) dan punya alamat IP sendiri. Inilah jenis yang dipakai CPOS |
| **Kamera analog** | Kamera lama dengan kabel koaksial (BNC) ke DVR. Tidak punya IP. Masih bisa dipakai lewat DVR-nya |
| **NVR** (Network Video Recorder) | "Perekam" untuk kamera IP. Menyimpan rekaman di harddisk. Biasanya juga bisa memberikan RTSP untuk setiap kameranya |
| **DVR** (Digital Video Recorder) | Perekam untuk kamera analog. DVR modern juga bisa memberikan RTSP |
| **Channel** | Nomor urut kamera di NVR/DVR. Kamera ke-1 = channel 1, dst. |
| **PoE** (Power over Ethernet) | Kabel LAN yang sekaligus membawa listrik ke kamera. Tidak berpengaruh ke CPOS |
| **Akun view-only** | Akun kamera yang **hanya boleh melihat**, tidak bisa mengubah pengaturan atau menghapus rekaman. Akun inilah yang dipakai di go2rtc, bukan akun `admin` |
| **SADP** (Hikvision) / **ConfigTool** (Dahua) | Aplikasi gratis dari pabrik untuk mencari semua kamera di LAN beserta alamat IP-nya |
| **ONVIF** | Standar bersama antar-merk kamera. Kamera yang mendukung ONVIF bisa "ditanya" alamat RTSP-nya oleh aplikasi lain |
| **ONVIF Device Manager** | Aplikasi gratis (Windows) untuk mencari kamera ONVIF dan melihat alamat RTSP-nya. Berguna untuk merk yang alamat RTSP-nya tidak diketahui |
| **ANPR / LPR** | Fitur kamera untuk membaca plat nomor otomatis. Untuk tahap AI nanti, belum dipakai sekarang |

### B.4 Video

| Istilah | Penjelasan |
|---|---|
| **RTSP** (Real Time Streaming Protocol) | "Bahasa" yang dipakai kamera untuk mengirim video langsung lewat jaringan. Browser tidak bisa membukanya langsung, makanya perlu go2rtc |
| **Alamat RTSP** | Alamat lengkap untuk mengambil video dari kamera. Bentuknya: `rtsp://USER:PASSWORD@IP:554/JALUR`. Contoh: `rtsp://cpos_view:Rahasia123@192.168.10.31:554/Streaming/Channels/101` |
| **Stream utama (main stream)** | Video kualitas penuh dari kamera (mis. 1920×1080). Besar. Di CPOS dipakai untuk **layar penuh** |
| **Sub-stream** | Video kecil dari kamera yang sama (mis. 640×360). Ringan. Di CPOS dipakai untuk **grid** dan untuk dilihat dari HO |
| **Resolusi** | Ukuran gambar dalam titik (piksel). 1920×1080 = "Full HD" / 2 MP |
| **FPS** (frame per second) | Jumlah gambar per detik. Video biasa 15–25 FPS |
| **Bitrate** | Besar data video per detik (kbps / Mbps). Makin besar, makin tajam, makin berat jaringannya |
| **Codec H.264 / H.265** | Cara video "dipadatkan" agar kecil. H.265 lebih hemat, tetapi lebih berat diolah. Keduanya bisa dipakai, go2rtc + ffmpeg yang mengurus |
| **JPEG** | Format satu gambar diam (foto). Grid CPOS mengambil satu JPEG tiap 2 detik |
| **MJPEG** (Motion JPEG) | "Video" yang sebenarnya rangkaian gambar JPEG yang dikirim terus-menerus. Bisa langsung ditampilkan browser. Dipakai CPOS untuk layar penuh |
| **Snapshot** | Satu gambar yang diambil dari video pada saat tertentu |

### B.5 Perangkat lunak

| Istilah | Penjelasan |
|---|---|
| **go2rtc** | Program kecil, gratis, satu file, yang menjadi "penerjemah" video: menerima RTSP dari kamera, lalu memberikan JPEG / MJPEG ke CPOS. Situs: https://github.com/AlexxIT/go2rtc |
| **Gateway video** | Sebutan di CPOS untuk PC/server yang menjalankan go2rtc. Satu gateway bisa melayani banyak kamera (puluhan) dalam satu area |
| **ffmpeg** | Program gratis "pengolah video". go2rtc memakainya untuk mengubah video menjadi gambar JPEG / MJPEG. **Wajib ada** di folder go2rtc. Situs: https://www.gyan.dev/ffmpeg/builds/ (Windows) |
| **go2rtc.yaml** | File pengaturan go2rtc. Isinya daftar kamera: nama stream dan alamat RTSP-nya. **Password kamera hanya ditulis di file ini**, tidak di CPOS |
| **YAML** | Format penulisan file pengaturan. Aturan pentingnya: **spasi di awal baris berarti**, jangan pakai tombol Tab, dan setelah titik dua (`:`) beri satu spasi |
| **Nama stream** | Nama pendek yang Anda buat sendiri di `go2rtc.yaml` untuk setiap alamat RTSP, mis. `ybs_cam01`. Nama inilah yang diisi di CPOS |
| **API** | "Loket" yang dibuka sebuah program agar program lain bisa meminta sesuatu. CPOS meminta gambar ke loket API go2rtc di port 1984 |
| **VLC** | Pemutar video gratis (https://www.videolan.org). Dipakai untuk **mengetes alamat RTSP** sebelum dipasang: kalau VLC bisa memutar, go2rtc pasti bisa |
| **Service (layanan Windows)** | Program yang berjalan sendiri di belakang layar sejak PC menyala, tanpa perlu login. go2rtc sebaiknya dijadikan service |
| **NSSM** | Program gratis kecil untuk menjadikan program biasa (go2rtc.exe) sebagai service Windows. Situs: https://nssm.cc |
| **Task Scheduler** | Bawaan Windows. Alternatif NSSM: menjalankan go2rtc otomatis saat PC menyala |
| **.env** | File pengaturan CPOS (di folder `CPOS`). Berisi pengaturan seperti alamat database. Untuk CCTV hanya pengaturan opsional (bagian E) |
| **Proxy** | Perantara. Server CPOS bertindak sebagai proxy: ia yang mengambil gambar dari gateway lalu meneruskannya ke browser |

### B.6 Istilah di layar CPOS

| Istilah | Arti |
|---|---|
| **Titik** | Lokasi kamera: Pos Masuk, Pos Keluar, Jembatan, Sortasi, Umum. Dipakai untuk menyaring di halaman Monitoring CCTV |
| **Peran** | Fungsi kamera: Depan, Atas, Plat, Wajah, Umum. Disiapkan untuk tahap berikutnya |
| **AI** | Tanpa AI / AI di kamera / AI di server. Untuk tahap berikutnya; sekarang biarkan "Tanpa AI" |
| **Terhubung** | Kamera berhasil mengirim gambar dalam 3 menit terakhir |
| **Cakupan data** | Pengaturan di Hak Akses yang menentukan kamera area/PT mana yang terlihat (bagian C.10) |

---

## C. Langkah pemasangan lengkap

Urutan besar:

1. Kumpulkan data kamera dari IT.
2. Cek jaringan ke kamera.
3. Tes alamat RTSP di VLC.
4. Siapkan PC gateway dan pasang go2rtc + ffmpeg.
5. Tulis `go2rtc.yaml`.
6. Jalankan dan tes go2rtc.
7. Jadikan go2rtc service + buka firewall.
8. Perbarui database CPOS.
9. Daftarkan gateway dan kamera di CPOS.
10. Atur hak akses.
11. Buka dari cabang dan HO.

### C.1 Kumpulkan data dari IT

Isi tabel ini untuk setiap kamera (bisa di Excel):

| Data | Contoh | Catatan |
|---|---|---|
| Lokasi / titik | Gerbang Masuk | |
| Area CPOS | YBS · PKS | |
| Merk & tipe | Hikvision DS-2CD2T47 | tertulis di stiker kamera / NVR |
| Tersambung lewat | langsung / NVR channel 3 | |
| Alamat IP | 192.168.10.31 | kalau lewat NVR: IP NVR-nya |
| Port RTSP | 554 | biasanya 554 |
| Akun view-only | `cpos_view` + password | minta IT membuatkan, **jangan akun admin** |
| Alamat RTSP utama & sub | lihat C.3 | |

Juga tanyakan ke IT:
- PC/server mana yang akan menjadi **gateway** (lihat C.4), dan alamat IP-nya.
- Apakah PC gateway bisa menjangkau kamera (VLAN/firewall).
- Untuk HO: apakah server CPOS HO bisa menjangkau PC gateway cabang lewat VPN di port **1984**.

**Membuat akun view-only di Hikvision** (dilakukan IT):
1. Buka alamat IP kamera/NVR di browser, login sebagai admin.
2. Configuration › System › User Management › **Add**.
3. Isi user `cpos_view`, password, level **User/Operator**, centang hanya **Remote: Live View**.

Merk lain punya menu serupa (Users / Akun).

### C.2 Cek jaringan

Lakukan dari **PC yang akan menjadi gateway**.

1. Buka **Command Prompt** (tekan Windows, ketik `cmd`, Enter).
2. Cek kamera menjawab:
   ```
   ping 192.168.10.31
   ```
   - Muncul `Reply from 192.168.10.31 ...` → jaringan tersambung.
   - Muncul `Request timed out` / `Destination host unreachable` → minta IT memeriksa kabel, IP, atau VLAN.
3. Cek pintu RTSP (port 554) terbuka. Buka **PowerShell**, lalu:
   ```
   Test-NetConnection 192.168.10.31 -Port 554
   ```
   - `TcpTestSucceeded : True` → bagus.
   - `False` → port 554 diblokir firewall/VLAN, atau RTSP di kamera dimatikan. Minta IT membukanya.

### C.3 Tes alamat RTSP di VLC

1. Pasang **VLC** dari https://www.videolan.org.
2. Susun alamat RTSP: `rtsp://USER:PASSWORD@IP:554/JALUR`.

   Jalur (bagian setelah `:554`) menurut merk:

   | Merk | Stream utama | Sub-stream |
   |---|---|---|
   | Hikvision (kamera langsung) | `/Streaming/Channels/101` | `/Streaming/Channels/102` |
   | Hikvision lewat NVR, kamera ke-n | `/Streaming/Channels/n01` (mis. kamera 3: `301`) | `/Streaming/Channels/n02` (`302`) |
   | Dahua (kamera / NVR) | `/cam/realmonitor?channel=1&subtype=0` | `/cam/realmonitor?channel=1&subtype=1` |
   | Uniview | `/unicast/c1/s0/live` | `/unicast/c1/s1/live` |
   | Merk lain | cari dengan **ONVIF Device Manager**, atau lihat manual kamera | |

3. Di VLC: menu **Media › Open Network Stream** (Ctrl+N), tempel alamat, tekan **Play**.
4. Hasil:
   - Video muncul → alamat benar. Catat alamatnya.
   - Diminta login / "unauthorized" → user atau password salah.
   - Lama lalu gagal → IP/port salah atau diblokir (ulangi C.2).
   - Gagal hanya di sub-stream → sub-stream mungkin belum diaktifkan di pengaturan kamera (menu Video/Encoding).

**Penting, password dengan karakter khusus.** Kalau password mengandung `@ : / # ? %`, karakter itu harus diganti kodenya di alamat RTSP:

| Karakter | Ganti dengan |
|---|---|
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `#` | `%23` |
| `?` | `%3F` |
| `%` | `%25` |

Contoh: password `Cctv@2026` ditulis `Cctv%402026`. Lebih mudah lagi: minta IT membuat password view-only tanpa karakter khusus.

### C.4 Siapkan PC gateway, pasang go2rtc + ffmpeg

**Pilih PC gateway:**
- PC/server Windows yang **menyala 24 jam** di jaringan yang sama dengan kamera, dengan **IP statis**.
- Bisa server CPOS cabang itu sendiri, atau mini PC terpisah.
- Spesifikasi kecil cukup (mis. Core i3, RAM 4–8 GB) untuk belasan kamera.
- Satu gateway per area/cabang. HO juga bisa punya gateway sendiri untuk kamera HO.

**Pasang:**
1. Buat folder `C:\go2rtc`.
2. Unduh go2rtc: https://github.com/AlexxIT/go2rtc/releases → bagian **Assets** → `go2rtc_win64.zip`. Ekstrak, taruh `go2rtc.exe` di `C:\go2rtc`.
3. Unduh ffmpeg: https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip`. Ekstrak, buka folder `bin`, salin **`ffmpeg.exe`** ke `C:\go2rtc`.

Isi folder sekarang:
```
C:\go2rtc\
  go2rtc.exe
  ffmpeg.exe
  go2rtc.yaml   ← dibuat di langkah berikut
```

### C.5 Tulis go2rtc.yaml

Buat file `C:\go2rtc\go2rtc.yaml` dengan Notepad (Save as type: **All Files**, supaya tidak jadi `.yaml.txt`).

```yaml
api:
  listen: ":1984"          # port API, cukup terbuka untuk server CPOS
  # username: cpos         # opsional: isi juga CCTV_GATEWAY_USER / CCTV_GATEWAY_PASSWORD di .env CPOS
  # password: rahasia
streams:
  # nama_stream: rtsp://USER:PASSWORD@IP_KAMERA:554/JALUR
  ybs_cam01:     rtsp://cpos_view:PASSWORD@192.168.10.31:554/Streaming/Channels/101
  ybs_cam01_sub: rtsp://cpos_view:PASSWORD@192.168.10.31:554/Streaming/Channels/102
  ybs_cam02:     rtsp://cpos_view:PASSWORD@192.168.10.32:554/Streaming/Channels/101
  ybs_cam02_sub: rtsp://cpos_view:PASSWORD@192.168.10.32:554/Streaming/Channels/102
```

Aturan:
- Setiap kamera **dua baris**: stream utama dan sub-stream (akhiran `_sub`).
- **Nama stream** hanya huruf, angka, titik, `-`, `_`, tanpa spasi. Saran pola: `kodeArea_camNN`.
- Isi alamat RTSP **persis** seperti yang berhasil di VLC.
- Indentasi memakai **2 spasi**, bukan Tab.
- Baris yang diawali `#` adalah komentar (tidak dibaca).
- Simpan file ini baik-baik; jangan dikirim lewat chat karena berisi password kamera.

### C.6 Jalankan dan tes go2rtc

1. Klik dua kali `C:\go2rtc\go2rtc.exe`. Muncul jendela hitam berisi tulisan log. **Biarkan terbuka.**
   - Kalau Windows bertanya izin jaringan (firewall), pilih **Allow**.
2. Di PC gateway, buka browser: `http://localhost:1984`.
   - Muncul halaman go2rtc berisi daftar stream (`ybs_cam01`, dst.).
   - Klik **stream** pada salah satu → video harus tampil.
3. Tes gambar JPEG (yang dipakai grid CPOS): buka
   `http://localhost:1984/api/frame.jpeg?src=ybs_cam01_sub`
   - Muncul satu foto → ffmpeg bekerja.
   - Error / kosong → `ffmpeg.exe` belum ada di folder yang sama.
4. Tes dari **server CPOS**: buka `http://IP_GATEWAY:1984` (mis. `http://192.168.10.5:1984`). Kalau tidak terbuka, lihat C.7 (firewall).

### C.7 Jadikan service + buka firewall

Supaya go2rtc tetap jalan walau PC restart dan tidak ada yang login.

**Dengan NSSM (disarankan):**
1. Unduh NSSM dari https://nssm.cc/download, ekstrak, salin `win64\nssm.exe` ke `C:\go2rtc`.
2. Tutup jendela go2rtc yang terbuka dari langkah C.6.
3. Buka **Command Prompt sebagai Administrator** (klik kanan › Run as administrator), lalu:
   ```
   cd C:\go2rtc
   nssm install go2rtc C:\go2rtc\go2rtc.exe
   nssm set go2rtc AppDirectory C:\go2rtc
   nssm start go2rtc
   ```
4. Cek: tekan Windows, ketik `services.msc` → cari **go2rtc** → Status **Running**, Startup type **Automatic**.
5. Setelah mengubah `go2rtc.yaml`, restart service: `nssm restart go2rtc` (atau lewat services.msc).

**Alternatif Task Scheduler:** Create Task › Trigger **At startup** › Action **Start a program** `C:\go2rtc\go2rtc.exe`, *Start in* `C:\go2rtc` › centang **Run whether user is logged on or not**.

**Buka firewall port 1984** (PowerShell sebagai Administrator):
```
New-NetFirewallRule -DisplayName "go2rtc 1984" -Direction Inbound -Protocol TCP -LocalPort 1984 -Action Allow
```
- Sebaiknya IT membatasi agar hanya **alamat IP server CPOS** yang boleh masuk ke port 1984.
- Port 554 kamera **tidak** perlu dibuka ke HO, hanya dari PC gateway ke kamera.

### C.8 Perbarui database CPOS

- **Database baru:** sudah termasuk di `schema.sql`, lewati langkah ini.
- **Database yang sudah berjalan:** backup dulu, lalu jalankan sekali di SSMS:
  1. `database/perubahan/004_normalisasi_orang.sql` (kalau belum pernah dijalankan);
  2. `database/perubahan/005_cctv.sql`.
- Cek sudah dijalankan: `SELECT * FROM dbo.SchemaLog` → ada baris `database/perubahan/005_cctv.sql`.

### C.9 Daftarkan gateway dan kamera di CPOS

Login sebagai admin › **Admin › Perangkat**.

1. **Gateway Video (CCTV) › Tambah Gateway**
   - **Nama:** mis. `GW-YBS`.
   - **Area:** area tempat gateway berada.
   - **Alamat:** `http://IP_GATEWAY:1984` (mis. `http://192.168.10.5:1984`). Tanpa garis miring di akhir.
   - Tekan **Tes Koneksi** → muncul "Gateway terhubung · N stream: ybs_cam01, ...". Kalau gagal, lihat bagian D.
   - **Simpan**.
2. **Kamera CCTV › Tambah Kamera** (ulangi untuk setiap kamera)
   - **Kode:** huruf besar/angka/`-`/`_`, mis. `CAM-01`.
   - **Nama:** mis. `Gerbang Masuk`.
   - **Area** dan **Gateway:** gateway harus di area yang sama dengan kamera.
   - **Titik:** Pos Masuk / Pos Keluar / Jembatan / Sortasi / Umum. Kalau Jembatan, pilih juga jembatan timbangnya.
   - **Peran**, **Merk:** isi sesuai kamera.
   - **Stream utama:** `ybs_cam01`; **Sub-stream:** `ybs_cam01_sub`. Harus **sama persis** dengan nama di `go2rtc.yaml` (huruf besar/kecil berpengaruh).
   - **AI:** biarkan **Tanpa AI**.
   - **Simpan**, lalu **Tes Koneksi** → gambar kamera tampil di form.

### C.10 Atur siapa yang boleh melihat

**Admin › Hak Akses**, pada menu **Monitoring CCTV** (`MON_CCTV`):

- **Hak Lihat:** centang untuk peran/departemen yang boleh membuka halaman.
- **Cakupan data** menentukan kamera mana yang terlihat:

  | Pilihan | Kamera yang terlihat |
  |---|---|
  | Area sendiri | kamera di area pengguna |
  | PT sendiri | kamera di semua area PT pengguna |
  | Semua PT | semua kamera |
  | PT tertentu | kamera di PT yang dipilih |

- **Hak bawaan:** peran Head Office dan Security.
- Contoh: security PKS YBS → Area sendiri; manager HO → Semua PT.
- Cek hasilnya dengan tombol **Cek Akses** untuk pengguna tertentu.

### C.11 Buka dari cabang dan HO

- Menu **Mills Operation › Monitoring CCTV**.
- Pilih lokasi (chip di atas) dan area, atur grid 1/2/3 kolom.
- Klik gambar kamera untuk **layar penuh**; tekan Esc atau X untuk menutup.
- **Dari HO:** server CPOS yang melayani pengguna HO harus bisa menjangkau gateway cabang lewat VPN/WAN di port 1984. Grid hanya memakai sub-stream, jadi kebutuhan jaringannya kecil (±0,3–0,5 Mbps per kamera yang tampil).

---

## D. Masalah yang sering terjadi

| Gejala | Kemungkinan penyebab | Yang dilakukan |
|---|---|---|
| VLC tidak bisa memutar | IP/port salah, port 554 diblokir, alamat jalur salah | ulangi C.2 dan C.3; cek jalur merk dengan ONVIF Device Manager |
| VLC minta login terus | user/password salah, atau password berisi karakter khusus | cek akun; ganti karakter khusus (C.3) |
| Halaman `localhost:1984` tidak terbuka | go2rtc tidak berjalan | cek jendela go2rtc / service di services.msc |
| Stream ada di go2rtc tetapi `frame.jpeg` error | `ffmpeg.exe` tidak ada di folder go2rtc | salin `ffmpeg.exe` ke `C:\go2rtc`, restart go2rtc |
| go2rtc langsung tertutup saat dibuka | penulisan `go2rtc.yaml` salah (Tab, spasi, titik dua) | periksa indentasi 2 spasi; jalankan dari Command Prompt untuk membaca pesan errornya |
| Tes Koneksi gateway di CPOS gagal | server CPOS tidak bisa menjangkau port 1984 | buka `http://IP_GATEWAY:1984` dari server CPOS; cek firewall (C.7) dan VPN |
| Gateway terhubung, tetapi kamera "Tidak terhubung" | nama stream di CPOS beda dengan `go2rtc.yaml`, atau kamera mati | samakan nama stream persis; cek kamera di halaman go2rtc |
| Kamera tidak muncul untuk pengguna tertentu | hak Lihat atau Cakupan data tidak mencakup area kamera | Admin › Hak Akses › Cek Akses |
| Layar penuh menolak dibuka ("terlalu banyak") | batas `CCTV_MAKS_LIVE` tercapai | tutup layar penuh lain, atau naikkan batas (bagian E) |
| Gambar dari HO lambat / patah-patah | jaringan VPN sempit | pastikan sub-stream diisi; turunkan resolusi/bitrate sub-stream di kamera |
| Gambar terlambat beberapa detik | normal untuk video lewat jaringan | – |

---

## E. Pengaturan, database, tahap berikutnya

### E.1 Pengaturan (.env CPOS, opsional)

| Kunci | Arti | Bawaan |
|---|---|---|
| `CCTV_GATEWAY_USER` / `CCTV_GATEWAY_PASSWORD` | Akun API go2rtc (bila `username`/`password` diaktifkan di bagian `api:` `go2rtc.yaml`) | kosong |
| `CCTV_MAKS_LIVE` | Jumlah video layar penuh yang boleh dibuka bersamaan | 4 |

- Setiap video layar penuh memakai satu thread server.
- Kalau `CCTV_MAKS_LIVE` dinaikkan, naikkan juga jumlah thread server (waitress).
- Setelah mengubah `.env`, restart CPOS.

### E.2 Database

- **Tabel:**
  - `CameraGateway`: gateway per area (nama, area, alamat);
  - `Camera`: kamera (kode, nama, area, gateway, titik, jembatan, peran, merk, nama stream, AI, terakhir terlihat);
  - `CameraEvent`: disiapkan untuk tahap AI (baca plat, lama berhenti), belum dipakai.
- **Tidak ada password kamera di database CPOS.** Database hanya menyimpan nama stream.
- **Log:** setiap kali seseorang membuka layar penuh tercatat di Log (modul CCTV, aksi `LIHAT_LIVE`).

### E.3 Tahap berikutnya (belum dikerjakan)

1. **Foto per tiket:** foto kamera diambil otomatis saat tahap tiket disimpan, dilihat di halaman Monitoring CCTV (tanpa mengubah halaman timbang/sortasi).
2. **AI:**
   - kamera ber-AI (mis. Hikvision ANPR) mengirim kejadian ke CPOS;
   - atau server AI di cabang untuk kamera biasa.

   Keduanya mengisi `CameraEvent`.
