# Panduan Monitoring CCTV (Tahap 1: live per area)

## Cara kerja

```
Kamera / NVR (RTSP, LAN cabang) → Gateway video go2rtc (server cabang / HO) → Server CPOS → Browser
```

- **Browser tidak terhubung langsung ke kamera.** Gambar diambil server CPOS dari gateway, lalu diteruskan ke browser.
  - Hak akses dan cakupan area tetap berlaku.
  - Alamat dan password kamera tidak keluar dari jaringan cabang.
- **Grid:** gambar diperbarui tiap 2 detik dari sub-stream (ringan, cocok dilihat dari HO).
- **Layar penuh:** video kualitas penuh (MJPEG). Siapa yang membuka kamera tercatat di Log.
- **Rekaman tetap di NVR.** CPOS hanya untuk memantau langsung.
- **Merk kamera bebas** (Hikvision, Dahua, dan lainnya), asalkan kamera bisa mengirim RTSP.

## Siapa boleh melihat

- **Menu:** Mills Operation › **Monitoring CCTV** (kode `MON_CCTV`).
- **Hak Lihat:** diatur di Admin › Hak Akses.
- **Kamera yang terlihat:** sesuai kolom **Cakupan data** aturan itu:
  - Area sendiri: kamera di area pengguna;
  - PT sendiri / Semua PT / PT tertentu: kamera di PT tersebut.
- **Hak bawaan:** peran Head Office dan Security.

## 1. Pasang gateway video (go2rtc), sekali per cabang / HO

1. Unduh `go2rtc` (satu file, gratis) dari https://github.com/AlexxIT/go2rtc/releases. Untuk Windows: `go2rtc_win64.zip`.
2. Unduh juga **ffmpeg** (dipakai go2rtc untuk membuat gambar JPEG / MJPEG). Taruh `ffmpeg.exe` di folder yang sama, atau pastikan ada di PATH.
3. Buat file `go2rtc.yaml` di folder yang sama. Contoh untuk Hikvision:

```yaml
api:
  listen: ":1984"          # port API, cukup terbuka untuk server CPOS
  # username: cpos         # opsional: isi juga CCTV_GATEWAY_USER / CCTV_GATEWAY_PASSWORD di .env CPOS
  # password: rahasia
streams:
  # nama_stream: rtsp://USER:PASSWORD@IP_KAMERA:554/Streaming/Channels/101
  ybs_cam01:     rtsp://cpos_view:PASSWORD@192.168.10.31:554/Streaming/Channels/101
  ybs_cam01_sub: rtsp://cpos_view:PASSWORD@192.168.10.31:554/Streaming/Channels/102
  ybs_cam02:     rtsp://cpos_view:PASSWORD@192.168.10.32:554/Streaming/Channels/101
  ybs_cam02_sub: rtsp://cpos_view:PASSWORD@192.168.10.32:554/Streaming/Channels/102
```

4. Jalankan `go2rtc.exe`. Supaya otomatis menyala saat PC hidup, pasang sebagai service (mis. dengan NSSM) atau lewat Task Scheduler.
5. Uji dari server CPOS: buka `http://IP_GATEWAY:1984`. Halaman go2rtc menampilkan daftar stream dan bisa memutar videonya.

Alamat RTSP umum:

| Merk | Stream utama | Sub-stream |
|---|---|---|
| Hikvision (kamera langsung) | `/Streaming/Channels/101` | `/Streaming/Channels/102` |
| Hikvision lewat NVR | kamera ke-n: `/Streaming/Channels/n01` | `/Streaming/Channels/n02` |
| Dahua | `/cam/realmonitor?channel=1&subtype=0` | `...&subtype=1` |
| Merk lain | lihat manual / ONVIF Device Manager | |

- **Tes sebelum dipasang:** buka alamat RTSP lengkap di **VLC** (Media › Open Network Stream). Kalau video muncul di VLC, go2rtc pasti bisa memakainya.
- **Akun kamera:** pakai akun **khusus lihat (view-only)**, bukan admin.
- **Port 554:** pastikan server gateway bisa menjangkau port 554 kamera (tidak diblokir firewall / VLAN).

## 2. Daftarkan di CPOS (Admin › Perangkat)

1. **Gateway Video (CCTV) › Tambah Gateway**
   - Isi nama, area, dan alamat (mis. `http://192.168.10.5:1984`).
   - Tekan **Tes Koneksi**: nama-nama stream akan muncul.
2. **Kamera CCTV › Tambah Kamera**
   - Isi kode, nama, area, gateway, titik (Pos Masuk / Pos Keluar / Jembatan / Sortasi / Umum), dan jembatan timbang bila titiknya jembatan.
   - Isi peran, merk, **nama stream utama** dan **nama sub-stream**, persis sama dengan nama di `go2rtc.yaml`.
   - Simpan, lalu **Tes Koneksi** untuk melihat gambarnya.

## 3. Dilihat dari HO

- Server CPOS (yang melayani pengguna HO) harus bisa menjangkau gateway cabang lewat jaringan antar kantor (VPN/WAN), ke port 1984 saja.
- Grid hanya memakai sub-stream, jadi kebutuhan jaringannya kecil.

## Pengaturan (.env CPOS, opsional)

| Kunci | Arti | Bawaan |
|---|---|---|
| `CCTV_GATEWAY_USER` / `CCTV_GATEWAY_PASSWORD` | Akun API go2rtc (bila diaktifkan di `go2rtc.yaml`) | kosong |
| `CCTV_MAKS_LIVE` | Jumlah video layar penuh yang boleh dibuka bersamaan | 4 |

- Setiap video layar penuh memakai satu thread server.
- Kalau `CCTV_MAKS_LIVE` dinaikkan, naikkan juga jumlah thread server (waitress).

## Database

- **Database baru:** sudah termasuk di `schema.sql`.
- **Database yang sudah berjalan:** jalankan `database/perubahan/005_cctv.sql` sekali di SSMS.
- **Tabel:**
  - `CameraGateway`: gateway per area;
  - `Camera`: kamera;
  - `CameraEvent`: disiapkan untuk tahap AI (baca plat, lama berhenti), belum dipakai.

## Tahap berikutnya

1. **Snapshot otomatis per tahap tiket** (Pos Security, Timbang 1/2, Keluar), tampil di detail tiket.
2. **AI:**
   - kamera ber-AI (mis. Hikvision ANPR) mengirim kejadian ke CPOS;
   - atau server AI di cabang untuk kamera biasa.

   Keduanya mengisi `CameraEvent`.
