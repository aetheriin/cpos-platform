// Pembelian TBS Daily: semua perusahaan tampil dalam satu layar dengan huruf sebesar mungkin.
// Kartu dibagi ke dua kolom yang tingginya seimbang, lalu ukuran huruf dicari dari yang terbesar sampai isi muat.
// Tabel tidak pernah digulir sendiri. Kalau pada huruf terkecil masih tidak muat, halamannya yang digulir supaya data tidak terpotong.
(() => {
    const isi = document.querySelector('.tbs-daily');
    const area = document.querySelector('.main-area');
    if (!isi || !area) return;
    const HURUF_MIN = 9, HURUF_MAKS = 15, LANGKAH = 0.25, JARAK_BAWAH = 10;

    function bagiKolom() {
        const kartu = [...isi.querySelectorAll('.tbs-kartu')];
        if (kartu.length < 2) return;
        const kolom = [{ tinggi: 0, isi: [] }, { tinggi: 0, isi: [] }];
        // Tinggi isi, bukan tinggi kartu: kartu sebaris di grid direntangkan sama tinggi
        const tinggi = k => k.querySelector('.section-header').offsetHeight + (k.querySelector('table')?.offsetHeight ?? 60);
        [...kartu].sort((a, b) => tinggi(b) - tinggi(a)).forEach(k => {
            const rendah = kolom[0].tinggi <= kolom[1].tinggi ? kolom[0] : kolom[1];
            rendah.isi.push(k);
            rendah.tinggi += tinggi(k);
        });
        kolom.forEach(({ isi: anggota }) => {
            const wadah = document.createElement('div');
            wadah.className = 'tbs-kolom';
            wadah.append(...anggota.sort((a, b) => kartu.indexOf(a) - kartu.indexOf(b)));
            isi.append(wadah);
        });
    }

    const pakaiHuruf = px => isi.style.setProperty('--tbs-huruf', `${px}px`);
    const muat = () => isi.getBoundingClientRect().bottom <= window.innerHeight - JARAK_BAWAH
        && [...isi.querySelectorAll('.section-body')].every(b => b.scrollWidth <= b.clientWidth);

    function sesuaikan() {
        area.scrollTop = 0;
        area.style.overflowY = 'hidden';
        let huruf = HURUF_MAKS;
        pakaiHuruf(huruf);
        while (huruf > HURUF_MIN && !muat()) {
            huruf -= LANGKAH;
            pakaiHuruf(huruf);
        }
        if (!muat()) area.style.overflowY = 'auto';
    }

    bagiKolom();
    sesuaikan();
    window.addEventListener('resize', sesuaikan);
    document.fonts?.ready.then(sesuaikan);
})();
