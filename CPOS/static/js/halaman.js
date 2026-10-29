// ===== HALAMAN TABEL (pagination di browser) =====
// <tbody data-per-halaman="20"> -> baris dibagi per halaman + navigasi di bawah tabel. Otomatis saat isi tbody
// diganti (innerHTML), tanpa kode tambahan di tiap tab. Baris yang disembunyikan pencarian (.hidden) tidak dihitung;
// baris satu-sel (kosong / catatan batas) selalu tampil. Server tetap membatasi jumlah data yang dikirim.
// Tambahan otomatis:
// - kepala tabel menempel di bawah header saat halaman digulir (bila tabel muat selebar kotaknya, .tabel-lekat di CSS);
// - jumlah baris per halaman diingat per user (Pilihan di common.js);
// - <tbody data-sorot>: baris yang baru muncul / berubah (tr data-jejak) disorot sebentar saat data dimuat ulang;
// - kaki tabel seragam di semua halaman: jumlah data · tombol Excel / PDF (ekspor.js) · baris per halaman · halaman.
//   Judul file ekspor = data-judul-ekspor di tbody, selain itu judul kotak tabel / judul halaman.
//   <tbody data-tanpa-ekspor> = tanpa tombol ekspor.
const PILIHAN_PER_HALAMAN = [10, 20, 50, 100];

const Halaman = {
    pasang(tbody) {
        const kunciPer = `per:${tbody.id || 'tabel'}`;
        const perTersimpan = Number(Pilihan.ambil(kunciPer));
        tbody._hal = { ke: 1, per: PILIHAN_PER_HALAMAN.includes(perTersimpan) ? perTersimpan : Number(tbody.dataset.perHalaman) || 20 };
        const nav = document.createElement('div');
        nav.className = 'kaki-tabel hidden';
        const ekspor = 'tanpaEkspor' in tbody.dataset || !tbody.id ? '' : `<div class="flex items-center gap-1.5">
            <button type="button" class="btn-secondary btn-sm" data-ekspor="xlsx" title="Unduh Excel (semua baris yang tampil)"><i class="fa-regular fa-file-excel text-emerald-600"></i> Excel</button>
            <button type="button" class="btn-secondary btn-sm" data-ekspor="pdf" title="Cetak / simpan PDF"><i class="fa-regular fa-file-pdf text-red-600"></i> PDF</button></div>`;
        nav.innerHTML = `<span data-info></span>${ekspor}<div class="flex-1"></div>
            <label class="flex items-center gap-1">Tampilkan <select data-per class="border border-slate-300 rounded px-1.5 py-1">
                ${PILIHAN_PER_HALAMAN.map(n => `<option value="${n}">${n}</option>`).join('')}</select> baris</label>
            <div data-nav-hal class="flex items-center gap-2">
            <button type="button" data-ke="-1" class="btn-secondary py-1 px-2.5 text-xs">‹ Sebelumnya</button>
            <span data-posisi class="font-medium text-slate-700"></span>
            <button type="button" data-ke="1" class="btn-secondary py-1 px-2.5 text-xs">Berikutnya ›</button></div>`;
        nav.querySelectorAll('[data-ekspor]').forEach(b => b.addEventListener('click', () =>
            eksporTabel(tbody.id, b.dataset.ekspor, this.judulEkspor(tbody))));
        nav.querySelector('[data-per]').value = tbody._hal.per;
        nav.querySelector('[data-per]').addEventListener('change', e => {
            tbody._hal.per = Number(e.target.value);
            tbody._hal.ke = 1;
            Pilihan.simpan(kunciPer, tbody._hal.per);
            this.segarkan(tbody);
        });
        nav.querySelectorAll('[data-ke]').forEach(b => b.addEventListener('click', () => {
            tbody._hal.ke += Number(b.dataset.ke);
            this.segarkan(tbody);
            this.wadah(tbody).scrollTop = 0;
        }));
        const wadah = this.wadah(tbody);
        this.lekatkan(wadah);
        wadah.insertAdjacentElement('afterend', nav);
        tbody._nav = nav;
        new MutationObserver(() => { this.sorot(tbody); this.segarkan(tbody); }).observe(tbody, { childList: true });
        this.segarkan(tbody);
    },

    // Judul file ekspor: data-judul-ekspor, judul kotak tabel (h2/h3 / teks tebal pertama), lalu judul halaman
    judulEkspor(tbody) {
        if (tbody.dataset.judulEkspor) return tbody.dataset.judulEkspor;
        const kotak = tbody.closest('.section-box, .card, [data-tab-content]');
        const judul = kotak && kotak.querySelector('h2, h3, .section-header-text, p.font-bold, p.font-semibold');
        const teks = judul && judul.textContent.replace(/\s+/g, ' ').trim();
        return teks && teks.length <= 60 ? teks : document.title.split(' · ')[0];
    },

    // Pembungkus tabel (div overflow-x-auto); dibuat bila belum ada
    wadah(tbody) {
        const tabel = tbody.closest('table');
        const induk = tabel.parentElement;
        if (induk.children.length === 1 && /overflow-(x-)?auto/.test(induk.className)) return induk;
        const div = document.createElement('div');
        div.className = 'overflow-x-auto';
        tabel.replaceWith(div);
        div.appendChild(tabel);
        return div;
    },

    // Kepala tabel menempel: pembungkus & kotak di atasnya tidak boleh jadi area gulir sendiri (overflow hidden/auto),
    // jadi diganti "clip" lewat kelas CSS. Hanya bila tabel muat selebar kotaknya; tabel yang lebih lebar dari layar
    // tetap bisa digeser ke samping (tanpa kepala menempel). Berhenti di .main-area (area gulir halaman).
    lekatkan(wadah) {
        // Tabel di modal / kotak bergulir sendiri (overflow-y-auto) tidak diubah
        if (!wadah.closest('.main-area') || /max-h-|overflow-y-auto/.test(wadah.className)) return;
        // Dicek dari style yang benar-benar berlaku (getComputedStyle), bukan nama kelas: kotak seperti
        // .section-box / .card memakai overflow hidden lewat CSS komponen. Kotak yang memang bergulir
        // sendiri (overflow-y auto/scroll + max-height) dibiarkan; tabelnya tidak dibuat menempel.
        const induk = [];
        for (let el = wadah.parentElement; !el.classList.contains('main-area'); el = el.parentElement) {
            const cs = getComputedStyle(el);
            if (/auto|scroll/.test(cs.overflowY) && cs.maxHeight !== 'none') return;
            if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') induk.push(el);
        }
        const tabel = wadah.querySelector('table');
        const atur = () => {
            const muat = tabel.offsetWidth <= wadah.clientWidth + 1;
            wadah.classList.toggle('tabel-lekat', muat);
            induk.forEach(el => el.classList.toggle('lekat-induk', muat));
        };
        new ResizeObserver(atur).observe(tabel);
        new ResizeObserver(atur).observe(wadah);
    },

    segarkan(tbody) {
        if (!tbody || !tbody._hal) return;
        const data = [...tbody.rows].filter(tr => tr.cells.length > 1 && !tr.classList.contains('baris-kerangka'));
        const tampil = data.filter(tr => !tr.classList.contains('hidden'));
        const { per } = tbody._hal;
        const total = tampil.length, jumlahHal = Math.max(1, Math.ceil(total / per));
        tbody._hal.ke = Math.min(Math.max(1, tbody._hal.ke), jumlahHal);
        const awal = (tbody._hal.ke - 1) * per;
        data.forEach(tr => { tr.style.display = ''; });
        tampil.forEach((tr, i) => { if (i < awal || i >= awal + per) tr.style.display = 'none'; });

        const nav = tbody._nav;
        nav.classList.toggle('hidden', !total);
        nav.querySelector('[data-nav-hal]').classList.toggle('hidden', jumlahHal <= 1);
        nav.querySelector('[data-info]').textContent = total
            ? `Menampilkan ${awal + 1}–${Math.min(awal + per, total)} dari ${total}` : '';
        nav.querySelector('[data-posisi]').textContent = `${tbody._hal.ke} / ${jumlahHal}`;
        nav.querySelector('[data-ke="-1"]').disabled = tbody._hal.ke <= 1;
        nav.querySelector('[data-ke="1"]').disabled = tbody._hal.ke >= jumlahHal;
    },

    // Sorot baris yang belum pernah tampil (jejak = data-jejak, atau isi sel pertama). Isi pertama tidak disorot.
    sorot(tbody) {
        if (!('sorot' in tbody.dataset)) return;
        const kenal = tbody._kenal || (tbody._kenal = new Set());
        const data = [...tbody.rows].filter(tr => tr.cells.length > 1);
        if (data.some(tr => tr.classList.contains('baris-kerangka'))) return;      // kerangka memuat (tabel_rapi.js)
        data.forEach(tr => {
            const jejak = tr.dataset.jejak || tr.cells[0].textContent.trim();
            if (tbody._sudahIsi && !kenal.has(jejak)) tr.classList.add('baris-baru');
            kenal.add(jejak);
        });
        tbody._sudahIsi = true;
    },

    // Tandai data yang sudah dikenal tanpa menyorot (mis. semua tiket saat halaman pertama dibuka, sebelum difilter)
    kenali(tbody, daftarJejak) {
        tbody._kenal = new Set([...(tbody._kenal || []), ...daftarJejak]);
        tbody._sudahIsi = true;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('tbody[data-per-halaman]').forEach(tb => Halaman.pasang(tb));
    document.querySelectorAll('tbody[data-sorot]:not([data-per-halaman])').forEach(tb =>
        new MutationObserver(() => Halaman.sorot(tb)).observe(tb, { childList: true }));
});
