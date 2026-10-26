// ===== REKAPIN: Request Operator (modules/rekapin/routes.py /rekapin/api/request*) =====
let dataRequest = [];
let statusRequest = '';
let aksiAktif = null;            // { id, status }
let tiketDipilih = '';
let jedaCari = null;

const STATUS_RK = { Pending: ['Menunggu', WARNA_BADGE.oranye], Approved: ['Disetujui', WARNA_BADGE.biru],
                    Rejected: ['Ditolak', WARNA_BADGE.merah], Done: ['Selesai', WARNA_BADGE.hijau] };
const hakRequest = () => JSON.parse(document.getElementById('tabelRkRequest').dataset.hak || '{}');

document.addEventListener('DOMContentLoaded', muatRequest);

function filterRequest(status) {
    statusRequest = statusRequest === status ? '' : status;
    document.querySelectorAll('[data-status-kartu]').forEach(k =>
        k.classList.toggle('ring-2', k.dataset.statusKartu === statusRequest));
    muatRequest();
}

function infoTiket(info) {
    const isi = [['Tanggal', info.Tanggal], ['Produk', info.ProductName], ['Kendaraan', info.VehicleNo], ['Supir', info.NamaSupir],
                 ['Bruto', info.Bruto], ['Tara', info.Tara], ['Netto', info.Netto], ['Operator', info.Operator]].filter(x => x[1]);
    if (!isi.length) return '';
    return `<details class="mt-1"><summary class="text-xs text-blue-600 cursor-pointer">Info tiket</summary>
        <dl class="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">${isi.map(([k, v]) =>
        `<dt class="text-slate-500">${escapeHtml(k)}</dt><dd class="font-mono text-slate-800">${escapeHtml(v)}</dd>`).join('')}</dl></details>`;
}

async function muatRequest() {
    const tbody = document.getElementById('tabelRkRequest');
    const hak = hakRequest();
    const kolom = hak.setujui ? 9 : 8;
    const res = await ambilJson(`/rekapin/api/request?status=${encodeURIComponent(statusRequest)}`);
    if (res.error) { tbody.innerHTML = barisKosong(kolom, res.error); return; }
    Object.entries(res.ringkas).forEach(([st, n]) => {
        const el = document.getElementById(`rkJumlah${st}`);
        if (el) el.textContent = n;
    });
    document.getElementById('rkFilterInfo').textContent =
        statusRequest ? `${t('Status')}: ${t(STATUS_RK[statusRequest][0])} · ${res.data.length}` : `${res.data.length} request`;
    dataRequest = res.data;
    tbody.innerHTML = res.data.map(r => {
        const aktif = !['Rejected', 'Done'].includes(r.status);
        const tombol = [
            hak.setujui && r.status === 'Pending' ? `<button type="button" class="link-aksi text-emerald-700" data-on-click="bukaAksiRequest" data-arg="${r.id}|Approved"><i class="fa-solid fa-check"></i> Setujui</button>` : '',
            hak.tolak && r.status === 'Pending' ? `<button type="button" class="link-aksi text-red-600" data-on-click="bukaAksiRequest" data-arg="${r.id}|Rejected"><i class="fa-solid fa-xmark"></i> Tolak</button>` : '',
            hak.selesai && aktif ? `<button type="button" class="link-aksi text-indigo-600" data-on-click="bukaAksiRequest" data-arg="${r.id}|Done"><i class="fa-solid fa-check-double"></i> Selesai</button>` : '',
            hak.ubah && aktif ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaRequest" data-arg="${r.id}">Ubah</button>` : '',
            hak.hapus && aktif ? `<button type="button" class="link-aksi text-red-600" data-on-click="hapusRequest" data-arg="${r.id}">Hapus</button>` : '',
        ].filter(Boolean).join(' ');
        return `<tr class="hover:bg-slate-50 align-top">
            ${hak.setujui ? `<td class="table-cell">${r.status === 'Pending' ? `<input type="checkbox" class="w-4 h-4" data-pilih-request="${r.id}" data-on-change="hitungPilihan">` : ''}</td>` : ''}
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(formatWaktu(r.dibuat))}<div class="text-slate-400">${escapeHtml(r.dibuat_oleh || '')}</div></td>
            <td class="table-cell font-semibold">${escapeHtml(r.operator)}<div class="text-xs font-normal text-slate-400">${escapeHtml(r.id_company || '')}</div></td>
            <td class="table-cell">${badge(r.kategori, WARNA_BADGE.abu)}</td>
            <td class="table-cell"><span class="font-mono">${escapeHtml(r.tiket)}</span>${infoTiket(r.info_tiket || {})}</td>
            <td class="table-cell text-slate-600 max-w-48">${escapeHtml(r.catatan || '—')}</td>
            <td class="table-cell text-slate-600">${escapeHtml(r.catatan_aksi || '—')}${r.aksi_oleh ? `<div class="text-[11px] text-slate-400">${escapeHtml(r.aksi_oleh)}</div>` : ''}</td>
            <td class="table-cell">${badge(t(STATUS_RK[r.status][0]), STATUS_RK[r.status][1])}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-2">${tombol || '<span class="text-xs text-slate-400">—</span>'}</td></tr>`;
    }).join('') || barisKosong(kolom, 'Belum ada request');
    hitungPilihan();
}

function formatWaktu(teks) {
    const d = new Date(teks);
    return isNaN(d) ? (teks || '') : d.toLocaleString('id-ID', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ===== Pilih banyak -> Setujui Terpilih =====
function idTerpilih() {
    return [...document.querySelectorAll('[data-pilih-request]:checked')].map(c => c.dataset.pilihRequest);
}

function hitungPilihan() {
    const tombol = document.getElementById('rkSetujuiTerpilih');
    if (!tombol) return;
    const n = idTerpilih().length;
    tombol.classList.toggle('hidden', !n);
    document.getElementById('rkJumlahPilih').textContent = n ? `(${n})` : '';
}

function pilihSemuaRequest(el) {
    document.querySelectorAll('[data-pilih-request]').forEach(c => { c.checked = el.checked; });
    hitungPilihan();
}

async function setujuiTerpilih(btn) {
    const ids = idTerpilih();
    if (!ids.length || !await Dialog.konfirmasi({ judul: 'Setujui request terpilih?', teksYa: 'Setujui',
        pesan: `${ids.length} request yang masih menunggu akan disetujui.` })) return;
    const data = await denganTombol(btn, () => kirimForm('/rekapin/api/request/setujui-terpilih', { ids: ids.join(',') }));
    if (tampilkanHasil(data)) { document.getElementById('rkPilihSemua').checked = false; muatRequest(); }
}

// ===== Tambah / Ubah =====
async function bukaRequest(id) {
    const r = id ? dataRequest.find(x => x.id === id) : null;
    const pilih = document.getElementById('rkOperator');
    const operator = await ambilJson('/rekapin/api/operator');
    if (operator.error) { tampilkanHasil(operator); return; }
    pilih.innerHTML = `<option value="">${t('Pilih operator')}</option>` + operator.map(o =>
        `<option value="${o.id_user}">${escapeHtml(o.nama)} · ${escapeHtml(o.area)}</option>`).join('');
    document.getElementById('rkRequestJudul').textContent = t(r ? 'Ubah Request' : 'Tambah Request');
    document.getElementById('rkRequestId').value = r ? r.id : '';
    pilih.value = r ? r.id_operator : '';
    document.getElementById('rkKategori').value = r ? r.id_kategori : '';
    document.getElementById('rkCatatan').value = r ? (r.catatan || '') : '';
    document.getElementById('rkCariTiket').value = '';
    document.getElementById('rkDaftarTiket').classList.add('hidden');
    pilihTiket(r ? r.tiket : '', r ? ringkasTiket(r.info_tiket || {}) : '');
    openModal('modalRkRequest');
}

function ringkasTiket(x) {
    return [x.VehicleNo, x.ProductName, x.Netto ? `Netto ${x.Netto} kg` : '', x.Tanggal].filter(Boolean).join(' · ');
}

function gantiOperator() {
    pilihTiket('', '');
    cariTiket();
}

function cariTiket() {
    clearTimeout(jedaCari);
    jedaCari = setTimeout(async () => {
        const operator = document.getElementById('rkOperator').value;
        const daftar = document.getElementById('rkDaftarTiket');
        if (!operator) { daftar.classList.add('hidden'); return; }
        const q = document.getElementById('rkCariTiket').value.trim();
        const rows = await ambilJson(`/rekapin/api/tiket?operator=${operator}&q=${encodeURIComponent(q)}`);
        daftar.classList.remove('hidden');
        if (rows.error) { daftar.innerHTML = `<p class="px-3 py-2 text-red-600">${escapeHtml(rows.error)}</p>`; return; }
        daftar.innerHTML = rows.map(r => `<button type="button" class="block w-full text-left px-3 py-2 hover:bg-blue-50${r.TicketNo === tiketDipilih ? ' bg-blue-50' : ''}"
                data-on-click="pilihTiket" data-arg="${escapeHtml(r.TicketNo)}|${escapeHtml(ringkasTiket(r))}">
                <p class="font-mono font-semibold text-slate-900">${escapeHtml(r.TicketNo)}</p><p class="text-xs text-slate-500">${escapeHtml(ringkasTiket(r))}</p></button>`).join('')
            || `<p class="px-3 py-2 text-slate-400">${t('Tidak ada tiket 7 hari terakhir')}</p>`;
    }, 250);
}

function pilihTiket(no, ringkas) {
    tiketDipilih = no;
    const info = document.getElementById('rkTiketDipilih');
    info.classList.toggle('hidden', !no);
    info.innerHTML = no ? `<i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i>${t('Dipilih')}: <b class="font-mono">${escapeHtml(no)}</b> ${ringkas ? '· ' + escapeHtml(ringkas) : ''}` : '';
    document.getElementById('rkDaftarTiket').classList.add('hidden');
}

async function simpanRequest(btn) {
    const data = await denganTombol(btn, () => kirimForm('/rekapin/api/request/simpan', {
        id: document.getElementById('rkRequestId').value,
        operator: document.getElementById('rkOperator').value,
        kategori: document.getElementById('rkKategori').value,
        tiket: tiketDipilih,
        catatan: document.getElementById('rkCatatan').value.trim() }));
    if (!tampilkanHasil(data)) return;
    closeModal('modalRkRequest');
    muatRequest();
}

async function hapusRequest(id) {
    const r = dataRequest.find(x => x.id === id);
    if (!await Dialog.konfirmasi({ judul: 'Hapus request?', teksYa: 'Hapus', bahaya: true,
        pesan: `Request tiket ${r.tiket} (${r.operator}) akan dihapus.` })) return;
    if (tampilkanHasil(await kirimForm(`/rekapin/api/request/${id}/hapus`, {}))) muatRequest();
}

// ===== Setujui / Tolak / Selesai =====
function bukaAksiRequest(id, status) {
    const r = dataRequest.find(x => x.id === id);
    aksiAktif = { id, status };
    const [judul, tombol, kelas] = { Approved: ['Setujui Request', 'Setujui', 'btn-success'], Rejected: ['Tolak Request', 'Tolak', 'btn-danger'],
                                     Done: ['Tandai Selesai', 'Selesai', 'btn-primary'] }[status];
    document.getElementById('rkAksiJudul').textContent = t(judul);
    document.getElementById('rkAksiTiket').textContent = r.tiket;
    document.getElementById('rkAksiInfo').textContent = `${r.kategori} · ${r.operator}`;
    document.getElementById('rkAksiCatatan').value = '';
    document.getElementById('rkAksiCatatanBox').classList.toggle('hidden', status === 'Done');
    document.getElementById('rkAksiPesan').classList.toggle('hidden', status !== 'Done');
    const b = document.getElementById('rkAksiTombol');
    b.textContent = t(tombol);
    b.className = kelas;
    openModal('modalRkAksi');
}

async function kirimAksiRequest(btn) {
    const data = await denganTombol(btn, () => kirimForm(`/rekapin/api/request/${aksiAktif.id}/status`, {
        status: aksiAktif.status, catatan: document.getElementById('rkAksiCatatan').value.trim() }));
    if (!tampilkanHasil(data)) return;
    closeModal('modalRkAksi');
    muatRequest();
}
