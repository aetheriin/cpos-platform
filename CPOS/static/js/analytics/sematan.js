// ===== Laporan Analytics di dalam CPOS (templates/analytics/sematan.html) =====
// Klik / ketik di dalam bingkai tidak terlihat oleh halaman ini, jadi frontend Analytics mengirim pesan 'cpos-aktif'.
// Pesan itu dianggap aktivitas: penghitung idle direset dan sesi di server diperpanjang (paling sering 1x per 5 menit).
window.addEventListener('message', e => {
    const bingkai = document.getElementById('bingkaiAnalytics');
    if (!bingkai || e.source !== bingkai.contentWindow || !e.data || e.data.tipe !== 'cpos-aktif') return;
    SesiIdle.aktivitasLokal();
    aktivitasTerakhir = Date.now();
});
