(() => {
    const tombol = document.getElementById('btnMuatUlangTbs');
    if (!tombol) return;

    const INTERVAL_MS = 15 * 60 * 1000;

    // Hapus parameter setelah data baru selesai dimuat agar refresh otomatis
    // berikutnya tidak memaksa ERP mengambil data lagi.
    const urlSaatIni = new URL(window.location.href);
    if (urlSaatIni.searchParams.get('muat_ulang') === '1') {
        urlSaatIni.searchParams.delete('muat_ulang');
        history.replaceState(
            null,
            '',
            urlSaatIni.pathname + urlSaatIni.search + urlSaatIni.hash
        );
    }

    tombol.addEventListener('click', () => {
        tombol.disabled = true;
        tombol.innerHTML =
            '<i class="fa-solid fa-rotate fa-spin"></i> Memuat...';

        const url = new URL(window.location.href);
        url.searchParams.set('muat_ulang', '1');
        window.location.assign(url.toString());
    });

    let timer;

    function jadwalkanMuatUlang() {
        clearTimeout(timer);

        // Jangan memuat ulang halaman saat tab tidak terlihat.
        if (!document.hidden) {
            timer = setTimeout(() => window.location.reload(), INTERVAL_MS);
        }
    }

    document.addEventListener('visibilitychange', jadwalkanMuatUlang);
    jadwalkanMuatUlang();
})();