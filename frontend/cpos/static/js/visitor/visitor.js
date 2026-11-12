let kfIdAktivitas = null;       
let kfPenumpang = [];
let kfBisaEdit = true;
let kfScanBerjalan = false;
let kfFotoScan = null;          
let timerCariKunjungan = null;

const byId = id => document.getElementById(id);
const tglIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const kjSel = v => (v ? escapeHtml(String(v)) : '<span class="text-slate-300">–</span>');
const STATUS_KUNJUNGAN = { KUNJUNGAN_MENUNGGU: ['Waiting', WARNA_BADGE.oranye], KUNJUNGAN_DALAM: ['Inside', WARNA_BADGE.hijau],
                           KUNJUNGAN_SELESAI: ['Done', WARNA_BADGE.abu] };

// ===== Daftar: List Visitor + Employee Logs =====
function cariKunjunganTunda() {
    clearTimeout(timerCariKunjungan);
    timerCariKunjungan = setTimeout(muatKunjungan, 300);
}

async function muatKunjungan() {
    const p = new URLSearchParams({ tanggal: byId('kjTanggal').value, cari: byId('kjCari').value.trim() });
    const [vis, kar] = await Promise.all([
        ambilJson(`/api/visitor/kunjungan?kelompok=VISITOR&${p}`),
        ambilJson(`/api/visitor/kunjungan?kelompok=EMPLOYEE&${p}`),
    ]);
    byId('tabelVisitor').innerHTML = vis.error ? barisGagal(11, vis.error)
        : vis.map(r => `<tr class="hover:bg-slate-50 cursor-pointer" data-id="${r.id_aktivitas}">
            <td class="table-cell font-mono whitespace-nowrap">${kjSel(r.no_plat)}</td><td class="table-cell">${kjSel(r.lokasi)}</td>
            <td class="table-cell whitespace-nowrap">${kjSel(r.waktu_masuk)}</td><td class="table-cell">${kjSel(r.nama)}</td>
            <td class="table-cell">${kjSel(r.dari)}</td><td class="table-cell text-center">${r.nama ? r.jumlah_penumpang : kjSel('')}</td>
            <td class="table-cell">${kjSel(r.host)}</td><td class="table-cell">${kjSel(r.tujuan)}</td>
            <td class="table-cell whitespace-nowrap">${kjSel(r.waktu_keluar)}</td><td class="table-cell">${kjSel(r.kategori)}</td>
            <td class="table-cell">${kjSel(r.nik)}</td></tr>`).join('') || barisKosong(11, 'Belum ada kunjungan');
    byId('tabelEmployee').innerHTML = kar.error ? barisGagal(6, kar.error)
        : kar.map(r => `<tr class="hover:bg-slate-50 cursor-pointer" data-id="${r.id_aktivitas}">
            <td class="table-cell font-mono whitespace-nowrap">${kjSel(r.no_plat)}</td><td class="table-cell">${kjSel(r.nik)}</td>
            <td class="table-cell">${kjSel(r.nama)}</td><td class="table-cell whitespace-nowrap">${kjSel(r.waktu_masuk)}</td>
            <td class="table-cell whitespace-nowrap">${kjSel(r.waktu_keluar)}</td><td class="table-cell">${kjSel(r.kategori)}</td></tr>`).join('')
            || barisKosong(6, 'Belum ada log karyawan');
}

['tabelVisitor', 'tabelEmployee'].forEach(id => byId(id).addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]');
    if (tr) bukaKunjungan(Number(tr.dataset.id));
}));

async function muatPilihanKunjungan() {
    const d = await ambilJson('/api/visitor/dituju');
    if (d.error) return;
    byId('kfDituju').insertAdjacentHTML('beforeend', d.dituju.map(x =>
        `<option value="${x.id_personel}">${escapeHtml(x.nama_personel)}${x.peran ? ` (${escapeHtml(x.peran)})` : ''}</option>`).join(''));
}

// ===== Modal: buka / isi / tutup =====
function resetFormKunjungan() {
    batalScanKunjungan();
    byId('formKunjungan').reset();
    kfIdAktivitas = null;
    kfPenumpang = [];
    kfBisaEdit = true;
    kfFotoScan = null;
    ['kfIdPersonel', 'kfFaceId', 'kfNoTiket', 'kfLokasi', 'kfNik', 'kfNama'].forEach(id => { byId(id).value = ''; });
    byId('kfMasuk').textContent = '-';
    byId('kfKeluar').textContent = '-';
    byId('kfStatus').innerHTML = '';
    byId('kfInfoScan').innerHTML = '';
    byId('kfFoto').classList.add('hidden');
    byId('kfVideo').classList.add('hidden');
    byId('kfFaceIkon').classList.remove('hidden');
    pasangFotoKendaraan('kfDepan', null);
    pasangFotoKendaraan('kfBelakang', null);
    byId('btnKeluarKunjungan').classList.add('hidden');
    aturKunjunganEditable(true);
    renderPenumpang();
}

function aturKunjunganEditable(bisa) {
    kfBisaEdit = bisa;
    byId('kfFieldset').disabled = !bisa;
    const simpan = byId('btnSimpanKunjungan');
    if (simpan) simpan.classList.toggle('hidden', !bisa);
}

function bukaKunjunganBaru() {
    resetFormKunjungan();
    byId('kfNoTiket').value = 'Dibuat saat disimpan';
    byId('kfStatus').innerHTML = badge('New', WARNA_BADGE.biru);
    openModal('modalKunjungan');
}

async function bukaKunjungan(id) {
    resetFormKunjungan();
    const d = await ambilJson(`/api/visitor/kunjungan/${id}`);
    if (d.error) { Notif.gagal(d.error); return; }
    kfIdAktivitas = d.id_aktivitas;
    byId('kfIdPersonel').value = d.id_personel || '';
    byId('kfNoTiket').value = d.no_tiket || '-';
    byId('kfLokasi').value = d.lokasi || '';
    byId('kfNik').value = d.nik || '';
    byId('kfNama').value = d.nama || '';
    byId('kfPlat').value = d.no_plat || '';
    byId('kfDari').value = d.asal_perusahaan || '';
    byId('kfKeperluan').value = d.tujuan || '';
    isiPilihan(byId('kfJenis'), d.jenis_kendaraan);
    byId('kfDituju').value = d.id_dituju || '';
    kfPenumpang = [...(d.penumpang || [])];
    byId('kfMasuk').textContent = d.waktu_masuk || '-';
    byId('kfKeluar').textContent = d.waktu_keluar || '-';
    const [lbl, warna] = STATUS_KUNJUNGAN[d.status] || [d.status, WARNA_BADGE.abu];
    byId('kfStatus').innerHTML = badge(lbl, warna);
    if (d.id_kejadian_masuk) {
        pasangFotoKendaraan('kfDepan', `/api/visitor/${d.id_aktivitas}/foto/masuk/depan`);
        pasangFotoKendaraan('kfBelakang', `/api/visitor/${d.id_aktivitas}/foto/masuk/belakang`);
    }
    aturKunjunganEditable(d.status === 'KUNJUNGAN_MENUNGGU');      // hanya catatan menunggu yang bisa dilengkapi
    byId('btnKeluarKunjungan').classList.toggle('hidden', !(d.status === 'KUNJUNGAN_DALAM' && byId('modalKunjungan').dataset.bolehKeluar === '1'));
    renderPenumpang();
    openModal('modalKunjungan');
}

function tutupModalKunjungan() {
    batalScanKunjungan();
    closeModal('modalKunjungan');
}

function isiPilihan(sel, nilai) {
    if (nilai && ![...sel.options].some(o => o.value === nilai)) sel.add(new Option(nilai, nilai));
    sel.value = nilai || '';
}

function pasangFotoKendaraan(idImg, url) {
    const img = byId(idImg), ikon = byId(idImg + 'Ikon');
    img.onload = () => { img.classList.remove('hidden'); ikon.classList.add('hidden'); };
    img.onerror = () => { img.classList.add('hidden'); ikon.classList.remove('hidden'); };
    if (url) img.src = url;
    else { img.removeAttribute('src'); img.classList.add('hidden'); ikon.classList.remove('hidden'); }
}

// ===== Penumpang =====
function renderPenumpang() {
    byId('kfDaftarPenumpang').innerHTML = kfPenumpang.map((n, i) => `<li class="flex items-center justify-between gap-2">
        <span>${i + 1}. ${escapeHtml(n)}</span>
        ${kfBisaEdit ? `<button type="button" class="text-slate-400" data-on-click="hapusPenumpang" data-arg="${i}" title="Hapus"><i class="fa-solid fa-xmark"></i></button>` : ''}</li>`).join('');
}

function tambahPenumpang() {
    const input = byId('kfPenumpangBaru');
    const nama = input.value.trim().slice(0, 100);
    if (!nama) return;
    if (kfPenumpang.length >= 50) { Notif.gagal('Penumpang maksimal 50 orang.'); return; }
    kfPenumpang.push(nama);
    input.value = '';
    renderPenumpang();
    input.focus();
}

function hapusPenumpang(i) {
    kfPenumpang.splice(Number(i), 1);
    renderPenumpang();
}

byId('kfPenumpangBaru').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); tambahPenumpang(); }
});

// ===== Scan wajah di dalam modal =====
async function mulaiScanKunjungan() {
    if (kfScanBerjalan) return;
    const video = byId('kfVideo'), label = byId('kfInstruksi'), hitung = byId('kfHitung'), btn = byId('btnScanKunjungan');
    kfScanBerjalan = true;
    btn.disabled = true;
    byId('kfFoto').classList.add('hidden');
    byId('kfFaceIkon').classList.add('hidden');
    byId('kfInfoScan').innerHTML = '';
    video.classList.remove('hidden');
    label.classList.remove('hidden');
    try {
        await Kamera.mulai(video);
    } catch (err) {
        label.textContent = 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.';
        selesaiScanKunjungan();
        return;
    }
    hitung.classList.replace('hidden', 'flex');
    const { absensi: wajib } = await aturanTantangan();
    const hasil = await rekamWajah(video, {
        wajib,
        tampil: (teks, angka) => { label.textContent = teks; if (angka) hitung.textContent = angka; else hitung.classList.replace('flex', 'hidden'); },
        batal: () => !kfScanBerjalan,
    });
    hitung.classList.replace('flex', 'hidden');
    if (!hasil) { selesaiScanKunjungan(); return; }
    kfFotoScan = hasil.frames[0];
    const img = byId('kfFoto');
    img.src = URL.createObjectURL(kfFotoScan);
    img.classList.remove('hidden');
    video.classList.add('hidden');
    Kamera.stop();
    label.textContent = 'Memproses...';
    const fd = new FormData();
    hasil.frames.forEach((b, i) => fd.append('frames', b, `frame${i}.jpg`));
    fd.append('tantangan', hasil.tantangan);
    fd.append('perangkat', 'Web');
    const data = await kirimForm('/api/visitor/scan', fd, { timeout: TIMEOUT_WAJAH_MS });
    label.classList.add('hidden');
    selesaiScanKunjungan();
    terapkanHasilScan(data);
}

function selesaiScanKunjungan() {
    kfScanBerjalan = false;
    byId('btnScanKunjungan').disabled = false;
}

function batalScanKunjungan() {
    kfScanBerjalan = false;
    if (typeof Kamera !== 'undefined') Kamera.stop();
    byId('kfVideo').classList.add('hidden');
    byId('kfInstruksi').classList.add('hidden');
    byId('btnScanKunjungan').disabled = false;
}

function terapkanHasilScan(d) {
    const info = byId('kfInfoScan');
    byId('kfIdPersonel').value = '';
    byId('kfFaceId').value = '';
    if (d.error && !d.status) { info.innerHTML = `<div class="note-warning">${escapeHtml(d.error)}</div>`; return; }
    if (d.status === 'TIDAK_DIKENALI') {
        const bisaDaftar = byId('modalKunjungan').dataset.bolehScan === '1' && typeof bukaTambahDariScan === 'function';
        info.innerHTML = `<div class="note-warning">Wajah tidak dikenali.${bisaDaftar ? ` <button type="button" class="btn-primary btn-sm ml-2" data-on-click="daftarDariScan"><i class="fa-solid fa-user-plus mr-1"></i> Daftarkan Orang</button>` : ''}</div>`;
        return;
    }
    if (d.status === 'DITOLAK') {
        info.innerHTML = `<div class="note-warning bg-red-50 border-red-200 text-red-700">${escapeHtml(d.nama_personel)} masuk daftar BLACKLIST. Akses ditolak dan tercatat.</div>`;
        return;
    }
    if (d.di_dalam) {
        info.innerHTML = `<div class="note-info">${escapeHtml(d.nama_personel)} masih di dalam sejak ${escapeHtml(d.masuk_sejak || '-')}.
            <button type="button" class="btn-primary btn-sm ml-2" data-on-click="keluarKunjungan" data-arg="${d.activity_id}"><i class="fa-solid fa-right-from-bracket mr-1"></i> Going out</button></div>`;
        return;
    }
    byId('kfIdPersonel').value = d.id_personel;
    byId('kfFaceId').value = d.face_id || '';
    byId('kfNik').value = d.nik || '';
    byId('kfNama').value = d.nama_personel || '';
    if (!byId('kfDari').value) byId('kfDari').value = d.asal_perusahaan || '';
    if (!byId('kfKeperluan').value) byId('kfKeperluan').value = d.keperluan || '';
}

function daftarDariScan() {
    if (typeof bukaTambahDariScan === 'function') bukaTambahDariScan(kfFotoScan);
}

// ===== Simpan & Going out =====
byId('formKunjungan').addEventListener('submit', async e => {
    e.preventDefault();
    await denganTombol(e.submitter, async () => {
        const fd = new FormData(e.target);
        if (kfIdAktivitas === null) {                    // kunjungan manual: buat catatan menunggu dulu
            const dibuat = await kirimForm('/api/visitor/kunjungan/manual', { no_plat: fd.get('no_plat') || '' });
            if (!dibuat || dibuat.error) { Notif.gagal((dibuat && dibuat.error) || 'Gagal membuat kunjungan.'); return; }
            kfIdAktivitas = dibuat.activity_id;          // bila Save gagal validasi, percobaan berikutnya memakai catatan yang sama
        }
        fd.delete('penumpang');
        kfPenumpang.forEach(n => fd.append('penumpang', n));
        fd.set('jumlah_penumpang', String(kfPenumpang.length));
        fd.set('perangkat', 'Web');
        const data = await kirimForm(`/api/visitor/kunjungan/${kfIdAktivitas}/lengkapi`, fd);
        if (!tampilkanHasil(data)) return;
        tutupModalKunjungan();
        muatKunjungan();
    });
});

async function keluarKunjungan(id) {
    const data = await kirimForm(`/api/visitor/kunjungan/${id}/keluar`, {});
    if (!tampilkanHasil(data)) return;
    tutupModalKunjungan();
    muatKunjungan();
}

function keluarDariModal() {
    if (kfIdAktivitas !== null) keluarKunjungan(kfIdAktivitas);
}

// ===== Sinkron kamera deteksi plat =====
async function sinkronKunjungan() {
    try { await kirimForm('/api/visitor/sinkron', {}); } catch (err) { /* gagal diam-diam: daftar tetap dimuat */ }
}

// ===== Mulai =====
byId('kjTanggal').value = tglIso(new Date());
sinkronKunjungan().finally(muatKunjungan);
muatPilihanKunjungan();
setInterval(async () => {
    if (document.hidden || !byId('modalKunjungan').classList.contains('hidden')) return;   // jangan ganggu saat form terbuka
    await sinkronKunjungan();
    muatKunjungan();
}, 30000);