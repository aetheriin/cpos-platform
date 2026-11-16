// ===== DATA MASTER > MITRA & PRODUK =====
let daftarMitra = [];
let daftarProduk = [];
let jenisProdukMaster = 'Produk';
const bolehUbah = id => document.getElementById(id).dataset.bolehUbah === '1';

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
    const isTbsLuar = jenisProdukMaster === 'TBSLuar';
    const url = isTbsLuar
        ? '/api/master/produk/tbs-luar'
        : '/api/master/produk';

    const data = await ambilJson(url);
    const tbody = document.getElementById('tabelProduk');
    const header = document.getElementById('headerProduk');

    if (data.error) {
        tbody.innerHTML = barisGagal(isTbsLuar ? 3 : 7, data.error);
        return;
    }

    if (isTbsLuar) {
        header.innerHTML = `
            <th class="table-cell">Nama Produk</th>
            <th class="table-cell text-right">Jumlah Tiket</th>
            <th class="table-cell">Terakhir Dipakai</th>
        `;

        tbody.innerHTML = data.map(p => `
            <tr class="hover:bg-slate-50">
                <td class="table-cell">${escapeHtml(p.nama_produk || '-')}</td>
                <td class="table-cell text-right">
                    ${Number(p.jumlah_tiket || 0).toLocaleString('id-ID')}
                </td>
                <td class="table-cell">${escapeHtml(p.terakhir_dipakai || '-')}</td>
            </tr>
        `).join('') || barisKosong(3, 'Belum ada produk pada tiket TBS Luar');

        return;
    }

    daftarProduk = data;
    header.innerHTML = `
        <th class="table-cell">Nama Produk</th>
        <th class="table-cell">State</th>
        <th class="table-cell">Deskripsi</th>
        <th class="table-cell">Kode Awal</th>
        <th class="table-cell">Flags</th>
        <th class="table-cell text-right">QE Ratio</th>
        <th class="table-cell text-right">Aksi</th>
    `;

    tbody.innerHTML = data.map(p => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(p.nama_produk || '-')}</td>
            <td class="table-cell">${escapeHtml(p.state || '-')}</td>
            <td class="table-cell">${escapeHtml(p.deskripsi || '-')}</td>
            <td class="table-cell">${escapeHtml(p.kode_awal || '-')}</td>
            <td class="table-cell">${escapeHtml(p.prod_flags || '-')}</td>
            <td class="table-cell text-right">${
                p.qe_ratio == null
                    ? '-'
                    : Number(p.qe_ratio).toLocaleString('id-ID')
            }</td>
            <td class="table-cell text-right">
                ${bolehUbah('tabelProduk') ? `
                    <button type="button" class="link-aksi text-blue-600"
                            data-on-click="bukaProduk" data-arg="${p.id_produk}">
                        Ubah
                    </button>` : ''}
            </td>
        </tr>
    `).join('') || barisKosong(7, 'Belum ada produk Ascend');
}

function pilihJenisProdukMaster(jenis) {
    jenisProdukMaster = jenis === 'TBSLuar' ? 'TBSLuar' : 'Produk';

    const isTbsLuar = jenisProdukMaster === 'TBSLuar';
    document.getElementById('filterProdukMaster')
        ?.classList.toggle('btn-primary', !isTbsLuar);
    document.getElementById('filterProdukMaster')
        ?.classList.toggle('btn-secondary', isTbsLuar);
    document.getElementById('filterTbsLuarMaster')
        ?.classList.toggle('btn-primary', isTbsLuar);
    document.getElementById('filterTbsLuarMaster')
        ?.classList.toggle('btn-secondary', !isTbsLuar);
    document.getElementById('btnTambahProdukAscend')
        ?.classList.toggle('hidden', isTbsLuar);

    muatProduk();
}

function bukaProduk(id) {
    const form = document.getElementById('formProduk');
    const p = id == null
        ? null
        : daftarProduk.find(x => Number(x.id_produk) === Number(id));

    form.reset();
    isiForm(form, p || {
        id_produk: '',
        state: 'Liquid',
        deskripsi: '',
        kode_awal: '',
        prod_flags: '',
        qe_ratio: 1,
        req_do: false,
    });

    const perluDo = form.querySelector('[name="req_do"]');
    if (perluDo) perluDo.checked = Boolean(p?.req_do);

    document.getElementById('judulModalProduk').textContent =
        p ? 'Ubah Produk Ascend' : 'Tambah Produk Ascend';

    openModal('modalProduk');
    document.getElementById('prodNama').focus();
}

document.getElementById('formProduk')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/master/produk/simpan', {
        modal: 'modalProduk',
        setelahnya: muatProduk,
    });
});
