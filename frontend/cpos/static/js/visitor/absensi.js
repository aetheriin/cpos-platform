// ===== ABSENSI KARYAWAN: absensi harian & rekap bulanan (dipindah dari tab Logs Visitor & Staff Logs) =====
let modeAbsensi = 'absensi';

const tglIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const STATUS_WAKTU = { TEPAT_WAKTU: ['Tepat waktu', WARNA_BADGE.hijau], TERLAMBAT: ['Terlambat', WARNA_BADGE.merah],
                       PULANG_AWAL: ['Pulang awal', WARNA_BADGE.oranye], HARI_LIBUR: ['Hari libur', WARNA_BADGE.abu] };
const badgeWaktu = s => s ? badge(...(STATUS_WAKTU[s] || [s, WARNA_BADGE.abu])) : '<span class="text-slate-300">–</span>';

const KEPALA_ABSENSI = {
    absensi: ['Nama', 'Jabatan', 'Masuk', 'Status Masuk', 'Keluar', 'Status Keluar'],
    bulanan: ['Nama', 'Jabatan', 'Hari Hadir', 'Terlambat', 'Menit Terlambat', 'Pulang Awal'],
};
const KOLOM_ANGKA_ABSENSI = { bulanan: [2, 3, 4, 5] };

function pilihModeAbsensi(el) {
    aktifkanChip(el);
    modeAbsensi = el.dataset.modeLog;
    document.querySelectorAll('[data-filter-log]').forEach(x => x.classList.toggle('hidden', !x.dataset.filterLog.split(' ').includes(modeAbsensi)));
    const angka = KOLOM_ANGKA_ABSENSI[modeAbsensi] || [];
    document.getElementById('kepalaAbsensi').innerHTML = `<tr>${KEPALA_ABSENSI[modeAbsensi].map((k, i) =>
        `<th class="table-cell${angka.includes(i) ? ' text-right' : ''}">${k}</th>`).join('')}</tr>`;
    muatAbsensi();
}

async function muatAbsensi() {
    const tbody = document.getElementById('tabelAbsensi');
    const n = KEPALA_ABSENSI[modeAbsensi].length;
    const url = modeAbsensi === 'absensi'
        ? `/api/visitor/absensi?tanggal=${document.getElementById('absTanggal').value}`
        : `/api/visitor/absensi/bulanan?bulan=${document.getElementById('absBulan').value}`;
    const data = await ambilJson(url);
    if (data.error) { tbody.innerHTML = barisGagal(n, data.error); return; }
    if (modeAbsensi === 'absensi') {
        tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td><td class="table-cell text-slate-600">${escapeHtml(r.peran || '–')}</td>
            <td class="table-cell font-mono">${escapeHtml(r.jam_masuk || '–')}</td><td class="table-cell">${badgeWaktu(r.status_masuk)}</td>
            <td class="table-cell font-mono">${escapeHtml(r.jam_pulang || '–')}</td><td class="table-cell">${badgeWaktu(r.status_pulang)}</td></tr>`).join('')
            || barisKosong(n, 'Belum ada karyawan');
    } else {
        tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td><td class="table-cell text-slate-600">${escapeHtml(r.peran || '–')}</td>
            <td class="table-cell text-right font-mono">${r.hari_hadir}</td><td class="table-cell text-right font-mono">${r.jml_terlambat}</td>
            <td class="table-cell text-right font-mono">${r.menit_terlambat}</td><td class="table-cell text-right font-mono">${r.jml_pulang_awal}</td></tr>`).join('')
            || barisKosong(n, 'Belum ada absensi bulan ini');
    }
}

document.getElementById('absTanggal').value = tglIso(new Date());
document.getElementById('absBulan').value = tglIso(new Date()).slice(0, 7);
pilihModeAbsensi(document.querySelector('[data-mode-log="absensi"]'));