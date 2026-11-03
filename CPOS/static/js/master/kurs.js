// ===== DATA MASTER > KURS MATA UANG =====
// Tabel & form tambah memakai js/master/referensi.js (jenis "kurs"); di sini: tombol "Ambil dari internet" di form, dan impor Excel / CSV.

// Dipanggil referensi.js setelah form kurs dibuat: tombol saran kurs ECB untuk mata uang & tanggal yang dipilih
function pasangSaranKurs() {
    const kurs = document.getElementById('ref_kurs');
    if (!kurs || document.getElementById('btnSaranKurs')) return;
    kurs.insertAdjacentHTML('afterend', `<div class="flex items-center gap-2 mt-1.5">
        <button type="button" id="btnSaranKurs" class="btn-light btn-sm" data-on-click="ambilSaranKurs">
            <i class="fa-solid fa-globe mr-1"></i> Ambil dari internet</button>
        <span id="infoSaranKurs" class="text-xs text-slate-500"></span></div>`);
}

async function ambilSaranKurs() {
    const info = document.getElementById('infoSaranKurs');
    const p = new URLSearchParams({ id_mata_uang: document.getElementById('ref_id_mata_uang').value,
                                    tanggal: document.getElementById('ref_tanggal').value });
    info.textContent = 'Mengambil...';
    const data = await ambilJson(`/api/master/kurs/internet?${p}`);
    if (data.error) { info.textContent = ''; Notif.gagal(data.error); return; }
    document.getElementById('ref_kurs').value = data.kurs;
    const sumber = document.getElementById('ref_sumber');
    if (sumber && !sumber.value) sumber.value = 'INTERNET';
    info.textContent = `Kurs ECB ${data.kode} per ${data.tanggal.split('-').reverse().join('/')}. Periksa sebelum disimpan.`;
}

// ===== IMPOR =====
let hasilImporKurs = null;

function bukaImporKurs() {
    document.getElementById('berkasKurs').value = '';
    document.getElementById('hasilImporKurs').classList.add('hidden');
    document.getElementById('btnSimpanImporKurs').disabled = true;
    hasilImporKurs = null;
    openModal('modalImporKurs');
}

function labelRef(kunci, id) {
    if (id === null || id === undefined || id === '') return '-';
    return typeof labelPilihan === 'function' && dataRef.kurs ? labelPilihan(dataRef.kurs, kunci, id) : String(id);
}

async function kirimImporKurs(simpan) {
    const file = document.getElementById('berkasKurs').files[0];
    if (!file) { Notif.peringatan('Pilih berkas .xlsx atau .csv'); return null; }
    const fd = new FormData();
    fd.append('berkas', file);
    fd.append('simpan', simpan ? '1' : '0');
    return kirimForm('/api/master/kurs/impor', fd);
}

async function periksaImporKurs(btn) {
    const data = await denganTombol(btn, () => kirimImporKurs(false));
    if (!data) return;
    if (data.error) { Notif.gagal(data.error); return; }
    hasilImporKurs = data.baris;
    const ok = data.baris.filter(r => !r.galat).length;
    const galat = data.baris.length - ok;
    const awas = data.baris.filter(r => !r.galat && r.peringatan).length;
    document.getElementById('ringkasImporKurs').innerHTML = `${ok} baris siap disimpan` +
        (galat ? ` · <span class="text-red-600">${galat} baris ditolak (tidak ikut disimpan)</span>` : '') +
        (awas ? ` · <span class="text-amber-700">${awas} perlu diperiksa</span>` : '');
    document.getElementById('tabelImporKurs').innerHTML = data.baris.map(r => `
        <tr class="${r.galat ? 'bg-red-50' : ''}">
            <td class="table-cell font-mono text-xs">${r.baris}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.tanggal ? r.tanggal.split('-').reverse().join('/') : '-')}</td>
            <td class="table-cell">${escapeHtml(labelRef('id_mata_uang', r.id_mata_uang))}</td>
            <td class="table-cell text-right tabular-nums">${r.kurs != null ? Number(r.kurs).toLocaleString('id-ID', { maximumFractionDigits: 4 }) : '-'}</td>
            <td class="table-cell">${escapeHtml(labelRef('jenis', r.jenis))}</td>
            <td class="table-cell">${escapeHtml(r.id_company ? labelRef('id_company', r.id_company) : (r.galat ? '-' : 'Semua'))}</td>
            <td class="table-cell text-xs">${r.galat ? `<span class="text-red-700">${escapeHtml(r.galat)}</span>`
                : r.peringatan ? `<span class="text-amber-700">Periksa: ${escapeHtml(r.peringatan)}</span>` : '<span class="text-emerald-700">Siap</span>'}</td>
        </tr>`).join('') || barisKosong(7, 'Tidak ada baris data');
    document.getElementById('hasilImporKurs').classList.remove('hidden');
    const tombol = document.getElementById('btnSimpanImporKurs');
    tombol.disabled = ok === 0;
    tombol.textContent = ok ? `Simpan ${ok} kurs` : 'Simpan';
}

async function simpanImporKurs(btn) {
    if (!hasilImporKurs) return;
    const data = await denganTombol(btn, () => kirimImporKurs(true));
    if (!tampilkanHasil(data)) return;
    closeModal('modalImporKurs');
    muatRef('kurs');
}
