// ===== HALAMAN LIST: tiket aktif per tahap + history per produk 7 hari =====
// Tahap tiket = siapa yang harus memproses berikutnya: Timbangan, Sortasi / Lab (sesuai alur mill), Timbangan lagi.
// Tab Security = semua tiket aktif (truk yang masih di dalam) + posisinya. Lama di dalam ada di History.
// Tiket aktif dimuat ulang tiap 15 detik; tiket baru / yang pindah tahap disorot sebentar (Halaman.sorot).
// Pilihan tahap & produk history diingat per user (Pilihan di common.js).
let daftarTiket = [];
let tahapAktif = '';
let tiketSudahDimuat = false;
const jejakTiket = t => `${t.no_tiket}|${t.status_alur}|${(t.tahap_menunggu || []).join(',')}`;
const teksMenit = m => m >= 60 ? `${Math.floor(m / 60)} j ${m % 60} m` : `${m} m`;
const t_ = s => (typeof t === 'function' ? t(s) : s);

// Alur dinamis: server mengirim tahap yang ditunggu (tahap_menunggu); paralel bisa lebih dari satu
const TAB_TAHAP = { TIMBANG_1: 'timbangan', TIMBANG_2: 'timbangan', SORTASI: 'sortasi', LAB: 'lab', SECURITY_KELUAR: 'security' };
const NAMA_TAHAP_TIKET = { SECURITY: 'Security', TIMBANG_1: 'Timbang 1', TIMBANG_2: 'Timbang 2', SORTASI: 'Sortasi', LAB: 'Laboratorium', SECURITY_KELUAR: 'Security Keluar' };

function tahapTiket(t) {
    if (Array.isArray(t.tahap_menunggu)) return [...new Set(t.tahap_menunggu.map(k => TAB_TAHAP[k]).filter(Boolean))];
    if (t.status_alur === 'SECURITY_REGISTER') return ['timbangan'];
    if (t.status_alur === 'TIMBANG_1') {                     // menunggu inspeksi sesuai alur mill tiket
        const tahap = ['SORTASI', 'LAB'].filter(k => tiketPunyaTahap(t, k)).map(k => k.toLowerCase());
        return tahap.length ? tahap : ['timbangan'];
    }
    return ['timbangan'];                                    // TIMBANG_2: menunggu timbang kedua
}

// Cetak QR hanya untuk tiket yang belum selesai (/cetak/tiket menolak tiket selesai)
const TIKET_SELESAI_LIST = ['SELESAI', 'REJECTED', 'VOID'];
const LABEL_TAHAP = { security: 'Security', timbangan: 'Timbangan', sortasi: 'Sortasi', lab: 'Laboratorium' };

document.addEventListener('DOMContentLoaded', () => {
    const chip = document.getElementById('chipTahap');
    // ?tahap= (dari Dashboard › Posisi truk) didahulukan, lalu pilihan terakhir user
    const tersimpan = new URLSearchParams(location.search).get('tahap') ?? Pilihan.ambil('tahap');
    tahapAktif = tersimpan != null && chip.querySelector(`[data-tahap="${CSS.escape(tersimpan)}"]`) ? tersimpan : chip.dataset.awal || '';
    aktifkanChip(chip.querySelector(`[data-tahap="${CSS.escape(tahapAktif)}"]`));
    // ?cari=... (dari pencarian global) -> kotak cari terisi
    const cariAwal = new URLSearchParams(location.search).get('cari');
    if (cariAwal) document.getElementById('searchTiket').value = cariAwal;
    new Poller(muatTiketAktif, 15000).start();
    muatHistoryProduk();
});

async function muatTiketAktif() {
    const data = await ambilJson('/api/security/list-tiket-aktif', { polling: tiketSudahDimuat });
    const tbody = document.getElementById('tabelTicketAktif');
    if (data.error) { if (!tiketSudahDimuat) tbody.innerHTML = barisGagal(7, data.error); return; }
    // Muatan pertama: semua tiket dianggap sudah dikenal (tidak disorot walau tab tahap diganti)
    if (!tiketSudahDimuat) Halaman.kenali(tbody, data.map(jejakTiket));
    tiketSudahDimuat = true;
    daftarTiket = data;
    tampilkanTiket();
}

const angkaKg = v => v == null ? '–' : Number(v).toLocaleString('id-ID');
// Sel dua baris: teks utama + keterangan kecil di bawahnya
const duaBaris = (atas, bawah, mono = false) => `<span class="block ${mono ? 'font-mono font-semibold text-slate-900' : 'text-slate-800'} whitespace-nowrap">${atas}</span>
    <span class="block text-xs text-slate-500 truncate max-w-[14rem]">${bawah || '-'}</span>`;

function tampilkanTiket() {
    const baris = daftarTiket.filter(t => !tahapAktif || tahapAktif === 'security' || tahapTiket(t).includes(tahapAktif));
    document.getElementById('tabelTicketAktif').innerHTML = baris.map(t => {
        // Tab tujuan saat "Buka": tahap yang dipilih, atau tahap berikutnya tiket ini
        const tab = tahapAktif && tahapAktif !== 'security' ? tahapAktif : tahapTiket(t).slice(-1)[0];
        const menunggu = Array.isArray(t.tahap_menunggu)
            ? t.tahap_menunggu.map(k => t_(NAMA_TAHAP_TIKET[k] || k)).join(' / ')
            : { SECURITY_REGISTER: 'Timbang 1', TIMBANG_2: 'Timbang 2' }[t.status_alur] || LABEL_TAHAP[tahapTiket(t)[0]];
        // Lama menunggu tahap berjalan (tahap paralel mulai bersamaan, jadi cukup ambil yang terbesar)
        const tunggu = Math.max(-1, ...(t.tahap || []).filter(x => x.berjalan && x.menit != null).map(x => x.menit));
        return `<tr class="hover:bg-slate-50" data-jejak="${escapeHtml(jejakTiket(t))}">
            <td class="table-cell">${duaBaris(escapeHtml(t.no_tiket), escapeHtml(t.created_at), true)}</td>
            <td class="table-cell">${duaBaris(escapeHtml(t.no_plat), escapeHtml(t.supir), true)}</td>
            <td class="table-cell">${duaBaris(`<span class="font-semibold">${escapeHtml(t.produk)}</span>`, escapeHtml(labelKode(t.jenis_transaksi)))}</td>
            <td class="table-cell">${duaBaris(escapeHtml(t.supplier), `<span class="font-mono">${escapeHtml(t.no_do || 'Tanpa DO')}</span>`)}</td>
            <td class="table-cell">${badgeStatusTiket(t.status_alur)}</td>
            <td class="table-cell text-xs"><span class="font-semibold text-slate-600">${escapeHtml(menunggu)}</span>${tunggu >= 0
                ? ` <span class="font-mono ${tunggu >= 60 ? 'text-red-600 font-semibold' : 'text-slate-400'}" title="${escapeHtml(t_('Lama menunggu'))}">· ${teksMenit(tunggu)}</span>` : ''}
                ${jejakDurasi(t.tahap)}</td>
            <td class="table-cell text-right whitespace-nowrap">
                <a class="aksi-ikon" title="Buka di form" href="/weighbridge?view=form&tab=${encodeURIComponent(tab)}&plat=${encodeURIComponent(t.no_plat)}"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>
                <a class="aksi-ikon" title="Cetak QR" href="/cetak/tiket/${encodeURIComponent(t.no_tiket)}" target="_blank"><i class="fa-solid fa-print"></i></a>
            </td>
        </tr>`;
    }).join('') || barisKosong(7, tahapAktif === 'security' ? 'Tidak ada truk di dalam'
        : tahapAktif ? `Tidak ada tiket yang menunggu ${LABEL_TAHAP[tahapAktif]}` : 'Belum ada tiket aktif');
    document.getElementById('infoJumlahTiket').innerHTML = `Menampilkan <b class="text-slate-900">${baris.length}</b> dari ${daftarTiket.length} tiket aktif`;
    saringTabel(document.getElementById('searchTiket').value);
}

// Jejak tahap tiket alur dinamis: selesai (centang + lamanya), berjalan (kuning + lama sejauh ini), berikutnya (abu).
// Tahap bersamaan digabung dengan "+". Tiket lama (tanpa tahap) tidak punya jejak.
function jejakDurasi(tahap) {
    if (!Array.isArray(tahap) || !tahap.length) return '';
    const chip = x => {
        const nama = escapeHtml(t_(NAMA_TAHAP_TIKET[x.kode] || x.kode));
        const lama = x.menit != null && x.kode !== 'SECURITY' ? ` <span class="font-mono opacity-75">(${teksMenit(x.menit)})</span>` : '';
        if (x.status === 'SELESAI') return `<span class="text-emerald-700"><i class="fa-solid fa-check text-[9px]"></i> ${nama}${lama}</span>`;
        if (x.berjalan) return `<span class="rounded bg-amber-50 px-1 text-amber-700 font-semibold">${nama}${lama}</span>`;
        return `<span class="text-slate-400">${nama}</span>`;
    };
    const grup = [];
    tahap.forEach(x => { if (grup.length && grup[grup.length - 1][0].grup === x.grup) grup[grup.length - 1].push(x); else grup.push([x]); });
    return `<div class="mt-1 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11px] leading-4">${grup.map(g => g.map(chip).join(' + '))
        .join('<i class="fa-solid fa-angle-right text-[9px] text-slate-300"></i>')}</div>`;
}

function filterTahap(el) {
    aktifkanChip(el);
    tahapAktif = el.dataset.tahap;
    Pilihan.simpan('tahap', tahapAktif);
    tampilkanTiket();
}

async function muatHistoryProduk() {
    const idProduk = document.getElementById('filterProdukHistory').value;
    const data = await ambilJson(`/api/list/history-produk?id_produk=${encodeURIComponent(idProduk)}`);
    const tbody = document.getElementById('tabelHistoryProduk');
    if (data.error) { tbody.innerHTML = barisGagal(10, data.error); return; }
    const bolehPeriksa = tbody.dataset.bolehPeriksa === '1';
    const bolehKoreksi = tbody.dataset.bolehKoreksi === '1';
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${duaBaris(escapeHtml(r.no_tiket), escapeHtml(r.created_at), true)}</td>
            <td class="table-cell">${duaBaris(escapeHtml(r.no_plat), escapeHtml(r.supir), true)}</td>
            <td class="table-cell">${duaBaris(`<span class="font-semibold">${escapeHtml(r.produk)}</span>`, escapeHtml(labelKode(r.jenis_transaksi)))}</td>
            <td class="table-cell">${duaBaris(escapeHtml(r.supplier), `<span class="font-mono">${escapeHtml(r.no_do || 'Tanpa DO')}</span>`)}</td>
            <td class="table-cell text-right font-mono text-slate-600">${angkaKg(r.berat_bruto)}</td>
            <td class="table-cell text-right font-mono text-slate-600">${angkaKg(r.berat_tara)}</td>
            <td class="table-cell text-right font-mono font-bold text-blue-700">${angkaKg(r.berat_netto)}</td>
            <td class="table-cell whitespace-nowrap text-xs">${labelLama(r.lama_menit)}</td>
            <td class="table-cell">${badgeStatusTiket(r.status_alur)}${r.diperiksa_pada
                ? `<span class="block text-[11px] text-emerald-700 mt-1" title="${escapeHtml(r.diperiksa_pada)}"><i class="fa-solid fa-check mr-1"></i>Diperiksa ${escapeHtml(r.pemeriksa || '')}</span>` : ''}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${TIKET_SELESAI_LIST.includes(r.status_alur) ? '' :
                `<a class="aksi-ikon" title="Cetak QR tiket" href="/cetak/tiket/${encodeURIComponent(r.no_tiket)}" target="_blank"><i class="fa-solid fa-print"></i></a>`}${
                bolehPeriksa && r.status_alur === 'SELESAI' && !r.diperiksa_pada
                ? `<button type="button" class="link-aksi text-emerald-700" data-on-click="periksaTiket" data-arg="${escapeHtml(r.no_tiket)}">Periksa</button>` : ''}${
                bolehKoreksi && r.status_alur !== 'VOID'
                ? `<button type="button" class="link-aksi text-amber-700" data-on-click="bukaKoreksi" data-arg="${escapeHtml(r.no_tiket)}">Ajukan Koreksi</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(10, 'Belum ada transaksi 7 hari terakhir');
    const total = data.reduce((a, r) => a + (Number(r.berat_netto) || 0), 0);
    document.getElementById('infoTotalNetto').innerHTML = `Total netto 7 hari: <b class="text-slate-900">${angkaKg(total)} kg</b>`;
    catatanBatas(tbody, data.length, 500, 10);
    saringTabel(document.getElementById('searchTiket').value);
}

// Cari: "bm1455" cocok dengan "BM 1455 JJ"
function saringTabel(kata) {
    const cari = kata.toUpperCase().replace(/\s+/g, '');
    ['tabelTicketAktif', 'tabelHistoryProduk'].forEach(id => {
        document.querySelectorAll(`#${id} tr`).forEach(tr => {
            if (tr.children.length < 2) return;
            tr.classList.toggle('hidden', !!cari && !tr.textContent.toUpperCase().replace(/\s+/g, '').includes(cari));
        });
        Halaman.segarkan(document.getElementById(id));
    });
}

// Lama truk di dalam (tiket dibuat s/d timbang terakhir); merah bila lebih dari 4 jam
function labelLama(menit) {
    if (menit == null) return '-';
    const jam = Math.floor(menit / 60);
    const teks = jam ? `${jam} jam ${menit % 60} mnt` : `${menit} mnt`;
    return jam >= 4 ? `<span class="text-red-600 font-semibold">${teks}</span>` : teks;
}

// Verifikasi tiket selesai (hak Setujui di menu Daftar Tiket): pemeriksa & waktunya dicatat
async function periksaTiket(noTiket) {
    const ok = await Dialog.konfirmasi({ judul: `Tandai tiket ${noTiket} sudah diperiksa?`, teksYa: 'Ya, sudah diperiksa',
        pesan: 'Nama Anda dan waktu pemeriksaan dicatat pada tiket ini dan tidak bisa dibatalkan.' });
    if (!ok) return;
    if (tampilkanHasil(await kirimForm(`/api/tiket/${encodeURIComponent(noTiket)}/periksa`, {}))) muatHistoryProduk();
}

// ===== AJUKAN KOREKSI TIKET =====
let noKoreksi = null;

async function bukaKoreksi(noTiket) {
    const data = await ambilJson(`/api/tiket/${encodeURIComponent(noTiket)}/koreksi`);
    if (data.error) { Notif.gagal(data.error); return; }
    noKoreksi = noTiket;
    const t = data.tiket;
    const isi = (id, daftar, pilih) => {
        const sel = document.getElementById(id);
        [...sel.options].filter(o => o.value !== '').forEach(o => o.remove());
        daftar.forEach(o => sel.add(new Option(o.nama, o.id)));
        sel.value = String(pilih);
    };
    document.getElementById('formKoreksi').reset();
    isi('korCustomer', data.customer, t.id_supplier);
    isi('korProduk', data.produk, t.id_produk);
    isi('korSupir', data.supir, t.id_driver);
    document.getElementById('korPlat').value = t.no_plat;
    document.getElementById('noTiketKoreksi').textContent = noTiket;
    openModal('modalKoreksi');
    document.getElementById('korAlasan').focus();
}

document.getElementById('formKoreksi')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('[type=submit]');
    const data = await denganTombol(btn, () => kirimForm(`/api/tiket/${encodeURIComponent(noKoreksi)}/koreksi`, new FormData(e.target)));
    if (!tampilkanHasil(data)) return;
    closeModal('modalKoreksi');
    muatHistoryProduk();
    if (typeof muatPengajuan === 'function') muatPengajuan();
});

// Dari notifikasi (?bagian=koreksi): langsung ke bagian Pengajuan Koreksi
document.addEventListener('DOMContentLoaded', () => {
    if (new URLSearchParams(location.search).get('bagian') === 'koreksi') {
        setTimeout(() => document.getElementById('bagianKoreksi')?.scrollIntoView({ block: 'start' }), 600);
    }
});
