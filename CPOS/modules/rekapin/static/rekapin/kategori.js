// ===== REKAPIN: Kategori Request (rekap.RequestCategory, /rekapin/api/kategori*) =====
let dataKategori = [];

document.addEventListener('DOMContentLoaded', muatKategori);

async function muatKategori() {
    const tbody = document.getElementById('tabelRkKategori');
    const hak = JSON.parse(tbody.dataset.hak || '{}');
    const rows = await ambilJson('/rekapin/api/kategori');
    if (rows.error) { tbody.innerHTML = barisKosong(6, rows.error); return; }
    dataKategori = rows;
    document.getElementById('rkJumlahKategori').textContent = `${rows.filter(k => k.is_active).length} aktif dari ${rows.length}`;
    tbody.innerHTML = rows.map((k, i) => `<tr class="hover:bg-slate-50${k.is_active ? '' : ' opacity-60'}">
        <td class="table-cell font-mono text-xs text-slate-400">${String(i + 1).padStart(2, '0')}</td>
        <td class="table-cell font-semibold text-slate-900">${escapeHtml(k.nama)}</td>
        <td class="table-cell text-right font-mono">${k.jumlah_request}</td>
        <td class="table-cell font-mono text-xs">${escapeHtml(k.dibuat)}</td>
        <td class="table-cell">${badge(t(k.is_active ? 'Aktif' : 'Nonaktif'), k.is_active ? WARNA_BADGE.hijau : WARNA_BADGE.abu)}</td>
        <td class="table-cell text-right whitespace-nowrap space-x-2">
            ${hak.ubah ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaKategori" data-arg="${k.id}">Ubah</button>
                <button type="button" class="link-aksi text-slate-600" data-on-click="aktifKategori" data-arg="${k.id}">${t(k.is_active ? 'Nonaktifkan' : 'Aktifkan')}</button>` : ''}
            ${hak.hapus ? `<button type="button" class="link-aksi text-red-600" data-on-click="hapusKategori" data-arg="${k.id}">Hapus</button>` : ''}</td></tr>`).join('')
        || barisKosong(6, 'Belum ada kategori');
}

function bukaKategori(id) {
    const k = id ? dataKategori.find(x => x.id === id) : null;
    document.getElementById('rkKategoriJudul').textContent = t(k ? 'Ubah Kategori' : 'Tambah Kategori');
    document.getElementById('rkKategoriId').value = k ? k.id : '';
    document.getElementById('rkKategoriNama').value = k ? k.nama : '';
    openModal('modalRkKategori');
    document.getElementById('rkKategoriNama').focus();
}

async function simpanKategori(btn) {
    const kirim = () => kirimForm('/rekapin/api/kategori/simpan', {
        id: document.getElementById('rkKategoriId').value, nama: document.getElementById('rkKategoriNama').value.trim() });
    const data = btn && btn.tagName === 'BUTTON' ? await denganTombol(btn, kirim) : await kirim();
    if (!tampilkanHasil(data)) return;
    closeModal('modalRkKategori');
    muatKategori();
}

async function aktifKategori(id) {
    const k = dataKategori.find(x => x.id === id);
    if (tampilkanHasil(await kirimForm(`/rekapin/api/kategori/${id}/aktif`, { aktif: k.is_active ? '0' : '1' }))) muatKategori();
}

async function hapusKategori(id) {
    const k = dataKategori.find(x => x.id === id);
    if (!await Dialog.konfirmasi({ judul: 'Hapus kategori?', teksYa: 'Hapus', bahaya: true,
        pesan: k.jumlah_request ? `${k.nama} sudah dipakai ${k.jumlah_request} request, jadi hanya dinonaktifkan.` : `${k.nama} akan dihapus.` })) return;
    if (tampilkanHasil(await kirimForm(`/rekapin/api/kategori/${id}/hapus`, {}))) muatKategori();
}
