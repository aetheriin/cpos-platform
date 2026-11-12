// ===== MODE TERANG / GELAP =====
// Dimuat di <head> (bukan defer) supaya kelas "dark" terpasang sebelum halaman tampil (tidak berkedip putih).
// Pilihan disimpan per browser (localStorage 'tema': 'terang' / 'gelap'); bawaan terang.
// Kuncinya sama dengan Analytics (satu alamat /analytics), jadi laporan di dalam bingkai ikut tema yang sama.
(function () {
    let tema = 'terang';
    try { tema = localStorage.getItem('tema') || 'terang'; } catch (e) { /* storage diblokir: pakai terang */ }
    document.documentElement.classList.toggle('dark', tema === 'gelap');
})();

// Selama tema berganti semua transisi dimatikan (kelas ganti-tema), supaya sidebar (transition-all), header, dan laporan Analytics
// di dalam bingkai berubah warna bersamaan, tanpa ada yang memudar lebih lambat.
const gaya_ganti_tema = '.ganti-tema, .ganti-tema *, .ganti-tema *::before, .ganti-tema *::after { transition: none !important; }';
(function () {
    const gaya = document.createElement('style');
    gaya.textContent = gaya_ganti_tema;
    document.head.appendChild(gaya);
})();

function gantiTema() {
    let bingkai = null;
    try { bingkai = document.getElementById('bingkaiAnalytics')?.contentDocument?.documentElement || null; } catch (e) { /* beda alamat */ }
    if (bingkai && !bingkai.querySelector('#gaya-ganti-tema')) {   // laporan versi lama belum punya aturan ganti-tema
        const g = bingkai.ownerDocument.createElement('style');
        g.id = 'gaya-ganti-tema';
        g.textContent = gaya_ganti_tema;
        bingkai.ownerDocument.head.appendChild(g);
    }
    const akar = [document.documentElement, bingkai].filter(Boolean);
    akar.forEach((a) => a.classList.add('ganti-tema'));
    const gelap = document.documentElement.classList.toggle('dark');
    const tema = gelap ? 'gelap' : 'terang';
    try { localStorage.setItem('tema', tema); } catch (e) { /* abaikan */ }
    document.querySelectorAll('[data-on-click="gantiTema"]').forEach(tombolTema);
    // laporan Analytics yang sedang terbuka langsung ikut berganti (tanpa muat ulang)
    try {
        const doc = document.getElementById('bingkaiAnalytics')?.contentDocument;
        if (doc) doc.documentElement.dataset.tema = tema;
    } catch (e) { /* bingkai beda alamat: ikut tema saat dibuka berikutnya */ }
    akar.forEach((a) => void a.offsetHeight);   // terapkan warna baru selagi transisi mati
    requestAnimationFrame(() => requestAnimationFrame(() => akar.forEach((a) => a.classList.remove('ganti-tema'))));
}

// Label tombol menyebut apa yang terjadi bila diklik
function tombolTema(btn) {
    const gelap = document.documentElement.classList.contains('dark');
    btn.setAttribute('aria-pressed', gelap ? 'true' : 'false');
    btn.title = gelap ? 'Pakai tampilan terang' : 'Pakai tampilan gelap';
    btn.setAttribute('aria-label', btn.title);
}

document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('[data-on-click="gantiTema"]').forEach(tombolTema));
