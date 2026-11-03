// ===== MONITORING CCTV: grid kamera per area (gambar diperbarui berkala), layar penuh = video MJPEG lewat server CPOS =====
const JEDA_GRID_MS = 2000;      // gambar grid diperbarui tiap 2 detik (sub-stream ringan)
let semuaKamera = [];
let titikAktif = '';
let timerGrid = null;
const urlGambar = {};           // id kamera -> object URL terakhir (dilepas saat diganti)

document.addEventListener('DOMContentLoaded', muatKamera);
document.addEventListener('visibilitychange', () => { if (document.hidden) hentikanGrid(); else mulaiGrid(); });

async function muatKamera() {
    const data = await ambilJson('/api/cctv/kamera');
    const grid = document.getElementById('gridCctv');
    if (data.error) { grid.innerHTML = `<div class="section-box p-8 text-center text-sm text-red-600 col-span-full">${escapeHtml(data.error)}</div>`; return; }
    semuaKamera = data;
    const area = [...new Map(data.map(k => [k.id_comp_area, k.area])).entries()];
    const pilih = document.getElementById('pilihArea');
    pilih.innerHTML = '<option value="">Semua area</option>' + area.map(([id, n]) => `<option value="${id}">${escapeHtml(n)}</option>`).join('');
    pilih.classList.toggle('hidden', area.length < 2);
    const ada = new Set(data.map(k => k.titik));
    document.querySelectorAll('#chipTitik [data-titik]').forEach(b => { if (b.dataset.titik) b.classList.toggle('hidden', !ada.has(b.dataset.titik)); });
    tampilKamera();
}

function pilihTitik(el) {
    aktifkanChip(el);
    titikAktif = el.dataset.titik;
    tampilKamera();
}

function pilihGrid(el) {
    aktifkanChip(el);
    const n = el.dataset.kolom;
    document.getElementById('gridCctv').className = `grid gap-3 ${n === '1' ? 'grid-cols-1' : n === '2' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-3'}`;
}

const kameraTampil = () => {
    const area = document.getElementById('pilihArea').value;
    return semuaKamera.filter(k => (!titikAktif || k.titik === titikAktif) && (!area || String(k.id_comp_area) === area));
};

function tampilKamera() {
    hentikanGrid();
    const daftar = kameraTampil();
    const kartu = (j, n, ik, w) => `<div class="section-box p-3 flex items-center gap-3"><span class="judul-ikon ${w}"><i class="fa-solid ${ik}"></i></span>
        <div><p class="text-xl font-extrabold text-slate-900 leading-none">${n}</p><p class="text-xs text-slate-500 mt-1">${j}</p></div></div>`;
    document.getElementById('ringkasCctv').innerHTML = kartu('Kamera', semuaKamera.length, 'fa-video', 'judul-ikon-biru')
        + kartu('Terhubung (yang tampil)', `<span id="jmlOnline">…</span>`, 'fa-signal', 'judul-ikon-hijau')
        + kartu('Area', new Set(semuaKamera.map(k => k.id_comp_area)).size, 'fa-location-dot', 'judul-ikon-gelap');
    document.getElementById('gridCctv').innerHTML = daftar.map(k => `
        <div class="rounded-xl overflow-hidden bg-slate-900 ring-1 ring-slate-200" data-kamera="${k.id_kamera}">
            <button type="button" class="relative block w-full aspect-video" data-on-click="bukaLive" data-arg="${k.id_kamera}" title="Layar penuh">
                <img alt="" class="absolute inset-0 w-full h-full object-contain hidden" data-gambar>
                <div class="absolute inset-0 flex flex-col items-center justify-center text-slate-400" data-memuat>
                    <i class="fa-solid fa-spinner fa-spin text-2xl"></i></div>
                <span class="absolute top-2 left-2 text-[10px] font-bold rounded px-1.5 py-0.5 bg-red-600 text-white hidden" data-live>
                    <span class="inline-block w-1.5 h-1.5 rounded-full bg-white mr-1 align-middle"></span>LIVE</span>
                <span class="absolute bottom-2 left-2 text-[11px] font-semibold text-white bg-black/50 rounded px-2 py-0.5">${escapeHtml(k.kode)} · ${escapeHtml(k.nama)}</span>
            </button>
            <div class="px-3 py-2 bg-white flex items-center justify-between text-xs">
                <span class="text-slate-600 truncate">${escapeHtml(k.nama_titik)}${k.jembatan ? ` · ${escapeHtml(k.jembatan)}` : ''} · ${escapeHtml(k.area)}</span>
                <span class="flex gap-3 text-slate-400"><a href="/api/cctv/${k.id_kamera}/frame" download="${escapeHtml(k.kode)}.jpg" title="Simpan foto"><i class="fa-solid fa-camera"></i></a>
                    <button type="button" data-on-click="bukaLive" data-arg="${k.id_kamera}" title="Layar penuh"><i class="fa-solid fa-expand"></i></button></span>
            </div>
        </div>`).join('') || `<div class="section-box p-10 text-center text-sm text-slate-400 col-span-full">
            ${semuaKamera.length ? 'Tidak ada kamera di lokasi ini' : 'Belum ada kamera untuk area Anda'}</div>`;
    mulaiGrid();
}

async function perbaruiSatu(el) {
    const id = el.dataset.kamera;
    const img = el.querySelector('[data-gambar]'), memuat = el.querySelector('[data-memuat]'), live = el.querySelector('[data-live]');
    try {
        const r = await fetch(`/api/cctv/${id}/frame?t=${Date.now()}`);
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'Kamera tidak terhubung');
        const url = URL.createObjectURL(await r.blob());
        img.onload = () => { if (urlGambar[id] && urlGambar[id] !== url) URL.revokeObjectURL(urlGambar[id]); urlGambar[id] = url; };
        img.src = url;
        img.classList.remove('hidden'); live.classList.remove('hidden'); memuat.classList.add('hidden');
        el.dataset.online = '1';
    } catch (e) {
        el.dataset.online = '';
        img.classList.add('hidden'); live.classList.add('hidden'); memuat.classList.remove('hidden');
        memuat.innerHTML = `<i class="fa-solid fa-video-slash text-3xl mb-2"></i><p class="text-xs font-semibold px-4 text-center">${escapeHtml(e.message)}</p>`;
    }
}

async function perbaruiGrid() {
    const kotak = [...document.querySelectorAll('#gridCctv [data-kamera]')];
    await Promise.all(kotak.map(perbaruiSatu));
    const jml = document.getElementById('jmlOnline');
    if (jml) jml.textContent = `${kotak.filter(el => el.dataset.online === '1').length} / ${kotak.length}`;
}

function mulaiGrid() {
    hentikanGrid();
    if (!document.querySelector('#gridCctv [data-kamera]')) return;
    perbaruiGrid();
    timerGrid = setInterval(perbaruiGrid, JEDA_GRID_MS);
}

function hentikanGrid() {
    clearInterval(timerGrid);
    timerGrid = null;
}

// ===== Layar penuh: video MJPEG (kualitas penuh); grid dijeda supaya hemat jaringan =====
function bukaLive(id) {
    const k = semuaKamera.find(x => x.id_kamera === Number(id));
    if (!k) return;
    hentikanGrid();
    document.getElementById('judulLive').textContent = `${k.kode} · ${k.nama}`;
    document.getElementById('subLive').textContent = `${k.nama_titik} · ${k.area}`;
    document.getElementById('unduhLive').href = `/api/cctv/${k.id_kamera}/frame`;
    document.getElementById('unduhLive').download = `${k.kode}.jpg`;
    const img = document.getElementById('gambarLive'), pesan = document.getElementById('pesanLive');
    pesan.classList.add('hidden');
    img.onerror = () => { pesan.textContent = 'Video tidak dapat dibuka. Kamera terputus atau terlalu banyak video yang sedang dibuka.'; pesan.classList.remove('hidden'); };
    img.src = `/api/cctv/${k.id_kamera}/live?t=${Date.now()}`;
    openModal('modalLive');
}

function tutupLive() {
    const img = document.getElementById('gambarLive');
    img.onerror = null;
    img.removeAttribute('src');           // putus video supaya slot di server dilepas
    closeModal('modalLive');
    mulaiGrid();
}

