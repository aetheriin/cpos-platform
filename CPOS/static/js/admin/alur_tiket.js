// ===== ADMIN › ALUR TIKET: susunan tahap tiket + pemakaian per Area + Produk =====
// Alur = kelompok tahap berurutan; isi satu kelompok = tahap bersamaan (paralel). Security selalu pertama,
// Security Keluar opsional di akhir. Aturan sah dicek ulang di server (utils/alur.validasi_kelompok).
const TAHAP_TENGAH = ['TIMBANG_1', 'SORTASI', 'LAB', 'TIMBANG_2'];
let dataAlurTiket = { alur: [], aturan: [], tahap: [], area: [], produk: [] };

document.addEventListener('DOMContentLoaded', muatAlurTiket);

async function muatAlurTiket() {
    const data = await ambilJson('/api/admin/alur-tiket');
    if (data.error) {
        document.getElementById('tabelAlurTiket').innerHTML = barisKosong(5, data.error);
        document.getElementById('tabelAturanAlur').innerHTML = barisKosong(5, data.error);
        return;
    }
    dataAlurTiket = data;
    isiTabelAlurTiket();
    isiTabelAturanAlur();
}

function namaTahap(kode) {
    return (dataAlurTiket.tahap.find(t => t.kode === kode) || {}).nama || kode;
}

// Security → Timbang Masuk → [Sortasi | Lab] → Timbang Keluar (kelompok bersamaan dalam satu kotak)
function rantaiKelompok(kelompok) {
    const chip = kode => `<span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-700 whitespace-nowrap">${escapeHtml(namaTahap(kode))}</span>`;
    return `<div class="flex flex-wrap items-center gap-1.5">${kelompok.map((k, i) =>
        `${i ? '<i class="fa-solid fa-arrow-right text-[10px] text-slate-400"></i>' : ''}${k.length > 1
            ? `<span class="inline-flex flex-col gap-1 rounded-lg border border-dashed border-blue-300 bg-blue-50 p-1" title="Bersamaan: urutan bebas">
                   <span class="text-[10px] font-semibold uppercase tracking-wider text-blue-500 px-1">Bersamaan</span>${k.map(chip).join('')}</span>`
            : chip(k[0])}`).join('')}</div>`;
}

function isiTabelAlurTiket() {
    const tbody = document.getElementById('tabelAlurTiket');
    tbody.innerHTML = dataAlurTiket.alur.map(a => {
        const pakai = [a.dipakai_produk ? `${a.dipakai_produk} produk` : '', a.dipakai_aturan ? `${a.dipakai_aturan} aturan` : '',
                       a.dipakai_tiket ? `${a.dipakai_tiket} tiket` : ''].filter(Boolean).join(' · ');
        return `<tr class="hover:bg-slate-50 align-top">
        <td class="table-cell"><p class="font-semibold text-slate-800">${escapeHtml(a.nama)}</p>
            ${a.sistem ? `<p class="mt-0.5">${badge('Alur sistem', WARNA_BADGE.abu)}</p>` : ''}
            ${a.keterangan ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(a.keterangan)}</p>` : ''}</td>
        <td class="table-cell">${rantaiKelompok(a.kelompok)}</td>
        <td class="table-cell text-xs text-slate-500 whitespace-nowrap">${escapeHtml(pakai || '-')}</td>
        <td class="table-cell">${badgeAktif(a.is_active)}</td>
        <td class="table-cell text-right whitespace-nowrap">${a.sistem ? '' : `
            <button type="button" class="link-aksi text-blue-600" data-on-click="bukaAlurTiket" data-arg="${a.id_alur}">Ubah</button>`}
            <button type="button" class="link-aksi text-slate-600 ml-3" data-on-click="salinAlurTiket" data-arg="${a.id_alur}">Salin</button>${a.sistem ? '' : `
            <button type="button" class="link-aksi text-slate-600 ml-3" data-on-click="aktifAlurTiket" data-arg="${a.id_alur}">${a.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            <button type="button" class="link-aksi text-red-600 ml-3" data-on-click="hapusAlurTiket" data-arg="${a.id_alur}">Hapus</button>`}</td>
    </tr>`;
    }).join('') || barisKosong(5, 'Belum ada alur.', { fungsi: 'bukaAlurTiket', label: 'Tambah Alur' });
}

function isiTabelAturanAlur() {
    const tbody = document.getElementById('tabelAturanAlur');
    tbody.innerHTML = dataAlurTiket.aturan.map(r => `<tr class="hover:bg-slate-50 align-top">
        <td class="table-cell font-semibold text-slate-800 whitespace-nowrap">${escapeHtml(r.area)}</td>
        <td class="table-cell whitespace-nowrap">${r.produk ? escapeHtml(r.produk) : '<span class="text-slate-400">Semua produk</span>'}</td>
        <td class="table-cell"><p class="font-medium text-slate-700">${escapeHtml(r.alur)}${r.alur_aktif ? '' : ` ${badge('Alur nonaktif', WARNA_BADGE.abu)}`}</p>
            <div class="mt-1">${rantaiKelompok((dataAlurTiket.alur.find(a => a.id_alur === r.id_alur) || {}).kelompok || [])}</div></td>
        <td class="table-cell">${badgeAktif(r.is_active)}</td>
        <td class="table-cell text-right whitespace-nowrap">
            <button type="button" class="link-aksi text-blue-600" data-on-click="bukaAturanAlur" data-arg="${r.id_aturan}">Ubah</button>
            <button type="button" class="link-aksi text-slate-600 ml-3" data-on-click="aktifAturanAlur" data-arg="${r.id_aturan}">${r.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            <button type="button" class="link-aksi text-red-600 ml-3" data-on-click="hapusAturanAlur" data-arg="${r.id_aturan}">Hapus</button></td>
    </tr>`).join('') || barisKosong(5, 'Belum ada pemakaian alur. Semua tiket memakai alur bawaan produk.',
        { fungsi: 'bukaAturanAlur', label: 'Tambah Pemakaian' });
}

// ===== EDITOR ALUR =====
function bukaAlurTiket(id, salin = false) {
    const a = dataAlurTiket.alur.find(x => x.id_alur === id);
    const form = document.getElementById('formAlurTiket');
    form.reset();
    form.elements.id_alur.value = a && !salin ? a.id_alur : '';
    form.elements.nama.value = a ? (salin ? `${a.nama} (salinan)` : a.nama) : '';
    form.elements.keterangan.value = a ? (a.keterangan || '') : '';
    document.getElementById('judulAlurTiket').textContent = a && !salin ? 'Ubah Alur Tiket' : 'Tambah Alur Tiket';
    document.getElementById('daftarTahapTiket').innerHTML = '';
    const kelompok = a ? a.kelompok : [['SECURITY'], ['TIMBANG_1'], ['TIMBANG_2']];
    kelompok.slice(1).forEach(k => k.forEach((kode, i) => kode !== 'SECURITY_KELUAR' && tambahTahapTiket(kode, i > 0)));
    document.getElementById('alurTiketKeluar').checked = kelompok.some(k => k.includes('SECURITY_KELUAR'));
    pratinjauAlurTiket();
    openModal('modalAlurTiket');
}

function salinAlurTiket(id) {
    bukaAlurTiket(id, true);
}

function tambahTahapTiket(kode = '', bersamaan = false) {
    if (typeof kode !== 'string') kode = '';
    const wadah = document.getElementById('daftarTahapTiket');
    const baris = document.createElement('div');
    baris.className = 'tahap-tiket flex flex-wrap items-center gap-2';
    baris.innerHTML = `<span class="nomor-tahap w-7 h-7 rounded-full bg-slate-900 text-white text-xs font-bold flex items-center justify-center flex-shrink-0"></span>
        <select class="input-field flex-1 min-w-[10rem]" aria-label="Tahap" data-on-change="pratinjauAlurTiket">
            <option value="">Pilih tahap...</option>${TAHAP_TENGAH.map(k =>
                `<option value="${k}"${k === kode ? ' selected' : ''}>${escapeHtml(namaTahap(k))}</option>`).join('')}</select>
        <label class="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer select-none" title="Dikerjakan bersamaan dengan tahap di atasnya (urutan bebas)">
            <input type="checkbox" class="w-3.5 h-3.5" data-bersamaan data-on-change="pratinjauAlurTiket"${bersamaan ? ' checked' : ''}> Bersamaan dengan tahap sebelumnya</label>
        <button type="button" class="btn-secondary btn-sm" title="Naik" data-on-click="geserTahapTiket" data-arg="$el|-1"><i class="fa-solid fa-arrow-up"></i></button>
        <button type="button" class="btn-secondary btn-sm" title="Turun" data-on-click="geserTahapTiket" data-arg="$el|1"><i class="fa-solid fa-arrow-down"></i></button>
        <button type="button" class="btn-secondary btn-sm text-red-600" title="Hapus tahap" data-on-click="hapusTahapTiket" data-arg="$el"><i class="fa-solid fa-trash"></i></button>`;
    wadah.appendChild(baris);
    pratinjauAlurTiket();
}

function geserTahapTiket(el, arah) {
    const baris = el.closest('.tahap-tiket');
    const sasaran = arah < 0 ? baris.previousElementSibling : baris.nextElementSibling;
    if (!sasaran) return;
    if (arah < 0) sasaran.before(baris); else sasaran.after(baris);
    pratinjauAlurTiket();
}

function hapusTahapTiket(el) {
    el.closest('.tahap-tiket').remove();
    pratinjauAlurTiket();
}

// Baris editor -> [["SECURITY"], [...], ...]; tahap pertama setelah Security tidak bisa "bersamaan"
function kelompokEditor() {
    const kelompok = [['SECURITY']];
    document.querySelectorAll('#daftarTahapTiket .tahap-tiket').forEach((b, i) => {
        const kode = b.querySelector('select').value || '?';
        if (i > 0 && b.querySelector('[data-bersamaan]').checked) kelompok[kelompok.length - 1].push(kode);
        else kelompok.push([kode]);
    });
    if (document.getElementById('alurTiketKeluar').checked) kelompok.push(['SECURITY_KELUAR']);
    return kelompok;
}

// Cerminan validasi_kelompok di server, supaya admin langsung tahu sebelum menyimpan
function masalahKelompok(kelompok) {
    const rata = kelompok.flat();
    if (rata.length < 2) return 'Tambahkan minimal satu tahap setelah Security.';
    if (rata.includes('?')) return 'Ada tahap yang belum dipilih.';
    const ganda = rata.find((t, i) => rata.indexOf(t) !== i);
    if (ganda) return `${namaTahap(ganda)} dipilih lebih dari sekali.`;
    const posisi = {};
    kelompok.forEach((k, i) => k.forEach(t => { posisi[t] = i; }));
    if ('TIMBANG_2' in posisi && !('TIMBANG_1' in posisi)) return `${namaTahap('TIMBANG_2')} membutuhkan ${namaTahap('TIMBANG_1')}.`;
    if ('TIMBANG_2' in posisi && posisi.TIMBANG_2 <= posisi.TIMBANG_1)
        return `${namaTahap('TIMBANG_2')} harus setelah ${namaTahap('TIMBANG_1')} (tidak boleh sebelum atau bersamaan).`;
    return '';
}

function pratinjauAlurTiket() {
    const baris = [...document.querySelectorAll('#daftarTahapTiket .tahap-tiket')];
    let nomor = 1;
    baris.forEach((b, i) => {
        const centang = b.querySelector('[data-bersamaan]');
        centang.disabled = i === 0;
        if (i === 0) centang.checked = false;
        if (!centang.checked) nomor++;
        b.querySelector('.nomor-tahap').textContent = nomor;
        b.classList.toggle('pl-6', centang.checked);
    });
    const kelompok = kelompokEditor();
    document.getElementById('pratinjauAlurTiket').innerHTML = rantaiKelompok(kelompok);
    const masalah = masalahKelompok(kelompok);
    const p = document.getElementById('peringatanAlurTiket');
    p.textContent = masalah;
    p.classList.toggle('hidden', !masalah);
}

document.getElementById('formAlurTiket').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const kelompok = kelompokEditor();
    const masalah = masalahKelompok(kelompok);
    if (masalah) { Notif.peringatan(masalah); return; }
    const fd = new FormData(form);
    fd.append('kelompok', JSON.stringify(kelompok));
    const data = await denganTombol(form.querySelector('[type=submit]'), () => kirimForm('/api/admin/alur-tiket/simpan', fd));
    if (!tampilkanHasil(data)) return;
    closeModal('modalAlurTiket');
    muatAlurTiket();
});

function aktifAlurTiket(id) {
    const a = dataAlurTiket.alur.find(x => x.id_alur === id);
    if (!a) return;
    konfirmasiAktif({ url: `/api/admin/alur-tiket/${id}/aktif`, aktif: !a.is_active, jenis: 'alur', nama: a.nama,
        pesanNonaktif: 'Pemakaian alur yang menunjuk ke alur ini dilewati; tiket baru memakai aturan lain atau alur bawaan produk.',
        setelahnya: muatAlurTiket });
}

async function hapusAlurTiket(id) {
    const a = dataAlurTiket.alur.find(x => x.id_alur === id);
    if (!a) return;
    const ok = await Dialog.konfirmasi({ judul: 'Hapus alur?', teksYa: 'Hapus', bahaya: true, pesan: `Alur ${a.nama} dihapus.` });
    if (!ok) return;
    const data = await kirimForm(`/api/admin/alur-tiket/${id}/hapus`, {});
    if (tampilkanHasil(data)) muatAlurTiket();
}

// ===== PEMAKAIAN ALUR (Area + Produk -> Alur) =====
function opsiDaftar(daftar, kosong = null) {
    return (kosong !== null ? `<option value="">${escapeHtml(kosong)}</option>` : '') +
        daftar.map(x => `<option value="${x.id}">${escapeHtml(x.nama)}</option>`).join('');
}

function bukaAturanAlur(id) {
    const r = dataAlurTiket.aturan.find(x => x.id_aturan === id);
    const form = document.getElementById('formAturanAlur');
    document.getElementById('aturanArea').innerHTML = opsiDaftar(dataAlurTiket.area);
    document.getElementById('aturanProduk').innerHTML = opsiDaftar(dataAlurTiket.produk, 'Semua produk');
    document.getElementById('aturanAlur').innerHTML = opsiDaftar(dataAlurTiket.alur
        .filter(a => !a.sistem && (a.is_active || (r && a.id_alur === r.id_alur))).map(a => ({ id: a.id_alur, nama: a.nama })));
    form.reset();
    form.elements.id_aturan.value = r ? r.id_aturan : '';
    if (r) {
        form.elements.id_comp_area.value = r.id_comp_area;
        form.elements.id_produk.value = r.id_produk ?? '';
        form.elements.id_alur.value = r.id_alur;
    }
    document.getElementById('judulAturanAlur').textContent = r ? 'Ubah Pemakaian Alur' : 'Tambah Pemakaian Alur';
    pratinjauAturanAlur();
    openModal('modalAturanAlur');
}

function pratinjauAturanAlur() {
    const a = dataAlurTiket.alur.find(x => String(x.id_alur) === document.getElementById('aturanAlur').value);
    document.getElementById('pratinjauAturanAlur').innerHTML = a ? rantaiKelompok(a.kelompok) : '';
}

document.getElementById('formAturanAlur').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/alur-tiket/aturan/simpan', { modal: 'modalAturanAlur', setelahnya: muatAlurTiket });
});

function aktifAturanAlur(id) {
    const r = dataAlurTiket.aturan.find(x => x.id_aturan === id);
    if (!r) return;
    konfirmasiAktif({ url: `/api/admin/alur-tiket/aturan/${id}/aktif`, aktif: !r.is_active, jenis: 'pemakaian alur',
        nama: `${r.area} · ${r.produk || 'Semua produk'}`,
        pesanNonaktif: 'Tiket baru memakai aturan lain atau alur bawaan produk.', setelahnya: muatAlurTiket });
}

async function hapusAturanAlur(id) {
    const r = dataAlurTiket.aturan.find(x => x.id_aturan === id);
    if (!r) return;
    const ok = await Dialog.konfirmasi({ judul: 'Hapus pemakaian alur?', teksYa: 'Hapus', bahaya: true,
        pesan: `${r.area} · ${r.produk || 'Semua produk'} tidak lagi memakai alur ${r.alur}.` });
    if (!ok) return;
    const data = await kirimForm(`/api/admin/alur-tiket/aturan/${id}/hapus`, {});
    if (tampilkanHasil(data)) muatAlurTiket();
}

// ===== CEK ALUR =====
const ASAL_ALUR = {
    AREA_PRODUK: 'Dari pemakaian alur Area + Produk',
    AREA_SEMUA: 'Dari pemakaian alur Area + semua produk',
    PRODUK: 'Alur bawaan produk (area ini belum punya pemakaian alur untuk produk ini)',
};

function bukaCekAlur() {
    document.getElementById('cekArea').innerHTML = opsiDaftar(dataAlurTiket.area);
    document.getElementById('cekProduk').innerHTML = opsiDaftar(dataAlurTiket.produk);
    document.getElementById('formCekAlur').reset();
    document.getElementById('hasilCekAlur').classList.add('hidden');
    openModal('modalCekAlur');
}

document.getElementById('formCekAlur').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const data = await denganTombol(form.querySelector('[type=submit]'), () => kirimForm('/api/admin/alur-tiket/cek', new FormData(form)));
    const hasil = document.getElementById('hasilCekAlur');
    if (data.error) { tampilkanHasil(data); hasil.classList.add('hidden'); return; }
    hasil.innerHTML = `<p class="font-semibold text-slate-800">${escapeHtml(data.nama || '-')}</p>
        <p class="text-xs text-slate-500 mt-0.5 mb-2">${escapeHtml(ASAL_ALUR[data.asal] || '')}</p>${rantaiKelompok(data.kelompok)}
        <p class="text-xs text-slate-400 mt-2">Transaksi "Penimbangan saja" selalu memakai alur sistem Penimbangan saja.</p>`;
    hasil.classList.remove('hidden');
});
