// ===== MODE TERANG / GELAP =====
// Dimuat di <head> (bukan defer) supaya kelas "dark" terpasang sebelum halaman tampil (tidak berkedip putih).
// Pilihan disimpan per browser (localStorage 'tema': 'terang' / 'gelap'); bawaan terang.
// Kuncinya sama dengan Analytics (satu alamat /analytics), jadi laporan di dalam bingkai ikut tema yang sama.
(function () {
    let tema = 'terang';
    try { tema = localStorage.getItem('tema') || 'terang'; } catch (e) { /* storage diblokir: pakai terang */ }
    document.documentElement.classList.toggle('dark', tema === 'gelap');
})();

function gantiTema() {
    const gelap = document.documentElement.classList.toggle('dark');
    const tema = gelap ? 'gelap' : 'terang';
    try { localStorage.setItem('tema', tema); } catch (e) { /* abaikan */ }
    document.querySelectorAll('[data-on-click="gantiTema"]').forEach(tombolTema);
    // laporan Analytics yang sedang terbuka langsung ikut berganti (tanpa muat ulang)
    try {
        const doc = document.getElementById('bingkaiAnalytics')?.contentDocument;
        if (doc) doc.documentElement.dataset.tema = tema;
    } catch (e) { /* bingkai beda alamat: ikut tema saat dibuka berikutnya */ }
}

// Label tombol menyebut apa yang terjadi bila diklik
function tombolTema(btn) {
    const gelap = document.documentElement.classList.contains('dark');
    btn.setAttribute('aria-pressed', gelap ? 'true' : 'false');
    btn.title = gelap ? 'Pakai tampilan terang' : 'Pakai tampilan gelap';
    btn.setAttribute('aria-label', btn.title);
}

document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('[data-on-click="gantiTema"]').forEach(tombolTema));
