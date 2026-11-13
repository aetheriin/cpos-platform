// ===== DATA MASTER > CUSTOMER/PENGANGKUTAN/PRODUK ASCEND ONLY =====
let daftarMitra = [];
let daftarProduk = [];
document.addEventListener('DOMContentLoaded', () => { muatMitra(); muatProduk(); });

async function muatMitra() {
    const [customer, pengangkutan] = await Promise.all([
        ambilJson('/api/master/ascend/customer'), ambilJson('/api/master/ascend/pengangkutan')
    ]);
    renderAscendList('tabelCustomerAscend', customer, 'Customer');
    renderAscendList('tabelPengangkutanAscend', pengangkutan, 'Pengangkutan');
}
function renderAscendList(id, data, label) {
    const tbody = document.getElementById(id); if (!tbody) return;
    if (data?.error) { tbody.innerHTML = barisGagal(3, data.error); return; }
    tbody.innerHTML = (data || []).map(x => `<tr class="hover:bg-slate-50" data-cari="${escapeHtml(`${x.kode} ${x.nama}`.toLowerCase())}">
        <td class="table-cell font-mono">${escapeHtml(x.id)}</td><td class="table-cell">${escapeHtml(x.kode || '-')}</td><td class="table-cell">${escapeHtml(x.nama)}</td></tr>`).join('') || barisKosong(3, `Tidak ada ${label} dari Ascend`);
    saringBaris(id, document.getElementById('cariMitra')?.value || '');
}
function cariMitra(teks) { saringBaris('tabelCustomerAscend', teks); saringBaris('tabelPengangkutanAscend', teks); }

async function muatProduk() {
    const [produk, tbs] = await Promise.all([
        ambilJson('/api/master/ascend/produk?jenis_tiket=Produk'),
        ambilJson('/api/master/ascend/produk?jenis_tiket=TBSLuar')
    ]);
    const tbody = document.getElementById('tabelProduk'); if (!tbody) return;
    if (produk?.error || tbs?.error) { tbody.innerHTML = barisGagal(3, produk?.error || tbs?.error); return; }
    daftarProduk = [...(produk || []), ...(tbs || [])];
    tbody.innerHTML = daftarProduk.map(p => `<tr class="hover:bg-slate-50"><td class="table-cell">${escapeHtml(p.nama_produk)}</td>
        <td class="table-cell">${escapeHtml(p.jenis_tiket)}</td><td class="table-cell">${p.jenis_tiket === 'TBSLuar' ? 'TBS Luar' : 'DO Produk Ascend'}</td></tr>`).join('') || barisKosong(3, 'Produk tidak ditemukan pada DO Ascend');
}
