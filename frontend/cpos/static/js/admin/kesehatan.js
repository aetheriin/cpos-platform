// ===== ADMIN > KESEHATAN SISTEM =====
document.addEventListener('DOMContentLoaded', muatKesehatan);

// status: 'ok' | 'peringatan' | 'gagal' -> warna & ikon kartu
const GAYA_STATUS = {
    ok: ['text-emerald-600', 'fa-circle-check'],
    peringatan: ['text-amber-600', 'fa-triangle-exclamation'],
    gagal: ['text-red-600', 'fa-circle-xmark'],
    info: ['text-slate-800', 'fa-circle-info'],
};
const URUTAN_STATUS = { gagal: 0, peringatan: 1 };   // yang bermasalah tampil paling depan

function kartu(judul, ikon, nilai, info, status = 'info') {
    const [warna, ikonStatus] = GAYA_STATUS[status];
    return { judul, status, html: `<div class="stat-card">
        <div class="flex items-center justify-between">
            <p class="stat-label"><i class="fa-solid ${ikon} mr-1"></i> ${escapeHtml(judul)}</p>
            <i class="fa-solid ${ikonStatus} ${warna}"></i>
        </div>
        <p class="stat-value ${warna}">${escapeHtml(nilai)}</p>
        <p class="text-xs text-slate-500 mt-1">${escapeHtml(info)}</p>
    </div>` };
}

// Satu baris jawaban "ada yang bermasalah?" di atas kartu
function ringkasan(daftar) {
    const masalah = daftar.filter(k => k.status in URUTAN_STATUS);
    if (!masalah.length) {
        return '<p class="col-span-full flex items-center gap-2 text-sm font-semibold text-emerald-700"><i class="fa-solid fa-circle-check"></i> Semua normal</p>';
    }
    const gaya = masalah.some(k => k.status === 'gagal') ? 'note-danger' : 'note-warning text-sm';
    return `<p class="col-span-full ${gaya} flex items-center gap-2 font-semibold"><i class="fa-solid fa-triangle-exclamation"></i>
        ${masalah.length} perlu dicek: ${masalah.map(k => escapeHtml(k.judul)).join(', ')}</p>`;
}

function statusBackup(db) {
    if (db.backup_terakhir === 'tidak bisa dibaca') return ['Tidak terbaca', 'Akun aplikasi tidak punya akses msdb. Cek di SSMS.', 'peringatan'];
    if (!db.backup_terakhir) return ['Belum pernah', 'Jadwalkan backup harian sekarang.', 'gagal'];
    const umur = db.backup_umur_jam;
    return [db.backup_terakhir, `${db.backup_tipe} · ${umur} jam lalu`, umur > 26 ? 'peringatan' : 'ok'];
}

// Tanpa jembatan timbang aktif tidak ada yang bisa terputus, jadi bukan peringatan
function kartuTimbangan(t) {
    if (!t.jumlah) return kartu('Timbangan', 'fa-weight-scale', '0 / 0 terhubung', 'Belum ada jembatan timbang yang aktif');
    return kartu('Timbangan', 'fa-weight-scale', `${t.jumlah_terhubung} / ${t.jumlah} terhubung`, 'Koneksi serial tiap jembatan timbang aktif',
                 t.terhubung ? 'ok' : 'peringatan');
}

async function muatKesehatan() {
    const d = await ambilJson('/api/admin/kesehatan');
    const wadah = document.getElementById('kartuKesehatan');
    if (d.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(d.error)}</p>`; return false; }
    const db = d.database;
    const [nilaiBackup, infoBackup, stBackup] = db.ok ? statusBackup(db) : ['-', 'Database tidak terhubung', 'gagal'];
    const disk = d.disk;
    const daftar = [
        kartu('Database', 'fa-database', db.ok ? 'Terhubung' : 'Gagal',
              db.ok ? `${db.nama || ''} · respons ${db.latensi_ms} ms` : (db.error || 'Cek SQL Server / .env'),
              db.ok ? (db.latensi_ms > 500 ? 'peringatan' : 'ok') : 'gagal'),
        kartu('Ukuran Database', 'fa-hard-drive', db.ukuran_mb != null ? `${db.ukuran_mb} MB` : '-', 'Data + log SQL Server'),
        kartu('Cadangan Data Terakhir', 'fa-clock-rotate-left', nilaiBackup, infoBackup, stBackup),
        kartu('Disk Server', 'fa-server', `${disk.sisa_gb} GB sisa`, `dari ${disk.total_gb} GB · terpakai ${disk.terpakai_persen}%`,
              disk.terpakai_persen > 90 ? 'gagal' : disk.terpakai_persen > 80 ? 'peringatan' : 'ok'),
        kartu('Folder Unggahan', 'fa-folder-open', `${d.upload.ukuran_mb} MB${d.upload.lebih ? '+' : ''}`, 'Foto wajah, surat blacklist, foto absensi'),
        kartuTimbangan(d.timbangan),
        kartu('Versi Aplikasi', 'fa-code-branch', d.aplikasi.versi, `${d.aplikasi.git} · Python ${d.aplikasi.python}`),
        kartu('Server Berjalan', 'fa-power-off', `${d.aplikasi.uptime_jam} jam`, `sejak ${d.aplikasi.berjalan_sejak}`),
        kartu('Sesi Aktif', 'fa-users', String(d.aplikasi.sesi_aktif), 'Pengguna yang sedang login'),
    ];
    const urut = daftar.map((k, i) => [URUTAN_STATUS[k.status] ?? 2, i, k]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(x => x[2]);
    wadah.innerHTML = ringkasan(daftar) + urut.map(k => k.html).join('');
    document.getElementById('waktuCekKesehatan').textContent = `Dicek ${new Date().toLocaleTimeString('id-ID')}`;
}
