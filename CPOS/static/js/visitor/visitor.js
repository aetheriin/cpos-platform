// ===== VISITOR & STAFF LOGS: Scan Wajah · Logs (Data Orang: face_recognition/personel.js) =====
// Scan -> karyawan: absensi langsung tercatat; driver / tamu: form kunjungan atau catat keluar;
// tidak dikenali: daftarkan di tempat (form Tambah Orang dengan foto hasil scan, jenis dipilih dari dropdown).
let scanBerjalan = false;
let fotoScan = null;            // Blob frame terakhir (untuk mendaftarkan wajah yang tidak dikenali)
let scanDimuat = false, logsDimuat = false;
let modeLog = 'aktivitas';
let timerCariLog = null;

const tglIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const STATUS_WAKTU = { TEPAT_WAKTU: ['Tepat waktu', WARNA_BADGE.hijau], TERLAMBAT: ['Terlambat', WARNA_BADGE.merah],
                       PULANG_AWAL: ['Pulang awal', WARNA_BADGE.oranye], HARI_LIBUR: ['Hari libur', WARNA_BADGE.abu] };
const WARNA_STATUS_SCAN = { WAJAH_BERHASIL: WARNA_BADGE.hijau, WAJAH_TIDAK_DIKENALI: WARNA_BADGE.oranye, WAJAH_DITOLAK: WARNA_BADGE.merah };

window.addEventListener('tabChange', e => {
    if (e.detail !== 'scan') batalScan();
    if (e.detail === 'scan' && !scanDimuat) { scanDimuat = true; muatScan(); muatPilihanKunjungan(); }
    if (e.detail === 'logs' && !logsDimuat) {
        logsDimuat = true;
        document.getElementById('logTanggal').value = tglIso(new Date());
        document.getElementById('logBulan').value = tglIso(new Date()).slice(0, 7);
        pilihModeLog(document.querySelector('[data-mode-log="aktivitas"]'));
    }
});
window.addEventListener('orangDisimpan', () => { if (scanDimuat) muatScan(); });

// ===== Ringkasan & masih di dalam =====
async function muatScan() {
    const [r, dalam] = await Promise.all([ambilJson('/api/visitor/ringkasan'), ambilJson('/api/visitor/di-dalam')]);
    if (!r.error) {
        const kartu = [['Karyawan masuk', r.karyawan, 'fa-user-tie'], ['Driver masuk', r.driver, 'fa-truck'], ['Tamu masuk', r.tamu, 'fa-user'],
                       ['Masih di dalam', r.di_dalam, 'fa-door-open'], ['Tidak dikenali / ditolak', r.tidak_dikenali + r.ditolak, 'fa-triangle-exclamation']];
        document.getElementById('kartuRingkasan').innerHTML = kartu.map(([j, n, ik]) => `
            <div class="section-box p-3 flex items-center gap-3"><span class="judul-ikon judul-ikon-biru"><i class="fa-solid ${ik}"></i></span>
                <div><p class="text-xl font-extrabold text-slate-900 leading-none">${n}</p><p class="text-xs text-slate-500 mt-1">${j}</p></div></div>`).join('');
    }
    const wadah = document.getElementById('daftarDiDalam');
    if (dalam.error) { wadah.innerHTML = `<p class="p-4 text-red-600">${escapeHtml(dalam.error)}</p>`; return; }
    document.getElementById('jmlDiDalam').textContent = dalam.length;
    const bolehKeluar = wadah.dataset.bolehKeluar === '1';
    wadah.innerHTML = dalam.map(d => `
        <div class="px-4 py-2.5 flex items-center justify-between gap-3">
            <div class="min-w-0"><p class="font-semibold text-slate-800 truncate">${escapeHtml(d.nama_personel)}</p>
                <p class="text-xs text-slate-500">${escapeHtml(d.nama_kategori || '')} · masuk ${escapeHtml(d.jam)}${d.no_plat ? ` · ${escapeHtml(d.no_plat)}` : ''}</p></div>
            ${bolehKeluar ? `<button type="button" class="btn-secondary btn-sm" data-on-click="catatKeluar" data-arg="${d.id_personel}">Keluar</button>` : ''}
        </div>`).join('') || '<p class="p-4 text-center text-slate-400">Tidak ada</p>';
}

async function muatPilihanKunjungan() {
    const d = await ambilJson('/api/visitor/dituju');
    if (d.error) return;
    document.getElementById('kunjDituju').insertAdjacentHTML('beforeend', d.dituju.map(x =>
        `<option value="${x.id_personel}">${escapeHtml(x.nama_personel)}${x.peran ? ` (${escapeHtml(x.peran)})` : ''}</option>`).join(''));
    document.getElementById('saranKeperluan').innerHTML = d.keperluan.map(k => `<option value="${escapeHtml(k)}">`).join('');
}

// ===== Scan =====
async function mulaiScan() {
    if (scanBerjalan) return;
    const video = document.getElementById('vslVideo'), label = document.getElementById('vslInstruksi');
    const hitung = document.getElementById('vslHitung'), btn = document.getElementById('btnMulaiScan');
    resetHasil();
    scanBerjalan = true;
    btn.disabled = true;
    document.getElementById('vslFoto').classList.add('hidden');
    try {
        await Kamera.mulai(video);
    } catch (err) {
        label.textContent = 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.';
        selesaiScan();
        return;
    }
    hitung.classList.replace('hidden', 'flex');
    const { absensi: wajib } = await aturanTantangan();
    const hasil = await rekamWajah(video, {
        wajib,
        tampil: (teks, angka) => { label.textContent = teks; if (angka) hitung.textContent = angka; else hitung.classList.replace('flex', 'hidden'); },
        batal: () => !scanBerjalan,
    });
    hitung.classList.replace('flex', 'hidden');
    if (!hasil) return;
    fotoScan = hasil.frames[0];
    const img = document.getElementById('vslFoto');
    img.src = URL.createObjectURL(fotoScan);
    img.classList.remove('hidden');
    Kamera.stop();
    label.textContent = 'Memproses...';
    const fd = new FormData();
    hasil.frames.forEach((b, i) => fd.append('frames', b, `frame${i}.jpg`));
    fd.append('tantangan', hasil.tantangan);
    fd.append('perangkat', 'Web');
    const data = await kirimForm('/api/visitor/scan', fd, { timeout: TIMEOUT_WAJAH_MS });
    label.textContent = 'Tekan Mulai Scan';
    selesaiScan();
    tampilHasil(data);
    muatScan();
}

function selesaiScan() {
    scanBerjalan = false;
    const btn = document.getElementById('btnMulaiScan');
    if (btn) btn.disabled = false;
}

function batalScan() {
    scanBerjalan = false;
    if (typeof Kamera !== 'undefined') Kamera.stop();
    selesaiScan();
}

function resetHasil() {
    const form = document.getElementById('formKunjungan');
    form.classList.add('hidden');
    form.reset();
    document.getElementById('vslHasil').className = 'section-box p-8 text-center text-sm text-slate-400';
    document.getElementById('vslHasil').textContent = 'Belum ada scan';
}

function kartuOrang(d, isi, warna = 'border-slate-200') {
    const foto = d.foto_path ? `<img src="${escapeHtml(urlBerkas(d.foto_path))}" class="w-full h-full object-cover" alt="">`
                             : '<i class="fa-solid fa-user text-3xl text-slate-400"></i>';
    return `<div class="section-box border-2 ${warna} overflow-hidden">
        <div class="p-5 flex items-start gap-4">
            <div class="w-20 h-24 rounded-lg bg-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">${foto}</div>
            <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2"><p class="text-lg font-bold text-slate-900">${escapeHtml(d.nama_personel)}</p>${badgeKategori(d.kategori)}
                    ${d.is_blacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : ''}</div>
                <p class="text-sm text-slate-500">${escapeHtml(d.kode_personel || '-')} · NIK ${escapeHtml(d.nik || '-')}
                    ${d.peran ? ` · ${escapeHtml(d.peran)}` : ''}${d.asal_perusahaan ? ` · ${escapeHtml(d.asal_perusahaan)}` : ''}</p>
                <div class="mt-3">${isi}</div>
            </div>
        </div></div>`;
}

function tampilHasil(d) {
    const wadah = document.getElementById('vslHasil');
    wadah.className = '';
    if (d.error && !d.status) { wadah.innerHTML = `<div class="note-warning">${escapeHtml(d.error)}</div>`; return; }
    if (d.status === 'TIDAK_DIKENALI') {
        const daftar = document.querySelector('[data-on-click="bukaTambahPersonel"]');
        wadah.innerHTML = `<div class="section-box border-2 border-amber-300 p-5">
            <p class="font-bold text-amber-800"><i class="fa-solid fa-circle-question mr-1"></i> Wajah tidak dikenali</p>
            <p class="text-sm text-slate-600 mt-1">Scan tercatat di Logs. Bila orangnya belum terdaftar, daftarkan sekarang dengan foto ini.</p>
            ${daftar ? '<button type="button" class="btn-primary mt-3" data-on-click="daftarDariScan"><i class="fa-solid fa-user-plus mr-1"></i> Daftarkan Orang</button>' : ''}
        </div>`;
        return;
    }
    if (d.status === 'DITOLAK') {
        wadah.innerHTML = kartuOrang(d, `<div class="note-warning bg-red-50 border-red-200 text-red-700">Masuk daftar BLACKLIST. Akses ditolak dan tercatat.</div>`, 'border-red-300');
        return;
    }
    if (d.status === 'DUPLIKAT') { wadah.innerHTML = kartuOrang(d, `<div class="note-info">${escapeHtml(d.error)}</div>`); return; }
    if (d.status === 'ABSENSI') {
        const [lbl, warna] = STATUS_WAKTU[d.status_waktu] || [d.status_waktu || '', WARNA_BADGE.abu];
        wadah.innerHTML = kartuOrang(d, `<div class="flex flex-wrap items-center gap-2">
            ${badge(d.jenis === 'MASUK' ? 'MASUK' : 'KELUAR', d.jenis === 'MASUK' ? WARNA_BADGE.hijau : WARNA_BADGE.biru)}
            <span class="font-mono font-semibold">${escapeHtml(d.waktu)}</span>${badge(lbl, warna)}
            ${d.selisih_menit && d.status_waktu !== 'TEPAT_WAKTU' ? `<span class="text-xs text-slate-500">${Math.abs(d.selisih_menit)} menit</span>` : ''}</div>`, 'border-emerald-300');
        return;
    }
    // Driver / tamu
    if (d.di_dalam) {
        wadah.innerHTML = kartuOrang(d, `<p class="text-sm text-slate-600 mb-3">Masih di dalam sejak ${escapeHtml(d.masuk_sejak)}.</p>
            <button type="button" class="btn-primary" data-on-click="catatKeluar" data-arg="${d.id_personel}|${escapeHtml(d.foto_scan || '')}">
            <i class="fa-solid fa-right-from-bracket mr-1"></i> Catat Keluar</button>`, 'border-utama-300');
        return;
    }
    wadah.innerHTML = kartuOrang(d, '<p class="text-sm text-slate-600">Isi data kunjungan di bawah, lalu Catat Masuk.</p>', 'border-utama-300');
    const form = document.getElementById('formKunjungan');
    form.elements.id_personel.value = d.id_personel;
    form.elements.foto_scan.value = d.foto_scan || '';
    form.elements.keperluan.value = d.keperluan || '';
    form.classList.remove('hidden');
    form.elements.keperluan.focus();
}

function daftarDariScan() {
    if (typeof bukaTambahDariScan === 'function') bukaTambahDariScan(fotoScan);
}

document.getElementById('formKunjungan').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.submitter;
    const data = await denganTombol(btn, () => kirimForm('/api/visitor/masuk', new FormData(e.target)));
    if (!tampilkanHasil(data)) return;
    resetHasil();
    muatScan();
});

async function catatKeluar(arg) {
    const [id, foto] = String(arg).split('|');
    const data = await kirimForm('/api/visitor/keluar', { id_personel: id, foto_scan: foto || '' });
    if (!tampilkanHasil(data)) return;
    resetHasil();
    muatScan();
}

// ===== Logs =====
const KEPALA_LOG = {
    aktivitas: ['Waktu', 'Nama', 'Jenis', 'Aktivitas', 'Hasil', 'Keperluan / Keterangan', 'Area', 'Dicatat oleh'],
    absensi: ['Nama', 'Jabatan', 'Masuk', 'Status Masuk', 'Keluar', 'Status Keluar'],
    bulanan: ['Nama', 'Jabatan', 'Hari Hadir', 'Terlambat', 'Menit Terlambat', 'Pulang Awal'],
};
const KOLOM_ANGKA = { bulanan: [2, 3, 4, 5] };

function pilihModeLog(el) {
    aktifkanChip(el);
    modeLog = el.dataset.modeLog;
    document.querySelectorAll('[data-filter-log]').forEach(x => x.classList.toggle('hidden', !x.dataset.filterLog.split(' ').includes(modeLog)));
    const angka = KOLOM_ANGKA[modeLog] || [];
    document.getElementById('kepalaLog').innerHTML = `<tr>${KEPALA_LOG[modeLog].map((k, i) =>
        `<th class="table-cell${angka.includes(i) ? ' text-right' : ''}">${k}</th>`).join('')}</tr>`;
    muatLogs();
}

function cariLogTunda() {
    clearTimeout(timerCariLog);
    timerCariLog = setTimeout(muatLogs, 300);
}

const badgeWaktu = s => s ? badge(...(STATUS_WAKTU[s] || [s, WARNA_BADGE.abu])) : '<span class="text-slate-300">–</span>';

async function muatLogs() {
    const tbody = document.getElementById('tabelLog');
    const n = KEPALA_LOG[modeLog].length;
    let url;
    if (modeLog === 'aktivitas') {
        const p = new URLSearchParams({ tanggal: document.getElementById('logTanggal').value, jenis: document.getElementById('logJenis').value,
                                        status: document.getElementById('logStatus').value, cari: document.getElementById('logCari').value.trim() });
        url = `/api/visitor/logs?${p}`;
    } else if (modeLog === 'absensi') url = `/api/visitor/absensi?tanggal=${document.getElementById('logTanggal').value}`;
    else url = `/api/visitor/absensi/bulanan?bulan=${document.getElementById('logBulan').value}`;
    const data = await ambilJson(url);
    if (data.error) { tbody.innerHTML = barisKosong(n, data.error); return; }
    if (modeLog === 'aktivitas') {
        tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell font-mono whitespace-nowrap">${escapeHtml(r.jam)}</td>
            <td class="table-cell">${r.nama_personel ? escapeHtml(r.nama_personel) : '<span class="text-slate-400">Tidak dikenal</span>'}
                ${r.foto_scan ? ` <a href="${escapeHtml(urlBerkas(r.foto_scan))}" target="_blank" class="text-utama-600" title="Foto saat scan"><i class="fa-solid fa-image"></i></a>` : ''}</td>
            <td class="table-cell">${r.kategori ? badgeKategori(r.kategori) : '<span class="text-slate-300">–</span>'}</td>
            <td class="table-cell">${r.jenis ? escapeHtml(r.jenis === 'MASUK' ? 'Masuk' : 'Keluar') : '<span class="text-slate-300">–</span>'}
                ${r.status_waktu ? ` ${badgeWaktu(r.status_waktu)}` : ''}</td>
            <td class="table-cell">${badge(r.nama_status, WARNA_STATUS_SCAN[r.status] || WARNA_BADGE.abu)}</td>
            <td class="table-cell text-slate-600">${escapeHtml([r.keterangan, r.nama_dituju && `bertemu ${r.nama_dituju}`, r.no_plat].filter(Boolean).join(' · ') || '–')}</td>
            <td class="table-cell text-slate-600">${escapeHtml(r.area || '–')}</td>
            <td class="table-cell text-slate-600">${escapeHtml(r.dicatat_oleh || '–')}</td></tr>`).join('') || barisKosong(n, 'Belum ada aktivitas');
    } else if (modeLog === 'absensi') {
        tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td><td class="table-cell text-slate-600">${escapeHtml(r.peran || '–')}</td>
            <td class="table-cell font-mono">${escapeHtml(r.jam_masuk || '–')}</td><td class="table-cell">${badgeWaktu(r.status_masuk)}</td>
            <td class="table-cell font-mono">${escapeHtml(r.jam_pulang || '–')}</td><td class="table-cell">${badgeWaktu(r.status_pulang)}</td></tr>`).join('')
            || barisKosong(n, 'Belum ada karyawan');
    } else {
        tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td><td class="table-cell text-slate-600">${escapeHtml(r.peran || '–')}</td>
            <td class="table-cell text-right font-mono">${r.hari_hadir}</td><td class="table-cell text-right font-mono">${r.jml_terlambat}</td>
            <td class="table-cell text-right font-mono">${r.menit_terlambat}</td><td class="table-cell text-right font-mono">${r.jml_pulang_awal}</td></tr>`).join('')
            || barisKosong(n, 'Belum ada absensi bulan ini');
    }
}
