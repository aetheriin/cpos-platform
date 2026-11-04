// ===== LAYOUT BASE: sidebar, tab, section =====
// Dipakai semua halaman yang extends base.html. Logika info bar ada di info_bar.js.

function getTabAktif() {
    const btn = document.querySelector('.tab-btn-active');
    return btn ? btn.dataset.tab : null;
}

function daftarTab() {
    return [...document.querySelectorAll('.tab-btn')].map(btn => btn.dataset.tab);
}


function setUrlParam(key, value) {
    const url = new URL(window.location);
    url.searchParams.set(key, value);
    window.history.replaceState({}, '', url);
}

// Layar lebar: menu samping disembunyikan / ditampilkan. Layar tablet (< 1280px): laci di atas isi (CSS .sidebar-buka).
const LAYAR_TABLET = window.matchMedia('(max-width: 1279px)');

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!LAYAR_TABLET.matches) { sidebar.classList.toggle('sidebar-collapsed'); return; }
    const buka = !sidebar.classList.contains('sidebar-buka');
    sidebar.classList.toggle('sidebar-buka', buka);
    let latar = document.getElementById('sidebarLatar');
    if (buka && !latar) {
        latar = document.createElement('div');
        latar.id = 'sidebarLatar';
        latar.className = 'sidebar-latar';
        latar.addEventListener('click', toggleSidebar);
        sidebar.insertAdjacentElement('afterend', latar);
    } else if (!buka && latar) latar.remove();
}

// Sidebar: menu Lv2 dropdown (punya bagian Lv3) yang dibuka / ditutup diingat di browser ini.
// Dropdown yang berisi halaman aktif selalu terbuka.
document.addEventListener('DOMContentLoaded', () => {
    let buka = {};
    try { buka = JSON.parse(localStorage.getItem('sidebar_sub') || '{}'); } catch (e) { buka = {}; }
    document.querySelectorAll('.sidebar-sub').forEach(d => {
        if (!d.hasAttribute('data-aktif') && buka[d.dataset.kode] !== undefined) d.open = buka[d.dataset.kode];
        d.addEventListener('toggle', () => {
            buka[d.dataset.kode] = d.open;
            try { localStorage.setItem('sidebar_sub', JSON.stringify(buka)); } catch (e) { /* mode privat */ }
        });
    });
});

// List & Form adalah dua halaman terpisah (List tanpa info bar & tab, Form dengan info bar + tab)
function setSidebarView(view) {
    window.location.href = `/weighbridge?view=${view}`;
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.toggle('tab-btn-active', el.dataset.tab === tabName);
    });
    document.querySelectorAll('[data-tab-content]').forEach(el => {
        el.classList.toggle('hidden', el.dataset.tabContent !== tabName);
    });
    setUrlParam('tab', tabName);
    window.dispatchEvent(new CustomEvent('tabChange', { detail: tabName }));
}

function toggleSection(id) {
    document.getElementById(`body-${id}`).classList.toggle('section-body-hidden');
    document.getElementById(`chevron-${id}`).classList.toggle('section-chevron-collapsed');
}

// Tab awal: ?tab=..., <meta name="tab-awal"> (sesuai role), selain itu tab pertama
document.addEventListener('DOMContentLoaded', () => {
    const tabs = daftarTab();
    if (!tabs.length) return;
    const awal = [new URLSearchParams(window.location.search).get('tab'),
                  document.querySelector('meta[name="tab-awal"]')?.content];
    switchTab(awal.find(t => tabs.includes(t)) || tabs[0]);
});

// ===== Tombol kembali ke atas: muncul setelah digulir lebih dari 300px (isi halaman bergulir di .main-area) =====
document.addEventListener('DOMContentLoaded', () => {
    const tombol = document.getElementById('tombolKeAtas');
    const wadah = document.querySelector('.main-area');
    if (!tombol || !wadah) return;
    const periksa = () => tombol.classList.toggle('hidden', wadah.scrollTop < 300);
    wadah.addEventListener('scroll', periksa, { passive: true });
    periksa();
    tombol.addEventListener('click', () => {
        const pelan = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        wadah.scrollTo({ top: 0, behavior: pelan ? 'smooth' : 'auto' });
    });
});

// ===== Tabel rapi: judul kolom mengikuti perataan isinya (angka rata kanan, status di tengah) =====
// Baris isi pertama yang lengkap menjadi patokan; berlaku juga untuk tabel yang diisi ulang lewat JavaScript.
function samakanPerataanTabel(tabel) {
    const kepala = tabel.tHead && tabel.tHead.rows[tabel.tHead.rows.length - 1];
    const baris = [...(tabel.tBodies[0]?.rows || [])].find(r => r.cells.length === kepala?.cells.length && !r.querySelector('[colspan]') && !r.classList.contains('baris-kerangka'));
    if (!kepala || !baris) return;
    [...kepala.cells].forEach((th, i) => {
        const td = baris.cells[i];
        const rata = td.classList.contains('text-right') ? 'text-right' : td.classList.contains('text-center') ? 'text-center' : null;
        th.classList.remove('text-left');
        if (rata) th.classList.add(rata);
        else if (!th.classList.contains('text-center') && !th.classList.contains('text-right')) th.classList.add('text-left');
    });
}
document.addEventListener('DOMContentLoaded', () => {
    let tunda = null;
    const semua = () => document.querySelectorAll('table').forEach(samakanPerataanTabel);
    new MutationObserver(() => { clearTimeout(tunda); tunda = setTimeout(semua, 50); })
        .observe(document.body, { childList: true, subtree: true });
    semua();
});

// Bilah tab disembunyikan (#tabHeader.hidden): tiap tab dibuka dari menu samping sebagai halaman sendiri; judul halaman ikut tab aktif
window.addEventListener('tabChange', e => {
    const bar = document.getElementById('tabHeader');
    const judul = document.querySelector('.halaman-judul h1');
    if (!bar || !judul || !bar.classList.contains('hidden') || bar.querySelectorAll('.tab-btn').length < 2) return;
    const tombol = bar.querySelector(`.tab-btn[data-tab="${e.detail}"]`);
    if (!tombol) return;
    const sub = document.querySelector('.halaman-judul p');
    if (!judul.dataset.induk) judul.dataset.induk = judul.textContent.trim();
    judul.textContent = tombol.textContent.trim();
    if (sub) sub.textContent = judul.dataset.induk;
});
