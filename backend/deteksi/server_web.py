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
from anpr.konfigurasi import FOLDER_PROYEK, muat_konfigurasi, muat_semua_kamera
from anpr import gerbang
from anpr.pengaturan_db import baca_pengaturan, info_kamera
from baca_plat import SumberFile, gambar_bacaan

MAKS_RIWAYAT = 50
# Huruf Plus Jakarta Sans disalin dari CPOS (static/vendor/fonts) supaya tampilan sama
FOLDER_FONT = FOLDER_PROYEK / "font"
FONT = {f"plus-jakarta-sans-latin-{w}-normal.woff2" for w in (400, 500, 600, 700)}

HALAMAN = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deteksi Plat</title>
<script>
// Tema sama dengan CPOS: localStorage 'tema' = 'terang' / 'gelap', bawaan terang
try { if (localStorage.getItem('tema') === 'gelap') document.documentElement.classList.add('dark'); } catch (e) {}
</script>
<style>
@font-face{font-family:'Plus Jakarta Sans';font-weight:400;font-display:swap;src:url('/font/plus-jakarta-sans-latin-400-normal.woff2') format('woff2')}
@font-face{font-family:'Plus Jakarta Sans';font-weight:500;font-display:swap;src:url('/font/plus-jakarta-sans-latin-500-normal.woff2') format('woff2')}
@font-face{font-family:'Plus Jakarta Sans';font-weight:600;font-display:swap;src:url('/font/plus-jakarta-sans-latin-600-normal.woff2') format('woff2')}
@font-face{font-family:'Plus Jakarta Sans';font-weight:700;font-display:swap;src:url('/font/plus-jakarta-sans-latin-700-normal.woff2') format('woff2')}
/* Warna dari CPOS (tailwind-source.css): utama-600/700, skala slate, latar kartu gelap #121a2b */
:root{--latar:#f8fafc;--kartu:#fff;--garis:#e2e8f0;--garis-lembut:#f1f5f9;--teks:#1e293b;--teks-kuat:#0f172a;--teks-redup:#475569;
  --utama:#127cbf;--utama-tua:#0d66a0;--utama-lembut:#ecf6fd;--kepala:#f8fafc;--hijau:#059669;--hijau-teks:#047857;--merah:#b91c1c;color-scheme:light}
html.dark{--latar:#0b1120;--kartu:#121a2b;--garis:#253046;--garis-lembut:#1a2335;--teks:#e2e8f0;--teks-kuat:#f1f5f9;--teks-redup:#94a3b8;
  --utama:#127cbf;--utama-tua:#0d66a0;--utama-lembut:#0f2440;--kepala:#1a2335;--hijau:#10b981;--hijau-teks:#6ee7b7;--merah:#fca5a5;color-scheme:dark}
*{box-sizing:border-box}
body{font-family:'Plus Jakarta Sans',system-ui,sans-serif;margin:0;background:var(--latar);color:var(--teks);font-size:14px}
header{background:var(--kartu);border-bottom:1px solid var(--garis);padding:12px 20px;display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:center}
h1{margin:0;font-size:18px;font-weight:700;color:var(--teks-kuat)}
h2{margin:0 0 4px;font-size:15px;font-weight:700;color:var(--teks-kuat)}
.redup{color:var(--teks-redup);font-size:12px}
main{padding:20px;max-width:1600px;margin:0 auto}
.seg{display:inline-flex;gap:4px;padding:4px;background:var(--garis-lembut);border:1px solid var(--garis);border-radius:8px}
.chip{min-height:36px;padding:6px 14px;border:0;border-radius:6px;background:transparent;color:var(--teks-redup);font:inherit;font-size:13px;font-weight:600;cursor:pointer}
.chip:hover{color:var(--teks-kuat)}
.chip[aria-selected="true"],.chip.aktif{background:var(--kartu);color:var(--teks-kuat);box-shadow:0 1px 2px rgb(15 23 42/.08)}
.btn-primary,.btn-secondary{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:40px;padding:8px 16px;border-radius:8px;font:inherit;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}
.btn-primary{background:var(--utama);color:#fff;border:1px solid var(--utama)}
.btn-primary:hover{background:var(--utama-tua)}
.btn-primary:disabled{opacity:.6;cursor:not-allowed}
.btn-secondary{background:var(--kartu);color:var(--teks);border:1px solid var(--garis)}
.btn-secondary:hover{background:var(--garis-lembut)}
.btn-ikon{min-height:40px;min-width:40px;padding:0;border-radius:8px;border:1px solid var(--garis);background:var(--kartu);color:var(--teks-redup);cursor:pointer;font-size:16px}
:focus-visible{outline:2px solid var(--utama);outline-offset:2px}
.section-box{background:var(--kartu);border:1px solid var(--garis);border-radius:12px;box-shadow:0 1px 2px rgb(15 23 42/.05);overflow:hidden}
.section-head{padding:12px 16px;border-bottom:1px solid var(--garis-lembut)}
.konten[hidden]{display:none}
.kontrol-grid{margin-bottom:16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.tata{display:flex;gap:16px;flex-wrap:wrap}
#area-kamera{display:grid;gap:12px;align-content:start;flex:2 1 600px;min-width:0}
.grid-1{grid-template-columns:1fr}
.grid-4{grid-template-columns:repeat(2,minmax(0,1fr))}
.grid-banyak{grid-template-columns:repeat(3,minmax(0,1fr))}
@media (max-width:700px){.grid-4,.grid-banyak{grid-template-columns:1fr}}
figure{margin:0;background:#000;border-radius:12px;overflow:hidden;border:1px solid var(--garis)}
figure img{width:100%;aspect-ratio:16/9;object-fit:contain;display:block}
figcaption{font-size:12px;color:var(--teks);padding:8px 12px;background:var(--kartu);font-weight:600}
#riwayat{flex:1 1 340px;min-width:0}
#terakhir{font-size:26px;font-weight:700;color:var(--hijau-teks);margin:4px 0 0;font-family:'Plus Jakarta Sans',system-ui,sans-serif}
.tabel-wadah{overflow:auto;max-height:34rem}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--garis-lembut);white-space:nowrap}
th{position:sticky;top:0;background:var(--kepala);color:var(--teks-redup);font-weight:600;border-bottom:1px solid var(--garis)}
tbody tr:hover{background:var(--garis-lembut)}
.kosong{text-align:center;color:var(--teks-redup);padding:32px 14px}
.unduh{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.ikon-excel{color:var(--hijau)}
.form{max-width:520px;padding:20px}
label{display:block;margin:0 0 6px;font-size:14px;font-weight:600;color:var(--teks)}
input{width:100%;min-height:40px;padding:8px 12px;background:var(--kartu);color:var(--teks);border:1px solid var(--garis);border-radius:8px;font:inherit;margin-bottom:14px}
input::placeholder{color:var(--teks-redup)}
input:focus{outline:none;border-color:var(--utama);box-shadow:0 0 0 3px rgb(18 124 191/.2)}
#pesan{margin:12px 0 0;font-size:13px;min-height:1.2em}
#pesan.galat{color:var(--merah)}
#pesan.berhasil{color:var(--hijau-teks)}
</style></head><body>

<header>
 <div><h1>Deteksi Plat</h1><span id="info" class="redup">Memuat…</span></div>
 <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
  <div class="seg" role="tablist" aria-label="Halaman">
   <button class="chip" role="tab" id="t-live" aria-selected="true" aria-controls="tab-live" data-tab="tab-live">Kamera langsung</button>
   <button class="chip" role="tab" id="t-laporan" aria-selected="false" aria-controls="tab-laporan" tabindex="-1" data-tab="tab-laporan">Laporan</button>
   <button class="chip" role="tab" id="t-kamera" aria-selected="false" aria-controls="tab-kamera" tabindex="-1" data-tab="tab-kamera">Kelola kamera</button>
  </div>
  <button type="button" class="btn-ikon" id="tombolTema" aria-label="Ganti ke mode gelap" title="Ganti tema">☾</button>
 </div>
</header>

<main>
<section id="tab-live" class="konten" role="tabpanel" aria-labelledby="t-live">
  <div class="kontrol-grid">
    <span class="redup">Tata letak kamera</span>
    <div class="seg" role="group" aria-label="Tata letak kamera">
      <button type="button" class="chip" data-grid="grid-1" aria-pressed="false">1 kamera</button>
      <button type="button" class="chip aktif" data-grid="grid-4" aria-pressed="true">2 x 2</button>
      <button type="button" class="chip" data-grid="grid-banyak" aria-pressed="false">3 kolom</button>
    </div>
  </div>
  <div class="tata">
    <div id="area-kamera" class="grid-4"><p class="redup">Memuat kamera…</p></div>
    <div id="riwayat" class="section-box">
      <div class="section-head">
        <h2>Deteksi terakhir</h2>
        <p id="terakhir">Belum ada data</p>
      </div>
      <div class="tabel-wadah">
        <table><thead><tr><th>Waktu</th><th>Kamera</th><th>Jenis</th><th>Plat</th><th>Pemilik</th></tr></thead>
        <tbody id="baris"><tr><td colspan="5" class="kosong">Belum ada data</td></tr></tbody></table>
      </div>
    </div>
  </div>
</section>

<section id="tab-laporan" class="konten section-box" role="tabpanel" aria-labelledby="t-laporan" hidden>
  <div class="form" style="max-width:none">
    <h2>Unduh laporan deteksi</h2>
    <p class="redup">Semua kendaraan yang terbaca kamera pada periode yang dipilih.</p>
    <div class="unduh">
      <a href="/api/excel?rentang=hari_ini" class="btn-secondary"><svg class="ikon-excel" viewBox="0 0 24 24" height="1.1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9.5 12.5 5 5m0-5-5 5"/></svg>Excel hari ini</a>
      <a href="/api/excel?rentang=minggu_ini" class="btn-secondary"><svg class="ikon-excel" viewBox="0 0 24 24" height="1.1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9.5 12.5 5 5m0-5-5 5"/></svg>Excel 7 hari</a>
      <a href="/api/excel?rentang=bulan_ini" class="btn-secondary"><svg class="ikon-excel" viewBox="0 0 24 24" height="1.1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9.5 12.5 5 5m0-5-5 5"/></svg>Excel bulan ini</a>
    </div>
  </div>
</section>

<section id="tab-kamera" class="konten" role="tabpanel" aria-labelledby="t-kamera" hidden>
  <form id="formKamera" class="section-box form" autocomplete="off">
    <h2>Tambah kamera</h2>
    <p class="redup" style="margin:0 0 16px">Kamera CCTV dengan alamat RTSP. Kamera langsung tampil setelah Deteksi Plat dijalankan ulang.</p>
    <label for="kam-nama">Nama kamera atau pos</label>
    <input type="text" id="kam-nama" placeholder="Contoh: POS_TIMBANGAN" required>
    <label for="kam-rtsp">Alamat RTSP</label>
    <input type="text" id="kam-rtsp" placeholder="rtsp://user:sandi@alamat-ip:554/Streaming/Channels/101" required>
    <button type="submit" class="btn-primary" id="simpanKamera">Simpan kamera</button>
    <p id="pesan" role="status"></p>
  </form>
</section>
</main>

<script>
const el = id => document.getElementById(id);

// Tab
const tab = [...document.querySelectorAll('[role="tab"]')];
function bukaTab(t, fokus) {
  tab.forEach(x => {
    const ya = x === t;
    x.setAttribute('aria-selected', String(ya));
    x.tabIndex = ya ? 0 : -1;
    el(x.dataset.tab).hidden = !ya;
  });
  if (fokus) t.focus();
}
tab.forEach(t => {
  t.addEventListener('click', () => bukaTab(t, false));
  t.addEventListener('keydown', e => {
    const i = tab.indexOf(t);
    const ke = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tab.length - 1 }[e.key];
    if (ke === undefined) return;
    e.preventDefault();
    bukaTab(tab[(ke + tab.length) % tab.length], true);
  });
});

// Tema
function pasangTombolTema() {
  const gelap = document.documentElement.classList.contains('dark');
  el('tombolTema').textContent = gelap ? '☀' : '☾';
  el('tombolTema').setAttribute('aria-label', gelap ? 'Ganti ke mode terang' : 'Ganti ke mode gelap');
}
el('tombolTema').addEventListener('click', () => {
  const gelap = document.documentElement.classList.toggle('dark');
  try { localStorage.setItem('tema', gelap ? 'gelap' : 'terang'); } catch (e) {}
  pasangTombolTema();
});
pasangTombolTema();

// Tata letak kamera
document.querySelectorAll('[data-grid]').forEach(b => b.addEventListener('click', () => {
  el('area-kamera').className = b.dataset.grid;
  document.querySelectorAll('[data-grid]').forEach(x => {
    x.classList.toggle('aktif', x === b);
    x.setAttribute('aria-pressed', String(x === b));
  });
}));

// Tambah kamera
el('formKamera').addEventListener('submit', async e => {
  e.preventDefault();
  const nama = el('kam-nama').value.trim(), rtsp = el('kam-rtsp').value.trim();
  const pesan = el('pesan');
  if (!nama || !rtsp) { pesan.className = 'galat'; pesan.textContent = 'Isi nama kamera dan alamat RTSP.'; return; }
  el('simpanKamera').disabled = true;
  try {
    const r = await fetch('/api/kamera', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nama, rtsp }) });
    if (!r.ok) throw new Error();
    pesan.className = 'berhasil';
    pesan.textContent = `Kamera ${nama.toUpperCase()} disimpan.`;
    el('formKamera').reset();
  } catch (err) {
    pesan.className = 'galat';
    pesan.textContent = 'Kamera belum tersimpan. Periksa sambungan ke server Deteksi Plat, lalu coba lagi.';
  } finally {
    el('simpanKamera').disabled = false;
  }
});

// Kamera dan riwayat
const keterangan = {};
function buatPanel(daftar) {
  const area = el('area-kamera');
  area.innerHTML = '';
  for (const k of daftar) {
    const f = document.createElement('figure');
    const img = document.createElement('img');
    img.src = '/video/' + encodeURIComponent(k.nama);
    img.alt = 'Kamera ' + k.nama;
    img.width = 640; img.height = 360;
    const cap = document.createElement('figcaption');
    f.appendChild(img); f.appendChild(cap); area.appendChild(f);
    keterangan[k.nama] = cap;
  }
}

async function muat() {
  try {
    const r = await fetch('/api/status'); const d = await r.json();
    if (Object.keys(keterangan).length === 0) {
      if (d.kamera.length > 0) buatPanel(d.kamera);
      else el('area-kamera').innerHTML = '<p class="redup">Belum ada kamera. Tambahkan di Kelola kamera.</p>';
    }
    for (const k of d.kamera) {
      if (keterangan[k.nama]) keterangan[k.nama].textContent = `${k.nama} · ${k.status} · ${k.resolusi} · ${k.fps.toFixed(1)} fps`;
    }
    el('info').textContent = `${d.kamera.length} kamera aktif · AI ${d.ai_ms.toFixed(0)} ms per gambar`;
    el('terakhir').textContent = d.riwayat.length ? `${d.riwayat[0].plat} (${d.riwayat[0].jenis})` : 'Belum ada data';

    const tb = el('baris'); tb.textContent = '';
    if (!d.riwayat.length) { tb.innerHTML = '<tr><td colspan="5" class="kosong">Belum ada data</td></tr>'; return; }
    for (const x of d.riwayat) {
      const tr = document.createElement('tr');
      for (const v of [x.waktu, x.kamera, x.jenis, x.plat, x.pemilik]) {
        const td = document.createElement('td'); td.textContent = v ?? ''; tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
  } catch (e) { el('info').textContent = 'Server Deteksi Plat tidak terjangkau. Mencoba lagi…'; }
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
        self.riwayat = []

    def tambah_kamera(self, nama):
        with self.kondisi:
            self.kamera.setdefault(nama, {
                "jpeg": jpeg_pesan(f"{nama}: menyambung ke kamera..."),
                "nomor": 0,
                "status": "memulai",
                "resolusi": "-",
                "fps": 0.0,
            })
            self.kondisi.notify_all()

    def hapus_kamera(self, nama):
        with self.kondisi:
            self.kamera.pop(nama, None)
            self.kondisi.notify_all()

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
        baris = {"waktu": f"{datetime.fromtimestamp(hasil.waktu):%d-%m-%Y %H:%M:%S}", 
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
    """Satu model AI; daftar kamera aktif disinkronkan berkala dari database."""
    from anpr.pembaca import PembacaPlat
    from anpr.penstabil import PenstabilPlat
    from anpr.penyimpan import Penyimpan

    daftar_jalur = []

    def buat_jalur(konf):
        sumber = KameraRTSP(
            konf.daftar_url_rtsp(),
            konf.nama_kamera
        ).mulai()

        penstabil = PenstabilPlat(
            konf.min_frame_sama,
            konf.jendela_detik,
            konf.jeda_ulang_detik,
        )

        keadaan.tambah_kamera(konf.nama_kamera)

        jalur = Jalur(
            konf,
            sumber,
            penstabil,
            Penyimpan(konf.folder_hasil, konf.nama_kamera),
        )

        print(f"[{konf.nama_kamera}] Kamera ditambahkan ke backend.")
        return jalur

    try:
        detektor_kendaraan = DetektorKendaraan(
            os.path.join(FOLDER_PROYEK, "yolox_s.onnx")
        )

        # Pembaca tetap dapat dibuat meskipun saat startup belum ada kamera aktif.
        konf_pembaca = daftar_konf[0] if daftar_konf else muat_konfigurasi()
        pembaca = PembacaPlat(konf_pembaca)

        if args.video:
            sumber = SumberFile(args.video).mulai()
            penstabil = PenstabilPlat(
                1 if sumber.foto else konf_pembaca.min_frame_sama,
                konf_pembaca.jendela_detik,
                konf_pembaca.jeda_ulang_detik,
            )
            daftar_jalur.append(Jalur(
                konf_pembaca,
                sumber,
                penstabil,
                Penyimpan(konf_pembaca.folder_hasil, konf_pembaca.nama_kamera),
            ))
            keadaan.tambah_kamera(konf_pembaca.nama_kamera)
        else:
            for konf in daftar_konf:
                daftar_jalur.append(buat_jalur(konf))

        print("Pembaca plat & CPOS System berjalan.")

        def sinkronkan_kamera():
            konfigurasi_baru = muat_semua_kamera()

            # Jangan menghentikan kamera jika database sedang gagal dibaca.
            if konfigurasi_baru is None:
                print("[SQL] Daftar kamera tidak berubah; database gagal dibaca.")
                return

            nama_baru = [k.nama_kamera for k in konfigurasi_baru]
            if len(nama_baru) != len(set(nama_baru)):
                print("[KAMERA] Ada nama kamera duplikat; daftar tidak diterapkan.")
                return

            konfigurasi_by_nama = {
                k.nama_kamera: k for k in konfigurasi_baru
            }

            # Hentikan kamera yang dinonaktifkan atau URL RTSP-nya berubah.
            for jalur in list(daftar_jalur):
                nama = jalur.konf.nama_kamera
                konf_baru = konfigurasi_by_nama.get(nama)

                url_berubah = (
                    konf_baru is not None
                    and konf_baru.daftar_url_rtsp()
                    != jalur.konf.daftar_url_rtsp()
                )

                if konf_baru is None or url_berubah:
                    jalur.sumber.berhenti()
                    daftar_jalur.remove(jalur)
                    keadaan.hapus_kamera(nama)
                    print(f"[{nama}] Kamera dinonaktifkan atau konfigurasinya berubah.")

            nama_berjalan = {
                jalur.konf.nama_kamera for jalur in daftar_jalur
            }

            # Jalankan kamera baru atau kamera yang URL RTSP-nya berubah.
            for konf in konfigurasi_baru:
                if konf.nama_kamera not in nama_berjalan:
                    daftar_jalur.append(buat_jalur(konf))

        def terapkan_pengaturan():
            pengaturan_baru = baca_pengaturan()

            if pengaturan_baru:
                pembaca.konf.min_conf_ocr = pengaturan_baru["conf"]

                for jalur in daftar_jalur:
                    jalur.penstabil.jeda_ulang_detik = pengaturan_baru["jeda_detik"]

                gerbang.STATE["jendela"] = pengaturan_baru["jendela_detik"]

            info = info_kamera()
            if info is not None:
                gerbang.STATE["info"] = info

        terakhir_sinkron = 0
        terakhir_pengaturan = 0

        while not berhenti.is_set():
            sekarang = time.time()

            if not args.video and sekarang - terakhir_sinkron >= 10:
                sinkronkan_kamera()
                terakhir_sinkron = sekarang

            if sekarang - terakhir_pengaturan >= 30:
                terapkan_pengaturan()
                terakhir_pengaturan = sekarang

            if args.video and daftar_jalur and all(j.selesai for j in daftar_jalur):
                break

            if not daftar_jalur:
                time.sleep(1)
                continue

            ada_frame_baru = False

            for jalur in list(daftar_jalur):
                if not jalur.selesai and proses(
                    jalur, pembaca, keadaan, detektor_kendaraan
                ):
                    ada_frame_baru = True

            if not ada_frame_baru:
                time.sleep(0.05)

    except Exception as e:
        traceback.print_exc()

        for jalur in daftar_jalur:
            keadaan.pasang_info(
                jalur.konf.nama_kamera,
                f"ERROR: {e}",
                "-",
                0.0,
            )
            keadaan.pasang_gambar(
                jalur.konf.nama_kamera,
                jpeg_pesan("Terjadi error, lihat jendela konsol"),
            )

    finally:
        for jalur in daftar_jalur:
            try:
                jalur.sumber.berhenti()
            except Exception:
                pass

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
        elif jalur.startswith("/font/") and jalur[6:] in FONT:
            self._kirim("font/woff2", (FOLDER_FONT / jalur[6:]).read_bytes())
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
                    if nama not in k.kamera:
                        break

                    k.kondisi.wait_for(
                        lambda: (
                            nama not in k.kamera
                            or k.kamera[nama]["nomor"] != terakhir
                        ),
                        timeout=5,
                    )

                    if nama not in k.kamera:
                        break

                    jpeg = k.kamera[nama]["jpeg"]
                    terakhir = k.kamera[nama]["nomor"]

                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n"
                    b"Content-Length: %d\r\n\r\n" % len(jpeg)
                )
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
    p.add_argument("--host", default="0.0.0.0", help="127.0.0.1 = hanya bisa dihubungi dari PC ini (CPOS di PC yang sama)")
    p.add_argument("--video", help="uji dari file video / foto alih-alih kamera (hanya kamera pertama)")
    args = p.parse_args()

    if args.video:
        daftar_konf = [muat_konfigurasi()]
    else:
        daftar_konf = muat_semua_kamera()

        if daftar_konf is None:
            print("[SQL] Belum bisa membaca daftar kamera. Akan mencoba kembali.")
            daftar_konf = []

    daftar_nama = [k.nama_kamera for k in daftar_konf]
    if len(set(daftar_nama)) != len(daftar_nama):
        sys.exit("Nama kamera tidak boleh ada yang sama")

    keadaan = Keadaan(daftar_nama)
    Penangan.keadaan = keadaan
    berhenti = threading.Event()
    threading.Thread(target=pekerja, args=(args, daftar_konf, keadaan, berhenti), daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), Penangan)
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
