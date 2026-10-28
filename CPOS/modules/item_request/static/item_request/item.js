// ===== NEW ITEM REQUEST: cari item paling mirip + tebak kategori (/item-request/api/*) =====
// Data & model dimuat di server saat halaman pertama dibuka (1 - 2 menit); selama itu tombol CARI menunggu.
let pollingItem = null;

document.addEventListener('DOMContentLoaded', cekStatusItem);

function tampilStatusItem(st) {
    const kotak = document.getElementById('irStatus');
    const warna = { MEMUAT: 'border-blue-200 bg-blue-50 text-blue-800', GAGAL: 'border-red-200 bg-red-50 text-red-700' }[st.keadaan];
    kotak.classList.toggle('hidden', !warna);
    if (warna) {
        kotak.className = `mb-4 rounded-lg border px-4 py-3 text-sm ${warna}`;
        kotak.innerHTML = st.keadaan === 'MEMUAT'
            ? `<i class="fa-solid fa-spinner fa-spin mr-2"></i>${escapeHtml(st.pesan)}`
            : `<i class="fa-solid fa-triangle-exclamation mr-2"></i>${escapeHtml(st.pesan)}
               <button type="button" class="btn-secondary btn-sm ml-3" data-on-click="muatUlangItem">Coba lagi</button>`;
    }
    document.getElementById('irTombolCari').disabled = st.keadaan !== 'SIAP';
}

function isiCompanyItem(companies) {
    const sel = document.getElementById('irCompany');
    if (sel.options.length > 1) return;
    companies.forEach(c => sel.add(new Option(c, c)));
}

async function cekStatusItem() {
    const st = await ambilJson('/item-request/api/status');
    if (st.error) return;
    tampilStatusItem(st);
    if (st.keadaan === 'SIAP') isiCompanyItem(st.companies);
    clearTimeout(pollingItem);
    if (st.keadaan === 'MEMUAT' || st.keadaan === 'BELUM') pollingItem = setTimeout(cekStatusItem, 3000);
}

async function muatUlangItem() {
    const st = await kirimForm('/item-request/api/muat-ulang', {});
    if (!st.error) tampilStatusItem(st);
    cekStatusItem();
}

const angkaItem = (v, desimal) => v == null ? '-' : Number(v).toLocaleString('en-US', { minimumFractionDigits: desimal, maximumFractionDigits: desimal });

document.getElementById('formCariItem').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const data = await denganTombol(form.querySelector('[type=submit]'), () => kirimForm('/item-request/api/cari', new FormData(form)));
    if (data.error) { tampilkanHasil(data); return; }
    document.getElementById('irKategori').classList.toggle('hidden', !data.category);
    document.getElementById('irKategoriNilai').textContent = data.category || '';
    document.getElementById('irHasil').classList.remove('hidden');
    document.getElementById('irInfo').textContent = `"${data.query}" · ${data.company === 'SEMUA' ? 'ALL COMP' : data.company}`;
    document.getElementById('tabelItem').innerHTML = data.hasil.map(r => `<tr class="hover:bg-slate-50">
        <td class="table-cell font-bold font-mono">${angkaItem(r.similarity, 2)}%</td>
        <td class="table-cell">${escapeHtml(r.comp)}</td>
        <td class="table-cell font-mono">${escapeHtml(r.item_code)}</td>
        <td class="table-cell font-semibold text-slate-800">${escapeHtml(r.item_name)}</td>
        <td class="table-cell">${escapeHtml(r.category)}</td>
        <td class="table-cell font-mono">${r.beli ? escapeHtml(r.beli.no ?? '-') : '-'}</td>
        <td class="table-cell font-mono">${r.beli && r.beli.tanggal ? escapeHtml(r.beli.tanggal) : '-'}</td>
        <td class="table-cell text-right font-mono">${r.beli && r.beli.qty != null ? escapeHtml(String(r.beli.qty)) : '-'}</td>
        <td class="table-cell text-right font-mono">${r.beli ? angkaItem(r.beli.harga, 2) : '-'}</td></tr>`).join('')
        || barisKosong(9, 'Tidak ditemukan item yang sesuai.');
});
