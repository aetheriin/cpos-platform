document.addEventListener('DOMContentLoaded', muatMonitorSplitTiket);

async function muatMonitorSplitTiket() {
    const tbody = document.getElementById('tabelTiketPisah');
    if (!tbody) return;

    const rows = await ambilJson('/api/kelebihan-do/tiket-pisah');

    if (!Array.isArray(rows)) {
        tbody.innerHTML = barisGagal(
            7,
            rows?.error || 'Data pemantauan split Tiket gagal dimuat.'
        );
        return;
    }

    const waktu = nilai => {
        if (!nilai) return '-';
        const tanggal = new Date(nilai);
        return Number.isNaN(tanggal.getTime())
            ? String(nilai)
            : tanggal.toLocaleString('id-ID');
    };

    const alokasi = row => {
        const anak = row.tiket_pisah || [];
        if (!anak.length) return '-';

        return anak.map(t => `
            <div class="mb-1">
                <span class="font-mono">${escapeHtml(t.no_tiket)}</span>
                · DO <span class="font-mono">${escapeHtml(t.no_do)}</span>
                · ${Number(t.berat_netto || 0).toLocaleString('id-ID')} kg
            </div>
        `).join('');
    };

    tbody.innerHTML = rows.map(row => {
        const status = row.status === 'MENUNGGU_DO2'
            ? 'Menunggu DO2'
            : row.status === 'SELESAI_PISAH'
                ? 'Split selesai'
                : 'Selesai tanpa split';

        const do2 = row.status === 'SELESAI_PISAH'
            ? row.no_do2 || '-'
            : '-';

        const keterangan = row.status === 'MENUNGGU_DO2'
            ? `${row.pesan_error || 'Menunggu DO2'} · percobaan ${row.jumlah_percobaan || 0}`
            : status;

        return `
            <tr class="hover:bg-slate-50 align-top">
                <td class="table-cell whitespace-nowrap">
                    ${escapeHtml(waktu(row.waktu_timbang))}
                </td>
                <td class="table-cell font-mono">
                    ${escapeHtml(row.ticket_no || '')}
                </td>
                <td class="table-cell font-mono">
                    ${escapeHtml(row.no_do1 || '')}
                </td>
                <td class="table-cell font-mono">
                    ${escapeHtml(do2)}
                </td>
                <td class="table-cell text-right whitespace-nowrap">
                    ${row.berat_akhir == null
                        ? '-'
                        : `${Number(row.berat_akhir).toLocaleString('id-ID')} kg`}
                </td>
                <td class="table-cell text-xs">${alokasi(row)}</td>
                <td class="table-cell">${escapeHtml(keterangan)}</td>
            </tr>
        `;
    }).join('') || barisKosong(
        7,
        'Belum ada tiket pending atau hasil split Tiket'
    );
}