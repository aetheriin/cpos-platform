// ===== DATA ORANG (Visitor & Staff Logs › Data Orang, Data Master › Supir): daftar, tambah, ubah, hapus =====
// Jenis orang: Karyawan (area + departemen + jabatan), Driver / Tamu (asal perusahaan, keperluan), Driver = SIM.
let personelDimuat = false;
let filterPersonelAktif = '';
let timerCariPersonel = null;
let daftarPersonel = [];

// state modal Tambah / Update
let modePersonel = 'tambah';          
let idPersonelEdit = null;
let fotoPersonel = null;              
let sumberFotoPersonel = 'UPLOAD';
let adaAkunPersonel = false;          // karyawan ber-akun: jabatan diatur di Kelola Pengguna

// Data Master > Supir: hanya satu jenis (tanpa chip filter, jenis di modal terkunci)
const TAB_PERSONEL = document.querySelector('[data-tab-content="orang"]') ? 'orang' : 'personel';
const KATEGORI_TETAP = document.querySelector(`[data-tab-content="${TAB_PERSONEL}"]`)?.dataset.kategoriTetap || '';
if (KATEGORI_TETAP) filterPersonelAktif = KATEGORI_TETAP;

window.addEventListener('tabChange', e => {
    if (e.detail === TAB_PERSONEL && !personelDimuat) {
        personelDimuat = true;
        muatPersonel();
    }
});

// ===== DAFTAR =====
function filterPersonel(el) {
    aktifkanChip(el);
    filterPersonelAktif = el.dataset.filter;
    muatPersonel();
}

function cariPersonelTunda() {
    clearTimeout(timerCariPersonel);
    timerCariPersonel = setTimeout(muatPersonel, 300);
}

async function muatPersonel() {
    const params = new URLSearchParams({ cari: document.getElementById('cariPersonel').value.trim() });
    if (filterPersonelAktif === 'BLACKLIST') params.set('blacklist', '1');
    else if (filterPersonelAktif) params.set('kategori', filterPersonelAktif);

    const data = await ambilJson(`/api/personel?${params}`);
    const tbody = document.getElementById('tabelPersonel');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return; }
    daftarPersonel = data;
    tbody.innerHTML = data.map(p => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${kodeAtauKosong(p.kode_personel)}</td>
            <td class="table-cell">${escapeHtml(p.nama_personel)}</td>
            <td class="table-cell font-mono">${escapeHtml(p.nik || '-')}</td>
            <td class="table-cell">${badgeKategori(p.kategori)}</td>
            <td class="table-cell text-slate-600">${escapeHtml(keteranganOrang(p))}</td>
            <td class="table-cell space-x-1">${p.is_blacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : badge('Aktif', WARNA_BADGE.hijau)}${badgeSim(p)}</td>
            <td class="table-cell text-right space-x-2 whitespace-nowrap">${tbody.dataset.bolehUbah === '0' ? '' : `
                <button type="button" data-on-click="bukaEditPersonel" data-arg="${Number(p.id_personel)}" class="link-aksi text-blue-600">Ubah</button>
                ${p.is_blacklisted ? '' : `<button type="button" data-on-click="bukaHapusPersonel" data-arg="${Number(p.id_personel)}" class="link-aksi text-red-600">Hapus</button>`}`}
            </td>
        </tr>`).join('') || barisKosong(7, 'Belum ada data', aksiKosong('bukaTambahPersonel', 'Tambah Orang'));
    catatanBatas(tbody, data.length, 200, 7);
}

function keteranganOrang(p) {
    if (p.kategori === 'KARYAWAN') return [p.peran, p.area].filter(Boolean).join(' · ') || '-';
    return [p.asal_perusahaan, p.keperluan].filter(Boolean).join(' · ') || '-';
}

// SIM driver: kedaluwarsa / belum dilengkapi (data lama dari sebelum migrasi 009)
function badgeSim(p) {
    if (!p.no_sim) return p.kategori === 'DRIVER' ? badge('SIM kosong', WARNA_BADGE.merah) : '';
    if (!p.sim_berlaku_sampai || p.kode_jenis_sim === 'BELUM_DIISI') return badge('SIM belum lengkap', WARNA_BADGE.oranye);
    if (p.sim_berlaku_sampai < tanggalHariIni()) return badge('SIM kedaluwarsa', WARNA_BADGE.merah);
    return '';
}

function tanggalHariIni() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ===== MODAL TAMBAH / UPDATE =====
function resetFormPersonel() {
    ['personelKode', 'personelNama', 'personelNik', 'personelSim', 'personelJenisSim', 'personelSimBerlaku',
     'personelArea', 'personelDept', 'personelJabatan', 'personelAsal', 'personelKeperluan']
        .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    adaAkunPersonel = false;
    document.getElementById('personelKategori').value = KATEGORI_TETAP || '';
    document.getElementById('personelFile').value = '';
    document.getElementById('personelCekPesan').textContent = '';
    fotoPersonel = null;
    lepasPreviewPersonel();
    tampilkanPreviewPersonel(null);
    setSemuaCek(null);
    setSumberFoto('UPLOAD');
    perbaruiHintSim();
}

async function bukaTambahPersonel() {
    modePersonel = 'tambah';
    idPersonelEdit = null;
    resetFormPersonel();
    document.getElementById('personelJudul').textContent = KATEGORI_TETAP === 'DRIVER' ? 'Tambah Supir' : 'Tambah Orang';
    document.getElementById('personelSubjudul').textContent = '';
    document.getElementById('personelNoteUpdate').classList.add('hidden');
    document.getElementById('btnSimpanPersonel').textContent = 'Simpan';
    document.getElementById('personelDropTeks').textContent = 'Seret foto ke sini atau klik untuk memilih';
    openModal('modalPersonel');

    if (KATEGORI_TETAP) isiSaranKodePersonel();
}

// Dari Scan Wajah (wajah tidak dikenali): form tambah dengan foto hasil scan, jenis dipilih dari dropdown
async function bukaTambahDariScan(blob) {
    await bukaTambahPersonel();
    if (!blob) return;
    fotoPersonel = new File([blob], 'scan.jpg', { type: 'image/jpeg' });
    tampilkanPreviewBlob(fotoPersonel);
    sumberFotoPersonel = 'KAMERA';
    cekFotoPersonel();
}

function aturDeptPersonel(pilih) {
    const area = document.getElementById('personelArea').value;
    const sel = document.getElementById('personelDept');
    const lama = typeof pilih === 'string' ? pilih : sel.value;
    [...sel.options].filter(o => o.value).forEach(o => o.remove());
    [...(document.getElementById('sumberDeptPersonel')?.content.querySelectorAll('option') || [])]
        .filter(o => area && o.dataset.area.split(',').includes(area)).forEach(o => sel.add(o.cloneNode(true)));
    sel.value = [...sel.options].some(o => o.value === lama) ? lama : '';
}

// Kode otomatis per kategori (mis. DRV-012); HO masih bisa mengubahnya
async function isiSaranKodePersonel() {
    const kategori = document.getElementById('personelKategori').value;
    const kode = document.getElementById('personelKode');
    if (!kategori) { kode.value = ''; return; }
    const saran = await ambilJson(`/api/personel/saran-kode?kategori=${encodeURIComponent(kategori)}`);
    if (saran.kode && document.getElementById('personelKategori').value === kategori) kode.value = saran.kode;
}

function gantiKategoriPersonel() {
    perbaruiHintSim();
    if (modePersonel === 'tambah') isiSaranKodePersonel();     // ubah: kode lama tetap
}

async function bukaEditPersonel(id) {
    const p = daftarPersonel.find(x => x.id_personel === id);
    if (!p) return;
    modePersonel = 'update';
    idPersonelEdit = id;
    resetFormPersonel();
    document.getElementById('personelJudul').textContent = 'Ubah Data';
    document.getElementById('personelSubjudul').textContent = formatNamaPersonel(p.kode_personel, p.id_personel, p.nama_personel);
    document.getElementById('btnSimpanPersonel').textContent = 'Simpan Perubahan';
    document.getElementById('personelDropTeks').textContent = 'Foto saat ini · klik untuk mengganti (opsional)';
    document.getElementById('personelKode').value = p.kode_personel || '';
    document.getElementById('personelNama').value = p.nama_personel;
    document.getElementById('personelNik').value = p.nik;
    document.getElementById('personelKategori').value = p.kategori;
    document.getElementById('personelSim').value = p.no_sim || '';
    document.getElementById('personelJenisSim').value = p.kode_jenis_sim === 'BELUM_DIISI' ? '' : (p.id_jenis_sim || '');
    document.getElementById('personelSimBerlaku').value = p.sim_berlaku_sampai || '';
    adaAkunPersonel = !!p.akun;
    const isi = (id, v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
    isi('personelArea', p.id_comp_area); aturDeptPersonel(p.id_department || '');
    isi('personelJabatan', p.id_jabatan); isi('personelAsal', p.asal_perusahaan); isi('personelKeperluan', p.keperluan);
    tampilkanPreviewPersonel(p.foto_path ? urlBerkas(p.foto_path) : null);
    perbaruiHintSim();
    openModal('modalPersonel');

    if (!p.kode_personel) isiSaranKodePersonel();
}

function tutupModalPersonel() {
    Kamera.stop();
    lepasPreviewPersonel();
    fotoPersonel = null;
    closeModal('modalPersonel');
}

// Isian mengikuti jenis: SIM (driver), area + departemen + jabatan (karyawan), asal perusahaan + keperluan (driver / tamu)
function perbaruiHintSim() {
    const sel = document.getElementById('personelKategori');
    const jenis = sel.value;
    const wajib = sel.selectedIndex >= 0 && sel.options[sel.selectedIndex].dataset.wajibSim === '1';
    const tampil = (kelas, ya) => document.querySelectorAll(`#modalPersonel .${kelas}`).forEach(el => el.classList.toggle('hidden', !ya));
    tampil('blok-sim', wajib);
    tampil('blok-karyawan', jenis === 'KARYAWAN' && !adaAkunPersonel);
    tampil('blok-akun', jenis === 'KARYAWAN' && adaAkunPersonel);
    tampil('blok-visitor', jenis === 'DRIVER' || jenis === 'TAMU');
    if (!wajib) ['personelSim', 'personelJenisSim', 'personelSimBerlaku'].forEach(id => document.getElementById(id).value = '');
}

// ----- sumber foto: Upload / Kamera -----
async function setSumberFoto(sumber) {
    sumberFotoPersonel = sumber;
    document.getElementById('segUpload').classList.toggle('seg-item-active', sumber === 'UPLOAD');
    document.getElementById('segKamera').classList.toggle('seg-item-active', sumber === 'KAMERA');
    document.getElementById('panelUpload').classList.toggle('hidden', sumber !== 'UPLOAD');
    document.getElementById('panelKamera').classList.toggle('hidden', sumber !== 'KAMERA');
    if (sumber === 'KAMERA') {
        try {
            await Kamera.mulai(document.getElementById('personelVideo'));
        } catch (err) {
            Notif.gagal('Kamera tidak dapat dibuka. Izinkan akses kamera atau gunakan Unggah Foto.');
            setSumberFoto('UPLOAD');
        }
    } else {
        Kamera.stop();
    }
}

// Object URL preview dilepas setiap ganti foto / tutup modal supaya tidak menumpuk di memori
let urlPreviewPersonel = null;

function lepasPreviewPersonel() {
    if (urlPreviewPersonel) URL.revokeObjectURL(urlPreviewPersonel);
    urlPreviewPersonel = null;
}

function tampilkanPreviewBlob(blob) {
    lepasPreviewPersonel();
    urlPreviewPersonel = URL.createObjectURL(blob);
    tampilkanPreviewPersonel(urlPreviewPersonel);
}

function tampilkanPreviewPersonel(src) {
    document.getElementById('personelPreview').innerHTML = src
        ? `<img src="${escapeHtml(src)}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-400 text-3xl"></i>';
}

async function pilihFotoPersonel(file) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { Notif.peringatan('Ukuran foto maksimal 10 MB'); return; }
    fotoPersonel = await kecilkanFoto(file);         
    tampilkanPreviewBlob(fotoPersonel);
    cekFotoPersonel();
}

function dropFotoPersonel(e) {
    e.preventDefault();
    pilihFotoPersonel(e.dataTransfer.files[0]);
}

async function ambilFotoKamera() {
    const blob = await Kamera.ambilFrame(document.getElementById('personelVideo'), 0.9, 1024);
    fotoPersonel = new File([blob], 'kamera.jpg', { type: 'image/jpeg' });
    tampilkanPreviewBlob(fotoPersonel);
    cekFotoPersonel();
}

// ----- 3 pengecekan foto (✓ / ✕) -----
function setCek(key, lolos) {
    const li = document.querySelector(`#personelCek [data-cek="${key}"]`);
    const teks = li.textContent.replace(/^[✓✕○…]\s*/, '');
    const [ikon, warna] = lolos === true ? ['✓', 'text-emerald-600'] : lolos === false ? ['✕', 'text-red-600']
        : lolos === 'proses' ? ['…', 'text-slate-500'] : ['○', 'text-slate-400'];
    li.className = warna;
    li.textContent = `${ikon} ${teks}`;
}

function setSemuaCek(nilai) {
    ['satu_wajah', 'tidak_mirip_personel', 'tidak_mirip_blacklist'].forEach(k => setCek(k, nilai));
}

async function cekFotoPersonel() {
    setSemuaCek('proses');
    document.getElementById('personelCekPesan').textContent = '';
    const formData = new FormData();
    formData.append('foto', fotoPersonel, fotoPersonel.name || 'foto.jpg');
    if (idPersonelEdit) formData.append('id_personel', idPersonelEdit);

    const hasil = await kirimForm('/api/personel/cek-foto', formData, { timeout: TIMEOUT_WAJAH_MS });
    if (hasil.error && hasil.satu_wajah === undefined) {
        setSemuaCek(null);
        document.getElementById('personelCekPesan').textContent = hasil.error;
        return;
    }
    setCek('satu_wajah', hasil.satu_wajah);
    setCek('tidak_mirip_personel', hasil.tidak_mirip_personel ?? null);
    setCek('tidak_mirip_blacklist', hasil.tidak_mirip_blacklist ?? null);
    document.getElementById('personelCekPesan').textContent = hasil.pesan || '';
}

async function simpanPersonel() {
    if (!document.getElementById('personelKategori').value) { Notif.peringatan('Pilih jenis orang'); return; }
    if (modePersonel === 'tambah' && !fotoPersonel) { Notif.peringatan('Foto wajah wajib diisi (upload atau kamera)'); return; }
    const formData = new FormData();
    [['kode_personel', 'personelKode'], ['nama', 'personelNama'], ['nik', 'personelNik'],
     ['kategori', 'personelKategori'], ['no_sim', 'personelSim'], ['id_jenis_sim', 'personelJenisSim'],
     ['sim_berlaku', 'personelSimBerlaku'], ['id_comp_area', 'personelArea'], ['id_department', 'personelDept'],
     ['id_jabatan', 'personelJabatan'], ['asal_perusahaan', 'personelAsal'], ['keperluan', 'personelKeperluan']]
        .forEach(([k, id]) => { const el = document.getElementById(id); if (el) formData.append(k, el.value.trim()); });
    formData.append('foto_sumber', sumberFotoPersonel);
    if (fotoPersonel) formData.append('foto', fotoPersonel, fotoPersonel.name || 'foto.jpg');

    const url = modePersonel === 'tambah' ? '/api/personel/tambah' : `/api/personel/${idPersonelEdit}/update`;
    const btn = document.getElementById('btnSimpanPersonel');
    const data = await denganTombol(btn, () => kirimForm(url, formData, { timeout: TIMEOUT_WAJAH_MS }), 'Menyimpan...');
    if (data.error) {
        if (data.cek) {
            setCek('satu_wajah', data.cek.satu_wajah);
            setCek('tidak_mirip_personel', data.cek.tidak_mirip_personel ?? null);
            setCek('tidak_mirip_blacklist', data.cek.tidak_mirip_blacklist ?? null);
        }
        Notif.gagal(data.error);
        return;
    }
    Notif.sukses(data.message);
    tutupModalPersonel();
    muatPersonel();
    if (data.menunggu && typeof muatPengajuan === 'function') muatPengajuan();
    window.dispatchEvent(new CustomEvent('orangDisimpan', { detail: data }));
}

// ===== HAPUS (dialog konfirmasi standar) =====
async function bukaHapusPersonel(id) {
    const p = daftarPersonel.find(x => x.id_personel === id);
    if (!p) return;
    const ok = await Dialog.konfirmasi({ judul: 'Hapus orang?', teksYa: 'Hapus', bahaya: true,
        pesan: `${p.nama_personel} (${p.kode_personel || 'belum ada kode'} · ${(LABEL_KATEGORI[p.kategori] || [p.kategori])[0]})\n`
            + 'Wajahnya tidak lagi dikenali saat scan. Riwayat scan & tiket tetap tersimpan.' });
    if (!ok) return;
    if (tampilkanHasil(await kirimForm(`/api/personel/${id}/hapus`, {}))) muatPersonel();
}
