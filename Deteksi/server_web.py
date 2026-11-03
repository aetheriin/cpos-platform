import argparse
import io
import json
import os
import socket
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import cv2
import numpy as np
import pandas as pd

from anpr.database import ambil_laporan_excel, simpan_riwayat
from anpr.foto import simpan_foto
from anpr.kamera import KameraRTSP
from anpr.kendaraan import DetektorKendaraan
from anpr.konfigurasi import FOLDER_PROYEK, muat_semua_kamera
from anpr import gerbang
from anpr.pengaturan_db import baca_pengaturan, info_kamera
from baca_plat import SumberFile, gambar_bacaan

MAKS_RIWAYAT = 50

HALAMAN = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPOS - Deteksi Plat Sawit</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#111;color:#eee}
 header{padding:10px 16px;background:#1b1b1b;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #333}
 .tabs{display:flex;gap:10px}
 .tabs button{background:#2a2a2a;color:#ccc;border:none;padding:8px 16px;cursor:pointer;border-radius:4px;font-weight:600}
 .tabs button.aktif{background:#06B6D4;color:#fff}
 .konten{display:none;padding:16px}
 .konten.aktif{display:block}
 
 /* Grid Kamera */
 .kontrol-grid{margin-bottom:16px;display:flex;gap:10px;align-items:center}
 .kontrol-grid button{background:#222;color:#eee;border:1px solid #444;padding:6px 14px;cursor:pointer;border-radius:4px}
 #area-kamera{display:grid;gap:12px;align-content:start}
 .grid-1{grid-template-columns: 1fr;}
 .grid-4{grid-template-columns: repeat(2, 1fr);}
 .grid-banyak{grid-template-columns: repeat(3, 1fr);}
 figure{margin:0;background:#000;border-radius:6px;overflow:hidden;border:1px solid #333}
 figure img{width:100%;display:block}
 figcaption{font-size:13px;color:#06B6D4;padding:6px 10px;background:#181818;font-weight:600}

 /* Tabel & Form */
 table{width:100%;border-collapse:collapse;font-size:14px;background:#1b1b1b;border-radius:6px;overflow:hidden}
 th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #333}
 th{color:#06B6D4;font-weight:600;background:#222}
 tr:hover{background:#252525}
 input, select{padding:8px 12px;background:#222;color:#fff;border:1px solid #444;border-radius:4px;width:100%;box-sizing:border-box;margin-bottom:12px}
 .btn-form{background:#06B6D4;color:#111;border:none;padding:10px 16px;cursor:pointer;font-weight:bold;border-radius:4px;width:100%}
 .btn-excel{background:#1D6F42;color:#fff;border:none;padding:10px 20px;cursor:pointer;border-radius:4px;text-decoration:none;display:inline-block;font-weight:600}
 .btn-excel:hover{background:#155231}
</style></head><body>

<header>
 <div><h1 style="margin:0;font-size:20px;color:#06B6D4">CPOS Plat Sawit</h1><span id="info" style="font-size:12px;color:#aaa">memuat...</span></div>
 <div class="tabs">
  <button class="aktif" onclick="bukaTab(event, 'tab-live')">Live View</button>
  <button onclick="bukaTab(event, 'tab-laporan')">Laporan Excel</button>
  <button onclick="bukaTab(event, 'tab-kamera')">Kelola Kamera</button>
 </div>
</header>

<div id="tab-live" class="konten aktif">
  <div class="kontrol-grid">
    <span style="font-size:13px;color:#aaa">Layout Kamera:</span>
    <button onclick="ubahGrid('grid-1')">1 Kamera</button>
    <button onclick="ubahGrid('grid-4')">4 Grid (2x2)</button>
    <button onclick="ubahGrid('grid-banyak')">6 Grid (3 Kolom)</button>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap">
    <section id="area-kamera" class="grid-4" style="flex:2 1 600px"></section>
    <section id="riwayat" style="flex:1 1 340px">
      <h3 style="margin-top:0;color:#06B6D4">Deteksi Terakhir</h3>
      <p id="terakhir" style="font-size:28px;font-weight:bold;color:#3c3;margin:0 0 12px">-</p>
      <table><thead><tr><th>Waktu</th><th>Kamera</th><th>Jenis</th><th>Plat</th><th>Pemilik</th></tr></thead>
      <tbody id="baris"></tbody></table>
    </section>
  </div>
</div>

<div id="tab-laporan" class="konten">
  <h2>Unduh Laporan Deteksi (SQL Server)</h2>
  <p style="color:#aaa">Pilih periode laporan untuk mengunduh data deteksi kendaraan lengkap dalam format Microsoft Excel:</p>
  <div style="display:flex;gap:12px;margin-top:20px">
    <a href="/api/excel?rentang=hari_ini" class="btn-excel">📊 Download Laporan Hari Ini</a>
    <a href="/api/excel?rentang=minggu_ini" class="btn-excel">📅 Download Laporan 7 Hari Terakhir</a>
    <a href="/api/excel?rentang=bulan_ini" class="btn-excel">📆 Download Laporan Bulan Ini</a>
  </div>
</div>

<div id="tab-kamera" class="konten">
  <h2>Tambah Kamera RTSP Baru</h2>
  <p style="color:#aaa">Tambahkan IP Camera / CCTV Hikvision tanpa perlu mengubah file .env:</p>
  <div style="max-width:480px;background:#1b1b1b;padding:20px;border-radius:6px;border:1px solid #333">
    <label style="display:block;margin-bottom:4px;font-size:13px;color:#ccc">Nama Kamera / Pos</label>
    <input type="text" id="kam-nama" placeholder="Contoh: POS_TIMBANGAN">
    
    <label style="display:block;margin-bottom:4px;font-size:13px;color:#ccc">RTSP Stream URL</label>
    <input type="text" id="kam-rtsp" placeholder="rtsp://admin:pass@192.168.1.64:554/Streaming/Channels/101">
    
    <button class="btn-form" onclick="tambahKamera()">💾 Simpan & Tambahkan Kamera</button>
  </div>
</div>

<script>
function bukaTab(evt, namaTab) {
  document.querySelectorAll('.konten').forEach(el => el.classList.remove('aktif'));
  document.querySelectorAll('.tabs button').forEach(el => el.classList.remove('aktif'));
  document.getElementById(namaTab).classList.add('aktif');
  evt.currentTarget.classList.add('aktif');
}

function ubahGrid(kelas) {
  const area = document.getElementById('area-kamera');
  area.className = kelas;
}

async function tambahKamera() {
  const nama = document.getElementById('kam-nama').value.trim();
  const rtsp = document.getElementById('kam-rtsp').value.trim();
  if(!nama || !rtsp){ alert('Mohon isi nama dan RTSP URL!'); return; }
  await fetch('/api/kamera', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({nama, rtsp})
  });
  alert('Kamera berhasil ditambahkan!');
  location.reload();
}

const keterangan = {};
function buatPanel(daftar){
  const area = document.getElementById('area-kamera');
  area.innerHTML = '';
  for(const k of daftar){
    const f = document.createElement('figure');
    const img = document.createElement('img');
    img.src = '/video/' + encodeURIComponent(k.nama); 
    img.alt = k.nama;
    const cap = document.createElement('figcaption');
    f.appendChild(img); f.appendChild(cap); area.appendChild(f);
    keterangan[k.nama] = cap;
  }
}

async function muat(){
  try{
    const r = await fetch('/api/status'); const d = await r.json();
    if(Object.keys(keterangan).length === 0 && d.kamera.length > 0) buatPanel(d.kamera);
    for(const k of d.kamera){
      if(keterangan[k.nama]) {
        keterangan[k.nama].textContent = k.nama + ' | ' + k.status + ' | ' + k.resolusi + ' | ' + k.fps.toFixed(1) + ' fps';
      }
    }
    document.getElementById('info').textContent = 'AI ' + d.ai_ms.toFixed(0) + ' ms/frame | Kamera Active: ' + d.kamera.length;
    document.getElementById('terakhir').textContent =
      d.riwayat.length ? d.riwayat[0].plat + ' (' + d.riwayat[0].jenis + ')' : '-';
    
    const tb = document.getElementById('baris'); tb.textContent = '';
    for(const x of d.riwayat){
      const tr = document.createElement('tr');
      for(const v of [x.waktu, x.kamera, x.jenis, x.plat, x.pemilik]){
        const td = document.createElement('td'); td.textContent = v; tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
  }catch(e){ document.getElementById('info').textContent = 'Server tidak terjangkau'; }
}
muat(); setInterval(muat, 2000);
</script></body></html>"""


def jpeg_pesan(teks):
    img = np.zeros((360, 640, 3), np.uint8)
    cv2.putText(img, teks, (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return cv2.imencode(".jpg", img)[1].tobytes()


class Keadaan:
    """Data bersama antara thread pembaca plat dan thread web server."""

    def __init__(self, daftar_nama):
        self.kondisi = threading.Condition()
        self.kamera = {n: {"jpeg": jpeg_pesan(f"{n}: menunggu kamera..."), "nomor": 0,
                           "status": "memulai", "resolusi": "-", "fps": 0.0} for n in daftar_nama}
        self.ai_ms = 0.0
        self.riwayat = []   # terbaru di depan

    def pasang_gambar(self, nama, jpeg):
        with self.kondisi:
            if nama in self.kamera:
                k = self.kamera[nama]
                k["jpeg"] = jpeg
                k["nomor"] += 1
                self.kondisi.notify_all()

    def pasang_info(self, nama, status, resolusi, fps):
        with self.kondisi:
            if nama in self.kamera:
                self.kamera[nama].update(status=status, resolusi=resolusi, fps=fps)

    def pasang_ai(self, ms):
        with self.kondisi:
            self.ai_ms = ms

    def tambah_plat(self, nama, hasil, jenis, pemilik):
        baris = {"waktu": f"{datetime.fromtimestamp(hasil.waktu):%d/%m/%Y %H:%M:%S}", 
                 "kamera": nama, "jenis": jenis, "pemilik": pemilik,
                 "plat": hasil.plat, "conf": f"{hasil.conf_ocr:.0%}", "frame": hasil.jumlah_frame}
        with self.kondisi:
            self.riwayat.insert(0, baris)
            del self.riwayat[MAKS_RIWAYAT:]

    def ringkasan(self):
        with self.kondisi:
            return {"ai_ms": self.ai_ms,
                    "kamera": [{"nama": n, "status": v["status"], "resolusi": v["resolusi"], "fps": v["fps"]}
                               for n, v in self.kamera.items()],
                    "riwayat": list(self.riwayat)}


class Jalur:
    """Satu kamera beserta penstabil dan penyimpan miliknya."""

    def __init__(self, konf, sumber, penstabil, penyimpan):
        self.konf, self.sumber, self.penstabil, self.penyimpan = konf, sumber, penstabil, penyimpan
        self.nomor_terakhir, self.status_gambar, self.selesai = 0, None, False


def proses(j, pembaca, keadaan, detektor_kendaraan):
    """Baca satu frame terbaru dari satu kamera. Return True bila ada frame baru yang diproses."""
    sumber, konf, nama = j.sumber, j.konf, j.konf.nama_kamera
    frame, waktu, nomor = sumber.ambil()
    res = f"{sumber.resolusi[0]}x{sumber.resolusi[1]}" if sumber.resolusi else "-"
    if frame is None or nomor == j.nomor_terakhir:
        if isinstance(sumber, SumberFile) and sumber.habis:
            keadaan.pasang_info(nama, "rekaman selesai", res, 0.0)
            j.selesai = True
            return False
        keadaan.pasang_info(nama, sumber.status, res, sumber.fps)
        if frame is None and sumber.status != j.status_gambar:
            j.status_gambar = sumber.status
            keadaan.pasang_gambar(nama, jpeg_pesan(f"{nama}: {sumber.status}"))
        return False
    j.nomor_terakhir, j.status_gambar = nomor, None

    bacaan = pembaca.baca(frame)
    ai_ms = pembaca.waktu_proses_ms
    if bacaan and konf.simpan_semua_bacaan:
        j.penyimpan.simpan_bacaan(waktu, bacaan, ai_ms)
        
    for hasil in j.penstabil.tambah(waktu, bacaan, frame):
        b = hasil.bacaan_terbaik
        
        # 1. Deteksi Jenis Kendaraan via YOLOX ONNX
        jenis = detektor_kendaraan.deteksi(hasil.frame_terbaik)
        
        # 2. Simpan foto bukti (lokal di folder backend; nanti bisa dipindah ke cloud)
        gambar = gambar_bacaan(hasil.frame_terbaik, [b])
        foto_rel, plat_rel = simpan_foto(hasil.waktu, nama, hasil.plat, gambar, b.crop)

        # 3. Simpan riwayat ke SQL Server; pemilik dicari lewat DetailVehicle -> UserC
        pemilik_str = simpan_riwayat(hasil.waktu, nama, jenis, hasil.plat, hasil.conf_ocr, foto_rel, plat_rel)

        j.penyimpan.simpan_plat(hasil, gambar)
        keadaan.tambah_plat(nama, hasil, jenis, pemilik_str)
        print(f"[{datetime.fromtimestamp(hasil.waktu):%H:%M:%S}] {nama} | {jenis} | Plat: {hasil.plat} | Pemilik: {pemilik_str}")

    tampil = gambar_bacaan(frame, bacaan, j.penstabil)
    if tampil.shape[1] > konf.lebar_tampilan:
        tampil = cv2.resize(tampil, (konf.lebar_tampilan, int(tampil.shape[0] * konf.lebar_tampilan / tampil.shape[1])),
                            interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", tampil, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if ok:
        keadaan.pasang_gambar(nama, buf.tobytes())
    keadaan.pasang_info(nama, sumber.status, res, sumber.fps)
    keadaan.pasang_ai(ai_ms)
    return True


def pekerja(args, daftar_konf, keadaan, berhenti):
    """Satu thread, satu model AI, kamera dibaca bergantian."""
    from anpr.pembaca import PembacaPlat
    from anpr.penstabil import PenstabilPlat
    from anpr.penyimpan import Penyimpan

    try:
        detektor_kendaraan = DetektorKendaraan(os.path.join(FOLDER_PROYEK, "yolox_s.onnx"))
        daftar_jalur = []
        for konf in daftar_konf:
            if args.video:
                sumber = SumberFile(args.video).mulai()
            else:
                sumber = KameraRTSP(konf.daftar_url_rtsp(), konf.nama_kamera).mulai()
            foto = isinstance(sumber, SumberFile) and sumber.foto
            penstabil = PenstabilPlat(1 if foto else konf.min_frame_sama, konf.jendela_detik, konf.jeda_ulang_detik)
            daftar_jalur.append(Jalur(konf, sumber, penstabil, Penyimpan(konf.folder_hasil, konf.nama_kamera)))
        
        pembaca = PembacaPlat(daftar_konf[0])
        
        print("Pembaca plat & CPOS System berjalan.")

        def terapkan_pengaturan():
        p = baca_pengaturan()
            if p:
                pembaca.konf.min_conf_ocr = p["conf"]
                for j in daftar_jalur:
                    j.penstabil.jeda_ulang_detik = p["jeda_detik"]
                gerbang.STATE["jendela"] = p["jendela_detik"]
            info = info_kamera()                       # gerbang & hadap kamera: perubahan di Admin berlaku tanpa restart
            if info is not None:
                gerbang.STATE["info"] = info

        terapkan_pengaturan()
        terakhir_baca = time.time()
        while not berhenti.is_set() and not all(j.selesai for j in daftar_jalur):
            if time.time() - terakhir_baca > 30:
                terapkan_pengaturan()
                terakhir_baca = time.time()
            ada = False
            for j in daftar_jalur:
                if not j.selesai and proses(j, pembaca, keadaan, detektor_kendaraan):
                    ada = True
            if not ada:
                time.sleep(0.01)
    except Exception as e:
        traceback.print_exc()
        for konf in daftar_konf:
            keadaan.pasang_info(konf.nama_kamera, f"ERROR: {e}", "-", 0.0)
            keadaan.pasang_gambar(konf.nama_kamera, jpeg_pesan("Terjadi error, lihat jendela konsol"))


class Penangan(BaseHTTPRequestHandler):
    keadaan = None

    def log_message(self, *args):
        pass

    def _kirim(self, tipe, isi, kode=200):
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(isi)

    def do_GET(self):
        jalur = self.path.split("?")[0]
        k = self.keadaan
        if jalur == "/":
            self._kirim("text/html; charset=utf-8", HALAMAN.encode("utf-8"))
        elif jalur == "/api/status":
            self._kirim("application/json; charset=utf-8", json.dumps(k.ringkasan()).encode("utf-8"))
        elif jalur == "/api/excel":
            rentang = "hari_ini"
            if "rentang=minggu_ini" in self.path: rentang = "minggu_ini"
            if "rentang=bulan_ini" in self.path: rentang = "bulan_ini"
            
            df = ambil_laporan_excel(rentang)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Laporan_CPOS')
            
            excel_data = output.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename=Laporan_CPOS_{rentang}.xlsx")
            self.send_header("Content-Length", str(len(excel_data)))
            self.end_headers()
            self.wfile.write(excel_data)
        elif jalur.startswith("/video/") and unquote(jalur[7:]) in k.kamera:
            self._video(k, unquote(jalur[7:]))
        elif jalur.startswith("/snapshot/") and unquote(jalur[10:]) in k.kamera:
            with k.kondisi:
                jpeg = k.kamera[unquote(jalur[10:])]["jpeg"]
            self._kirim("image/jpeg", jpeg)
        else:
            self._kirim("text/plain; charset=utf-8", b"Tidak ditemukan", 404)

    def do_POST(self):
        if self.path == "/api/kamera":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            file_kamera = FOLDER_PROYEK / "daftar_kamera.json"
            kamera_lama = []
            if os.path.exists(file_kamera):
                with open(file_kamera, 'r', encoding='utf-8') as f:
                    try:
                        kamera_lama = json.load(f)
                    except json.JSONDecodeError:
                        kamera_lama = []
            
            kamera_lama.append({"nama_kamera": data["nama"].upper(), "rtsp_url": data["rtsp"]})
            with open(file_kamera, 'w', encoding='utf-8') as f:
                json.dump(kamera_lama, f, indent=2)
                
            self._kirim("application/json", b'{"status": "ok"}')

    def _video(self, k, nama):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        terakhir = -1
        try:
            while True:
                with k.kondisi:
                    k.kondisi.wait_for(lambda: k.kamera[nama]["nomor"] != terakhir, timeout=5)
                    jpeg, terakhir = k.kamera[nama]["jpeg"], k.kamera[nama]["nomor"]
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpeg))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except OSError:
            pass


def alamat_lan():
    ada = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ada.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ada.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ip for ip in ada if not ip.startswith(("127.", "169.254.")))


def main():
    p = argparse.ArgumentParser(description="Web lokal deteksi plat CPOS")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--video", help="uji dari file video / foto alih-alih kamera (hanya kamera pertama)")
    args = p.parse_args()

    daftar_konf = muat_semua_kamera()
    if args.video:
        daftar_konf = daftar_konf[:1]
    elif not daftar_konf[0].kamera_ip and not daftar_konf[0].rtsp_url:
        sys.exit("KAMERA_IP / RTSP_URL belum diisi di file .env / daftar_kamera.json")
    
    daftar_nama = [k.nama_kamera for k in daftar_konf]
    if len(set(daftar_nama)) != len(daftar_nama):
        sys.exit("Nama kamera tidak boleh ada yang sama")

    keadaan = Keadaan(daftar_nama)
    Penangan.keadaan = keadaan
    berhenti = threading.Event()
    threading.Thread(target=pekerja, args=(args, daftar_konf, keadaan, berhenti), daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Penangan)
    print(f"\n=======================================================")
    print(f"CPOS System Ready. Kamera terhubung: {', '.join(daftar_nama)}")
    print(f"Buka Web UI di browser:")
    for ip in alamat_lan():
        print(f"    http://{ip}:{args.port}")
    print(f"    http://localhost:{args.port}  (di komputer ini)")
    print(f"=======================================================\nTekan Ctrl+C untuk berhenti.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        berhenti.set()
        server.server_close()


if __name__ == "__main__":
    main()
