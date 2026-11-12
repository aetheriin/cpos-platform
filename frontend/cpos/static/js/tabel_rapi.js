// ===== TABEL SERAGAM: kerangka memuat, urut kolom, format tanggal =====
// Berlaku otomatis untuk semua tabel di isi halaman (.konten), tanpa kode tambahan di tiap halaman.
// - Kerangka memuat: <tbody> yang masih kosong saat terlihat diisi baris abu-abu berkedip sampai datanya datang
//   (hilang sendiri saat isi tbody diganti). <tbody data-tanpa-kerangka> = tidak (mis. tabel yang baru diisi
//   setelah tombol ditekan). Tidak ada data dalam 15 detik -> kerangka dibuang.
// - Urut kolom: klik judul kolom -> naik / turun. Angka "28.500 kg", tanggal "28-10-2026 14:00", dan teks dikenali.
//   <table data-tanpa-urut> / <th data-tanpa-urut> = tidak bisa diurutkan (pohon menu, jadwal harian, dll.);
//   tabel laporan berbaris ringkasan (.tbs-tabel, RekapIn Pembelian TBS) juga tidak.
//   Urutan tetap berlaku saat data dimuat ulang. Baris satu sel (kosong / catatan batas) selalu di bawah.
// - Tanggal: teks "2026-10-28" / "2026-10-28 14:00" di sel tabel & teks data ditampilkan "28-10-2026" / "28-10-2026 14:00".

const KERANGKA_BARIS = 3;
const KERANGKA_MAKS_MS = 15000;

function kolomTabel(tbody) {
    const kepala = tbody.closest('table')?.tHead;
    return kepala && kepala.rows.length ? kepala.rows[kepala.rows.length - 1].cells.length : 1;
}

function pasangKerangka(tbody) {
    if (tbody.rows.length || tbody._kerangkaSelesai || 'tanpaKerangka' in tbody.dataset || !tbody.offsetParent
        || tbody.closest('.modal-overlay')) return;
    tbody._kerangkaSelesai = true;                      // sekali per tbody: muat ulang berikutnya tidak memakai kerangka
    const kolom = kolomTabel(tbody);
    const sel = [...Array(kolom)].map((_, i) => `<td class="table-cell"><span class="kerangka" style="width:${[70, 55, 85, 40][i % 4]}%"></span></td>`).join('');
    tbody.innerHTML = [...Array(KERANGKA_BARIS)].map(() => `<tr class="baris-kerangka" aria-hidden="true">${sel}</tr>`).join('');
    setTimeout(() => tbody.querySelectorAll('.baris-kerangka').forEach(tr => tr.remove()), KERANGKA_MAKS_MS);
}

function pasangKerangkaTerlihat() {
    document.querySelectorAll('.konten tbody').forEach(pasangKerangka);
}

// ---------- tanggal ----------
// Sel tabel, daftar keterangan (dd), teks data (.font-mono, mis. "Tanggal DO" di kartu Kontrak), [data-tgl]
const PILIH_TGL = 'td, dd, .font-mono, [data-tgl]';
const POLA_TGL_ISO = /(^|[^\w\-/])((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?![\w\-/])/g;

function rapikanTanggal(akar) {
    const sel = akar.matches && akar.matches(PILIH_TGL) ? [akar] : [];
    (akar.querySelectorAll ? [...sel, ...akar.querySelectorAll(PILIH_TGL)] : []).forEach(el => {
        const jalan = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        for (let n = jalan.nextNode(); n; n = jalan.nextNode()) {
            if (!/\d{4}-\d{2}-\d{2}/.test(n.data)) continue;
            const baru = n.data.replace(POLA_TGL_ISO, (_, a, y, m, d) => `${a}${d}-${m}-${y}`);
            if (baru !== n.data) n.data = baru;
        }
    });
}

// ---------- urut kolom ----------
// Nilai sel -> [jenis, nilai]: 0 = angka/tanggal, 1 = teks, 2 = kosong (selalu di bawah)
function nilaiUrut(td) {
    const teks = (td?.dataset.urut ?? td?.textContent ?? '').replace(/\s+/g, ' ').trim();
    if (!teks || /^[-–—]$/.test(teks)) return [2, ''];
    let m = teks.match(/^(\d{2})-(\d{2})-(\d{4})(?: (\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (m) return [0, Date.UTC(m[3], m[2] - 1, m[1], m[4] || 0, m[5] || 0, m[6] || 0)];
    m = teks.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/);
    if (m) return [0, Date.UTC(m[1], m[2] - 1, m[3], m[4] || 0, m[5] || 0)];
    const t = teks.replace(/^Rp\.?\s*/i, '').replace(/\s*(kg|%|ton|km|liter|l)$/i, '');
    if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(t) || /^-?\d+(,\d+)?$/.test(t)) return [0, Number(t.replace(/\./g, '').replace(',', '.'))];
    return [1, teks.toLocaleLowerCase()];
}

const pembandingTeks = new Intl.Collator('id', { numeric: true, sensitivity: 'base' });

function urutkanTabel(tabel) {
    const u = tabel._urut;
    const tbody = tabel.tBodies[0];
    if (!u || !tbody) return;
    const semua = [...tbody.rows].filter(tr => !tr.classList.contains('baris-kerangka'));
    const data = semua.filter(tr => tr.cells.length > 1);
    if (data.length < 2) return;
    const lain = semua.filter(tr => tr.cells.length <= 1);
    const kunci = new Map(data.map((tr, i) => [tr, [...nilaiUrut(tr.cells[u.kolom]), i]]));
    data.sort((a, b) => {
        const [ja, va, ia] = kunci.get(a), [jb, vb, ib] = kunci.get(b);
        if (ja !== jb) return ja - jb;                  // angka/tanggal, teks, lalu kosong
        if (ja === 2) return ia - ib;
        const hasil = ja === 0 ? va - vb : pembandingTeks.compare(va, vb);
        return (hasil || ia - ib) * (hasil ? u.arah : 1);
    });
    const urutBaru = [...data, ...lain];
    if (urutBaru.every((tr, i) => tbody.rows[i] === tr)) return;
    tabel._mengurutkan = true;
    tbody.append(...urutBaru);
    tabel._pengamatUrut.takeRecords();                  // perubahan karena pengurutan sendiri tidak memicu urut ulang
    tabel._mengurutkan = false;
}

function tandaUrut(tabel) {
    [...tabel.tHead.rows[0].cells].forEach((th, i) => {
        const ikon = th.querySelector('.ikon-urut');
        if (!ikon) return;
        const aktif = tabel._urut && tabel._urut.kolom === i;
        ikon.className = `ikon-urut fa-solid ${aktif ? (tabel._urut.arah > 0 ? 'fa-sort-up' : 'fa-sort-down') : 'fa-sort'}`;
        th.setAttribute('aria-sort', aktif ? (tabel._urut.arah > 0 ? 'ascending' : 'descending') : 'none');
    });
}

function pasangUrut(tabel) {
    if (tabel._urutTerpasang || 'tanpaUrut' in tabel.dataset || tabel.classList.contains('tbs-tabel') || !tabel.tHead || tabel.tHead.rows.length !== 1
        || !tabel.tBodies[0] || !tabel.closest('.konten')) return;
    tabel._urutTerpasang = true;
    [...tabel.tHead.rows[0].cells].forEach((th, i) => {
        const label = th.textContent.trim();
        if (!label || 'tanpaUrut' in th.dataset || /^(aksi|action|actions)$/i.test(label) || th.querySelector('input, select, button')) return;
        th.classList.add('th-urut');
        th.tabIndex = 0;
        th.title = th.title || 'Klik untuk mengurutkan';
        th.insertAdjacentHTML('beforeend', ' <i class="ikon-urut fa-solid fa-sort" aria-hidden="true"></i>');
        const klik = () => {
            const u = tabel._urut;
            tabel._urut = u && u.kolom === i ? { kolom: i, arah: -u.arah } : { kolom: i, arah: 1 };
            tandaUrut(tabel);
            urutkanTabel(tabel);
        };
        th.addEventListener('click', klik);
        th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); klik(); } });
    });
    // Data dimuat ulang (isi tbody diganti) -> urutan yang dipilih diterapkan lagi
    tabel._pengamatUrut = new MutationObserver(() => { if (!tabel._mengurutkan) urutkanTabel(tabel); });
    tabel._pengamatUrut.observe(tabel.tBodies[0], { childList: true });
}

function pasangUrutSemua() {
    document.querySelectorAll('.konten table').forEach(pasangUrut);
}

document.addEventListener('DOMContentLoaded', () => {
    rapikanTanggal(document.body);
    pasangUrutSemua();
    pasangKerangkaTerlihat();
    // Kerangka hilang begitu baris data pertama masuk walau kode halaman menambah baris (bukan mengganti isi)
    new MutationObserver(daftar => {
        const tbodySentuh = new Set();
        daftar.forEach(m => m.target.tagName === 'TBODY' && (m.target._kerangkaSelesai = true));
        daftar.forEach(m => m.addedNodes.forEach(n => {
            if (n.nodeType !== 1) return;
            rapikanTanggal(n);
            if (n.tagName === 'TR' && !n.classList.contains('baris-kerangka') && n.parentElement?.tagName === 'TBODY') tbodySentuh.add(n.parentElement);
            if (n.tagName === 'TABLE' || n.querySelector?.('table')) setTimeout(pasangUrutSemua, 0);
        }));
        tbodySentuh.forEach(tb => tb.querySelectorAll(':scope > .baris-kerangka').forEach(tr => tr.remove()));
    }).observe(document.body, { childList: true, subtree: true });
    // Tab lain dibuka -> tabelnya yang masih kosong ikut memakai kerangka
    window.addEventListener('tabChange', () => setTimeout(pasangKerangkaTerlihat, 0));
});
