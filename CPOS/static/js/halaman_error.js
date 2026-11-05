// Kembali ke halaman sebelumnya. Dibuka langsung tanpa riwayat: ke halaman utama.
document.getElementById('tombol-kembali')?.addEventListener('click', () => {
    if (window.history.length > 1) window.history.back();
    else window.location.href = '/';
});
