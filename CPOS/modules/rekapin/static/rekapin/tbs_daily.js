// Pembelian TBS Daily: semua perusahaan tampil dalam satu layar, urutannya tetap dan tiap kartu selebar tabelnya sendiri.
// Kartu dijajarkan satu baris. Kalau huruf harus lebih kecil dari HURUF_SEBARIS, kartu terakhir turun ke baris berikutnya.
// Ukuran huruf dicari dari yang terbesar sampai isi muat. Kalau pada huruf terkecil masih tidak muat, halamannya yang digulir.
(() => {
    const isi = document.querySelector('.tbs-daily');
    const area = document.querySelector('.main-area');
    if (!isi || !area) return;
    const HURUF_MIN = 9, HURUF_SEBARIS = 10, HURUF_MAKS = 20, LANGKAH = 0.25, JARAK_BAWAH = 10;
    const URUTAN = ['YBS', 'SUN', 'SJN'];

    function urutkan() {
        const posisi = k => {
            const i = URUTAN.indexOf(k.dataset.company);
            return i < 0 ? URUTAN.length : i;
        };
        [...isi.querySelectorAll('.tbs-kartu')].sort((a, b) => posisi(a) - posisi(b)).forEach(k => isi.append(k));
    }

    const pakaiHuruf = px => isi.style.setProperty('--tbs-huruf', `${px}px`);
    const muat = () => isi.getBoundingClientRect().bottom <= window.innerHeight - JARAK_BAWAH && isi.scrollWidth <= isi.clientWidth
        && [...isi.querySelectorAll('.section-body')].every(b => b.scrollWidth <= b.clientWidth);

    function cariHuruf(batas) {
        let huruf = HURUF_MAKS;
        pakaiHuruf(huruf);
        while (huruf > batas && !muat()) {
            huruf -= LANGKAH;
            pakaiHuruf(huruf);
        }
        return muat();
    }

    function sesuaikan() {
        area.scrollTop = 0;
        area.style.overflowY = 'hidden';
        isi.classList.add('tbs-sebaris');
        if (cariHuruf(HURUF_SEBARIS)) return;
        isi.classList.remove('tbs-sebaris');
        if (!cariHuruf(HURUF_MIN)) area.style.overflowY = 'auto';
    }

    urutkan();
    sesuaikan();
    window.addEventListener('resize', sesuaikan);
    document.fonts?.ready.then(sesuaikan);
})();
