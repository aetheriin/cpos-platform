// ===== ADMIN > PERANGKAT / KIOSK =====
let daftarPos = [];
let modeUbahPos = false;
let dataKameraPlat = { kamera: [], facing: {}, view_position: {} };

document.addEventListener('DOMContentLoaded', muatKameraPlat);
document.addEventListener('DOMContentLoaded', muatPerangkat);

async function muatPerangkat() {
    const data = await ambilJson('/api/admin/perangkat');
    const tbody = document.getElementById('tabelPos');
    if (data.error) { tbody.innerHTML = barisGagal(7, data.error); return false; }
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

// ===== KAMERA DETEKSI PLAT (RTSP langsung, dibaca backend deteksi; routes/deteksi_plat.py) =====

async function muatKameraPlat() {
    const tbody = document.getElementById('tabelKameraPlat');
    const data = await ambilJson('/api/admin/deteksi-plat/kamera');

    if (data.error) {
        tbody.innerHTML = barisGagal(6, data.error);
        return;
    }

    dataKameraPlat = data;
    tbody.innerHTML = data.kamera.map(k => `
        <tr class="hover:bg-slate-50${k.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono font-semibold">
                ${escapeHtml(k.nama)}
            </td>
            <td class="table-cell">${escapeHtml(k.company || '-')}</td>
            <td class="table-cell">${escapeHtml(k.area_name || '-')}</td>
            <td class="table-cell font-mono text-xs">
                ${escapeHtml(k.rtsp_tersamar || '-')}
            </td>
            <td class="table-cell text-center">
                ${k.is_active
                    ? badge('Aktif', WARNA_BADGE.hijau)
                    : badge('Nonaktif', WARNA_BADGE.abu)}   
            </td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600"
                    data-on-click="bukaKameraPlat"
                    data-arg="${k.id_kamera}">Ubah</button>

                <button type="button"
                    class="link-aksi ${k.is_active ? 'text-emerald-600' : 'text-red-600'}"
                    data-on-click="ubahAktifKameraPlat"
                    data-arg="${k.id_kamera}"
                    title="${k.is_active ? 'Nonaktifkan kamera' : 'Aktifkan kamera'}"
                    aria-label="${k.is_active ? 'Nonaktifkan kamera' : 'Aktifkan kamera'}">
                    <i class="fa-solid ${k.is_active ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
                </button>   
            </td>
        </tr>
    `).join('') || barisKosong(6, 'Belum ada kamera deteksi plat.');
}

function filterAreaKameraPlat(idCompany) {
    const area = document.getElementById('kpArea');

    for (const opsi of area.options) {
        if (!opsi.value) continue;

        const cocok = Boolean(idCompany)
            && opsi.dataset.company === String(idCompany);

        opsi.hidden = !cocok;
        opsi.disabled = !cocok;
    }

    area.disabled = !idCompany;

    const pilihanAktif = area.selectedOptions[0];
    if (
        pilihanAktif?.value
        && pilihanAktif.dataset.company !== String(idCompany)
    ) {
        area.value = '';
    }

    if (!idCompany && !area.value) {
        area.value = '';
    }
}

document.getElementById('kpCompany')
    .addEventListener('change', e => {
        filterAreaKameraPlat(e.target.value);
    });

async function ubahAktifKameraPlat(id) {
    const k = dataKameraPlat.kamera.find(
        x => x.id_kamera === Number(id)
    );

    if (!k) {
        Notif.gagal('Data kamera tidak ditemukan. Muat ulang daftar kamera.');
        return;
    }

    const formData = new FormData();
    formData.set('id_kamera', k.id_kamera);
    formData.set('nama', k.nama);
    formData.set('id_comp_area', k.id_comp_area);

    // Konfigurasi ini tetap dikirim dan disimpan untuk kebutuhan deteksi.
    formData.set('gate', k.gate || '');
    formData.set('facing', k.facing || 'MASUK');
    formData.set('view_position', k.view_position || '');
    formData.set('catatan', k.catatan || '');
    formData.set('urutan', k.urutan ?? 0);

    // RTSP kosong saat mengubah berarti alamat yang tersimpan tetap dipakai.
    formData.set('rtsp', '');
    formData.set('is_active', k.is_active ? '0' : '1');

    const hasil = await kirimForm(
        '/api/admin/deteksi-plat/kamera',
        formData
    );

    if (!tampilkanHasil(hasil)) return;

    await muatKameraPlat();
}

function bukaKameraPlat(id) {
    const form = document.getElementById('formKameraPlat');
    const k = dataKameraPlat.kamera.find(x => x.id_kamera === Number(id));
    form.reset();
    const companySelect = document.getElementById('kpCompany');
    const areaSelect = document.getElementById('kpArea');

    const areaTersimpan = k
        ? [...areaSelect.options].find(
            opsi => opsi.value === String(k.id_comp_area)
        )
        : null;

    companySelect.value = areaTersimpan?.dataset.company || '';
    filterAreaKameraPlat(companySelect.value);
    if (k) isiForm(form, { id_kamera: k.id_kamera, nama: k.nama, id_comp_area: k.id_comp_area, gate: k.gate || '', facing: k.facing,
                           view_position: k.view_position || '', catatan: k.catatan || '', urutan: k.urutan });
    else form.elements.id_kamera.value = '';
    form.elements.rtsp.placeholder = k ? k.rtsp_tersamar : 'rtsp://cpos_view:PASSWORD@192.168.10.31:554/Streaming/Channels/101';
    form.elements.is_active.value =
        k && !k.is_active ? '0' : '1';
    document.getElementById('judulModalKameraPlat').textContent = k ? `Ubah Kamera · ${k.nama}` : 'Tambah Kamera Deteksi Plat';
    openModal('modalKameraPlat');
}

function dataFormPlat(form) {
    return new FormData(form);
}

document.getElementById('formKameraPlat').addEventListener('submit', async e => {
    e.preventDefault();
    const data = await denganTombol(e.submitter, () => kirimForm('/api/admin/deteksi-plat/kamera', dataFormPlat(e.target)));
    if (!tampilkanHasil(data)) return;
    closeModal('modalKameraPlat');
    muatKameraPlat();
});