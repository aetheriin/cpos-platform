// Pembelian TBS Daily: semua perusahaan muat satu layar. Tabel diperkecil sampai 60%; kalau tetap tidak cukup, halaman boleh digulir supaya data tidak terpotong.
(() => {
    const isi = document.querySelector('.tbs-daily');
    const area = document.querySelector('.main-area');
    if (!isi || !area) return;
    const BATAS = 0.6;
    const sesuaikan = () => {
        let zoom = 1;
        isi.style.zoom = zoom;
        for (let i = 0; i < 4; i++) {
            const sisa = window.innerHeight - isi.getBoundingClientRect().top - 12;
            const tinggi = isi.getBoundingClientRect().height;
            if (tinggi <= sisa || zoom <= BATAS) break;
            zoom = Math.max(BATAS, zoom * sisa / tinggi);
            isi.style.zoom = zoom;
        }
        const muat = isi.getBoundingClientRect().bottom <= window.innerHeight;
        area.style.overflowY = muat ? 'hidden' : 'auto';
    };
    sesuaikan();
    window.addEventListener('resize', sesuaikan);
})();
