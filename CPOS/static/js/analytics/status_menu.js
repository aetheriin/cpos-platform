// ===== Tanda status laporan Analytics di sidebar (templates/partials/layout/sidebar.html) =====
// Menu laporan /an/<id> diberi titik: kuning = data sedang dimuat, hijau = data sudah dimuat dan siap dibuka.
// Statusnya dari backend Analytics (/analytics/api/laporan/status) untuk sesi CPOS ini. Diperiksa lebih sering selama ada yang memuat.
(() => {
    const menu = document.querySelectorAll('.sidebar-sublink[data-laporan]');
    if (!menu.length) return;
    const ARTI = { memuat: 'Data sedang dimuat', siap: 'Data siap' };
    // di halaman laporan pemuatan bisa mulai kapan saja (buka laporan, ganti periode), jadi diperiksa lebih rapat
    const JEDA_MEMUAT = 3000, JEDA_BIASA = document.getElementById('bingkaiAnalytics') ? 5000 : 20000;
    let jadwal = null;

    function tampilkan(status) {
        menu.forEach(a => {
            const titik = a.querySelector('.sidebar-status');
            const st = status[a.dataset.laporan];
            if (!titik) return;
            titik.hidden = !ARTI[st];
            titik.dataset.status = st || '';
            titik.title = ARTI[st] || '';
            titik.setAttribute('aria-label', ARTI[st] || '');
        });
    }

    async function periksa() {
        clearTimeout(jadwal);
        let status = {};
        try {
            const r = await fetch('/analytics/api/laporan/status', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
            if (r.ok) status = await r.json();
        } catch (e) {
            // backend Analytics belum menyala: tanpa titik, coba lagi nanti
        }
        tampilkan(status);
        const adaMemuat = Object.values(status).includes('memuat');
        if (!document.hidden) jadwal = setTimeout(periksa, adaMemuat ? JEDA_MEMUAT : JEDA_BIASA);
    }

    // laporan dibuka di bingkai halaman ini: status berubah segera, jadi periksa lebih cepat
    window.addEventListener('message', e => { if (e.data && e.data.tipe === 'cpos-aktif') periksa(); });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) periksa(); });

    // Semua laporan mulai dimuat di latar setelah login, supaya saat dibuka datanya sudah siap.
    // Backend hanya menjalankannya sekali per sesi CPOS, jadi aman dipanggil di tiap halaman.
    fetch('/analytics/api/laporan/pramuat', { method: 'POST', credentials: 'same-origin' })
        .catch(() => { /* backend Analytics belum menyala: laporan dimuat saat dibuka */ })
        .finally(periksa);
})();
