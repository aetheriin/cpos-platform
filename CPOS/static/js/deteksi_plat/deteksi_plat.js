// ===== DETEKSI PLAT (uji coba): riwayat dari backend deteksi plat; CPOS hanya menampilkan =====
let dataPlat = [];

window.addEventListener('tabChange', e => { if (e.detail === 'plat') muatPlat(); });

const hariIniLokal = () => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

async function muatPlat() {
    const dari = document.getElementById('fDari'), sampai = document.getElementById('fSampai');
    if (!dari.value) dari.value = hariIniLokal();
    if (!sampai.value) sampai.value = hariIniLokal();
    const tbody = document.getElementById('tabelPlat');
    const q = new URLSearchParams({ dari: dari.value, sampai: sampai.value,
        kamera: document.getElementById('fKamera').value, plat: document.getElementById('fPlat').value.trim() });
    const d = await ambilJson('/api/deteksi-plat?' + q);
    if (d.error) { tbody.innerHTML = barisKosong(7, d.error); return; }

    const pilih = document.getElementById('fKamera'), dipilih = pilih.value;
    pilih.innerHTML = '<option value="">Semua kamera</option>' + d.kamera.map(k => `<option value="${escapeHtml(k)}">${escapeHtml(k)}</option>`).join('');
    pilih.value = dipilih;

    dataPlat = d.data;
    document.getElementById('kpiTotal').textContent = dataPlat.length;
    document.getElementById('kpiTakDikenal').textContent = dataPlat.filter(r => !r.ada_pemilik).length;
    document.getElementById('kpiTerdaftar').textContent = dataPlat.filter(r => r.terdaftar).length;
    tbody.innerHTML = dataPlat.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.waktu)}</td>
            <td class="table-cell">${escapeHtml(r.kamera)}</td>
            <td class="table-cell">${escapeHtml(r.jenis)}</td>
            <td class="table-cell font-mono font-semibold whitespace-nowrap">${escapeHtml(r.plat)}${r.terdaftar ? ' ' + badge('Terdaftar', WARNA_BADGE.hijau) : ''}</td>
            <td class="table-cell">${r.ada_pemilik ? escapeHtml(r.pemilik) : badge('Tidak Diketahui', WARNA_BADGE.abu)}</td>
            <td class="table-cell text-right text-xs text-slate-500">${r.conf == null ? '-' : Number(r.conf).toFixed(2)}</td>
            <td class="table-cell text-right">${r.ada_foto
                ? `<button type="button" class="link-aksi text-blue-600" data-on-click="lihatFoto" data-arg="${r.id}">Foto</button>`
                : '<span class="text-slate-400">-</span>'}</td>
        </tr>`).join('') || barisKosong(7, 'Belum ada plat terdeteksi pada rentang ini');
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

// ===== VIDEO KAMERA DETEKSI (diteruskan CPOS dari backend deteksi; gambar sudah bertanda kotak plat & hasil bacaan) =====
let kameraVideo = [];
let timerFrame = null, timerStatus = null;

window.addEventListener('tabChange', e => { if (e.detail === 'plat') mulaiVideo(); });

function mulaiVideo() {
    hentikanVideo();
    muatStatusVideo().then(segarkanFrame);
    timerFrame = setInterval(segarkanFrame, 2000);
    timerStatus = setInterval(muatStatusVideo, 10000);
}

function hentikanVideo() {
    clearInterval(timerFrame);
    clearInterval(timerStatus);
    timerFrame = timerStatus = null;
}

async function muatStatusVideo() {
    const grid = document.getElementById('gridVideo'), pesan = document.getElementById('pesanVideo');
    const d = await ambilJson('/api/deteksi-plat/kamera');
    if (d.error) {
        grid.innerHTML = ''; kameraVideo = [];
        pesan.textContent = d.error; pesan.classList.remove('hidden');
        return;
    }
    pesan.classList.add('hidden');
    document.getElementById('infoAi').textContent = d.ai_ms ? `AI ${Math.round(d.ai_ms)} ms / frame` : '';
    const sama = d.kamera.map(k => k.nama).join('|') === kameraVideo.map(k => k.nama).join('|');
    if (!sama) {       // daftar kamera berubah: bangun ulang kotak (kalau sama, hanya keterangan yang diperbarui supaya gambar tidak berkedip)
        grid.innerHTML = d.kamera.map(k => `
            <div class="rounded-lg overflow-hidden border border-slate-200">
                <button type="button" class="block w-full bg-slate-900 aspect-video" data-on-click="bukaVideo" data-arg="${escapeHtml(k.nama)}" title="Layar penuh">
                    <img data-kamera="${escapeHtml(k.nama)}" alt="" class="w-full h-full object-contain">
                </button>
                <div class="flex items-center justify-between px-3 py-2 text-xs">
                    <span class="font-mono font-semibold">${escapeHtml(k.nama)}</span>
                    <span data-info-video="${escapeHtml(k.nama)}"></span>
                </div>
            </div>`).join('') || '';
        if (!d.kamera.length) { pesan.textContent = 'Belum ada kamera yang berjalan di backend deteksi'; pesan.classList.remove('hidden'); }
    }
    kameraVideo = d.kamera;
    grid.querySelectorAll('[data-info-video]').forEach(el => {
        const k = d.kamera.find(x => x.nama === el.dataset.infoVideo);
        if (!k) return;
        el.innerHTML = `${badge(k.fps > 0.1 ? 'Online' : 'Offline', k.fps > 0.1 ? WARNA_BADGE.hijau : WARNA_BADGE.abu)} <span class="text-slate-500">${escapeHtml(k.status)} · ${Number(k.fps).toFixed(1)} fps</span>`;
    });
}

function segarkanFrame() {
    if (document.hidden) return;
    document.querySelectorAll('#gridVideo img[data-kamera]').forEach(img => {
        img.src = `/api/deteksi-plat/video/${encodeURIComponent(img.dataset.kamera)}/frame?t=${Date.now()}`;
    });
}

// Layar penuh: video MJPEG; grid dijeda supaya hemat jaringan
function bukaVideo(nama) {
    hentikanVideo();
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
    mulaiVideo();
}