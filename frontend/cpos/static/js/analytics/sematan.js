// ===== Laporan Analytics di dalam CPOS (templates/analytics/sematan.html) =====
// Klik / ketik di dalam bingkai tidak terlihat oleh halaman ini, jadi frontend Analytics mengirim pesan 'cpos-aktif'.
// Pesan itu dianggap aktivitas: penghitung idle direset dan sesi di server diperpanjang (paling sering 1x per 5 menit).
window.addEventListener('message', e => {
    const bingkai = document.getElementById('bingkaiAnalytics');
    if (!bingkai || e.source !== bingkai.contentWindow || !e.data || e.data.tipe !== 'cpos-aktif') return;
    SesiIdle.aktivitasLokal();
    aktivitasTerakhir = Date.now();
});

// Laporan dibuka dari dalam bingkai (mis. tombol "Buka laporan" di AkasaBot): halaman CPOS ikut pindah ke /an/<id>, supaya sidebar,
// breadcrumb, dan alamat sesuai laporan yang tampil. Hanya laporan yang ada di daftar boleh akun ini.
window.addEventListener('message', e => {
    const bingkai = document.getElementById('bingkaiAnalytics');
    if (!bingkai || e.source !== bingkai.contentWindow || !e.data || e.data.tipe !== 'cpos-buka') return;
    const id = String(e.data.laporan || '');
    const boleh = (bingkai.dataset.laporan || '').split(',');
    if (/^[a-z0-9_]+$/.test(id) && boleh.includes(id) && location.pathname !== '/an/' + id) location.href = '/an/' + id;
});

// Bingkai mengisi area di bawah topbar dari tepi ke tepi dan laporan menggulir di dalamnya (CSS .analytics-bingkai), jadi laci filter &
// popup laporan diam di layar dengan sendirinya. Di sini hanya jarak tepi: isi laporan diberi jarak tepi yang sama dengan halaman CPOS
// supaya sejajar. Hanya bisa bila Analytics satu alamat dengan CPOS (/analytics).
(() => {
    const bingkai = document.getElementById('bingkaiAnalytics');
    const konten = bingkai && bingkai.closest('.konten');
    if (!konten) return;

    function samakanTepi() {
        let doc = null;
        try { doc = bingkai.contentDocument; } catch { /* beda alamat: tidak boleh dibaca */ }
        if (doc) doc.documentElement.style.setProperty('--tepi', getComputedStyle(konten).paddingLeft);
    }

    bingkai.addEventListener('load', samakanTepi);
    samakanTepi();   // bingkai bisa sudah selesai dimuat sebelum skrip ini jalan
    window.addEventListener('resize', samakanTepi);
})();
