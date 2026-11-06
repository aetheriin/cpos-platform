// ===== REKAPIN: Harga CPO & Kernel (dbo.DailyPrice atau Main.dbo.HARGA, /rekapin/api/harga*) =====
let dataHarga = [];
let hargaSementara = [];
const KOLOM_HARGA = ['harga_cpo', 'harga_kernel', 'oer_cpo', 'biaya_olah', 'qty_rsi'];
const KOLOM_HARGA_WAJIB = ['harga_cpo', 'harga_kernel', 'oer_cpo', 'biaya_olah'];
const BATAS_HARGA = { harga_cpo: 1_000_000, harga_kernel: 1_000_000, oer_cpo: 100, biaya_olah: 1_000_000 };
const rpHarga = v => v == null ? '—' : Number(v).toLocaleString('id-ID', { maximumFractionDigits: 2 });
const tglHarga = s => s ? s.split('-').reverse().join('-') : '';

document.addEventListener('click', e => {
    if (!e.target.closest('#rkTombolIsiHarga')) return;
    e.preventDefault();
    bukaHarga();
});
document.addEventListener('DOMContentLoaded', tampilkanHarga);

function resetFilterHarga() {
    document.getElementById('rkFilterTanggal').value = '';
    document.getElementById('rkFilterCompany').value = '';
    tampilkanHarga();
}

// Tombol Tampilkan: filter tanggal & perusahaan baru dijalankan saat diklik; status di kanan menunjukkan hasilnya
async function tampilkanHarga() {
    const tombol = document.getElementById('rkTombolTampilkan');
    const status = document.getElementById('rkStatusHarga');
    status.textContent = t('Memuat...');
    status.className = 'text-xs text-slate-400';
    const hasil = await denganTombol(tombol, muatHarga);
    const jam = new Date().toLocaleTimeString('id-ID');
    if (hasil && hasil.error) {
        status.textContent = `${t('Gagal')}: ${hasil.error}`;
        status.className = 'text-xs text-red-600';
        return;
    }
    const tgl = document.getElementById('rkFilterTanggal').value;
    const comp = document.getElementById('rkFilterCompany').value;
    const saring = [comp || t('semua perusahaan'), tgl ? tglHarga(tgl) : t('semua tanggal')].join(' · ');
    status.textContent = `${t('Dimuat')} ${jam} (${saring})`;
    status.className = 'text-xs text-emerald-700';
}

async function muatHarga() {
    const tbody = document.getElementById('tabelRkHarga');
    const hak = JSON.parse(tbody.dataset.hak || '{}');
    const q = new URLSearchParams({ tanggal: document.getElementById('rkFilterTanggal').value,
                                    company: document.getElementById('rkFilterCompany').value });
    const rows = await ambilJson(`/rekapin/api/harga?${q}`);
    if (rows.error) {
        tbody.innerHTML = barisGagal(9, rows.error);
        document.getElementById('rkJumlahHarga').textContent = '-';
        return rows;
    }
    dataHarga = rows;
    document.getElementById('rkJumlahHarga').textContent = rows.length;
    tbody.innerHTML = rows.map((r, i) => `<tr class="hover:bg-slate-50">
        <td class="table-cell font-semibold">${escapeHtml(r.id_company)}</td>
        <td class="table-cell font-mono">${tglHarga(r.tanggal)}</td>
        <td class="table-cell text-right font-mono font-semibold text-slate-900">${rpHarga(r.harga_cpo)}</td>
        <td class="table-cell text-right font-mono">${rpHarga(r.harga_kernel)}</td>
        <td class="table-cell text-right">${badge(`${rpHarga(r.oer_cpo)}%`, 'bg-emerald-50 text-emerald-700')}</td>
        <td class="table-cell text-right font-mono">${rpHarga(r.biaya_olah)}</td>
        <td class="table-cell text-right font-mono">${r.qty_rsi == null ? '—' : rpHarga(r.qty_rsi) + ' ton'}</td>
        <td class="table-cell text-xs text-slate-500">${escapeHtml(r.oleh || '')}<div>${escapeHtml(r.diubah)}</div></td>
        <td class="table-cell text-right whitespace-nowrap space-x-2">
            ${hak.ubah ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaHarga" data-arg="${i}">Ubah</button>` : ''}
            ${hak.hapus ? `<button type="button" class="link-aksi text-red-600" data-on-click="hapusHarga" data-arg="${i}">Hapus</button>` : ''}</td></tr>`).join('')
        || barisKosong(9, 'Belum ada data harga');
}

function bukaHarga(i) {
    const r = Number.isInteger(i) ? dataHarga[i] : null;
    openModal('modalRkHarga');
    document.getElementById('rkHargaJudul').textContent = t(r ? 'Ubah Harga' : 'Isi Harga');
    const company = document.getElementById('rkHargaCompany');
    company.value = r ? r.id_company : '';
    company.disabled = !!r;
    const tanggal = document.getElementById('rkHargaTanggal');
    tanggal.value = r ? r.tanggal : new Date().toLocaleDateString('sv-SE');
    tanggal.max = new Date().toLocaleDateString('sv-SE');
    tanggal.disabled = !!r;
    KOLOM_HARGA.forEach(k => { document.getElementById(`rkHarga_${k}`).value = r && r[k] != null ? r[k] : ''; });
    tampilkanHargaSementara();
}

function nilaiFormHarga() {
    const isi = {
        company: document.getElementById('rkHargaCompany').value,
        tanggal: document.getElementById('rkHargaTanggal').value,
    };
    KOLOM_HARGA.forEach(k => {
        const value = document.getElementById(`rkHarga_${k}`).value;
        isi[k] = value === '' && k === 'qty_rsi' ? null : value;
    });
    return isi;
}

function tampilkanHargaSementara() {
    const tbody = document.getElementById('rkHargaSementara');
    if (!tbody) return;
    document.getElementById('rkJumlahSementara').textContent = `${hargaSementara.length} data`;
    document.getElementById('rkSimpanSemuaHarga').disabled = hargaSementara.length === 0;
    tbody.innerHTML = hargaSementara.map((r, i) => `<tr>
        <td class="table-cell font-semibold">${escapeHtml(r.company)}</td>
        <td class="table-cell font-mono">${tglHarga(r.tanggal)}</td>
        <td class="table-cell text-right font-mono">${rpHarga(r.harga_cpo)}</td>
        <td class="table-cell text-right font-mono">${rpHarga(r.harga_kernel)}</td>
        <td class="table-cell text-right">${rpHarga(r.oer_cpo)}%</td>
        <td class="table-cell text-right font-mono">${rpHarga(r.biaya_olah)}</td>
        <td class="table-cell text-right font-mono">${r.qty_rsi == null ? '—' : `${rpHarga(r.qty_rsi)} ton`}</td>
        <td class="table-cell text-right whitespace-nowrap">
            <button type="button" class="link-aksi text-blue-600" data-on-click="editHargaSementara" data-arg="${i}">Ubah</button>
            <button type="button" class="link-aksi text-red-600 ml-2" data-on-click="hapusHargaSementara" data-arg="${i}">Hapus</button>
        </td></tr>`).join('') || barisKosong(8, 'Belum ada data sementara');
}

function tambahHargaSementara() {
    const formFields = ['rkHargaCompany', 'rkHargaTanggal', ...KOLOM_HARGA_WAJIB.map(k => `rkHarga_${k}`)];
    for (const id of formFields) {
        const field = document.getElementById(id);
        if (!field.reportValidity()) return;
    }
    const row = nilaiFormHarga();
    const company = document.getElementById('rkHargaCompany');
    if (row.qty_rsi !== null && (!Number.isFinite(Number(row.qty_rsi)) || Number(row.qty_rsi) < 0 || Number(row.qty_rsi) > 1_000_000_000)) {
        document.getElementById('rkHarga_qty_rsi').reportValidity();
        return;
    }
    if (KOLOM_HARGA_WAJIB.some(k => !Number.isFinite(Number(row[k])) || Number(row[k]) < 0 || Number(row[k]) > BATAS_HARGA[k])) {
        Notif.gagal('Nilai harga tidak valid. OER CPO harus antara 0 dan 100.');
        return;
    }
    const index = hargaSementara.findIndex(item => item.company === row.company && item.tanggal === row.tanggal);
    if (index >= 0) hargaSementara[index] = row;
    else hargaSementara.push(row);
    document.getElementById('rkHargaJudul').textContent = 'Isi Harga';
    company.disabled = false;
    company.value = '';
    document.getElementById('rkHargaTanggal').disabled = false;
    document.getElementById('rkHarga_oer_cpo').value = '';
    document.getElementById('rkHarga_qty_rsi').value = '';
    tampilkanHargaSementara();
}

function editHargaSementara(i) {
    const row = hargaSementara[i];
    if (!row) return;
    const company = document.getElementById('rkHargaCompany');
    company.value = row.company;
    company.disabled = true;
    const tanggal = document.getElementById('rkHargaTanggal');
    tanggal.value = row.tanggal;
    tanggal.disabled = true;
    KOLOM_HARGA.forEach(k => {
        document.getElementById(`rkHarga_${k}`).value = row[k] ?? '';
    });
    document.getElementById('rkHargaJudul').textContent = 'Ubah Data Sementara';
}

function hapusHargaSementara(i) {
    hargaSementara.splice(i, 1);
    tampilkanHargaSementara();
}

async function simpanHarga(btn) {
    if (!hargaSementara.length) return;
    const data = await denganTombol(btn, () => kirimForm('/rekapin/api/harga/simpan-batch', {
        items: JSON.stringify(hargaSementara.map(({ company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi }) =>
            ({ company, tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, qty_rsi }))),
    }));
    if (!tampilkanHasil(data)) return;
    hargaSementara = [];
    tampilkanHargaSementara();
    closeModal('modalRkHarga');
    tampilkanHarga();
}

async function hapusHarga(i) {
    const r = dataHarga[i];
    if (!await Dialog.konfirmasi({ judul: 'Hapus harga?', teksYa: 'Hapus', bahaya: true,
        pesan: `Harga ${r.id_company} tanggal ${tglHarga(r.tanggal)} akan dihapus.` })) return;
    if (tampilkanHasil(await kirimForm('/rekapin/api/harga/hapus', { company: r.id_company, tanggal: r.tanggal }))) tampilkanHarga();
}
