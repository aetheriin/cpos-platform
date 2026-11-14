// ===== DATA MASTER > MITRA & PRODUK =====
let daftarMitra = [];
const bolehUbah = id => document.getElementById(id).dataset.bolehUbah === '1';
let daftarProduk = [];

document.addEventListener('DOMContentLoaded', () => {
    muatMitra();
    muatProduk();
});

async function muatMitra() {
    const data = await ambilJson('/api/master/mitra');
    const tbody = document.getElementById('tabelMitra');

    if (data.error) {
        tbody.innerHTML = barisGagal(7, data.error);
        return;
    }

    daftarMitra = data;

    tbody.innerHTML = data.map(s => {
        const operasi = [
            s.is_transport && badge('Transport', WARNA_BADGE.oranye),
            s.is_expedition && badge('Ekspedisi', WARNA_BADGE.biru),
            s.supplier_tbs && badge('Supplier TBS', WARNA_BADGE.hijau),
        ].filter(Boolean).join(' ') || '-';

        const tipe = [
            s.kode_jenis_supplier,
            s.jenis_supplier,
        ].filter(Boolean).join(' · ') || '-';

        return `
            <tr class="hover:bg-slate-50${s.is_active ? '' : ' text-slate-400'}"
                data-cari="${escapeHtml(
                    `${s.kode_supplier} ${s.nama_supplier} ${tipe}`.toLowerCase()
                )}">
                <td class="table-cell font-mono">
                    ${escapeHtml(s.kode_supplier)}
                </td>
                <td class="table-cell">
                    ${escapeHtml(s.nama_supplier)}
                    ${s.alamat
                        ? `<span class="block text-[11px] text-slate-500">${escapeHtml(s.alamat)}</span>`
                        : ''}
                </td>
                <td class="table-cell">${escapeHtml(tipe)}</td>
                <td class="table-cell">${operasi}</td>
                <td class="table-cell">${escapeHtml(s.default_ticket_type || '-')}</td>
                <td class="table-cell">${badgeAktif(s.is_active)}</td>
                <td class="table-cell">${escapeHtml(s.created_at || '-')}</td>
            </tr>`;
    }).join('') || barisKosong(7, 'Belum ada Supplier Ascend');

    saringBaris('tabelMitra', document.getElementById('cariMitra').value);
}

function cariMitra(teks) {
    saringBaris('tabelMitra', teks);
}

async function muatProduk() {
    const data = await ambilJson('/api/master/produk');
    const tbody = document.getElementById('tabelProduk');

    if (data.error) {
        tbody.innerHTML = barisGagal(7, data.error);
        return;
    }

    tbody.innerHTML = data.map(p => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(p.nama_produk || '-')}</td>
            <td class="table-cell">${escapeHtml(p.state || '-')}</td>
            <td class="table-cell">${escapeHtml(p.deskripsi || '-')}</td>
            <td class="table-cell">${p.req_do ? 'Ya' : 'Tidak'}</td>
            <td class="table-cell">${escapeHtml(p.kode_awal || '-')}</td>
            <td class="table-cell">${escapeHtml(p.prod_flags || '-')}</td>
            <td class="table-cell text-right">${
                p.qe_ratio == null
                    ? '-'
                    : Number(p.qe_ratio).toLocaleString('id-ID')
            }</td>
        </tr>`
    ).join('') || barisKosong(7, 'Belum ada produk Ascend');
}
