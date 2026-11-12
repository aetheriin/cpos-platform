// ===== PILIH BANYAK DENGAN PENCARIAN (area, perusahaan, ...) =====
// Daftar centang panjang diganti: kotak cari -> daftar centang 2 kolom muncul saat mengetik -> pilihan tampil sebagai
// chip 2 kolom dengan tombol x. Centang asli tetap di dalam form (disembunyikan), jadi pengiriman form & kode yang
// mengisi centang (checked = ...) tidak berubah; tampilan menyesuaikan sendiri.
//   <div data-pilih-banyak data-cari="Ketik untuk mencari area..." data-kosong="Area yang dipilih akan muncul di sini..." [data-semua]>
//       <div id="...">...<label><input type="checkbox" name="area" value="..."> Teks</label>...</div>   <- boleh diisi ulang kode lain
//   </div>
// data-semua: tampilkan tombol "Pilih semua" / "Kosongkan".
const PilihBanyak = {
    pasang(akar) {
        if (akar.dataset.pilihBanyakSiap) return;
        akar.dataset.pilihBanyakSiap = '1';
        const sumber = document.createElement('div');
        sumber.className = 'hidden';
        sumber.dataset.sumber = '';
        while (akar.firstChild) sumber.appendChild(akar.firstChild);
        akar.innerHTML = `
            <div class="flex items-center gap-2">
                <div class="relative flex-1">
                    <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
                    <input type="search" class="input-field pl-8" autocomplete="off" data-pb-cari placeholder="${escapeHtml(t(akar.dataset.cari || 'Ketik untuk mencari...'))}">
                </div>
                ${akar.dataset.semua !== undefined ? `<button type="button" class="btn-secondary btn-sm whitespace-nowrap" data-pb-semua>${t('Pilih semua')}</button>
                    <button type="button" class="btn-secondary btn-sm whitespace-nowrap" data-pb-kosong>${t('Kosongkan')}</button>` : ''}
            </div>
            <div class="hidden mt-1 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 shadow-md" data-pb-daftar>
                <div class="grid grid-cols-2 gap-x-3 gap-y-2" data-pb-isi></div>
            </div>
            <div class="mt-2 max-h-32 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
                <div class="grid grid-cols-2 gap-2 min-h-[1.5rem]" data-pb-chip></div>
            </div>`;
        akar.appendChild(sumber);
        const cari = akar.querySelector('[data-pb-cari]');
        const daftar = akar.querySelector('[data-pb-daftar]');
        const opsi = () => [...sumber.querySelectorAll('input[type=checkbox]')].map(c => ({ c, teks: (c.closest('label') || c.parentElement).textContent.trim() }));

        const isiDaftar = () => {
            const q = cari.value.toLowerCase().trim();
            if (!q) { daftar.classList.add('hidden'); return; }
            daftar.classList.remove('hidden');
            const semua = opsi();
            const cocok = semua.filter(o => !o.c.disabled && o.teks.toLowerCase().includes(q));
            akar.querySelector('[data-pb-isi]').innerHTML = cocok.map(o => `
                <label class="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none min-w-0">
                    <input type="checkbox" class="w-3.5 h-3.5 flex-shrink-0" data-pb-i="${semua.indexOf(o)}"${o.c.checked ? ' checked' : ''}>
                    <span class="truncate">${escapeHtml(o.teks)}</span></label>`).join('')
                || `<p class="col-span-2 text-center text-xs italic text-slate-400 py-2">${t('Tidak ditemukan')}</p>`;
        };
        const ubah = (c, nilai) => {
            if (c.checked === nilai) return;
            c.checked = nilai;
            c.dispatchEvent(new Event('change', { bubbles: true }));
        };
        let jejak = '';
        const isiChip = () => {
            const semua = opsi();
            const terpilih = semua.filter(o => o.c.checked);
            jejak = semua.map(o => (o.c.checked ? 1 : 0) + o.c.value).join(',');
            akar.querySelector('[data-pb-chip]').innerHTML = terpilih.map(o => `
                <div class="flex items-center justify-between gap-2 rounded-md border border-blue-200 bg-blue-50 px-2 py-1.5 min-w-0">
                    <span class="truncate text-xs font-medium text-blue-700">${escapeHtml(o.teks)}</span>
                    ${o.c.disabled ? '' : `<button type="button" class="flex-shrink-0 text-blue-400 hover:text-blue-700" data-pb-hapus="${semua.indexOf(o)}" title="${t('Hapus')}"><i class="fa-solid fa-xmark text-xs"></i></button>`}
                </div>`).join('')
                || `<p class="col-span-2 text-xs italic text-slate-400 py-0.5">${escapeHtml(t(akar.dataset.kosong || 'Pilihan akan muncul di sini...'))}</p>`;
        };

        cari.addEventListener('input', isiDaftar);
        cari.addEventListener('focus', isiDaftar);
        cari.addEventListener('keydown', e => { if (e.key === 'Enter') e.preventDefault(); });
        akar.addEventListener('change', e => {
            const i = e.target.dataset.pbI;
            if (i === undefined) return;
            e.stopPropagation();
            ubah(opsi()[+i].c, e.target.checked);
            isiChip();
        });
        akar.addEventListener('click', e => {
            const hapus = e.target.closest('[data-pb-hapus]');
            if (hapus) { ubah(opsi()[+hapus.dataset.pbHapus].c, false); isiChip(); isiDaftar(); }
            if (e.target.closest('[data-pb-semua]')) { opsi().forEach(o => !o.c.disabled && ubah(o.c, true)); isiChip(); isiDaftar(); }
            if (e.target.closest('[data-pb-kosong]')) { opsi().forEach(o => !o.c.disabled && ubah(o.c, false)); isiChip(); isiDaftar(); }
        });
        document.addEventListener('click', e => { if (!akar.contains(e.target)) daftar.classList.add('hidden'); });
        // Centang diisi kode lain (buka form ubah, daftar dibuat ulang): tampilan disegarkan selama komponen terlihat
        setInterval(() => {
            if (!akar.offsetParent) { if (cari.value) { cari.value = ''; daftar.classList.add('hidden'); } return; }
            if (opsi().map(o => (o.c.checked ? 1 : 0) + o.c.value).join(',') !== jejak) isiChip();
        }, 300);
        isiChip();
    },
};

document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('[data-pilih-banyak]').forEach(el => PilihBanyak.pasang(el)));
