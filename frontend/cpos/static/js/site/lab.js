let noTiketLabAktif = null;
let idProdukLabAktif = null;
let standarAktif = {};

function tampilkanStandar(std) {
    standarAktif = std;
    document.getElementById('stdFfa').textContent = std.maks_ffa != null ? std.maks_ffa + '%' : '-';
    document.getElementById('stdAir').textContent = std.maks_air != null ? std.maks_air + '%' : '-';
    document.getElementById('stdKotoran').textContent = std.maks_kotoran != null ? std.maks_kotoran + '%' : '-';
    cekStandar();
}

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    const produk = String(data.produk || '').trim().toUpperCase();
    const tiketPks =
        data.status === 'ADA_TIKET' &&
        data.sumber === 'ASCEND' &&
        data.ticket_type === 'Produk' &&
        ['CPO', 'PK', 'KERNEL'].includes(produk);

    noTiketLabAktif = tiketPks ? data.no_tiket : null;
    idProdukLabAktif = tiketPks && data.id_produk ? data.id_produk : null;

    ['labFfa', 'labSuhu', 'labUlage', 'labAir', 'labKotoran', 'labWarna'].forEach(
        id => document.getElementById(id).value = ''
    );

    if (tiketPks && data.id_produk) {
        muatStandar(data.id_produk);
    } else {
        tampilkanStandar({});
        document.getElementById('labStatusLive').textContent = '-';
    }
});

async function muatStandar(idProduk) {
    const std = await ambilJson(`/api/lab/standar/${idProduk}`);
    if (std.error) { Notif.gagal(std.error); return; }
    tampilkanStandar(std);
}

function cekStandar() {
    if (standarAktif.maks_ffa == null) return;
    const ffa = parseFloat(document.getElementById('labFfa').value) || 0;
    const air = parseFloat(document.getElementById('labAir').value) || 0;
    const kotoran = parseFloat(document.getElementById('labKotoran').value) || 0;
    const lolos = ffa <= standarAktif.maks_ffa && air <= standarAktif.maks_air && kotoran <= standarAktif.maks_kotoran;
    document.getElementById('labStatusLive').textContent = lolos ? 'MEMENUHI' : 'TIDAK MEMENUHI';
    document.getElementById('labStatusLive').className = 'py-2 text-right font-bold ' + (lolos ? 'text-emerald-600' : 'text-red-600');
}

async function submitLab(btn) {
    if (!noTiketLabAktif) {
        Notif.peringatan('Silakan pilih plat atau tiket terlebih dahulu');
        return;
    }

    const formData = new FormData();
    formData.append('no_tiket', noTiketLabAktif);
    formData.append('ffa', document.getElementById('labFfa').value);
    formData.append('suhu', document.getElementById('labSuhu').value);
    formData.append('ulage', document.getElementById('labUlage').value);
    formData.append('kadar_air', document.getElementById('labAir').value);
    formData.append('kadar_kotoran', document.getElementById('labKotoran').value);
    formData.append('warna_locis', document.getElementById('labWarna').value);

    const data = await denganTombol(
        btn,
        () => kirimForm('/api/lab/simpan', formData)
    );
    if (tampilkanHasil(data)) {
        muatAntrianLabAscend();
        muatRiwayatLabAscend();
    }
}

async function muatAntrianLabAscend() {
    const data = await ambilJson('/api/lab/antrian');
    const tbody = document.getElementById('tabelAntrianLabAscend');

    if (data.error) {
        tbody.innerHTML = barisGagal(8, data.error);
        return;
    }

    const kg = nilai => nilai == null
        ? '-'
        : Number(nilai).toLocaleString('id-ID');

    tbody.innerHTML = data.map(r => `
        <tr>
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.tanggal || '-')}</td>
            <td class="table-cell">${escapeHtml(r.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(r.no_plat || '-')}</td>
            <td class="table-cell">${escapeHtml(r.customer || '-')}</td>
            <td class="table-cell">${escapeHtml(r.produk || '-')}</td>
            <td class="table-cell text-right">${kg(r.bruto)}</td>
            <td class="table-cell text-right">${kg(r.tara)}</td>
            <td class="table-cell text-right">${kg(r.netto)}</td>
        </tr>
    `).join('') || barisKosong(8, 'Tidak ada tiket yang menunggu input Lab di Ascend');
}

async function muatRiwayatLabAscend() {
    const data = await ambilJson('/api/lab/riwayat');
    const tbody = document.getElementById('tabelRiwayatLabAscend');

    if (data.error) {
        tbody.innerHTML = barisGagal(12, data.error);
        return;
    }

    const angka = nilai => nilai == null
        ? '-'
        : Number(nilai).toLocaleString('id-ID');

    tbody.innerHTML = data.map(r => `
        <tr>
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.lab_datetime || '-')}</td>
            <td class="table-cell">${escapeHtml(r.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(r.no_plat || '-')}</td>
            <td class="table-cell">${escapeHtml(r.customer || '-')}</td>
            <td class="table-cell">${escapeHtml(r.produk || '-')}</td>
            <td class="table-cell text-right">${angka(r.ffa)}</td>
            <td class="table-cell text-right">${angka(r.suhu)}</td>
            <td class="table-cell text-right">${angka(r.ulage)}</td>
            <td class="table-cell text-right">${angka(r.pct_air)}</td>
            <td class="table-cell text-right">${angka(r.pct_kotoran)}</td>
            <td class="table-cell">${escapeHtml(r.kcolor || '-')}</td>
            <td class="table-cell">${escapeHtml(r.lab_by || '-')}</td>
        </tr>
    `).join('') || barisKosong(12, 'Belum ada hasil Lab tersimpan di Ascend');
}

function bukaStandarMutu() {
    if (!idProdukLabAktif) { Notif.peringatan('Silakan pilih tiket produk PKS (masukkan plat, lalu tekan Tab)'); return; }
    document.getElementById('stdInputFfa').value = standarAktif.maks_ffa ?? '';
    document.getElementById('stdInputAir').value = standarAktif.maks_air ?? '';
    document.getElementById('stdInputKotoran').value = standarAktif.maks_kotoran ?? '';
    openModal('modalStandarMutu');
}

async function simpanStandarMutu(btn) {
    if (!idProdukLabAktif) return;
    const formData = new FormData();
    formData.append('id_produk', idProdukLabAktif);
    formData.append('maks_ffa', document.getElementById('stdInputFfa').value);
    formData.append('maks_air', document.getElementById('stdInputAir').value);
    formData.append('maks_kotoran', document.getElementById('stdInputKotoran').value);
    const data = await denganTombol(btn, () => kirimForm('/api/lab/standar/update', formData));
    if (!tampilkanHasil(data)) return;
    closeModal('modalStandarMutu');
    muatStandar(idProdukLabAktif);
    muatHistoryStandar();
}

// Riwayat perubahan standar mutu 2 hari terakhir (dimuat saat tab Laboratorium dibuka)
async function muatHistoryStandar() {
    const data = await ambilJson('/api/lab/standar/history');
    const tbody = document.getElementById('tabelHistoryStandar');
    if (data.error) { tbody.innerHTML = barisGagal(6, data.error); return; }
    tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
        <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.updated_at)}</td><td class="table-cell">${escapeHtml(r.nama_produk)}</td>
        <td class="table-cell text-right">${escapeHtml(r.maks_ffa)}%</td><td class="table-cell text-right">${escapeHtml(r.maks_air)}%</td>
        <td class="table-cell text-right">${escapeHtml(r.maks_kotoran)}%</td><td class="table-cell">${escapeHtml(r.oleh || '-')}</td>
    </tr>`).join('') || barisKosong(6, 'Tidak ada perubahan standar 2 hari terakhir');
}

window.addEventListener('tabChange', e => {
    if (e.detail === 'lab') {
        muatHistoryStandar();
        muatAntrianLabAscend();
        muatRiwayatLabAscend();
    }
});

function cetakCOA() {
    const area = document.getElementById('printAreaCOA');
    const nilai = id => escapeHtml(document.getElementById(id).value);
    area.innerHTML = `<h2>Certificate of Analysis</h2><p>No. Tiket: ${escapeHtml(noTiketLabAktif)}</p>
        <p>FFA: ${nilai('labFfa')}%</p>
        <p>Kadar Air: ${nilai('labAir')}%</p>
        <p>Kadar Kotoran: ${nilai('labKotoran')}%</p>`;
    area.id = 'printArea';
    window.print();
}