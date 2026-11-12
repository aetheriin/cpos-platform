const LABEL_AKSI_MENU = { tambah: 'Tambah', ubah: 'Ubah', hapus: 'Hapus', setujui: 'Setujui', tolak: 'Tolak', selesai: 'Selesai' };
let DATA_MENU = { menu: [], aplikasi: [], aksi: [] };

document.addEventListener('DOMContentLoaded', muatMenuKelola);

// Gaya per level sama dengan pohon Hak Akses (nama kelas utuh supaya ikut terbangun di tailwind.css)
const KELAS_IKON_MENU = { 1: 'pohon-ikon pohon-ikon-1', 2: 'pohon-ikon pohon-ikon-2', 3: 'pohon-ikon pohon-ikon-3' };

async function muatMenuKelola() {
    const data = await ambilJson('/api/admin/menu');
    const tbody = document.getElementById('tabelMenuKelola');
    if (data.error) { tbody.innerHTML = barisGagal(6, data.error); return false; }
    DATA_MENU = data;
    tampilMenuKelola();
}

const namaAksi = id => LABEL_AKSI_MENU[(DATA_MENU.aksi.find(a => a.id === id) || {}).nama] || id;

function tampilMenuKelola() {
    const q = (document.getElementById('cariMenuKelola').value || '').trim().toLowerCase();
    const menu = DATA_MENU.menu;
    let tampil = menu;
    if (q) {
        const per = Object.fromEntries(menu.map(m => [m.id_menu, m]));
        const cocok = new Set();
        menu.filter(m => m.nama.toLowerCase().includes(q) || m.kode.toLowerCase().includes(q))
            .forEach(m => { for (let x = m; x; x = per[x.id_induk]) cocok.add(x.id_menu); });
        tampil = menu.filter(m => cocok.has(m.id_menu));
    }
    const saudara = m => menu.filter(x => x.id_induk === m.id_induk);
    document.getElementById('tabelMenuKelola').innerHTML = tampil.map(m => {
        const s = saudara(m), i = s.indexOf(m);
        return `<tr class="hover:bg-slate-50${m.is_active ? '' : ' text-slate-400'}" data-menu="${m.id_menu}" data-induk="${m.id_induk || ''}" data-level="${m.level}">
            <td class="table-cell relative" style="padding-left:${0.75 + (m.level - 1) * 1.6}rem">
                ${Array.from({ length: m.level - 1 }, (_, n) => `<span class="pohon-garis" style="left:${1.5 + n * 1.6}rem"></span>`).join('')}
                <div class="flex items-center gap-2.5"><span class="seret-menu text-slate-300 hover:text-slate-600" style="cursor:grab" draggable="true" title="Seret untuk mengubah urutan (di antara menu seinduk)"><i class="fa-solid fa-grip-vertical"></i></span>
                <span class="${KELAS_IKON_MENU[m.level]}"><i class="fa-solid ${escapeHtml(m.level === 3 ? 'fa-circle' : (m.ikon || (m.level === 1 ? 'fa-layer-group' : 'fa-file-lines')))}"></i></span>
                <p class="min-w-0 ${m.level === 1 ? 'font-bold uppercase text-xs tracking-wider' : m.level === 2 ? 'font-semibold' : 'text-slate-600'}" title="${escapeHtml(m.kode)}">${escapeHtml(m.nama)}</p></div></td>
            <td class="table-cell font-mono text-xs">${m.url ? escapeHtml(m.url) : '<span class="text-slate-400">belum ada</span>'}</td>
            <td class="table-cell text-xs">${m.aksi.map(namaAksi).join(', ') || '<span class="text-slate-400">Lihat saja</span>'}</td>
            <td class="table-cell text-right font-mono">${m.jumlah_aturan}</td>
            <td class="table-cell">${badgeAktif(m.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap">
                <button type="button" class="px-1.5 text-slate-500 hover:text-blue-600 disabled:opacity-30" title="Naik" data-on-click="geserMenuKelola" data-arg="${m.id_menu}|-1"${i <= 0 ? ' disabled' : ''}><i class="fa-solid fa-arrow-up"></i></button>
                <button type="button" class="px-1.5 text-slate-500 hover:text-blue-600 disabled:opacity-30" title="Turun" data-on-click="geserMenuKelola" data-arg="${m.id_menu}|1"${i >= s.length - 1 ? ' disabled' : ''}><i class="fa-solid fa-arrow-down"></i></button>
                <button type="button" class="link-aksi text-blue-600 ml-2" data-on-click="bukaMenuKelola" data-arg="${m.id_menu}">Ubah</button>
                <button type="button" class="link-aksi ${m.is_active ? 'text-red-600' : 'text-emerald-600'} ml-2" data-on-click="aktifMenuKelola" data-arg="${m.id_menu}">${m.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td></tr>`;
    }).join('') || barisKosong(6, 'Menu tidak ditemukan');
}

async function geserMenuKelola(id, arah) {
    const r = await kirimForm(`/api/admin/menu/${id}/geser`, { arah });
    if (r.error) { Notif.gagal(r.error); return; }
    muatMenuKelola();
}

// Pilihan induk: Lv1 & Lv2 (Lv3 tidak bisa punya anak). Menu itu sendiri & turunannya tidak ditawarkan.
function isiPilihanInduk(m) {
    const turunan = new Set();
    if (m) { const antre = [m.id_menu]; while (antre.length) { const i = antre.pop(); DATA_MENU.menu.filter(x => x.id_induk === i).forEach(x => { turunan.add(x.id_menu); antre.push(x.id_menu); }); } }
    const opsi = DATA_MENU.menu.filter(x => x.level < 3 && (!m || (x.id_menu !== m.id_menu && !turunan.has(x.id_menu))))
        .map(x => `<option value="${x.id_menu}">${x.level === 2 ? '\u00A0\u00A0\u00A0› ' : ''}${escapeHtml(x.nama)} (${escapeHtml(x.kode)})</option>`);
    document.getElementById('menuInduk').innerHTML = '<option value="">— Tanpa induk (grup Level 1) —</option>' + opsi.join('');
}

function infoLevel() {
    const id = Number(document.getElementById('menuInduk').value) || null;
    const induk = DATA_MENU.menu.find(x => x.id_menu === id);
    const lv = induk ? induk.level + 1 : 1;
    document.getElementById('infoLevelMenu').textContent = lv === 1 ? 'Tanpa induk = grup Level 1.'
        : `Menjadi Level ${lv} di bawah ${induk.nama}.${lv === 2 ? ' Level 2 = halaman di sidebar.' : ' Level 3 = bagian / sub-halaman.'}`;
}
document.getElementById('menuInduk').addEventListener('change', infoLevel);

function pratinjauIkon() {
    const v = document.getElementById('menuIkon').value.trim();
    document.getElementById('contohIkon').innerHTML = /^fa-[a-z0-9-]+$/.test(v) ? `<i class="fa-solid ${escapeHtml(v)}"></i>` : '';
}

function bukaMenuKelola(id) {
    const m = DATA_MENU.menu.find(x => x.id_menu === Number(id));
    const form = document.getElementById('formMenuKelola');
    form.reset();
    isiPilihanInduk(m);
    document.getElementById('menuApp').innerHTML = DATA_MENU.aplikasi.map(a => `<option value="${a}">${a}</option>`).join('');
    document.getElementById('aksiMenuKelola').innerHTML = DATA_MENU.aksi.map(a => `<label class="inline-flex items-center gap-2">
        <input type="checkbox" name="aksi" value="${a.id}"${m && m.aksi.includes(a.id) ? ' checked' : ''}> ${LABEL_AKSI_MENU[a.nama] || a.nama}</label>`).join('');
    form.elements.id_menu.value = m ? m.id_menu : '';
    form.elements.kode.value = m ? m.kode : '';
    form.elements.kode.readOnly = !!m;
    form.elements.kode.required = !m;
    form.elements.kode.classList.toggle('bg-slate-50', !!m);
    form.elements.nama.value = m ? m.nama : '';
    form.elements.id_induk.value = m && m.id_induk ? m.id_induk : '';
    form.elements.url.value = m ? m.url || '' : '';
    form.elements.ikon.value = m ? m.ikon || '' : '';
    form.elements.aplikasi.value = m ? m.aplikasi : 'CPOS';
    document.getElementById('judulModalMenu').textContent = m ? `Ubah Menu · ${m.kode}` : 'Tambah Menu';
    infoLevel();
    pratinjauIkon();
    openModal('modalMenuKelola');
    (m ? form.elements.nama : form.elements.kode).focus();
}

document.getElementById('formMenuKelola').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/menu/simpan', { modal: 'modalMenuKelola', setelahnya: muatMenuKelola });
});

function aktifMenuKelola(id) {
    const m = DATA_MENU.menu.find(x => x.id_menu === Number(id));
    konfirmasiAktif({ url: `/api/admin/menu/${m.id_menu}/aktif`, aktif: !m.is_active, nama: m.nama, jenis: 'menu',
                      pesanNonaktif: 'Menu ini beserta turunannya hilang dari sidebar semua pengguna.', setelahnya: muatMenuKelola });
}

// ===== Seret & lepas untuk mengubah urutan (hanya di antara menu seinduk; anak ikut pindah bersama induknya) =====
let seret = null;        // { id, induk }: menu yang sedang diseret
let sisip = null;        // { target, setelah }: tempat jatuh saat ini
const tbodyMenu = document.getElementById('tabelMenuKelola');
const barisMenu = el => el && el.closest ? el.closest('tr[data-menu]') : null;
const idBaris = tr => Number(tr.dataset.menu);

// Menu itu + semua turunannya yang sedang tampil (baris yang berurutan di bawahnya dengan level lebih dalam)
function blokMenu(id) {
    const baris = [...tbodyMenu.querySelectorAll('tr[data-menu]')];
    const i = baris.findIndex(r => idBaris(r) === id);
    if (i < 0) return [];
    const level = Number(baris[i].dataset.level);
    const blok = [baris[i]];
    for (let j = i + 1; j < baris.length && Number(baris[j].dataset.level) > level; j++) blok.push(baris[j]);
    return blok;
}

// Dari baris yang sedang di-hover, naik ke induknya sampai ketemu menu yang seinduk dengan yang diseret (null = tidak boleh dilepas di sini)
function saudaraDari(tr) {
    let m = DATA_MENU.menu.find(x => x.id_menu === idBaris(tr));
    while (m && String(m.id_induk || '') !== seret.induk) m = DATA_MENU.menu.find(x => x.id_menu === m.id_induk);
    return m && m.id_menu !== seret.id ? m : null;
}

function bersihkanGaris() {
    tbodyMenu.querySelectorAll('td').forEach(td => { td.style.boxShadow = ''; });
}

function selesaiSeret() {
    if (seret) blokMenu(seret.id).forEach(r => { r.style.opacity = ''; });
    bersihkanGaris();
    seret = sisip = null;
}

tbodyMenu.addEventListener('dragstart', e => {
    const pegangan = e.target.closest ? e.target.closest('.seret-menu') : null;
    if (!pegangan) { e.preventDefault(); return; }
    const tr = barisMenu(pegangan);
    seret = { id: idBaris(tr), induk: tr.dataset.induk };
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(seret.id));          // Firefox butuh data agar seret berjalan
    e.dataTransfer.setDragImage(tr, 24, 16);
    blokMenu(seret.id).forEach(r => { r.style.opacity = '.4'; });
});

tbodyMenu.addEventListener('dragover', e => {
    if (!seret) return;
    const tr = barisMenu(e.target);
    bersihkanGaris();
    sisip = null;
    const s = tr && saudaraDari(tr);
    if (!s) return;
    e.preventDefault();                                               // di sini boleh dilepas
    const blok = blokMenu(s.id_menu);
    const tengah = (blok[0].getBoundingClientRect().top + blok[blok.length - 1].getBoundingClientRect().bottom) / 2;
    const setelah = e.clientY > tengah;
    sisip = { target: s.id_menu, setelah };
    const baris = setelah ? blok[blok.length - 1] : blok[0];
    baris.querySelectorAll('td').forEach(td => { td.style.boxShadow = `inset 0 ${setelah ? '-' : ''}3px 0 #3b82f6`; });
});

tbodyMenu.addEventListener('drop', async e => {
    if (!seret || !sisip) return;
    e.preventDefault();
    const { id, induk } = seret, { target, setelah } = sisip;
    selesaiSeret();
    const lama = DATA_MENU.menu.filter(x => String(x.id_induk || '') === induk).map(x => x.id_menu);
    const urutan = lama.filter(x => x !== id);
    urutan.splice(urutan.indexOf(target) + (setelah ? 1 : 0), 0, id);
    if (urutan.join() === lama.join()) return;                        // posisinya tidak berubah
    const r = await kirimForm('/api/admin/menu/urut', { id_induk: induk, urutan: JSON.stringify(urutan) });
    if (r.error) { Notif.gagal(r.error); return; }
    muatMenuKelola();
});

tbodyMenu.addEventListener('dragend', selesaiSeret);