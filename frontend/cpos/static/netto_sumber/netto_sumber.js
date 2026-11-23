// Form Netto Sumber (modules/netto_sumber/routes.py, /netto-sumber/api/*). Daftar tiket dimuat sekali per perusahaan dan rentang;
// produk, pencarian, dan status disaring di browser.
(() => {
    const akar = document.getElementById('nettoSumber');
    if (!akar) return;

    const el = id => document.getElementById(id);
    const hak = JSON.parse(akar.dataset.hak || '{}');
    const batas = Number(akar.dataset.batas) || 0;
    const maksHari = Number(akar.dataset.maksHari) || 62;
    const KOLOM = 10;
    const STATUS = {
        perlu_diisi: ['Perlu diisi', WARNA_BADGE.oranye],
        perlu_dicek: ['Perlu dicek', WARNA_BADGE.merah],
        dari_ascend: ['Dari Ascend', WARNA_BADGE.abu],
        diisi: ['Diisi', WARNA_BADGE.hijau],
    };

    let data = [];
    let tampil = [];
    let status = 'perlu_diisi';
    let aktif = null;
    let nomorMuat = 0;
    let jeda = null;

    const angka = n => Number(n).toLocaleString('id-ID', { maximumFractionDigits: 2 });
    const persen = n => Number(n).toLocaleString('id-ID', { maximumFractionDigits: 2 });
    // Format tanggal web CPOS: 20-11-2026 dan 20-11-2026 14:05
    const dua = n => String(n).padStart(2, '0');
    const tglDari = d => `${dua(d.getDate())}-${dua(d.getMonth() + 1)}-${d.getFullYear()}`;
    const tanggal = iso => tglDari(new Date(`${iso}T00:00:00`));
    const waktu = iso => { const d = new Date(iso); return `${tglDari(d)} ${dua(d.getHours())}:${dua(d.getMinutes())}`; };
    const sumber = t => (t.isian ? t.isian.netto_sumber : t.sumber_ascend);
    // Sama dengan _netto() di routes.py: 28340, 28.340, atau 28340,5. NaN bila bukan angka.
    function bacaAngka(teks) {
        let s = String(teks || '').replace(/\s/g, '');
        if (!s) return NaN;
        if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
        else if ((s.match(/\./g) || []).length > 1 || /^\d+\.\d{3}$/.test(s)) s = s.replace(/\./g, '');
        return /^\d+(\.\d+)?$/.test(s) ? Number(s) : NaN;
    }
    const bisaUbah = t => (!t.terkunci || hak.setujui) && (t.isian ? hak.ubah : hak.tambah);

    // Selisih = netto timbangan kita dikurangi netto sumber; hanya bila netto sumber wajar
    function selisih(netto, s) {
        if (!(s > 0) || !netto) return null;
        const kg = netto - s;
        return { kg, persen: Math.abs(kg) / netto * 100 };
    }

    // ===== Daftar =====
    function cocok(t, denganStatus) {
        const produk = el('nsProduk').value;
        const cari = el('nsCari').value.trim().toLocaleLowerCase('id-ID');
        return (!denganStatus || !status || t.status === status)
            && (!produk || t.produk === produk)
            && (!cari || [t.tiket, t.pembeli, t.no_do, t.kendaraan].some(v => (v || '').toLocaleLowerCase('id-ID').includes(cari)));
    }

    function baris(t, i) {
        const s = sumber(t);
        const dicek = t.status === 'perlu_dicek';          // angka Ascend-nya tidak bisa dipakai, jadi selisihnya tidak dihitung
        const beda = dicek ? null : selisih(t.netto, s);
        const [label, warna] = STATUS[t.status];
        const aksi = bisaUbah(t) ? (t.isian ? 'Ubah' : 'Isi') : 'Lihat';
        const kolomPt = el('nsPerusahaan').value ? ' hidden' : '';
        return `<tr class="hover:bg-slate-50 align-top">
            <td class="table-cell whitespace-nowrap">${escapeHtml(tanggal(t.tanggal))}</td>
            <td class="table-cell whitespace-nowrap${kolomPt}">${escapeHtml(t.comp)}</td>
            <td class="table-cell">
                <span class="font-mono text-slate-900 whitespace-nowrap">${escapeHtml(t.tiket)}</span>
                ${t.split ? `<span class="ml-1 text-[11px] font-semibold text-slate-500">split</span>` : ''}
                ${t.no_do ? `<div class="text-xs text-slate-500">DO ${escapeHtml(t.no_do)}</div>` : ''}
            </td>
            <td class="table-cell min-w-[5rem]">${escapeHtml(t.produk)}</td>
            <td class="table-cell">${escapeHtml(t.pembeli || '-')}</td>
            <td class="table-cell text-right tabular-nums">${angka(t.netto)}</td>
            <td class="table-cell text-right tabular-nums${dicek ? ' text-red-700' : ''}">${s ? angka(s) : ''}</td>
            <td class="table-cell text-right tabular-nums">${beda ? `${beda.kg > 0 ? '+' : ''}${angka(beda.kg)}<div class="text-xs text-slate-500">${persen(beda.persen)}%</div>` : ''}</td>
            <td class="table-cell whitespace-nowrap">${badge(label, warna)}${t.terkunci ? ' <i class="fa-solid fa-lock text-xs text-slate-400" title="Bulan sudah ditutup"></i><span class="sr-only">Bulan sudah ditutup</span>' : ''}</td>
            <td class="table-cell text-right"><button type="button" class="btn-secondary btn-sm whitespace-nowrap" data-buka="${i}">${aksi}<span class="sr-only"> ${escapeHtml(t.tiket)}</span></button></td>
        </tr>`;
    }

    function tampilkan() {
        const dasar = data.filter(t => cocok(t, false));
        const jumlah = { '': dasar.length };
        dasar.forEach(t => { jumlah[t.status] = (jumlah[t.status] || 0) + 1; });
        document.querySelectorAll('[data-jumlah]').forEach(s => { s.textContent = angka(jumlah[s.dataset.jumlah] || 0); });
        tampil = dasar.filter(t => cocok(t, true));
        document.querySelector('[data-kolom-pt]').classList.toggle('hidden', !!el('nsPerusahaan').value);
        const tbody = el('nsTabel');
        if (tampil.length) {
            tbody.innerHTML = tampil.map(baris).join('');
        } else if (!data.length) {
            tbody.innerHTML = barisKosong(KOLOM, 'Tidak ada tiket CPO, PFAD, R.POME, RUCO, atau tiket split pada rentang ini.');
        } else {
            const teks = status === 'perlu_diisi' && !el('nsCari').value && !el('nsProduk').value
                ? 'Semua tiket pada rentang ini sudah punya netto sumber.'
                : 'Tidak ada tiket yang cocok. Ubah status, produk, atau kata pencarian.';
            tbody.innerHTML = barisKosong(KOLOM, teks);
        }
    }

    function isiProduk() {
        const pilih = el('nsProduk');
        const lama = pilih.value;
        const daftar = [...new Set(data.map(t => t.produk))].sort((a, b) => a.localeCompare(b, 'id'));
        pilih.innerHTML = '<option value="">Semua produk</option>'
            + daftar.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('');
        pilih.value = daftar.includes(lama) ? lama : '';
    }

    function peringatan(res) {
        const pesan = [];
        if (res.pesan) pesan.push(res.pesan);
        if (res.gagal && res.gagal.length) pesan.push(`Tiket PT ${res.gagal.join(', ')} belum bisa dibaca dari Ascend, jadi belum masuk daftar. Coba muat ulang halaman.`);
        el('nsPeringatan').textContent = pesan.join(' ');
        el('nsPeringatan').classList.toggle('hidden', !pesan.length);
    }

    function rentangSalah() {
        const mulai = el('nsMulai').value;
        const akhir = el('nsAkhir').value;
        if (!mulai || !akhir) return 'Isi tanggal dari dan sampai.';
        if (mulai > akhir) return 'Tanggal dari tidak boleh setelah tanggal sampai.';
        const hari = (new Date(`${akhir}T00:00:00`) - new Date(`${mulai}T00:00:00`)) / 86400000 + 1;
        return hari > maksHari ? `Rentang paling panjang ${maksHari} hari.` : '';
    }

    async function muat() {
        const nomor = ++nomorMuat;
        const salah = rentangSalah();
        if (salah) {
            data = [];
            el('nsInfo').textContent = salah;
            el('nsTabel').innerHTML = barisGagal(KOLOM, salah);
            return;
        }
        el('nsInfo').textContent = 'Memuat tiket…';
        el('nsTabel').innerHTML = `<tr><td colspan="${KOLOM}" class="table-cell text-center py-10 text-sm text-slate-500">Memuat tiket dari Ascend…</td></tr>`;
        const q = new URLSearchParams({ perusahaan: el('nsPerusahaan').value, mulai: el('nsMulai').value, akhir: el('nsAkhir').value });
        const res = await ambilJson(`/netto-sumber/api/tiket?${q}`);
        if (nomor !== nomorMuat) return;            // sudah ada permintaan yang lebih baru
        if (res.error) {
            data = [];
            peringatan({});
            el('nsInfo').textContent = 'Tiket gagal dimuat.';
            el('nsTabel').innerHTML = barisGagal(KOLOM, res.error);
            document.querySelectorAll('[data-jumlah]').forEach(s => { s.textContent = '-'; });
            return;
        }
        data = res.data;
        peringatan(res);
        isiProduk();
        el('nsInfo').textContent = `${angka(data.length)} tiket · dimuat pukul ${waktu(res.dimuat).slice(11)}`;
        tampilkan();
    }

    function muatNanti() {
        clearTimeout(jeda);
        jeda = setTimeout(muat, 400);
    }

    // ===== Isian satu tiket =====
    function dataTiket(t) {
        const isi = [['Perusahaan', t.comp], ['Tanggal', tanggal(t.tanggal)], ['Produk', t.produk], ['Pembeli', t.pembeli || '-'],
                     ['Nomor DO', t.no_do || '-'], ['Kendaraan', t.kendaraan || '-'], ['Netto timbangan', `${angka(t.netto)} kg`],
                     ['Netto sumber Ascend', `${angka(t.sumber_ascend)} kg`]];
        return isi.map(([k, v]) => `<div class="min-w-0"><dt class="text-xs text-slate-500">${escapeHtml(k)}</dt>
            <dd class="font-medium text-slate-800 break-words${/kg$/.test(v) ? ' tabular-nums' : ''}">${escapeHtml(v)}</dd></div>`).join('');
    }

    function infoPasangan(t) {
        if (!t.split) return null;
        const pecahan = data.filter(x => x.comp === t.comp && x.induk === t.induk);
        const lain = pecahan.filter(x => x.tiket !== t.tiket);
        const rusak = pecahan.some(x => x.sumber_ascend < 0);
        const teks = [`Pecahan split dari ${t.induk}.`];
        if (rusak) {
            teks.push('Netto sumber Ascend untuk tiket split ini salah: pecahan pertama berisi netto timbangan, pecahan berikutnya minus. Isi netto sumber tiap pecahan di sini.');
        }
        lain.forEach(x => {
            const s = x.isian ? `${angka(x.isian.netto_sumber)} kg (isian)` : (rusak || !x.sumber_ascend) ? 'belum ada' : `${angka(x.sumber_ascend)} kg`;
            teks.push(`${x.tiket}: netto ${angka(x.netto)} kg, netto sumber ${s}.`);
        });
        if (lain.length) teks.push(`Total netto semua pecahan ${angka(pecahan.reduce((n, x) => n + x.netto, 0))} kg.`);
        return teks;
    }

    // Angka Ascend bisa dipakai bila lebih dari 0 dan bukan pecahan split yang salah (lihat infoPasangan)
    function bisaPakaiAscend(t) {
        if (!(t.sumber_ascend > 0)) return false;
        return !(t.split && data.some(x => x.comp === t.comp && x.induk === t.induk && x.sumber_ascend < 0));
    }

    function perluCatatan() {
        if (!aktif) return false;
        const nilai = bacaAngka(el('nsNilai').value);
        if (!(nilai > 0)) return false;
        const beda = selisih(aktif.netto, nilai);
        return !beda || beda.persen > batas;
    }

    function perbaruiSelisih() {
        const nilai = bacaAngka(el('nsNilai').value);
        const info = el('nsSelisih');
        info.classList.remove('text-red-700');
        el('nsNilai').removeAttribute('aria-invalid');
        if (!(nilai > 0)) {
            info.textContent = '';
        } else {
            const beda = selisih(aktif.netto, nilai);
            const kalimat = beda
                ? [`Selisih dengan netto timbangan ${beda.kg > 0 ? '+' : ''}${angka(beda.kg)} kg (${persen(beda.persen)}%).`,
                   beda.persen > batas ? `Lebih dari ${persen(batas)}%, isi catatan alasannya.` : '']
                : ['Netto timbangan tiket ini 0 kg, isi catatan alasannya.'];
            info.innerHTML = kalimat.filter(Boolean).map(k => `<span>${escapeHtml(k)}</span>`).join(' ');
        }
        const wajib = perluCatatan();
        el('nsCatatanTanda').textContent = wajib ? '(wajib)' : '(opsional)';
        el('nsCatatan').required = wajib;
        if (!wajib) tandaiCatatan('');
    }

    function tandaiCatatan(pesan) {
        el('nsCatatanGalat').textContent = pesan;
        if (pesan) el('nsCatatan').setAttribute('aria-invalid', 'true');
        else el('nsCatatan').removeAttribute('aria-invalid');
    }

    function riwayatHtml(r) {
        const nilai = r.netto_sumber == null ? 'Isian dibatalkan' : `${angka(r.netto_sumber)} kg`;
        const tambahan = [r.referensi && `Ref. ${r.referensi}`, r.catatan].filter(Boolean).map(escapeHtml).join(' · ');
        return `<li class="border-b border-slate-100 pb-2 last:border-0 last:pb-0">
            <div class="flex flex-wrap justify-between gap-x-3"><span class="font-semibold text-slate-800">${escapeHtml(nilai)}</span>
            <span class="text-slate-500">${escapeHtml(r.oleh || '-')} · ${escapeHtml(waktu(r.pada))}</span></div>
            ${tambahan ? `<p class="mt-0.5 break-words">${tambahan}</p>` : ''}</li>`;
    }

    async function muatRiwayat(t) {
        const daftar = el('nsRiwayat');
        daftar.innerHTML = '<li>Memuat riwayat…</li>';
        const res = await ambilJson(`/netto-sumber/api/riwayat?${new URLSearchParams({ perusahaan: t.comp, tiket: t.tiket })}`);
        if (aktif !== t) return;
        if (res.error) { daftar.innerHTML = `<li class="text-red-700">${escapeHtml(res.error)}</li>`; return; }
        daftar.innerHTML = res.length ? res.map(riwayatHtml).join('') : '<li>Belum pernah diisi.</li>';
    }

    function buka(t) {
        aktif = t;
        const ubah = bisaUbah(t);
        const [label] = STATUS[t.status];
        el('nsJudul').textContent = t.tiket;
        el('nsSubjudul').textContent = t.isian ? `Diisi ${t.isian.oleh || ''} · ${waktu(t.isian.pada)}` : label;
        el('nsDataTiket').innerHTML = dataTiket(t);
        // Satu kalimat satu span, supaya tiap kalimat bisa diterjemahkan (i18n.js mencocokkan teks utuh)
        const pasangan = infoPasangan(t);
        el('nsPasangan').innerHTML = pasangan ? pasangan.map(k => `<span>${escapeHtml(k)}</span>`).join(' ') : '';
        el('nsPasangan').classList.toggle('hidden', !pasangan);
        const kunci = !t.terkunci ? ''
            : hak.setujui ? 'Bulan tiket ini sudah ditutup. Anda tetap bisa mengubah karena punya hak Setujui.'
            : 'Bulan tiket ini sudah ditutup. Isian hanya bisa diubah pemegang hak Setujui.';
        el('nsKunci').textContent = kunci;
        el('nsKunci').classList.toggle('hidden', !kunci);
        el('nsNilai').value = t.isian ? angka(t.isian.netto_sumber) : '';
        el('nsReferensi').value = t.isian ? t.isian.referensi : '';
        el('nsCatatan').value = t.isian ? t.isian.catatan : '';
        ['nsNilai', 'nsReferensi', 'nsCatatan'].forEach(id => { el(id).disabled = !ubah; });
        el('nsSimpan').classList.toggle('hidden', !ubah);
        el('nsTutup').textContent = ubah ? 'Batal' : 'Tutup';
        el('nsKembalikan').classList.toggle('hidden', !(t.isian && ubah));
        tandaiCatatan('');
        perbaruiSelisih();
        el('nsRiwayatBox').open = !ubah;
        muatRiwayat(t);
        openModal('modalNettoSumber');
        (ubah ? el('nsNilai') : el('nsTutup')).focus();
    }

    async function kirim(tombol, tambahan) {
        const t = aktif;
        const res = await denganTombol(tombol, () => kirimForm('/netto-sumber/api/simpan', {
            perusahaan: t.comp, tiket: t.tiket, tanggal: t.tanggal, id_terakhir: t.id_terakhir,
            netto_sumber: el('nsNilai').value, referensi: el('nsReferensi').value.trim(), catatan: el('nsCatatan').value.trim(),
            ...tambahan,
        }));
        if (!tampilkanHasil(res)) return;
        closeModal('modalNettoSumber');
        muat();
    }

    el('nsForm').addEventListener('submit', async e => {
        e.preventDefault();
        if (!aktif || !bisaUbah(aktif)) return;
        const nilai = bacaAngka(el('nsNilai').value);
        if (!(nilai > 0)) {
            el('nsSelisih').textContent = 'Isi netto sumber dalam kg, lebih dari 0.';
            el('nsSelisih').classList.add('text-red-700');
            el('nsNilai').setAttribute('aria-invalid', 'true');
            el('nsNilai').focus();
            return;
        }
        if (perluCatatan() && !el('nsCatatan').value.trim()) {
            tandaiCatatan('Isi catatan alasan selisihnya, misalnya nomor surat dari pembeli.');
            el('nsCatatan').focus();
            return;
        }
        await kirim(el('nsSimpan'), {});
    });

    el('nsKembalikan').addEventListener('click', async () => {
        const t = aktif;
        if (!t || !await Dialog.konfirmasi({
            judul: 'Batalkan isian?', teksYa: 'Batalkan isian', bahaya: true,
            pesan: `Isian ${t.tiket} akan dibatalkan ${bisaPakaiAscend(t) ? `dan tiket kembali memakai netto sumber Ascend (${angka(t.sumber_ascend)} kg).` : 'dan tiket kembali tanpa netto sumber, karena angka Ascend-nya kosong atau salah.'} Riwayatnya tetap tersimpan.`,
        })) return;
        await kirim(el('nsKembalikan'), { batalkan: '1', netto_sumber: '', referensi: '', catatan: '' });
    });

    // Form ditutup (tombol, Esc, atau setelah simpan): fokus kembali ke tombol baris yang membukanya, bila barisnya masih ada
    let pembuka = null;
    el('nsTabel').addEventListener('click', e => { pembuka = e.target.closest('[data-buka]') ? e.target.closest('tr') : pembuka; }, true);
    new MutationObserver(() => {
        if (!el('modalNettoSumber').classList.contains('hidden') || !pembuka) return;
        const tiket = pembuka.querySelector('.font-mono')?.textContent;
        const tujuan = [...el('nsTabel').querySelectorAll('tr')].find(tr => tr.querySelector('.font-mono')?.textContent === tiket);
        (tujuan || pembuka).querySelector('[data-buka]')?.focus();
        pembuka = null;
    }).observe(el('modalNettoSumber'), { attributes: true, attributeFilter: ['class'] });

    el('nsNilai').addEventListener('input', perbaruiSelisih);
    el('nsCatatan').addEventListener('input', () => { if (el('nsCatatan').value.trim()) tandaiCatatan(''); });
    el('nsTabel').addEventListener('click', e => {
        const tombol = e.target.closest('[data-buka]');
        if (tombol) buka(tampil[Number(tombol.dataset.buka)]);
    });
    el('nsStatus').addEventListener('click', e => {
        const chip = e.target.closest('[data-status]');
        if (!chip) return;
        status = chip.dataset.status;
        el('nsStatus').querySelectorAll('[data-status]').forEach(c => {
            c.classList.toggle('chip-active', c === chip);
            c.setAttribute('aria-pressed', String(c === chip));
        });
        tampilkan();
    });
    ['nsPerusahaan', 'nsMulai', 'nsAkhir'].forEach(id => el(id).addEventListener('change', muatNanti));
    el('nsProduk').addEventListener('change', tampilkan);
    el('nsCari').addEventListener('input', tampilkan);

    muat();
})();
