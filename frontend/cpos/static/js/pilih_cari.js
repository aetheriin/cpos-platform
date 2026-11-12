// ===== PILIHAN DENGAN PENCARIAN (dropdown) =====
// Tombol menampilkan pilihan; diklik -> panel dengan kotak cari di atas & daftar pilihan (yang aktif bertanda centang).
// Otomatis untuk semua <select class="input-field"> (juga yang ditambahkan belakangan lewat JS).
// Tidak mau? beri atribut data-tanpa-cari. <select> lama tetap ada (tak terlihat) sebagai sumber nilai, jadi
// select.value = ..., .disabled, isi <option>, form.reset(), data-on-change, dan validasi required tetap jalan.
// Select wajib (required) di dalam form diberi pilihan kosong "-- Pilih ... --": saat Tambah tidak ada yang
// langsung terpilih, user harus memilih sendiri. Daftar pilihan baru muncul saat diklik / diketik.
const PILIH_CARI = 'select.input-field:not([data-tanpa-cari]), select[data-cari]';
const KELAS_TATA_LETAK = /(^|:)(w-|min-w-|max-w-|col-span-|flex-|grow|shrink|basis-)/;

function labelPilihan(sel) {
    const label = sel.id && document.querySelector(`label[for="${sel.id}"]`);
    const teks = label ? label.textContent.replace(/[*:]/g, '').trim() : '';
    return teks ? `-- Pilih ${teks.toLowerCase()} --` : '-- Pilih --';
}

// Pilihan kosong (tak bisa dipilih ulang) sebagai bawaan form.reset(), supaya Tambah dimulai dari kosong
function pasangPilihanKosong(sel, pilihKosong = true) {
    if (!sel.required || !sel.form || Array.from(sel.options).some(o => o.value === '')) return;
    const kosong = new Option(labelPilihan(sel), '', true, false);
    kosong.disabled = kosong.hidden = true;
    const terpilih = sel.selectedIndex >= 0 && sel.options[sel.selectedIndex].defaultSelected;
    sel.insertBefore(kosong, sel.firstChild);
    if (pilihKosong && !terpilih) sel.selectedIndex = 0;
}

function pasangPilihCari(sel) {
    if (sel.dataset.cariTerpasang || sel.multiple || Number(sel.size) > 1) return;
    sel.dataset.cariTerpasang = '1';
    pasangPilihanKosong(sel);

    // Lebar / posisi grid ikut ke pembungkus, sisanya (ukuran teks, padding) ke kotak ketik
    const kelas = sel.className.split(/\s+/).filter(Boolean);
    const bungkus = document.createElement('div');
    bungkus.className = ['relative', ...kelas.filter(k => KELAS_TATA_LETAK.test(k))].join(' ');
    if (sel.hasAttribute('data-henti-klik')) bungkus.setAttribute('data-henti-klik', '');
    sel.parentNode.insertBefore(bungkus, sel);

    // Tombol (tampilan pilihan) + panel: kotak cari di atas, daftar pilihan di bawah (pilihan aktif bertanda centang)
    const input = document.createElement('button');
    input.type = 'button';
    input.className = [...kelas.filter(k => !KELAS_TATA_LETAK.test(k)), 'w-full', 'pr-8', 'text-left', 'truncate', 'pilih-cari-tombol'].join(' ');
    if (sel.id) input.id = sel.id + 'Cari';
    if (sel.title) input.title = sel.title;
    const ikon = document.createElement('i');
    ikon.className = 'fa-solid fa-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none';
    const daftar = document.createElement('div');
    // position: fixed supaya panel tidak terpotong modal / tabel (overflow)
    daftar.className = 'pilih-cari-panel hidden';
    Object.assign(daftar.style, { position: 'fixed', zIndex: '1000', maxWidth: '28rem' });
    daftar.innerHTML = `<div class="pilih-cari-kepala"><div class="relative">
            <i class="fa-solid fa-magnifying-glass absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
            <input type="text" autocomplete="off" class="pilih-cari-ketik" placeholder="${escapeHtml(t('Cari...'))}"></div></div>
        <ul class="pilih-cari-daftar"></ul>`;
    const ketik = daftar.querySelector('input');
    const ul = daftar.querySelector('ul');
    bungkus.append(sel, input, ikon);
    document.body.appendChild(daftar);

    // Tak terlihat tetapi tetap bisa difokus browser, supaya pesan "wajib diisi" (required) tetap muncul
    Object.assign(sel.style, { position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', opacity: '0', pointerEvents: 'none' });
    sel.tabIndex = -1;
    sel.addEventListener('focus', () => input.focus());

    let sorot = -1, cocok = [];
    const opsi = () => Array.from(sel.options).filter(o => !o.disabled && !o.hidden && (o.value !== '' || o.text.trim()));
    const terpilih = () => (sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null);
    const terbuka = () => !daftar.classList.contains('hidden');
    const tampil = () => {
        const o = terpilih();
        const kosong = sel.options[0] && sel.options[0].value === '' ? sel.options[0].text.trim() : '';
        const ada = o && o.value !== '';
        input.textContent = ada ? o.text : (kosong || t('Pilih...'));
        input.classList.toggle('text-slate-400', !ada);
        ketik.placeholder = `${t('Cari')} ${(labelPilihan(sel).replace(/^-- Pilih |--$/g, '').trim() || '').toLowerCase()}...`.replace(/\s+\.\.\.$/, '...');
    };

    function render(kata) {
        const k = (kata || '').trim().toLowerCase();
        cocok = opsi().filter(o => !k || o.text.toLowerCase().includes(k));
        const aktif = terpilih();
        sorot = k ? (cocok.length ? 0 : -1) : Math.max(0, cocok.indexOf(aktif));
        ul.innerHTML = cocok.length
            ? cocok.map((o, i) => `<li data-i="${i}" class="pilih-cari-item${o === aktif && o.value !== '' ? ' pilih-cari-aktif' : ''}${o.value === '' ? ' text-slate-400' : ''}">
                <span class="truncate">${escapeHtml(o.text)}</span>${o === aktif && o.value !== '' ? '<i class="fa-solid fa-check text-blue-600 text-xs flex-shrink-0"></i>' : ''}</li>`).join('')
            : `<li class="px-3 py-2 text-sm italic text-center text-slate-400">${t('Data tidak ditemukan')}</li>`;
        posisi();
        tandai();
    }
    function buka() {
        if (sel.disabled) return;
        daftar.classList.remove('hidden');
        input.classList.add('pilih-cari-buka');
        ketik.value = '';
        render('');
        ketik.focus();
        setTimeout(() => { if (terbuka() && document.activeElement === input) ketik.focus(); }, 10);
    }
    // Di bawah tombol; pindah ke atas bila ruang di bawah sempit
    function posisi() {
        const k = input.getBoundingClientRect();
        const bawah = window.innerHeight - k.bottom - 8, atas = k.top - 8;
        const keAtas = bawah < 220 && atas > bawah;
        daftar.style.left = `${k.left}px`;
        daftar.style.width = `${Math.max(k.width, 200)}px`;
        ul.style.maxHeight = `${Math.max(100, Math.min(224, (keAtas ? atas : bawah) - 56))}px`;
        daftar.style.top = keAtas ? `${Math.max(8, k.top - 4 - daftar.offsetHeight)}px` : `${k.bottom + 4}px`;
    }
    const ikutiLayar = () => { if (terbuka()) posisi(); };
    window.addEventListener('resize', ikutiLayar);
    window.addEventListener('scroll', e => { if (!daftar.contains(e.target)) ikutiLayar(); }, true);
    function tandai() {
        ul.querySelectorAll('[data-i]').forEach(el => el.classList.toggle('pilih-cari-sorot', Number(el.dataset.i) === sorot));
        const el = ul.querySelector(`[data-i="${sorot}"]`);
        if (el) el.scrollIntoView({ block: 'nearest' });
    }
    function tutup(fokus) {
        if (!terbuka()) return;
        daftar.classList.add('hidden');
        input.classList.remove('pilih-cari-buka');
        if (fokus) input.focus();
    }
    function pilih(o) {
        const lama = sel.value;
        nilaiAsli.set.call(sel, o ? o.value : '');
        tampil();
        tutup(true);
        if (sel.value !== lama) {
            sel.dispatchEvent(new Event('input', { bubbles: true }));
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    input.addEventListener('click', () => (terbuka() ? tutup() : buka()));
    // Tombol terfokus: panah / Enter / Spasi / huruf membuka panel (huruf langsung jadi kata cari)
    input.addEventListener('keydown', e => {
        if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); buka(); }
        else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            // Huruf yang terketik sebelum kotak cari sempat terfokus tetap masuk ke kata cari
            e.preventDefault();
            if (!terbuka()) buka();
            ketik.value += e.key;
            ketik.focus();
            render(ketik.value);
        }
    });
    ketik.addEventListener('input', () => render(ketik.value));
    ketik.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (cocok.length) sorot = (sorot + (e.key === 'ArrowDown' ? 1 : -1) + cocok.length) % cocok.length;
            tandai();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (cocok[sorot]) pilih(cocok[sorot]);
        } else if (e.key === 'Escape') {
            e.stopPropagation();                                  // jangan ikut menutup modal
            tutup(true);
        } else if (e.key === 'Tab') {
            if (ketik.value.trim() && cocok[sorot]) pilih(cocok[sorot]); else tutup();
        }
    });
    // mousedown (bukan click) supaya terpilih sebelum kotak cari kehilangan fokus
    ul.addEventListener('mousedown', e => {
        e.preventDefault();
        const el = e.target.closest('[data-i]');
        if (el) pilih(cocok[Number(el.dataset.i)]);
    });
    document.addEventListener('mousedown', e => { if (terbuka() && !daftar.contains(e.target) && !bungkus.contains(e.target)) tutup(); });
    // Modal ditutup / tombol hilang dari layar -> panel ikut tertutup
    new MutationObserver(() => { if (terbuka() && !input.offsetParent) tutup(); })
        .observe(document.body, { attributes: true, subtree: true, attributeFilter: ['class'] });

    // select.value = ... dari JS lain (mis. terisi dari DO) -> kotak ketik ikut berubah
    const nilaiAsli = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    Object.defineProperty(sel, 'value', {
        configurable: true,
        get() { return nilaiAsli.get.call(sel); },
        set(v) { nilaiAsli.set.call(sel, v); tampil(); },
    });
    const indeksAsli = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    Object.defineProperty(sel, 'selectedIndex', {
        configurable: true,
        get() { return indeksAsli.get.call(sel); },
        set(v) { indeksAsli.set.call(sel, v); tampil(); },
    });
    sel.addEventListener('change', tampil);
    sel.form?.addEventListener('reset', () => setTimeout(tampil));
    const aturDisabled = () => {
        input.disabled = sel.disabled;
        input.classList.toggle('bg-slate-50', sel.disabled);
        if (sel.disabled) tutup();
    };
    new MutationObserver(() => { pasangPilihanKosong(sel, false); aturDisabled(); tampil(); })
        .observe(sel, { attributes: true, attributeFilter: ['disabled'], childList: true, subtree: true, characterData: true });
    aturDisabled();
    tampil();
}

function pasangSemuaPilihCari(akar) {
    if (akar.matches?.(PILIH_CARI)) pasangPilihCari(akar);
    akar.querySelectorAll?.(PILIH_CARI).forEach(pasangPilihCari);
}

pasangSemuaPilihCari(document);
// Select yang dibuat belakangan (baris tabel / form dinamis) ikut dipasang
new MutationObserver(daftar => daftar.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) pasangSemuaPilihCari(n); })))
    .observe(document.body, { childList: true, subtree: true });
