// ===== REKAPIN: Harga CPO & Kernel (dbo.DailyPrice, /rekapin/api/harga*) =====
let dataHarga = [];
const KOLOM_HARGA = ['harga_cpo', 'harga_kernel', 'oer_cpo', 'biaya_olah', 'qty_rsi'];
const rpHarga = v => v == null ? '—' : Number(v).toLocaleString('id-ID', { maximumFractionDigits: 2 });
const tglHarga = s => s ? s.split('-').reverse().join('-') : '';

document.addEventListener('DOMContentLoaded', muatHarga);

function resetFilterHarga() {
    document.getElementById('rkFilterTanggal').value = '';
    document.getElementById('rkFilterCompany').value = '';
    muatHarga();
}

async function muatHarga() {
    const tbody = document.getElementById('tabelRkHarga');
    const hak = JSON.parse(tbody.dataset.hak || '{}');
    const q = new URLSearchParams({ tanggal: document.getElementById('rkFilterTanggal').value,
                                    company: document.getElementById('rkFilterCompany').value });
    const rows = await ambilJson(`/rekapin/api/harga?${q}`);
    if (rows.error) { tbody.innerHTML = barisKosong(9, rows.error); return; }
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
    document.getElementById('rkHargaJudul').textContent = t(r ? 'Ubah Harga' : 'Isi Harga');
    const company = document.getElementById('rkHargaCompany');
    if (r) company.value = r.id_company;
    company.disabled = !!r;
    const tanggal = document.getElementById('rkHargaTanggal');
    tanggal.value = r ? r.tanggal : new Date().toLocaleDateString('sv-SE');
    tanggal.max = new Date().toLocaleDateString('sv-SE');
    tanggal.disabled = !!r;
    KOLOM_HARGA.forEach(k => { document.getElementById(`rkHarga_${k}`).value = r && r[k] != null ? r[k] : ''; });
    openModal('modalRkHarga');
}

async function simpanHarga(btn) {
    const isi = { company: document.getElementById('rkHargaCompany').value, tanggal: document.getElementById('rkHargaTanggal').value };
    KOLOM_HARGA.forEach(k => { isi[k] = document.getElementById(`rkHarga_${k}`).value; });
    const data = await denganTombol(btn, () => kirimForm('/rekapin/api/harga/simpan', isi));
    if (!tampilkanHasil(data)) return;
    closeModal('modalRkHarga');
    muatHarga();
}

async function hapusHarga(i) {
    const r = dataHarga[i];
    if (!await Dialog.konfirmasi({ judul: 'Hapus harga?', teksYa: 'Hapus', bahaya: true,
        pesan: `Harga ${r.id_company} tanggal ${tglHarga(r.tanggal)} akan dihapus.` })) return;
    if (tampilkanHasil(await kirimForm('/rekapin/api/harga/hapus', { company: r.id_company, tanggal: r.tanggal }))) muatHarga();
}
