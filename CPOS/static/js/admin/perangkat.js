// ===== ADMIN > PERANGKAT / KIOSK =====
let daftarPos = [];
let modeUbahPos = false;

document.addEventListener('DOMContentLoaded', muatPerangkat);

async function muatPerangkat() {
    const data = await ambilJson('/api/admin/perangkat');
    const tbody = document.getElementById('tabelPos');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return false; }
    daftarPos = data.perangkat;

    const t = data.timbangan;
    const elT = document.getElementById('statTimbangan');
    elT.textContent = `${t.terhubung} / ${t.jumlah}`;
    elT.className = `stat-value ${t.jumlah && t.terhubung === t.jumlah ? 'text-emerald-600' : 'text-red-600'}`;
    document.getElementById('statTimbanganInfo').textContent = 'Port serial yang sedang dibaca server';
    tampilkanJembatan(data.jembatan || []);
    document.getElementById('statJumlahPos').textContent = daftarPos.length;
    document.getElementById('statPosAktif').textContent = `${daftarPos.filter(p => p.is_active).length} aktif`;
    const elEnv = document.getElementById('statTokenEnv');
    elEnv.textContent = data.token_env ? 'Dipakai' : 'Kosong';
    elEnv.className = `stat-value ${data.token_env ? 'text-amber-600' : 'text-slate-800'}`;

    tbody.innerHTML = daftarPos.map(p => `
        <tr class="hover:bg-slate-50${p.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(p.id_pos)}</td>
            <td class="table-cell">${escapeHtml(p.nama)}</td>
            <td class="table-cell">${escapeHtml(p.area || '-')}${p.lokasi ? `<span class="text-slate-400"> · ${escapeHtml(p.lokasi)}</span>` : ''}</td>
            <td class="table-cell">${badgeAktif(p.is_active)}</td>
            <td class="table-cell">${p.terakhir_detik == null ? '<span class="text-slate-400">Belum terhubung</span>'
                : `${durasiSingkat(p.terakhir_detik)} lalu`}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(p.ip || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaPos" data-arg="${escapeHtml(p.id_pos)}">Ubah</button>
                <button type="button" class="link-aksi text-amber-700" data-on-click="gantiTokenPos" data-arg="${escapeHtml(p.id_pos)}">Ganti Token</button>
                <button type="button" class="link-aksi ${p.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifPos"
                    data-arg="${escapeHtml(p.id_pos)}">${p.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td>
        </tr>`).join('') || barisKosong(7, 'Belum ada pos kiosk. Tambah pos agar setiap kiosk punya token sendiri.');
}

function bukaPos(idPos) {
    const form = document.getElementById('formPos');
    const p = daftarPos.find(x => x.id_pos === idPos);
    modeUbahPos = !!p;
    form.reset();
    if (p) isiForm(form, p);
    form.elements.id_pos.readOnly = modeUbahPos;
    form.elements.id_pos.classList.toggle('bg-slate-50', modeUbahPos);
    document.getElementById('judulModalPos').textContent = p ? 'Ubah Pos Kios' : 'Tambah Pos Kios';
    openModal('modalPos');
    (p ? form.elements.nama : form.elements.id_pos).focus();
}

document.getElementById('formPos').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, modeUbahPos ? '/api/admin/perangkat/ubah' : '/api/admin/perangkat/tambah', {
        modal: 'modalPos',
        setelahnya: data => { muatPerangkat(); if (data.token) tampilkanToken(data.id_pos, data.token); },
    });
});

function tampilkanToken(idPos, token) {
    document.getElementById('isiEnvKiosk').textContent =
        `KIOSK_ID=${idPos}\nKIOSK_TOKEN=${token}\nWEIGHBRIDGE_URL=${location.origin}`;
    openModal('modalToken');
}

// Clipboard API hanya ada di HTTPS / localhost; admin yang dibuka lewat http://IP memakai cara lama (execCommand)
async function salinTokenKiosk() {
    const el = document.getElementById('isiEnvKiosk');
    const teks = el.textContent;
    try {
        await navigator.clipboard.writeText(teks);
        Notif.sukses('Berhasil disalin');
        return;
    } catch (e) { /* lanjut ke cara lama */ }
    const area = document.createElement('textarea');
    area.value = teks;
    area.setAttribute('readonly', '');
    area.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    el.closest('.modal-box').appendChild(area);         // di dalam modal supaya fokus tidak keluar dari dialog
    area.select();
    let berhasil = false;
    try { berhasil = document.execCommand('copy'); } catch (e) { berhasil = false; }
    area.remove();
    if (berhasil) { Notif.sukses('Berhasil disalin'); return; }
    window.getSelection().selectAllChildren(el);           // tetap gagal: teks diblok, tinggal Ctrl+C
    Notif.peringatan('Browser menolak penyalinan otomatis. Teks sudah diblok, tekan Ctrl+C.');
}

async function gantiTokenPos(idPos) {
    const ok = await Dialog.konfirmasi({
        judul: 'Ganti token?', pesan: `Token lama pos ${idPos} langsung tidak berlaku. Kios itu berhenti sampai .env-nya diisi token baru.`,
        teksYa: 'Ganti Token', bahaya: true,
    });
    if (!ok) return;
    const data = await kirimForm('/api/admin/perangkat/ganti-token', { id_pos: idPos });
    if (tampilkanHasil(data)) tampilkanToken(data.id_pos, data.token);
}

function ubahAktifPos(idPos) {
    const p = daftarPos.find(x => x.id_pos === idPos);
    konfirmasiAktif({
        url: '/api/admin/perangkat/aktif', data: { id_pos: idPos }, aktif: !p.is_active, nama: `Pos ${idPos}`, jenis: 'pos kiosk',
        pesanNonaktif: 'Kios di pos ini ditolak server sampai diaktifkan lagi.', setelahnya: muatPerangkat,
    });
}

// ===== JEMBATAN TIMBANG =====
let daftarJembatan = [];

function tampilkanJembatan(data) {
    daftarJembatan = data;
    const baris = (label, nilai, mono = true) => `<div class="flex items-start justify-between gap-3 text-sm">
        <span class="text-slate-500 flex-shrink-0">${label}</span><span class="${mono ? 'font-mono font-semibold ' : ''}text-slate-800 text-right">${nilai}</span></div>`;
    document.getElementById('tabelJembatan').innerHTML = data.map(j => {
        const st = j.status;
        const [status, warna] = !j.is_active ? ['NONAKTIF', 'text-slate-500 bg-slate-100 border-slate-200']
            : !st ? ['TIDAK DIBACA', 'text-slate-500 bg-slate-100 border-slate-200']
            : st.terhubung ? ['ONLINE', 'text-emerald-700 bg-emerald-50 border-emerald-200'] : ['TERPUTUS', 'text-red-700 bg-red-50 border-red-200'];
        const live = st && st.terhubung ? `${escapeHtml(st.berat)} kg${st.siap_kunci ? ' · stabil' : ''}`
            : `<span class="font-sans font-normal text-slate-400" title="${escapeHtml((st && st.error) || '')}">${st ? 'tidak terhubung' : '-'}</span>`;
        return `<div class="rounded-xl border border-slate-200 p-5${j.is_active ? '' : ' opacity-60'}">
            <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <p class="font-bold text-slate-900">${escapeHtml(j.kode)} · ${escapeHtml(j.nama)}</p>
                    <p class="text-xs font-mono text-slate-500">${escapeHtml(j.area)} · mode ${escapeHtml(j.mode)}</p>
                </div>
                <span class="text-[11px] font-bold px-2 py-0.5 rounded border flex-shrink-0 ${warna}">● ${status}</span>
            </div>
            <div class="mt-4 rounded-lg bg-slate-50 border border-slate-100 p-3 space-y-1.5">
                ${baris('Sambungan', j.mode === 'AGEN' ? `Agen ID ${j.id_jembatan} · ${escapeHtml(j.port)}` : escapeHtml(j.port))}
                ${baris('Serial', `${Number(j.baudrate)}-${j.data_bits}-${escapeHtml(j.parity)}-${Number(j.stop_bits)}`)}
                ${baris('Format data', escapeHtml(j.format_data))}
                ${baris('Berat saat ini', live)}
            </div>
            <div class="flex flex-wrap items-center justify-end gap-3 mt-3">
                ${j.is_active ? `<button type="button" class="btn-light btn-sm" data-on-click="bukaMentah" data-arg="${j.id_jembatan}"><i class="fa-solid fa-wave-square"></i> Data mentah</button>` : ''}
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaJembatan" data-arg="${j.id_jembatan}">Ubah</button>
                <button type="button" class="link-aksi ${j.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifJembatan"
                    data-arg="${j.id_jembatan}">${j.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </div>
        </div>`;
    }).join('') || '<p class="text-sm text-slate-400 text-center py-6 lg:col-span-2">Belum ada jembatan timbang</p>';
}

function bukaJembatan(id) {
    const form = document.getElementById('formJembatan');
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    form.reset();
    isiForm(form, j ? { ...j, stop_bits: String(Number(j.stop_bits)), pola: j.pola || '' }
                    : { id_jembatan: '', mode: 'AGEN', baudrate: 9600, data_bits: 7, parity: 'E', stop_bits: '1', format_data: 'ST_GS',
                        faktor: 1, toleransi_kg: 5, durasi_stabil: 3, berat_min_kg: 100, wajib_st: false });
    aturModeJembatan();
    document.getElementById('judulModalJembatan').textContent = j ? `Ubah Jembatan ${j.kode}` : 'Tambah Jembatan Timbang';
    openModal('modalJembatan');
    document.getElementById('jtKode').focus();
}

function aturModeJembatan() {
    const agen = document.getElementById('jtMode').value === 'AGEN';
    document.getElementById('jtPortHint').textContent = agen
        ? 'COM di PC jembatan (lihat Device Manager › Ports di PC itu)'
        : 'COM di PC server ini, atau socket://IP:PORT untuk alat serial-to-LAN';
    document.getElementById('jtPolaBox').classList.toggle('hidden', document.getElementById('jtFormat').value !== 'POLA');
}

// ===== DATA MENTAH: menyetel baudrate / parity / format di lokasi =====
let timerMentah = null;

function bukaMentah(id) {
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    document.getElementById('judulMentah').textContent = `Data mentah ${j.kode} (${j.port} ${j.baudrate} ${j.data_bits}${j.parity}${Number(j.stop_bits)} · ${j.format_data})`;
    document.getElementById('tabelMentah').innerHTML = '';
    openModal('modalMentah');
    muatMentah(id);
    clearInterval(timerMentah);
    timerMentah = setInterval(() => muatMentah(id), 1000);
}

function tutupMentah() {
    clearInterval(timerMentah);
    closeModal('modalMentah');
    muatPerangkat();
}

async function muatMentah(id) {
    const data = await ambilJson(`/api/admin/jembatan/${id}/mentah`);
    const status = document.getElementById('statusMentah');
    if (data.error) { status.innerHTML = `<span class="text-red-600">${escapeHtml(data.error)}</span>`; return; }
    const st = data.status;
    status.innerHTML = st.terhubung
        ? `<span class="text-emerald-600 font-semibold">Terhubung</span> · berat <b>${escapeHtml(st.berat)} kg</b>
           ${st.siap_kunci ? '· <span class="text-emerald-600">stabil, boleh disimpan</span>' : '· belum stabil'}
           ${st.detik_sejak_data != null ? `· data terakhir ${st.detik_sejak_data} detik lalu` : ''}`
        : `<span class="text-red-600 font-semibold">Tidak terhubung</span> · ${escapeHtml(st.error || '-')}`;
    document.getElementById('tabelMentah').innerHTML = data.baris.map(b => `
        <tr><td class="table-cell">${escapeHtml(b.waktu)}</td><td class="table-cell whitespace-pre">${escapeHtml(JSON.stringify(b.teks))}</td>
            <td class="table-cell text-right">${b.berat == null ? '<span class="text-red-600">tidak terbaca</span>' : escapeHtml(b.berat)}</td>
            <td class="table-cell">${b.stabil ? 'ST' : ''}</td></tr>`).join('')
        || barisKosong(4, data.sisa_buffer ? `Belum ada bingkai utuh. Sisa diterima: ${JSON.stringify(data.sisa_buffer)}` : 'Belum ada data diterima');
}

document.getElementById('formJembatan').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/jembatan/simpan', { modal: 'modalJembatan', setelahnya: muatPerangkat });
});

function ubahAktifJembatan(id) {
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    konfirmasiAktif({
        url: `/api/admin/jembatan/${id}/aktif`, aktif: !j.is_active, nama: `Jembatan ${j.kode}`, jenis: 'jembatan timbang',
        pesanNonaktif: 'Tidak bisa dipilih lagi di PC operator timbang.', setelahnya: muatPerangkat,
    });
}

// ===== GATEWAY VIDEO & KAMERA CCTV (Monitoring CCTV, routes/cctv.py) =====
let dataCctv = { gateway: [], kamera: [], jembatan: [], titik: {}, peran: {}, ai: {} };

document.addEventListener('DOMContentLoaded', muatCctv);

async function muatCctv() {
    const data = await ambilJson('/api/admin/cctv');
    const tGw = document.getElementById('tabelGateway'), tKam = document.getElementById('tabelKamera');
    if (data.error) { tGw.innerHTML = barisKosong(7, data.error); tKam.innerHTML = barisKosong(9, data.error); return; }
    dataCctv = data;
    const opsi = obj => Object.entries(obj).map(([k, v]) => `<option value="${k}">${escapeHtml(v)}</option>`).join('');
    // Pilihan tetap: diisi sekali saja (mengisi ulang saat form terbuka akan mengganti pilihan yang sedang dipakai)
    [['kamTitik', data.titik], ['kamPeran', data.peran], ['kamAi', data.ai]].forEach(([id, isi]) => {
        const sel = document.getElementById(id);
        if (!sel.options.length || sel.options.length === 1 && !sel.options[0].value) sel.innerHTML = opsi(isi);
    });
    tGw.innerHTML = data.gateway.map(g => `
        <tr class="hover:bg-slate-50${g.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-semibold">${escapeHtml(g.nama)}</td><td class="table-cell">${escapeHtml(g.area)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(g.url)}</td><td class="table-cell text-right font-mono">${g.jumlah_kamera}</td>
            <td class="table-cell">${escapeHtml(g.terakhir || 'Belum terhubung')}</td><td class="table-cell text-center">${badgeAktif(g.is_active)}</td>
            <td class="table-cell text-right"><button type="button" class="link-aksi text-blue-600" data-on-click="bukaGateway" data-arg="${g.id_gateway}">Ubah</button></td>
        </tr>`).join('') || barisKosong(7, 'Belum ada gateway video. Pasang go2rtc di server cabang / HO, lalu tambahkan di sini.');
    tKam.innerHTML = data.kamera.map(k => `
        <tr class="hover:bg-slate-50${k.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono font-semibold">${escapeHtml(k.kode)}</td><td class="table-cell">${escapeHtml(k.nama)}</td>
            <td class="table-cell">${escapeHtml(k.area)}</td>
            <td class="table-cell">${escapeHtml(data.titik[k.titik] || k.titik)}${k.jembatan ? `<span class="text-slate-400"> · ${escapeHtml(k.jembatan)}</span>` : ''}</td>
            <td class="table-cell">${escapeHtml(data.peran[k.peran] || k.peran)}</td><td class="table-cell text-slate-600">${escapeHtml(k.merk || '-')}</td>
            <td class="table-cell">${badge(data.ai[k.ai] || k.ai, k.ai === 'NONE' ? WARNA_BADGE.abu : 'bg-violet-100 text-violet-700')}</td>
            <td class="table-cell text-center">${!k.is_active ? badgeAktif(false) : k.terakhir ? badge('Terhubung ' + k.terakhir.slice(5), WARNA_BADGE.hijau)
                : badge('Belum dites', WARNA_BADGE.oranye)}</td>
            <td class="table-cell text-right"><button type="button" class="link-aksi text-blue-600" data-on-click="bukaKamera" data-arg="${k.id_kamera}">Ubah</button></td>
        </tr>`).join('') || barisKosong(9, 'Belum ada kamera');
}

function bukaGateway(id) {
    const form = document.getElementById('formGateway');
    const g = dataCctv.gateway.find(x => x.id_gateway === Number(id));
    form.reset();
    document.getElementById('gwHasilTes').textContent = '';
    if (g) isiForm(form, { id_gateway: g.id_gateway, nama: g.nama, id_comp_area: g.id_comp_area, url: g.url });
    else form.elements.id_gateway.value = '';
    form.elements.is_active.checked = g ? !!g.is_active : true;
    document.getElementById('judulModalGateway').textContent = g ? 'Ubah Gateway Video' : 'Tambah Gateway Video';
    openModal('modalGateway');
}

async function tesGateway(btn) {
    const hasil = document.getElementById('gwHasilTes');
    const data = await denganTombol(btn, () => kirimForm('/api/admin/cctv/gateway/tes', { url: document.getElementById('gwUrl').value.trim() }), 'Menguji...');
    hasil.className = `field-hint ${data.error ? 'text-red-600' : 'text-emerald-700'}`;
    hasil.textContent = data.error || data.message;
}

function dataFormCctv(form) {
    const fd = new FormData(form);
    fd.set('is_active', form.elements.is_active.checked ? '1' : '0');
    return fd;
}

document.getElementById('formGateway').addEventListener('submit', async e => {
    e.preventDefault();
    const data = await denganTombol(e.submitter, () => kirimForm('/api/admin/cctv/gateway', dataFormCctv(e.target)));
    if (!tampilkanHasil(data)) return;
    closeModal('modalGateway');
    muatCctv();
});

function aturPilihanKamera(pilihGateway, pilihJembatan) {
    const area = document.getElementById('kamArea').value;
    const gw = document.getElementById('kamGateway');
    const lamaGw = typeof pilihGateway === 'number' ? String(pilihGateway) : gw.value;
    gw.innerHTML = dataCctv.gateway.filter(g => String(g.id_comp_area) === area && g.is_active)
        .map(g => `<option value="${g.id_gateway}">${escapeHtml(g.nama)}</option>`).join('') || '<option value="">-- Belum ada gateway di area ini --</option>';
    if ([...gw.options].some(o => o.value === lamaGw)) gw.value = lamaGw;
    const jb = document.getElementById('kamJembatan');
    const lamaJb = typeof pilihJembatan === 'number' ? String(pilihJembatan) : jb.value;
    jb.innerHTML = '<option value="">-- Pilih --</option>' + dataCctv.jembatan.filter(j => String(j.id_comp_area) === area)
        .map(j => `<option value="${j.id}">${escapeHtml(j.nama)}</option>`).join('');
    if ([...jb.options].some(o => o.value === lamaJb)) jb.value = lamaJb;
    const jembatan = document.getElementById('kamTitik').value === 'JEMBATAN';
    document.getElementById('blokKamJembatan').classList.toggle('hidden', !jembatan);
    if (!jembatan) jb.value = '';
}

let idKameraTes = null;
function bukaKamera(id) {
    const form = document.getElementById('formKamera');
    const k = dataCctv.kamera.find(x => x.id_kamera === Number(id));
    form.reset();
    idKameraTes = k ? k.id_kamera : null;
    if (k) isiForm(form, { id_kamera: k.id_kamera, kode: k.kode, nama: k.nama, id_comp_area: k.id_comp_area, titik: k.titik, peran: k.peran,
                           merk: k.merk || '', stream_utama: k.stream_utama, stream_ringan: k.stream_ringan || '', ai: k.ai, urutan: k.urutan });
    else form.elements.id_kamera.value = '';
    form.elements.is_active.checked = k ? !!k.is_active : true;
    aturPilihanKamera(k ? k.id_gateway : null, k ? k.id_jembatan : null);
    document.getElementById('judulModalKamera').textContent = k ? `Ubah Kamera · ${k.kode}` : 'Tambah Kamera';
    document.getElementById('btnTesKamera').disabled = !k;
    document.getElementById('kamTesGambar').classList.add('hidden');
    document.getElementById('kamTesPesan').classList.remove('hidden');
    document.getElementById('kamTesPesan').textContent = k ? 'Klik Tes Koneksi' : 'Simpan dulu, lalu Tes Koneksi';
    openModal('modalKamera');
}

async function tesKamera() {
    if (!idKameraTes) return;
    const img = document.getElementById('kamTesGambar'), pesan = document.getElementById('kamTesPesan');
    pesan.textContent = 'Mengambil gambar...';
    pesan.classList.remove('hidden'); img.classList.add('hidden');
    const r = await fetch(`/api/admin/cctv/kamera/${idKameraTes}/tes?t=${Date.now()}`);
    if (!r.ok) { pesan.textContent = (await r.json().catch(() => ({}))).error || 'Kamera tidak terhubung'; return; }
    img.src = URL.createObjectURL(await r.blob());
    img.classList.remove('hidden'); pesan.classList.add('hidden');
}

document.getElementById('formKamera').addEventListener('submit', async e => {
    e.preventDefault();
    const data = await denganTombol(e.submitter, () => kirimForm('/api/admin/cctv/kamera', dataFormCctv(e.target)));
    if (!tampilkanHasil(data)) return;
    closeModal('modalKamera');
    muatCctv();
});
