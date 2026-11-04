// ===== DATA MASTER > KURS MATA UANG =====
// Tabel & form tambah memakai js/master/referensi.js (jenis "kurs"); di sini: tombol "Ambil dari internet" di form, dan impor Excel / CSV.

// Sumber yang kursnya bisa diambil otomatis lewat API -> label tombol. Form tambah hanya menawarkan sumber ini dan Manual;
// JISDOR, kurs pajak, dan kurs bank (tanpa API) hanya dipakai sebagai label asal kurs saat impor Excel.
const SUMBER_OTOMATIS = { INTERNET: 'Ambil kurs dari internet' };
const SUMBER_FORM = ['', ...Object.keys(SUMBER_OTOMATIS), 'MANUAL'];

// Dipanggil referensi.js setelah form kurs dibuat: petunjuk mata uang belum terdaftar, dan tombol ambil kurs
// yang hanya muncul bila sumber yang dipilih bisa diambil otomatis
function pasangSaranKurs() {
    const kurs = document.getElementById('ref_kurs');
    if (!kurs || document.getElementById('btnSaranKurs')) return;
    kurs.insertAdjacentHTML('afterend', `<div id="saranKurs" class="items-center gap-2 mt-1.5" style="display:none">
        <button type="button" id="btnSaranKurs" class="btn-light btn-sm whitespace-nowrap shrink-0" data-on-click="ambilSaranKurs"></button>
        <span id="infoSaranKurs" class="text-xs text-slate-500"></span></div>`);
    document.getElementById('ref_id_mata_uang')?.insertAdjacentHTML('afterend',
        '<p class="field-hint">Tidak ada di pilihan? Tambahkan dulu di tab Mata Uang &amp; Bank (kode ISO, mis. SGD).</p>');
    const sumber = document.getElementById('ref_sumber');
    if (sumber) {
        [...sumber.options].filter(o => !SUMBER_FORM.includes(o.value)).forEach(o => o.remove());
        sumber.addEventListener('change', aturSaranKurs);
    }
    aturSaranKurs();
}

function aturSaranKurs() {
    const label = SUMBER_OTOMATIS[document.getElementById('ref_sumber')?.value];
    // style.display, bukan kelas hidden: di CSS CPOS .hidden kalah dari .flex / .inline-flex
    document.getElementById('saranKurs').style.display = label ? 'flex' : 'none';
    document.getElementById('btnSaranKurs').textContent = label || '';
    document.getElementById('infoSaranKurs').textContent = '';
}

async function ambilSaranKurs() {
    const info = document.getElementById('infoSaranKurs');
    const p = new URLSearchParams({ id_mata_uang: document.getElementById('ref_id_mata_uang').value,
                                    tanggal: document.getElementById('ref_tanggal').value });
    info.textContent = 'Mengambil...';
    const data = await ambilJson(`/api/master/kurs/internet?${p}`);
    if (data.error) { info.textContent = ''; Notif.gagal(data.error); return; }
    document.getElementById('ref_kurs').value = data.kurs;
    info.textContent = `Kurs ${data.kode} per ${data.tanggal.split('-').reverse().join('/')} (European Central Bank). Periksa sebelum disimpan.`;
}

// ===== IMPOR =====
let hasilImporKurs = null;

// Pilihan bawaan impor diambil dari pilihan form kurs (/api/master/ref/kurs)
function isiPilihanImpor(id, kunci, kosong) {
    const sel = document.getElementById(id);
    const opsi = (dataRef.kurs?.pilihan[kunci] || []).map(o => `<option value="${escapeHtml(o.id)}">${escapeHtml(o.label)}</option>`).join('');
    sel.innerHTML = (kosong !== null ? `<option value="">${escapeHtml(kosong)}</option>` : '') + opsi;
}

function bukaImporKurs() {
    const form = document.getElementById('formImporKurs');
    form.reset();
    isiPilihanImpor('imporMataUang', 'id_mata_uang', '- Dari kolom berkas -');
    isiPilihanImpor('imporJenis', 'jenis', null);
    isiPilihanImpor('imporSumber', 'sumber', '-');
    isiPilihanImpor('imporPerusahaan', 'id_company', 'Semua perusahaan');
    document.getElementById('imporJenis').value = 'TRANSAKSI';
    ubahImporKurs();
    openModal('modalImporKurs');
}

// Berkas / pilihan berubah -> hasil pemeriksaan lama tidak berlaku lagi, periksa ulang dulu
function ubahImporKurs() {
    hasilImporKurs = null;
    document.getElementById('hasilImporKurs').classList.add('hidden');
    const tombol = document.getElementById('btnSimpanImporKurs');
    tombol.disabled = true;
    tombol.textContent = 'Simpan';
}

function labelRef(kunci, id) {
    if (id === null || id === undefined || id === '') return '-';
    return dataRef.kurs ? labelPilihanRef(dataRef.kurs, kunci, id) : String(id);
}

const angkaKurs = v => Number(v).toLocaleString('id-ID', { maximumFractionDigits: 4 });

async function kirimImporKurs(simpan) {
    const form = document.getElementById('formImporKurs');
    const file = document.getElementById('berkasKurs').files[0];
    if (!file) { Notif.peringatan('Pilih berkas .xlsx atau .csv'); return null; }
    const fd = new FormData(form);
    fd.append('berkas', file);
    fd.append('simpan', simpan ? '1' : '0');
    return kirimForm('/api/master/kurs/impor', fd);
}

function hasilBaris(r) {
    if (r.galat) return `<span class="text-red-700">Ditolak: ${escapeHtml(r.galat)}</span>`;
    if (r.aksi === 'lewati') {
        return r.kurs_lama === r.kurs ? '<span class="text-slate-500">Sudah ada, sama. Dilewati</span>'
            : `<span class="text-slate-500">Sudah ada (Rp ${angkaKurs(r.kurs_lama)}). Dilewati</span>`;
    }
    const awas = r.peringatan ? ` <span class="text-amber-700">Periksa: ${escapeHtml(r.peringatan)}</span>` : '';
    if (r.aksi === 'ganti') return `<span class="text-blue-700">Mengganti Rp ${angkaKurs(r.kurs_lama)}</span>${awas}`;
    return `<span class="text-emerald-700">Baru</span>${awas}`;
}

async function periksaImporKurs(btn) {
    const data = await denganTombol(btn, () => kirimImporKurs(false));
    if (!data) return;
    if (data.error) { Notif.gagal(data.error); return; }
    hasilImporKurs = data.baris;
    const hitung = f => data.baris.filter(f).length;
    const baru = hitung(r => !r.galat && r.aksi === 'baru'), ganti = hitung(r => !r.galat && r.aksi === 'ganti');
    const lewati = hitung(r => !r.galat && r.aksi === 'lewati'), galat = hitung(r => r.galat);
    const awas = hitung(r => !r.galat && r.aksi !== 'lewati' && r.peringatan);
    document.getElementById('ringkasImporKurs').innerHTML = [
        `${baru} baru`, ganti ? `${ganti} mengganti kurs lama` : '', lewati ? `${lewati} sudah ada, dilewati` : '',
        galat ? `<span class="text-red-600">${galat} ditolak</span>` : '', awas ? `<span class="text-amber-700">${awas} perlu diperiksa</span>` : '',
    ].filter(Boolean).join(' · ');
    document.getElementById('tabelImporKurs').innerHTML = data.baris.map(r => `
        <tr class="${r.galat ? 'bg-red-50' : r.aksi === 'lewati' ? 'text-slate-400' : ''}">
            <td class="table-cell font-mono text-xs">${r.baris}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.tanggal ? r.tanggal.split('-').reverse().join('/') : '-')}</td>
            <td class="table-cell">${escapeHtml(labelRef('id_mata_uang', r.id_mata_uang))}</td>
            <td class="table-cell text-right tabular-nums">${r.kurs != null ? angkaKurs(r.kurs) : '-'}</td>
            <td class="table-cell">${escapeHtml(labelRef('jenis', r.jenis))}</td>
            <td class="table-cell">${escapeHtml(r.id_company ? labelRef('id_company', r.id_company) : (r.galat ? '-' : 'Semua'))}</td>
            <td class="table-cell text-xs">${hasilBaris(r)}</td>
        </tr>`).join('') || barisKosong(7, 'Tidak ada baris data');
    document.getElementById('hasilImporKurs').classList.remove('hidden');
    const tombol = document.getElementById('btnSimpanImporKurs');
    const jumlah = baru + ganti;
    tombol.disabled = jumlah === 0;
    tombol.textContent = jumlah ? `Simpan ${jumlah} kurs` : 'Tidak ada yang disimpan';
}

async function simpanImporKurs(btn) {
    if (!hasilImporKurs) return;
    const data = await denganTombol(btn, () => kirimImporKurs(true));
    if (!tampilkanHasil(data)) return;
    closeModal('modalImporKurs');
    muatRef('kurs');
}
