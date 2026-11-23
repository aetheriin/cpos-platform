let noTiketSortasiAktif = null;

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    noTiketSortasiAktif = null;

    [
        'srDeductionKg',
        'srMentah',
        'srBusuk',
        'srTangkai',
        'srSampah',
        'srMatang',
        'srBrondolan',
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    hitungPotongan();

    if (
        data.status === 'ADA_TIKET' &&
        data.sumber === 'ASCEND' &&
        tiketPunyaTahap(data, 'SORTASI')
    ) {
        noTiketSortasiAktif = data.no_tiket;
    }

    muatHistorySortasi();
});

function hitungPotongan() {
    const input = document.getElementById('srDeductionKg');
    const ringkasan = document.getElementById('srTotalPotongan');

    if (!input || !ringkasan || input.value.trim() === '') {
        ringkasan.textContent = '- kg';
        return;
    }

    const kg = Number(input.value);
    ringkasan.textContent = Number.isFinite(kg)
        ? `${kg.toLocaleString('id-ID')} kg`
        : '- kg';
}

async function submitSortasi(btn) {
    if (!noTiketSortasiAktif) {
        Notif.peringatan('Silakan pilih tiket Ascend terlebih dahulu');
        return;
    }

    const formData = new FormData();
    formData.append('no_tiket', noTiketSortasiAktif);
    formData.append(
        'deduction_kg',
        document.getElementById('srDeductionKg').value
    );

    const grading = [
        ['mentah', 'srMentah'],
        ['busuk', 'srBusuk'],
        ['tangkai', 'srTangkai'],
        ['sampah', 'srSampah'],
        ['matang', 'srMatang'],
        ['brondolan', 'srBrondolan'],
    ];

    for (const [nama, id] of grading) {
        const nilai = document.getElementById(id).value.trim();
        if (nilai !== '') {
            formData.append(nama, nilai);
        }
    }

    const data = await denganTombol(
        btn,
        () => kirimForm('/api/sortasi/simpan', formData)
    );

    if (tampilkanHasil(data)) {
        muatHistorySortasi();
    }
}

async function muatHistorySortasi() {
    const data = await ambilJson('/api/history/sortasi');
    const tbody = document.getElementById('tabelHistorySortasi');
    if (data.error) {
        tbody.innerHTML = barisGagal(7, data.error);
        return;
    }

    const kg = nilai => nilai == null
        ? '-'
        : Number(nilai).toLocaleString('id-ID');

    tbody.innerHTML = data.map(r => `
        <tr>
            <td class="table-cell">${escapeHtml(r.sortasi_datetime || '-')}</td>
            <td class="table-cell">${escapeHtml(r.no_tiket || '-')}</td>
            <td class="table-cell">${escapeHtml(r.no_plat || '-')}</td>
            <td class="table-cell">${escapeHtml(r.nama_produk || '-')}</td>
            <td class="table-cell">${escapeHtml(r.nama_supplier || '-')}</td>
            <td class="table-cell text-right">${kg(r.deduction_kg)}</td>
            <td class="table-cell">${escapeHtml(r.sortasi_by || '-')}</td>
        </tr>
    `).join('') || barisKosong(7, 'Belum ada riwayat Sortasi Ascend');
}