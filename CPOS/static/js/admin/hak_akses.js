// ===== ADMIN > HAK AKSES (aturan per menu) =====
// Tiap menu punya daftar aturan "Diberikan ke": Semua user / Peran (departemen + jabatan) / Jabatan / Departemen / User,
// Izinkan atau Larang per aksi (Larang menang). Aturan menu induk menjadi gerbang bagi anaknya.
// Menu Dashboard: tiap aturan Izinkan boleh membawa isi dashboard (widget); dipakai yang paling spesifik.
const AKSI = ['lihat', 'tambah', 'ubah', 'hapus', 'setujui', 'tolak', 'selesai'];
const JENIS = [['ALL', 'Semua user'], ['ROLE', 'Peran'], ['LEVEL', 'Jabatan'], ['DEPT', 'Departemen'], ['USER', 'User']];
let DATA = { menu: [], widget: [], jabatan: [], departemen: [], peran: [], halaman_awal: [] };
let menuAktif = null;
let aturan = [];
let berubah = false;
let salinan = null;              
let barisPilihUser = null;       
let barisWidget = null;   
let jumlahAsli = 0;              

const bentukAturan = a => JSON.stringify({ jenis: a.jenis, id_target: a.id_target, tolak: a.tolak,
                                           aksi: AKSI.filter(k => a.aksi[k]), widget: a.widget, cakupan: a.cakupan });
const statusAturan = a => !a._asli ? 'baru' : (a._asli !== bentukAturan(a) ? 'diubah' : '');
const GAYA_STATUS = {
    baru: 'background:rgba(16,185,129,.14);box-shadow:inset 4px 0 0 #10b981',
    diubah: 'background:rgba(245,158,11,.14);box-shadow:inset 4px 0 0 #f59e0b',
};

function penandaAturan(a) {
    const s = statusAturan(a);
    if (!s) return '';
    return `<span title="${s === 'baru' ? 'Aturan baru, belum disimpan' : 'Diubah, belum disimpan'}"
        style="display:inline-block;width:9px;height:9px;border-radius:9999px;background:${s === 'baru' ? '#10b981' : '#f59e0b'};margin-right:6px;vertical-align:middle"></span>`;
}

function perbaruiRingkasan() {
    const baru = aturan.filter(a => statusAturan(a) === 'baru').length;
    const diubah = aturan.filter(a => statusAturan(a) === 'diubah').length;
    const dihapus = Math.max(0, jumlahAsli - aturan.filter(a => a._asli).length);
    const bagian = [baru && `${baru} baru`, diubah && `${diubah} diubah`, dihapus && `${dihapus} dihapus`].filter(Boolean);
    document.getElementById('tandaBerubah').textContent = bagian.length ? `Belum disimpan · ${bagian.join(' · ')}` : 'Belum disimpan';
}// indeks baris yang sedang diatur widget-nya

document.addEventListener('DOMContentLoaded', async () => {
    await muatAkses();
    const cek = new URLSearchParams(location.search).get('cek');
    if (cek) { pilihTabAkses('cek'); bukaCek(Number(cek)); }
});

async function muatAkses() {
    const data = await ambilJson('/api/admin/akses');
    if (data.error) { document.getElementById('pohonMenu').innerHTML = `<p class="p-4 text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    DATA = data;
    tampilPohonMenu();
    tampilHalamanAwal();
}

function pilihTabAkses(tab) {
    document.querySelectorAll('[data-tab-akses]').forEach(b => b.classList.toggle('chip-active', b.dataset.tabAkses === tab));
    ['aturan', 'cek', 'awal'].forEach(t => document.getElementById(`tabAkses-${t}`).classList.toggle('hidden', t !== tab));
}

// ===== Pohon menu =====
const menuKode = kode => DATA.menu.find(m => m.kode === kode);

// Cabang yang dilipat (kode menu). Awal: halaman Lv2 yang punya bagian dilipat, grup Lv1 terbuka.
let pohonDilipat = null;
const anakMenu = kode => DATA.menu.filter(m => m.induk === kode);
const IKON_LEVEL = { 1: 'fa-layer-group', 2: 'fa-file-lines', 3: 'fa-circle' };
// Nama kelas ditulis utuh (bukan dirakit) supaya ikut terbangun di tailwind.css
const KELAS_IKON = { 1: 'pohon-ikon pohon-ikon-1', 2: 'pohon-ikon pohon-ikon-2', 3: 'pohon-ikon pohon-ikon-3' };

function lipatPohon(lipat) {
    pohonDilipat = new Set(lipat ? DATA.menu.filter(m => anakMenu(m.kode).length).map(m => m.kode) : []);
    tampilPohonMenu();
}

function lipatCabang(kode) {
    pohonDilipat.has(kode) ? pohonDilipat.delete(kode) : pohonDilipat.add(kode);
    tampilPohonMenu();
}

function tampilPohonMenu() {
    if (!pohonDilipat) pohonDilipat = new Set(DATA.menu.filter(m => m.level === 2 && anakMenu(m.kode).length).map(m => m.kode));
    const q = (document.getElementById('cariMenuAkses').value || '').trim().toLowerCase();
    let tampil = DATA.menu;
    if (q) {
        const cocok = new Set();
        DATA.menu.filter(m => m.nama.toLowerCase().includes(q) || m.kode.toLowerCase().includes(q)).forEach(m => {
            for (let x = m; x; x = x.induk ? menuKode(x.induk) : null) cocok.add(x.kode);
        });
        tampil = DATA.menu.filter(m => cocok.has(m.kode));
    } else {
        // Sembunyikan anak dari cabang yang dilipat (menu aktif tetap terlihat)
        const tersembunyi = m => { for (let x = m.induk ? menuKode(m.induk) : null; x; x = x.induk ? menuKode(x.induk) : null)
            if (pohonDilipat.has(x.kode) && !(menuAktif && menuAktif.kode === m.kode)) return true; return false; };
        tampil = DATA.menu.filter(m => !tersembunyi(m));
    }
    const LEBAR = 1.15;   // rem per level
    document.getElementById('pohonMenu').innerHTML = tampil.map(m => {
        const aktif = menuAktif && menuAktif.id_menu === m.id_menu;
        const punyaAnak = anakMenu(m.kode).length;
        const garis = Array.from({ length: m.level - 1 }, (_, i) => `<span class="pohon-garis" style="left:${1.3 + i * LEBAR}rem"></span>`).join('');
        return `<div class="pohon-baris ${aktif ? 'pohon-baris-aktif' : ''}" style="padding-left:${0.6 + (m.level - 1) * LEBAR}rem">
            ${garis}
            ${punyaAnak && !q ? `<button type="button" class="pohon-caret ${pohonDilipat.has(m.kode) ? 'pohon-caret-tutup' : ''}" data-on-click="lipatCabang" data-arg="${escapeHtml(m.kode)}"
                title="${pohonDilipat.has(m.kode) ? 'Buka' : 'Lipat'} (${punyaAnak})"><i class="fa-solid fa-chevron-down"></i></button>` : '<span class="w-4 flex-shrink-0"></span>'}
            <button type="button" class="flex-1 min-w-0 flex items-center gap-2 text-left" data-on-click="pilihMenuAkses" data-arg="${m.id_menu}">
                <span class="${KELAS_IKON[m.level]}"><i class="fa-solid ${m.level === 3 ? IKON_LEVEL[3] : (m.ikon || IKON_LEVEL[m.level])}"></i></span>
                <span class="flex-1 min-w-0 truncate ${m.level === 1 ? 'text-[11px] font-bold uppercase tracking-wider' : m.level === 2 ? 'font-semibold' : ''}"
                      title="${escapeHtml(m.nama)}">${escapeHtml(m.nama)}</span>
                ${m.url || m.level === 1 || punyaAnak ? '' : '<span class="text-[9px] italic opacity-60" title="Halamannya belum dibuat">segera</span>'}
                <span class="pohon-aturan ${m.jumlah_aturan ? '' : 'pohon-aturan-kosong'}" title="${m.jumlah_aturan ? `${m.jumlah_aturan} aturan` : 'Belum ada aturan (ikut menu induk)'}">${m.jumlah_aturan || '–'}</span>
            </button>
        </div>`;
    }).join('') || '<p class="p-4 text-sm text-slate-400">Menu tidak ditemukan</p>';
}

async function pilihMenuAkses(id) {
    if (berubah && menuAktif && menuAktif.id_menu !== id) {
        const ok = await Dialog.konfirmasi({ judul: 'Perubahan belum disimpan', pesan: `Aturan ${menuAktif.nama} belum disimpan. Tinggalkan tanpa menyimpan?`,
                                             teksYa: 'Tinggalkan', bahaya: true });
        if (!ok) return;
    }
    menuAktif = DATA.menu.find(m => m.id_menu === id);
    const data = await ambilJson(`/api/admin/akses/menu/${id}`);
    if (data.error) { Notif.gagal(data.error); return; }
    aturan = data;
    aturan.forEach(a => { a._asli = bentukAturan(a); });
    jumlahAsli = aturan.length;
    tandai(false);
    const remah = [];
    for (let x = menuKode(menuAktif.induk); x; x = x.induk ? menuKode(x.induk) : null) remah.unshift(x.nama);
    document.getElementById('remahMenuAkses').textContent = remah.length ? remah.join(' › ') : `Menu Level ${menuAktif.level}`;
    document.getElementById('judulMenuAkses').textContent = menuAktif.nama;
    document.querySelectorAll('[data-perlu-menu]').forEach(b => { b.disabled = false; });
    perbaruiTempel();
    tampilPohonMenu();
    tampilAturan();
}

// ===== Tabel aturan =====
const adaWidget = () => menuAktif && menuAktif.kode === 'DASHBOARD';
const aksiBerlaku = () => ['lihat', ...(menuAktif ? menuAktif.aksi : [])];

function tandai(ya) {
    berubah = ya;
    document.getElementById('tandaBerubah').classList.toggle('hidden', !ya);
    document.getElementById('btnSimpanAturan').disabled = !ya;
}

const opsi = (daftar, nilai) => daftar.map(([v, l]) => `<option value="${escapeHtml(v)}"${String(v) === String(nilai) ? ' selected' : ''}>${escapeHtml(l)}</option>`).join('');

function sasaran(a, i) {
    const dept = DATA.departemen.map(d => [d.id, d.nama]), jab = DATA.jabatan.map(j => [j.id, j.nama]);
    if (a.jenis === 'ALL') return '<span class="text-slate-500">Semua user yang login</span>';
    if (a.jenis === 'ROLE') {
        const [d, j] = String(a.id_target || '').split('|');
        return `<div class="flex gap-1">
            <select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="role_dept" title="Departemen">${opsi(dept, d)}</select>
            <select class="input-field py-1 text-xs w-32" data-i="${i}" data-f="role_jab" title="Jabatan">${opsi(jab, j)}</select></div>`;
    }
    if (a.jenis === 'LEVEL') return `<select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="id_target">${opsi(jab, a.id_target)}</select>`;
    if (a.jenis === 'DEPT') return `<select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="id_target">${opsi(dept, a.id_target)}</select>`;
    return `<button type="button" class="btn-secondary btn-sm max-w-full truncate" data-on-click="bukaPilihUser" data-arg="${i}">
        <i class="fa-solid fa-user mr-1"></i>${escapeHtml(a.id_target ? a.nama_target : 'Pilih user...')}</button>`;
}

// Cakupan data aturan Izinkan: data PT mana yang terlihat lewat menu ini (digabung bila beberapa aturan cocok)
const CAKUPAN = [['AREA', 'Area sendiri'], ['PT', 'PT sendiri'], ['SEMUA', 'Semua PT'], ['PT_TERTENTU', 'PT tertentu']];

function selCakupan(a, i) {
    if (a.tolak) return '<span class="text-slate-300">–</span>';
    const c = a.cakupan || { cakupan: 'AREA' };
    const pt = new Set(c.pt || []);
    return `<select class="input-field py-1 text-xs w-32" data-i="${i}" data-f="cakupan">${opsi(CAKUPAN, c.cakupan || 'AREA')}</select>
        ${c.cakupan === 'PT_TERTENTU' ? `<div class="flex flex-wrap gap-1 mt-1 max-w-[14rem]">${DATA.company.map(p => `
            <label class="pt-pilih ${pt.has(p.id) ? 'pt-pilih-aktif' : ''}" title="${escapeHtml(p.nama)}">
                <input type="checkbox" class="hidden" data-i="${i}" data-f="pt" data-pt="${escapeHtml(p.id)}"${pt.has(p.id) ? ' checked' : ''}>${escapeHtml(p.id)}</label>`).join('')}</div>` : ''}`;
}

const LABEL_AKSI = { lihat: 'Lihat', tambah: 'Tambah', ubah: 'Ubah', hapus: 'Hapus', setujui: 'Setujui', tolak: 'Tolak', selesai: 'Selesai' };

// Kolom aksi hanya yang berlaku di menu ini (mis. Dashboard: Lihat & Ubah)
function tampilKepala() {
    const sel = document.querySelector('#kepalaAturan .kolom-aksi');
    sel.parentElement.querySelectorAll('[data-kolom-aksi]').forEach(el => el.remove());
    aksiBerlaku().forEach(k => sel.insertAdjacentHTML('beforebegin',
        `<th class="table-cell !px-1 text-center text-[11px]" data-kolom-aksi>${LABEL_AKSI[k]}</th>`));
    sel.classList.add('hidden');
}

function tampilAturan() {
    const berlaku = aksiBerlaku();
    tampilKepala();
    perbaruiRingkasan();
    document.querySelectorAll('.kolom-widget').forEach(el => el.classList.toggle('hidden', !adaWidget()));
    const namaWidget = Object.fromEntries(DATA.widget.map(w => [w.kode, w.nama]));
    document.getElementById('tabelAturan').innerHTML = aturan.map((a, i) => `
        <tr class="${a.tolak ? 'bg-red-50/60' : 'hover:bg-slate-50'}" style="${GAYA_STATUS[statusAturan(a)] || ''}">
            <td class="table-cell !px-2 whitespace-nowrap">${penandaAturan(a)}<select class="input-field py-1 text-xs font-semibold w-24 ${a.tolak ? 'text-red-700' : 'text-emerald-700'}" data-i="${i}" data-f="tolak">
                ${opsi([['0', 'Izinkan'], ['1', 'Larang']], a.tolak ? '1' : '0')}</select></td>
            <td class="table-cell !px-2"><select class="input-field py-1 text-xs w-28" data-i="${i}" data-f="jenis">${opsi(JENIS, a.jenis)}</select></td>
            <td class="table-cell !px-2">${sasaran(a, i)}</td>
            ${berlaku.map(k => `<td class="table-cell !px-1 text-center"><input type="checkbox" class="w-4 h-4" data-i="${i}" data-f="aksi"
                data-aksi="${k}" title="${LABEL_AKSI[k]}"${a.aksi[k] ? ' checked' : ''}></td>`).join('')}
            <td class="table-cell !px-2">${selCakupan(a, i)}</td>
            ${adaWidget() ? `<td class="table-cell !px-2 min-w-[9rem]">${a.tolak ? '<span class="text-slate-300">–</span>'
                : `<button type="button" class="link-aksi text-blue-600 text-left" data-on-click="bukaWidgetAturan" data-arg="${i}">
                    ${a.widget.length ? a.widget.map(w => escapeHtml(namaWidget[w] || w)).join(', ') : '<span class="text-slate-400">Atur isi</span>'}</button>`}</td>` : ''}
            <td class="table-cell !px-2 text-right whitespace-nowrap">
                <button type="button" class="px-1.5 text-emerald-600 hover:text-emerald-800" title="Allow all baris ini" data-on-click="aksiBaris" data-arg="${i}|$true"><i class="fa-solid fa-check-double"></i></button>
                <button type="button" class="px-1.5 text-slate-400 hover:text-red-600" title="Deny all baris ini" data-on-click="aksiBaris" data-arg="${i}|$false"><i class="fa-solid fa-ban"></i></button>
                <button type="button" class="px-1.5 text-slate-400 hover:text-red-600" title="Hapus aturan" data-on-click="hapusAturan" data-arg="${i}"><i class="fa-solid fa-trash-can"></i></button>
            </td>
        </tr>`).join('') || barisKosong(12, 'Belum ada aturan: menu ini tidak terlihat oleh siapa pun.', { fungsi: 'tambahAturan', label: 'Tambah aturan' });
}

function targetAwal(jenis) {
    if (jenis === 'ROLE') return `${(DATA.departemen[0] || {}).id || ''}|${(DATA.jabatan[0] || {}).id || ''}`;
    if (jenis === 'LEVEL') return String((DATA.jabatan[0] || {}).id || '');
    if (jenis === 'DEPT') return (DATA.departemen[0] || {}).id || '';
    return null;
}

document.getElementById('tabelAturan').addEventListener('change', e => {
    const el = e.target, a = aturan[Number(el.dataset.i)];
    if (!a) return;
    const f = el.dataset.f;
    if (f === 'tolak') a.tolak = el.value === '1';
    else if (f === 'jenis') { a.jenis = el.value; a.id_target = targetAwal(a.jenis); a.nama_target = ''; }
    else if (f === 'id_target') a.id_target = el.value;
    else if (f === 'cakupan') a.cakupan = { cakupan: el.value, ...(el.value === 'PT_TERTENTU' ? { pt: (a.cakupan && a.cakupan.pt) || [] } : {}) };
    else if (f === 'pt') {
        const pt = new Set((a.cakupan && a.cakupan.pt) || []);
        el.checked ? pt.add(el.dataset.pt) : pt.delete(el.dataset.pt);
        a.cakupan = { cakupan: 'PT_TERTENTU', pt: [...pt] };
    }
    else if (f === 'role_dept' || f === 'role_jab') {
        const [d, j] = String(a.id_target || '|').split('|');
        a.id_target = f === 'role_dept' ? `${el.value}|${j}` : `${d}|${el.value}`;
    } else if (f === 'aksi') {
        a.aksi[el.dataset.aksi] = el.checked;
        // Izinkan: aksi apa pun berarti boleh melihat menunya. Larang Lihat = menu (dan anaknya) tidak terlihat.
        if (!a.tolak && el.checked && el.dataset.aksi !== 'lihat') a.aksi.lihat = true;
        if (!a.tolak && !el.checked && el.dataset.aksi === 'lihat') AKSI.forEach(k => { a.aksi[k] = false; });
    }
    tandai(true);
    tampilAturan();
});

function tambahAturan() {
    aturan.push({ jenis: 'ROLE', id_target: targetAwal('ROLE'), nama_target: '', tolak: false, aksi: { lihat: true }, widget: [],
                  cakupan: { cakupan: 'AREA' } });
    tandai(true);
    tampilAturan();
}

function hapusAturan(i) {
    aturan.splice(i, 1);
    tandai(true);
    tampilAturan();
}

function aksiBaris(i, nilai) {
    aksiBerlaku().forEach(k => { aturan[i].aksi[k] = nilai; });
    tandai(true);
    tampilAturan();
}

function semuaAksi(nilai) {
    aturan.forEach((_, i) => aksiBerlaku().forEach(k => { aturan[i].aksi[k] = nilai; }));
    tandai(true);
    tampilAturan();
}

// ===== Copy / Paste =====
function salinAturan() {
    salinan = { dari: menuAktif.nama, aturan: JSON.parse(JSON.stringify(aturan)) };
    Notif.info(`${aturan.length} aturan dari ${menuAktif.nama} disalin. Buka menu lain lalu klik Paste.`);
    perbaruiTempel();
}

function perbaruiTempel() {
    document.getElementById('btnTempel').disabled = !salinan || !menuAktif;
    document.getElementById('infoSalinan').textContent = salinan ? `Salinan: ${salinan.dari} (${salinan.aturan.length})` : '';
}

function tempelAturan() {
    if (!salinan) return;
    const berlaku = aksiBerlaku();
    const kunci = a => `${a.jenis}|${a.id_target}|${a.tolak}`;
    const ada = new Set(aturan.map(kunci));
    let n = 0;
    salinan.aturan.forEach(s => {
        if (ada.has(kunci(s))) return;        // sasaran yang sama sudah ada: tidak digandakan
        aturan.push({ ...s, _asli: undefined, aksi: Object.fromEntries(Object.entries(s.aksi).filter(([k]) => berlaku.includes(k))),
                      widget: adaWidget() ? s.widget : [] });
        n++;
    });
    Notif.info(n ? `${n} aturan ditempel. Periksa lalu Simpan.` : 'Semua sasaran dari salinan sudah ada di menu ini.');
    if (n) tandai(true);
    tampilAturan();
}

// ===== Simpan =====
document.getElementById('formAturan').addEventListener('submit', async e => {
    e.preventDefault();
    if (aturan.some(a => a.jenis === 'USER' && !a.id_target)) { Notif.peringatan('Ada aturan User yang belum dipilih usernya.'); return; }
    if (aturan.some(a => !a.tolak && a.cakupan && a.cakupan.cakupan === 'PT_TERTENTU' && !(a.cakupan.pt || []).length)) {
        Notif.peringatan('Cakupan PT tertentu: pilih minimal satu PT.'); return;
    }
    const kirim = aturan.map(a => ({ jenis: a.jenis, id_target: a.id_target, tolak: a.tolak,
                                     aksi: AKSI.filter(k => a.aksi[k]), widget: a.widget, cakupan: a.cakupan }));
    const btn = document.getElementById('btnSimpanAturan');
    const data = await denganTombol(btn, () => kirimForm(`/api/admin/akses/menu/${menuAktif.id_menu}`, { aturan: JSON.stringify(kirim) }));
    if (!tampilkanHasil(data)) return;
    const id = menuAktif.id_menu;
    tandai(false);
    await muatAkses();
    pilihMenuAkses(id);
});

// ===== Pilih user (aturan User) =====
function bukaPilihUser(i) {
    barisPilihUser = i;
    document.getElementById('cariPilihUser').value = '';
    document.getElementById('hasilPilihUser').innerHTML = '';
    openModal('modalPilihUser');
    document.getElementById('cariPilihUser').focus();
    cariPilihUser();
}

let timerCariUser = null;
function cariUser(q, wadahId, fungsi) {
    clearTimeout(timerCariUser);
    timerCariUser = setTimeout(async () => {
        const data = await ambilJson(`/api/admin/akses/user?q=${encodeURIComponent(q || '')}`);
        const wadah = document.getElementById(wadahId);
        if (data.error) { wadah.innerHTML = `<p class="p-3 text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
        wadah.innerHTML = data.map(u => `
            <button type="button" class="w-full text-left px-3 py-2 hover:bg-slate-50" data-on-click="${fungsi}" data-arg="${u.id_user}"
                data-nama="${escapeHtml(u.nama)} · ${escapeHtml(u.username)}">
                <p class="text-sm font-semibold text-slate-800">${escapeHtml(u.nama)} <span class="font-normal text-slate-400">· ${escapeHtml(u.username)}</span></p>
                <p class="text-xs text-slate-500">${escapeHtml(u.nik || '-')} · ${escapeHtml(u.peran || '-')}</p>
            </button>`).join('') || '<p class="p-3 text-sm text-slate-400">Tidak ada user yang cocok</p>';
    }, 250);
}

function cariPilihUser() { cariUser(document.getElementById('cariPilihUser').value, 'hasilPilihUser', 'pakaiUser'); }

function pakaiUser(id) {
    const tombol = document.querySelector(`#hasilPilihUser [data-arg="${id}"]`);
    Object.assign(aturan[barisPilihUser], { id_target: String(id), nama_target: tombol ? tombol.dataset.nama : String(id) });
    closeModal('modalPilihUser');
    tandai(true);
    tampilAturan();
}

// ===== Isi dashboard (widget) per aturan =====
function bukaWidgetAturan(i) {
    barisWidget = i;
    const a = aturan[i];
    document.getElementById('judulWidgetAturan').textContent = `· ${JENIS.find(j => j[0] === a.jenis)[1]}${a.nama_target ? ` ${a.nama_target}` : ''}`;
    const urut = [...a.widget, ...DATA.widget.map(w => w.kode).filter(k => !a.widget.includes(k))];
    const per = Object.fromEntries(DATA.widget.map(w => [w.kode, w]));
    document.getElementById('daftarWidgetAturan').innerHTML = urut.filter(k => per[k]).map(k => `
        <div class="flex items-center gap-3 px-3 py-2" data-widget-baris>
            <input type="checkbox" value="${escapeHtml(k)}" id="wa_${escapeHtml(k)}"${a.widget.includes(k) ? ' checked' : ''}>
            <label for="wa_${escapeHtml(k)}" class="flex-1 min-w-0">
                <span class="text-sm font-semibold text-slate-800">${escapeHtml(per[k].nama)}</span>
                <span class="block text-xs text-slate-500">${escapeHtml(per[k].keterangan || '')}</span>
            </label>
            <button type="button" class="btn-secondary px-2 py-1" title="Naik" data-on-click="geserWidget" data-arg="$el|-1"><i class="fa-solid fa-arrow-up"></i></button>
            <button type="button" class="btn-secondary px-2 py-1" title="Turun" data-on-click="geserWidget" data-arg="$el|1"><i class="fa-solid fa-arrow-down"></i></button>
        </div>`).join('');
    openModal('modalWidgetAturan');
}

function geserWidget(el, arah) {
    const baris = el.closest('[data-widget-baris]');
    const tujuan = arah < 0 ? baris.previousElementSibling : baris.nextElementSibling;
    if (tujuan) (arah < 0 ? tujuan.before(baris) : tujuan.after(baris));
}

function pakaiWidgetAturan() {
    aturan[barisWidget].widget = [...document.querySelectorAll('#daftarWidgetAturan input:checked')].map(c => c.value);
    if (aturan[barisWidget].widget.length) aturan[barisWidget].aksi.lihat = true;
    closeModal('modalWidgetAturan');
    tandai(true);
    tampilAturan();
}

// ===== Cek Akses User =====
function cariUserCek() { cariUser(document.getElementById('cariUserCek').value, 'hasilUserCek', 'bukaCek'); }

const LABEL_JENIS = Object.fromEntries(JENIS);

// ===== Cek Akses User: alasan, Beri hak khusus, Cabut =====
let cekUser = null, cekMenu = [], hakKhusus = null;

const punyaAturan = (m, larang) => m.sumber.some(s => s.aksi === 'lihat' && !!s.tolak === larang);

function rantaiCek(kode) {                         // dari menu paling atas sampai menu ini
    const rantai = [];
    for (let m = cekMenu.find(x => x.kode === kode); m; m = m.induk ? cekMenu.find(x => x.kode === m.induk) : null) rantai.unshift(m);
    return rantai;
}

function alasanCek(m) {
    const rantai = rantaiCek(m.kode);
    const larang = rantai.find(x => punyaAturan(x, true));
    if (larang) return `Dilarang oleh aturan Larang${larang.kode === m.kode ? '' : ` di ${larang.nama}`}`;
    const kurang = rantai.find(x => !punyaAturan(x, false));
    if (kurang) return kurang.kode === m.kode ? 'Belum ada aturan Izinkan untuk user ini' : `Menu induk ${kurang.nama} belum diizinkan`;
    return 'Terhalang aturan lain';
}

function aksiCek(m) {
    if (m.hak) {
        const khusus = m.sumber.some(s => !s.tolak && s.jenis === 'USER');
        return khusus ? `<button type="button" class="link-aksi text-red-600" data-on-click="cabutHakKhusus" data-arg="${escapeHtml(m.kode)}">Cabut hak khusus</button>` : '';
    }
    const larang = rantaiCek(m.kode).find(x => punyaAturan(x, true));
    return larang
        ? `<button type="button" class="link-aksi text-slate-600" data-on-click="bukaAturanDariCek" data-arg="${larang.id_menu}" title="Larang tidak bisa ditimpa hak khusus: ubah aturan Larang-nya">Buka aturan</button>`
        : `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaHakKhusus" data-arg="${escapeHtml(m.kode)}">Beri hak khusus</button>`;
}

async function bukaCek(id) {
    const data = await ambilJson(`/api/admin/akses/cek/${id}`);
    if (data.error) { Notif.gagal(data.error); return; }
    cekUser = data.user;
    cekMenu = data.menu;
    const namaWidget = Object.fromEntries(DATA.widget.map(w => [w.kode, w.nama]));
    document.getElementById('judulCek').textContent = `${data.user.nama} · ${data.user.username}`;
    document.getElementById('infoCek').textContent = `Peran: ${data.user.nama_level} · Isi dashboard: ${data.widget.map(w => namaWidget[w] || w).join(', ') || '-'}`;
    document.getElementById('tabelCek').innerHTML = cekMenu.map(m => {
        const kelompok = {};
        m.sumber.forEach(s => {
            const k = `${s.tolak}|${s.jenis}|${s.nama}`;
            (kelompok[k] = kelompok[k] || { ...s, aksi: [] }).aksi.push(LABEL_AKSI[s.aksi] || s.aksi);
        });
        const asal = Object.values(kelompok).map(s => {
            const warna = s.tolak ? 'bg-red-100 text-red-800' : (s.jenis === 'USER' ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-700');
            return `<span class="badge-status mr-1 mb-1 ${warna}">${s.tolak ? 'Larang' : 'Izinkan'} ${escapeHtml(s.aksi.join(', '))} · ${escapeHtml(LABEL_JENIS[s.jenis])}${s.jenis === 'ALL' ? '' : ` ${escapeHtml(s.nama || '')}`}</span>`;
        }).join('');
        const hak = m.hak ? AKSI.filter(k => m.hak[k]).map(k => LABEL_AKSI[k]).join(', ') : '';
        const alasan = m.hak ? '' : alasanCek(m);
        return `<tr class="${m.hak ? '' : 'text-slate-400'}">
            <td class="table-cell" style="padding-left:${0.75 + (m.level - 1) * 1.1}rem"><span class="${m.level === 1 ? 'font-semibold' : ''}">${escapeHtml(m.nama)}</span></td>
            <td class="table-cell">${m.hak ? `<span class="text-emerald-700">${escapeHtml(hak)}</span>` : 'Tidak terlihat'}</td>
            <td class="table-cell">${asal}${alasan ? `<span class="text-xs text-amber-700 block">${escapeHtml(alasan)}</span>` : (asal ? '' : '<span class="text-slate-300">-</span>')}</td>
            <td class="table-cell text-right whitespace-nowrap">${aksiCek(m)}</td></tr>`;
    }).join('');
}

function bukaAturanDariCek(idMenu) {
    pilihTabAkses('aturan');
    pilihMenuAkses(Number(idMenu));
}

function bukaHakKhusus(kode) {
    const m = cekMenu.find(x => x.kode === kode);
    if (!m || !cekUser) return;
    hakKhusus = kode;
    const ikut = rantaiCek(kode).filter(x => x.kode !== kode && !punyaAturan(x, false)).map(x => x.nama);
    document.getElementById('hkUser').textContent = `${cekUser.nama} (${cekUser.username})`;
    document.getElementById('hkMenu').textContent = m.nama;
    document.getElementById('hkRantai').textContent = ikut.length ? `Menu induk yang ikut dibukakan (Lihat): ${ikut.join(', ')}` : '';
    document.getElementById('hkAksi').innerHTML = ['lihat', ...m.aksi].map(k => `
        <label class="flex items-center gap-2"><input type="checkbox" class="w-4 h-4" value="${k}"${k === 'lihat' ? ' checked disabled' : ''}> ${LABEL_AKSI[k]}</label>`).join('');
    openModal('modalHakKhusus');
}

// Tambah / lengkapi aturan level User (Izinkan) untuk user yang sedang dicek pada satu menu. Return false bila gagal.
async function tambahAturanUser(m, aksi) {
    const data = await ambilJson(`/api/admin/akses/menu/${m.id_menu}`);
    if (data.error) { Notif.gagal(`${m.nama}: ${data.error}`); return false; }
    const idUser = String(cekUser.id_user);
    let a = data.find(x => !x.tolak && x.jenis === 'USER' && String(x.id_target) === idUser);
    if (!a) {
        a = { jenis: 'USER', id_target: cekUser.id_user, nama_target: '', tolak: false, aksi: {}, widget: [], cakupan: { cakupan: 'AREA' } };
        data.push(a);
    }
    aksi.forEach(k => { a.aksi[k] = true; });
    return kirimAturanMenu(m, data);
}

async function kirimAturanMenu(m, data) {
    const kirim = data.map(a => ({ jenis: a.jenis, id_target: a.id_target, tolak: a.tolak,
                                   aksi: AKSI.filter(k => a.aksi[k]), widget: a.widget, cakupan: a.cakupan }));
    const hasil = await kirimForm(`/api/admin/akses/menu/${m.id_menu}`, { aturan: JSON.stringify(kirim) });
    if (hasil.error) { Notif.gagal(`${m.nama}: ${hasil.error}`); return false; }
    return true;
}

async function simpanHakKhusus() {
    const kode = hakKhusus;
    if (!kode || !cekUser) return;
    const pilih = ['lihat', ...[...document.querySelectorAll('#hkAksi input:checked:not(:disabled)')].map(c => c.value)];
    await denganTombol(document.getElementById('btnHakKhusus'), async () => {
        for (const m of rantaiCek(kode)) {
            if (m.kode !== kode && punyaAturan(m, false)) continue;           // induk yang sudah punya Izinkan Lihat
            if (!(await tambahAturanUser(m, m.kode === kode ? pilih : ['lihat']))) return;
        }
        closeModal('modalHakKhusus');
        Notif.info(`Hak khusus diberikan ke ${cekUser.nama}. Berlaku dalam ±30 detik.`);
        await muatAkses();
        bukaCek(cekUser.id_user);
    });
}

async function cabutHakKhusus(kode) {
    const m = cekMenu.find(x => x.kode === kode);
    if (!m || !cekUser) return;
    const ok = await Dialog.konfirmasi({ judul: 'Cabut hak khusus', teksYa: 'Cabut', bahaya: true,
        pesan: `Hapus aturan level User untuk ${cekUser.nama} pada ${m.nama}? Hak dari Departemen / Jabatan / Peran tidak ikut dicabut.` });
    if (!ok) return;
    const data = await ambilJson(`/api/admin/akses/menu/${m.id_menu}`);
    if (data.error) { Notif.gagal(data.error); return; }
    const idUser = String(cekUser.id_user);
    const sisa = data.filter(x => !(x.jenis === 'USER' && !x.tolak && String(x.id_target) === idUser));
    if (!(await kirimAturanMenu(m, sisa))) return;
    Notif.info('Hak khusus dicabut.');
    await muatAkses();
    bukaCek(cekUser.id_user);
}

// ===== Halaman awal per peran =====
function tampilHalamanAwal() {
    const pilihan = DATA.halaman_awal.map(h => [h.url, h.nama]);
    document.getElementById('tabelHalamanAwal').innerHTML = DATA.peran.map(p => `
        <tr class="${p.is_active ? '' : 'text-slate-400'}">
            <td class="table-cell">${escapeHtml(p.nama)}</td>
            <td class="table-cell text-right font-mono">${p.jumlah_user}</td>
            <td class="table-cell"><select class="input-field py-1.5 max-w-md" data-on-change="simpanHalamanAwal" data-arg="$el" data-id="${p.id}">
                ${opsi(pilihan.some(([u]) => u === p.halaman_awal) ? pilihan : [[p.halaman_awal, p.halaman_awal], ...pilihan], p.halaman_awal)}</select></td>
        </tr>`).join('') || barisKosong(3, 'Belum ada peran');
}

async function simpanHalamanAwal(el) {
    tampilkanHasil(await kirimForm(`/api/admin/level/${el.dataset.id}/halaman-awal`, { halaman_awal: el.value }));
}

// ===== Beri ke semua turunan: "beri semua kunci" di induk, lalu tarik satu per satu di turunan =====
// Memakai tampilan & penyimpanan aturan yang sama dengan Simpan biasa (validasi, audit, cache ikut berjalan).
const turunanMenu = kode => anakMenu(kode).flatMap(m => [m, ...turunanMenu(m.kode)]);

async function beriKeTurunan() {
    if (!menuAktif) return;
    const turunan = turunanMenu(menuAktif.kode);
    if (!turunan.length) { Notif.info('Menu ini tidak punya turunan.'); return; }
    if (berubah) { Notif.peringatan('Simpan dulu aturan menu ini, baru diberikan ke turunannya.'); return; }
    const sumber = aturan.filter(a => !a.tolak);
    if (!sumber.length) { Notif.peringatan('Belum ada aturan Izinkan di menu ini untuk diberikan.'); return; }
    const ok = await Dialog.konfirmasi({
        judul: 'Beri ke semua turunan', teksYa: 'Beri',
        pesan: `${sumber.length} aturan Izinkan menu ${menuAktif.nama} akan ditambahkan ke ${turunan.length} menu di bawahnya. `
             + 'Aturan yang sudah ada tidak ditimpa, dan sasaran yang di-Tolak di menu turunan dilewati.' });
    if (!ok) return;

    const kunci = a => `${a.jenis}|${a.id_target}`;
    let diubah = 0;
    for (const anak of turunan) {
        const data = await ambilJson(`/api/admin/akses/menu/${anak.id_menu}`);
        if (data.error) { Notif.gagal(`${anak.nama}: ${data.error}`); return; }
        const berlaku = ['lihat', ...anak.aksi];                       // aksi yang memang ada di menu turunan itu
        const ditolak = new Set(data.filter(a => a.tolak).map(kunci));  // kunci yang sudah ditarik: tetap ditarik
        const ada = new Map(data.filter(a => !a.tolak).map(a => [kunci(a), a]));
        let baru = false;
        sumber.forEach(s => {
            const k = kunci(s);
            if (ditolak.has(k)) return;
            const aksi = berlaku.filter(x => s.aksi[x]);
            if (ada.has(k)) {                                           // sasaran sama sudah ada: hanya tambah aksi yang belum ada
                const a = ada.get(k);
                aksi.filter(x => !a.aksi[x]).forEach(x => { a.aksi[x] = true; baru = true; });
            } else if (aksi.length) {
                const a = { jenis: s.jenis, id_target: s.id_target, nama_target: s.nama_target, tolak: false,
                            aksi: Object.fromEntries(AKSI.map(x => [x, aksi.includes(x)])), widget: [], cakupan: s.cakupan };
                data.push(a);
                ada.set(k, a);
                baru = true;
            }
        });
        if (!baru) continue;
        const kirim = data.map(a => ({ jenis: a.jenis, id_target: a.id_target, tolak: a.tolak,
                                       aksi: AKSI.filter(x => a.aksi[x]), widget: a.widget, cakupan: a.cakupan }));
        const hasil = await kirimForm(`/api/admin/akses/menu/${anak.id_menu}`, { aturan: JSON.stringify(kirim) });
        if (hasil.error) { Notif.gagal(`${anak.nama}: ${hasil.error}`); break; }
        diubah++;
    }
    Notif.info(diubah ? `Aturan diberikan ke ${diubah} menu turunan. Berlaku di semua PC dalam ±30 detik.` : 'Semua turunan sudah punya aturan yang sama.');
    const id = menuAktif.id_menu;
    await muatAkses();
    pilihMenuAkses(id);
}