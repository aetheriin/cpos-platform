// ===== DATA MASTER > CUSTOMER/PENGANGKUTAN/PRODUK ASCEND ONLY =====
let daftarProduk = [];

document.addEventListener('DOMContentLoaded', () => {
    muatMitra();
    muatProduk();
});

async function muatMitra() {
    const [customer, pengangkutan] = await Promise.all([
        ambilJson('/api/master/ascend/customer'),
        ambilJson('/api/master/ascend/pengangkutan')
    ]);

    renderAscendList('tabelCustomerAscend', customer, 'Customer');
    renderAscendList('tabelPengangkutanAscend', pengangkutan, 'Pengangkutan');
}

function renderAscendList(id, data, label) {
    const tbody = document.getElementById(id);
    if (!tbody) return;

    if (data?.error) {
        tbody.innerHTML = barisGagal(3, data.error);
        return;
    }

    const rows = Array.isArray(data) ? data : [];
    tbody.innerHTML = rows.map(item => {
        const cari = `${item.id ?? ''} ${item.kode ?? ''} ${item.nama ?? ''}`.toLocaleLowerCase('id-ID');
        return `<tr class="hover:bg-slate-50" data-cari="${escapeHtml(cari)}">
            <td class="table-cell font-mono">${escapeHtml(item.id)}</td>
            <td class="table-cell">${escapeHtml(item.kode || '-')}</td>
            <td class="table-cell">${escapeHtml(item.nama || '-')}</td>
        </tr>`;
    }).join('') || barisKosong(3, `Tidak ada ${label} dari Ascend`);

    filterAscendRows(id, document.getElementById('cariMitra')?.value || '');
}

function cariMitra(teks) {
    filterAscendRows('tabelCustomerAscend', teks);
    filterAscendRows('tabelPengangkutanAscend', teks);
}

async function muatProduk() {
    const [produk, tbs] = await Promise.all([
        ambilJson('/api/master/ascend/produk?jenis_tiket=Produk'),
        ambilJson('/api/master/ascend/produk?jenis_tiket=TBSLuar')
    ]);

    const tbody = document.getElementById('tabelProduk');
    if (!tbody) return;

    if (produk?.error || tbs?.error) {
        tbody.innerHTML = barisGagal(3, produk?.error || tbs?.error);
        return;
    }

    const daftarProdukAscend = Array.isArray(produk) ? produk : [];
    const daftarTbsLuar = Array.isArray(tbs) ? tbs : [];
    daftarProduk = [...daftarProdukAscend, ...daftarTbsLuar];

    tbody.innerHTML = daftarProduk.map(item => {
        const jenis = item.jenis_tiket === 'TBSLuar' ? 'TBS Luar' : 'Produk';
        const sumber = item.jenis_tiket === 'TBSLuar'
            ? 'DO TBS Luar / jenis tiket TBS Luar'
            : 'DO Produk Outstanding Ascend';
        const cari = `${item.nama_produk ?? ''} ${jenis} ${sumber}`.toLocaleLowerCase('id-ID');

        return `<tr class="hover:bg-slate-50" data-cari="${escapeHtml(cari)}">
            <td class="table-cell">${escapeHtml(item.nama_produk || '-')}</td>
            <td class="table-cell">${escapeHtml(jenis)}</td>
            <td class="table-cell">${escapeHtml(sumber)}</td>
        </tr>`;
    }).join('') || barisKosong(3, 'Produk tidak ditemukan pada DO Outstanding Ascend');

    cariProdukAscend(document.getElementById('cariProdukAscend')?.value || '');
}

function cariProdukAscend(teks) {
    filterAscendRows('tabelProduk', teks);
}

function filterAscendRows(id, teks) {
    const tbody = document.getElementById(id);
    if (!tbody) return;

    const kata = String(teks || '').trim().toLocaleLowerCase('id-ID');
    tbody.querySelectorAll('tr[data-cari]').forEach(row => {
        row.hidden = kata !== '' && !String(row.dataset.cari || '').includes(kata);
    });
}
