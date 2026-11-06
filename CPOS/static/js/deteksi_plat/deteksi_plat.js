// ===== DETEKSI PLAT: video kamera per area + riwayat plat yang bertambah otomatis =====
// CPOS hanya menampilkan; backend deteksi jalan terpisah dan menulis ke database. Routes: routes/deteksi_plat.py
const JEDA_GRID_MS = 2000;        // gambar kamera diperbarui tiap 2 detik
const JEDA_STATUS_MS = 10000;     // daftar kamera & status backend deteksi tiap 10 detik
const JEDA_RIWAYAT_MS = 3000;     // cek plat baru tiap 3 detik

let dataPlat = [];
let kameraVideo = [];             // kamera dalam cakupan user (dari server)
let kolomGrid = '2';              // 1 = satu kamera, 2 = 2 kolom (4 kamera), 3 = 3 kolom (9 kamera)
let kameraSatu = '';              // kamera terpilih pada tampilan 1 kamera
let tandaGrid = '', tandaArea = '';
let idTerakhirPlat = 0;
let liveAktif = false;
let timerGrid = null, timerStatus = null, timerRiwayat = null;
const urlGambar = {};             // nama kamera -> object URL terakhir (dilepas saat diganti)

const hariIniLokal = () => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
const areaPilihan = () => document.getElementById('pilihArea').value;

window.addEventListener('tabChange', e => {
    if (e.detail !== 'plat') return;
    muatPlat(); mulaiVideo(); mulaiRiwayat();
});
document.addEventListener('visibilitychange', () => {
    if (document.hidden) { hentikanVideo(); hentikanRiwayat(); return; }
    if (!liveAktif) { mulaiVideo(); mulaiRiwayat(); }
});

// ---------- Video kamera ----------
function mulaiVideo() {
    hentikanVideo();
    muatStatusVideo().then(perbaruiGrid);
    timerGrid = setInterval(perbaruiGrid, JEDA_GRID_MS);
    timerStatus = setInterval(muatStatusVideo, JEDA_STATUS_MS);
}

function hentikanVideo() {
    clearInterval(timerGrid);
    clearInterval(timerStatus);
    timerGrid = timerStatus = null;
}

async function muatStatusVideo() {
    const pesan = document.getElementById('pesanVideo');
    const d = await ambilJson('/api/deteksi-plat/kamera');
    if (d.error) {
        kameraVideo = [];
        pesan.textContent = d.error; pesan.classList.remove('hidden');
        renderGrid(true);
        return;
    }
    pesan.textContent = d.peringatan ? `${d.peringatan}. Gambar kamera belum bisa ditampilkan sampai backend deteksi terjangkau.` : '';
    pesan.classList.toggle('hidden', !d.peringatan);
    document.getElementById('infoAi').textContent = d.ai_ms ? `AI ${Math.round(d.ai_ms)} ms / frame` : '';
    kameraVideo = d.kamera;
    isiPilihanArea();
    renderGrid(false);
}

function isiPilihanArea() {
    const area = new Map(kameraVideo.filter(k => k.id_comp_area).map(k => [k.id_comp_area, k.area]));
    const tanda = [...area.keys()].join(',');
    const pilih = document.getElementById('pilihArea');
    if (tanda !== tandaArea) {            // daftar area berubah: isi ulang (kalau sama, jangan diganggu saat dropdown dibuka)
        const dipilih = pilih.value;
        pilih.innerHTML = '<option value="">Semua area</option>' + [...area].map(([id, n]) => `<option value="${id}">${escapeHtml(n)}</option>`).join('');
        pilih.value = dipilih;
        tandaArea = tanda;
    }
    pilih.classList.toggle('hidden', area.size < 2);
}

const kameraTampil = () => {
    const area = areaPilihan();
    return kameraVideo.filter(k => !area || String(k.id_comp_area) === area);
};

const kotakKamera = k => `
    <div class="rounded-xl overflow-hidden bg-slate-900 ring-1 ring-slate-200" data-kamera="${escapeHtml(k.nama)}">
        <button type="button" class="relative block w-full aspect-video" data-on-click="bukaVideo" data-arg="${escapeHtml(k.nama)}" title="Layar penuh">
            <img alt="" class="absolute inset-0 w-full h-full object-contain hidden" data-gambar>
            <div class="absolute inset-0 flex flex-col items-center justify-center text-slate-400" data-memuat>
                <i class="fa-solid fa-spinner fa-spin text-2xl"></i></div>
            <span class="absolute top-2 left-2 text-[10px] font-bold rounded px-1.5 py-0.5 bg-red-600 text-white hidden" data-live>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-white mr-1 align-middle"></span>LIVE</span>
            <span class="absolute bottom-2 left-2 text-[11px] font-semibold text-white bg-black/50 rounded px-2 py-0.5">${escapeHtml(k.nama)}</span>
        </button>
        <div class="px-3 py-2 bg-white flex items-center justify-between text-xs">
            <span class="text-slate-600 truncate">${escapeHtml(k.area || '-')}${k.gate ? ` · ${escapeHtml(k.gate)}` : ''}</span>
            <span data-keterangan></span>
        </div>
    </div>`;

function renderGrid(paksa) {
    const grid = document.getElementById('gridVideo');
    const semua = kameraTampil();
    if (kolomGrid === '1' && !semua.some(k => k.nama === kameraSatu)) kameraSatu = semua[0] ? semua[0].nama : '';
    const daftar = kolomGrid === '1' ? semua.filter(k => k.nama === kameraSatu) : semua;
    const tanda = `${kolomGrid}|${areaPilihan()}|${daftar.map(k => k.nama).join('|')}`;
    if (paksa || tanda !== tandaGrid) {       // hanya dibangun ulang bila susunan berubah (supaya gambar tidak berkedip)
        tandaGrid = tanda;
        const pilihK = document.getElementById('pilihKamera');
        pilihK.classList.toggle('hidden', !(kolomGrid === '1' && semua.length > 1));
        pilihK.innerHTML = semua.map(k => `<option value="${escapeHtml(k.nama)}">${escapeHtml(k.nama)}</option>`).join('');
        pilihK.value = kameraSatu;
        grid.className = `grid gap-3 mb-5 ${kolomGrid === '1' ? 'grid-cols-1' : kolomGrid === '2' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-3'}`;
        grid.innerHTML = daftar.map(kotakKamera).join('') || `<div class="section-box p-10 text-center text-sm text-slate-400 col-span-full">
            ${kameraVideo.length ? 'Tidak ada kamera di area ini' : 'Belum ada kamera deteksi untuk area Anda'}</div>`;
        perbaruiGrid();
    }
    perbaruiKeterangan();
}

function perbaruiKeterangan() {
    document.querySelectorAll('#gridVideo [data-kamera]').forEach(el => {
        const k = kameraVideo.find(x => x.nama === el.dataset.kamera);
        const ket = el.querySelector('[data-keterangan]');
        if (!k || !ket) return;
        const hidup = k.fps > 0.1;
        ket.innerHTML = `${badge(hidup ? 'Online' : 'Offline', hidup ? WARNA_BADGE.hijau : WARNA_BADGE.abu)} `
            + `<span class="text-slate-500">${hidup ? Number(k.fps).toFixed(1) + ' fps' : escapeHtml(k.status)}</span>`;
    });
}

async function perbaruiSatu(el) {
    const nama = el.dataset.kamera;
    const img = el.querySelector('[data-gambar]'), memuat = el.querySelector('[data-memuat]'), live = el.querySelector('[data-live]');
    try {
        const r = await fetch(`/api/deteksi-plat/video/${encodeURIComponent(nama)}/frame?t=${Date.now()}`);
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'Kamera tidak terhubung');
        const url = URL.createObjectURL(await r.blob());
        img.onload = () => { if (urlGambar[nama] && urlGambar[nama] !== url) URL.revokeObjectURL(urlGambar[nama]); urlGambar[nama] = url; };
        img.src = url;
        img.classList.remove('hidden'); live.classList.remove('hidden'); memuat.classList.add('hidden');
    } catch (e) {
        img.classList.add('hidden'); live.classList.add('hidden'); memuat.classList.remove('hidden');
        memuat.innerHTML = `<i class="fa-solid fa-video-slash text-3xl mb-2"></i><p class="text-xs font-semibold px-4 text-center">${escapeHtml(e.message)}</p>`;
    }
}

async function perbaruiGrid() {
    if (document.hidden) return;
    await Promise.all([...document.querySelectorAll('#gridVideo [data-kamera]')].map(perbaruiSatu));
}

function gantiArea() {
    document.getElementById('fKamera').value = '';       // kamera di filter riwayat ikut area yang baru
    renderGrid(false);
    muatPlat();
}

function gantiKameraSatu() {
    kameraSatu = document.getElementById('pilihKamera').value;
    renderGrid(false);
}

function pilihGridPlat(el) {
    aktifkanChip(el);
    kolomGrid = el.dataset.kolom;
    renderGrid(false);
}

// Layar penuh: video MJPEG dari backend deteksi (sudah bertanda kotak plat & hasil bacaan); grid dijeda supaya hemat jaringan
function bukaVideo(nama) {
    hentikanVideo();
    liveAktif = true;
    const img = document.getElementById('gambarVideo'), pesan = document.getElementById('pesanLive');
    document.getElementById('judulVideo').textContent = nama;
    pesan.classList.add('hidden');
    img.onerror = () => { pesan.textContent = 'Video tidak dapat dibuka. Backend deteksi terputus atau terlalu banyak video yang sedang dibuka.'; pesan.classList.remove('hidden'); };
    img.src = `/api/deteksi-plat/video/${encodeURIComponent(nama)}/live?t=${Date.now()}`;
    openModal('modalVideo');
}

function tutupVideo() {
    const img = document.getElementById('gambarVideo');
    img.onerror = null;
    img.removeAttribute('src');           // putus video supaya slot di server dilepas
    closeModal('modalVideo');
    liveAktif = false;
    mulaiVideo();
}

// ---------- Riwayat plat ----------
function paramPlat() {
    const dari = document.getElementById('fDari'), sampai = document.getElementById('fSampai');
    if (!dari.value) dari.value = hariIniLokal();
    if (!sampai.value) sampai.value = hariIniLokal();
    return new URLSearchParams({ dari: dari.value, sampai: sampai.value, area: areaPilihan(),
        kamera: document.getElementById('fKamera').value, plat: document.getElementById('fPlat').value.trim() });
}

async function muatPlat() {
    const tbody = document.getElementById('tabelPlat');
    const d = await ambilJson('/api/deteksi-plat?' + paramPlat());
    if (d.error) { tbody.innerHTML = barisGagal(9, d.error); return; }

    const pilih = document.getElementById('fKamera'), dipilih = pilih.value;
    pilih.innerHTML = '<option value="">Semua kamera</option>' + d.kamera.map(k => `<option value="${escapeHtml(k)}">${escapeHtml(k)}</option>`).join('');
    pilih.value = dipilih;

    dataPlat = d.data;
    idTerakhirPlat = d.id_terakhir || 0;
    document.getElementById('kpiTotal').textContent = dataPlat.length;
    document.getElementById('kpiTakDikenal').textContent = dataPlat.filter(r => !r.ada_pemilik).length;
    document.getElementById('kpiTerdaftar').textContent = dataPlat.filter(r => r.terdaftar).length;
    tbody.innerHTML = dataPlat.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.waktu)}</td>
            <td class="table-cell text-xs">${escapeHtml(r.area)}</td>
            <td class="table-cell">${escapeHtml(r.kamera)}</td>
            <td class="table-cell whitespace-nowrap">${badgeArah(r.arah)}${r.sisi ? ` <span class="text-xs text-slate-500">plat ${r.sisi === 'DEPAN' ? 'depan' : 'belakang'}</span>` : ''}</td>
            <td class="table-cell">${escapeHtml(r.jenis)}</td>
            <td class="table-cell font-mono font-semibold whitespace-nowrap">${escapeHtml(r.plat)}${r.terdaftar ? ' ' + badge('Terdaftar', WARNA_BADGE.hijau) : ''}</td>
            <td class="table-cell">${r.ada_pemilik ? escapeHtml(r.pemilik) : badge('Tidak Diketahui', WARNA_BADGE.abu)}</td>
            <td class="table-cell text-right text-xs text-slate-500">${r.conf == null ? '-' : Number(r.conf).toFixed(2)}</td>
            <td class="table-cell text-right">${r.ada_foto
                ? `<button type="button" class="link-aksi text-blue-600" data-on-click="lihatFoto" data-arg="${r.id}">Foto</button>`
                : '<span class="text-slate-400">-</span>'}</td>
        </tr>`).join('') || barisKosong(9, 'Belum ada plat terdeteksi pada rentang ini');
}

// Plat baru: cek ringan (hanya ID terbesar); daftar dimuat ulang hanya bila ada yang baru
function mulaiRiwayat() {
    hentikanRiwayat();
    timerRiwayat = setInterval(cekPlatBaru, JEDA_RIWAYAT_MS);
}

function hentikanRiwayat() {
    clearInterval(timerRiwayat);
    timerRiwayat = null;
}

async function cekPlatBaru() {
    if (document.hidden) return;
    const sampai = document.getElementById('fSampai').value;
    if (sampai && sampai < hariIniLokal()) return;       // rentang yang sudah lewat tidak akan bertambah
    const d = await ambilJson('/api/deteksi-plat/terbaru?' + paramPlat());
    if (!d.error && d.id > idTerakhirPlat) muatPlat();
}

function lihatFoto(id) {
    const r = dataPlat.find(x => x.id === id);
    if (!r) return;
    const img = document.getElementById('gambarFoto');
    img.alt = '';
    img.onerror = () => { img.alt = 'Foto tidak ditemukan di folder penyimpanan'; };
    img.src = `/api/deteksi-plat/${id}/foto`;
    document.getElementById('judulFoto').textContent = `${r.plat} · ${r.kamera} · ${r.waktu}`;
    openModal('modalFoto');
}

function badgeArah(arah) {
    if (arah === 'MASUK') return badge('Masuk', WARNA_BADGE.hijau);
    if (arah === 'KELUAR') return badge('Keluar', WARNA_BADGE.biru);
    return badge(arah ? 'Belum pasti' : '-', WARNA_BADGE.abu);       // arah kosong = kamera tanpa gerbang
}