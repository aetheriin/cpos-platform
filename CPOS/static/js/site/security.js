// Pengaturan site dari server (.env WAJIB_SCAN_WAJAH), dikirim lewat <meta> di weighbridge.html
const WAJIB_SCAN_WAJAH = document.querySelector('meta[name="wajib-scan-wajah"]')?.content !== 'false';

document.addEventListener('DOMContentLoaded', () => aturStatusForm('draft'));

// ===== SINKRON FORM DENGAN HASIL LOOKUP PLAT =====
let saranDriver = null;

function badgeStatusPersonel(isBlacklisted) {
    return isBlacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : badge('Aktif', WARNA_BADGE.hijau);
}

// ===== PERINGATAN BLACKLIST (kendaraan dan / atau supir) =====
// Blacklist berlaku di semua area: banner menyebut siapa yang diblacklist dan siapa / area mana yang menetapkan.
const blacklistForm = { kendaraan: null, supir: null };     // { siapa, info: hasil /api/blacklist/info }

function aturBlacklist(jenis, data) {
    blacklistForm[jenis] = data;
    const isi = ['kendaraan', 'supir'].filter(j => blacklistForm[j]);
    const banner = document.getElementById('bannerBlacklist');
    banner.classList.toggle('hidden', !isi.length);
    banner.classList.toggle('flex', isi.length > 0);
    document.getElementById('formNoPlat').classList.toggle('border-red-500', !!blacklistForm.kendaraan);
    document.getElementById('bannerBlacklistIsi').innerHTML = isi.map(j => {
        const { siapa, info } = blacklistForm[j];
        const penetap = info && info.oleh ? `oleh ${escapeHtml(info.oleh)}${info.area_oleh ? ` (${escapeHtml(info.area_oleh)})` : ''}` : '';
        return `<div class="text-sm">
            <p class="font-semibold text-red-700">${j === 'kendaraan' ? 'Kendaraan' : 'Supir'}: ${escapeHtml(siapa)}</p>
            <p class="text-xs text-slate-700">${info && info.no_surat_blacklist ? `No. surat ${escapeHtml(info.no_surat_blacklist)} · ` : ''}` +
            `${info && info.tgl_blacklist ? `ditetapkan ${escapeHtml(info.tgl_blacklist)} ` : ''}${penetap} · berlaku di semua area · permanen` +
            `${info && info.file_surat_blacklist ? ` · <a href="${escapeHtml(urlBerkas(info.file_surat_blacklist))}" target="_blank" class="underline text-red-700">Lihat surat</a>` : ''}</p>
        </div>`;
    }).join('');
}

async function aturBlacklistSupir(dr) {
    if (!dr || !dr.is_blacklisted) { aturBlacklist('supir', null); return; }
    const siapa = formatNamaPersonel(dr.id_driver, dr.nama);
    aturBlacklist('supir', { siapa, info: null });
    const info = await ambilJson(`/api/blacklist/info/PERSONEL/${dr.id_driver}`);
    if (blacklistForm.supir && blacklistForm.supir.siapa === siapa && !info.error) aturBlacklist('supir', { siapa, info });
}

function kotakMerah(el, aktif) {
    el.classList.toggle('ring-4', aktif);
    el.classList.toggle('ring-red-600', aktif);
}

// Supir terakhir truk ini (pembanding untuk supir yang discan / dipilih di bagian Informasi Supir)
let pengemudiTerakhir = null;

function tampilkanPengemudiTerakhir(dr, utama = null) {
    pengemudiTerakhir = dr || null;
    tandaiPengemudiCocok(null);
    const info = document.getElementById('pengemudiTerakhirInfo');
    const foto = document.getElementById('pengemudiFotoBox');
    const kartu = document.getElementById('pengemudiKartu');
    kotakMerah(foto, !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('border-red-500', !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('bg-red-50', !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('bg-slate-50', !(dr && dr.is_blacklisted));
    const barisUtama = utama && (!dr || String(utama.id_driver) !== String(dr.id_driver))
        ? `<p class="text-xs text-blue-600">Supir utama: ${escapeHtml(utama.nama)}</p>` : '';
    if (!dr) {
        info.innerHTML = 'Belum ada riwayat' + barisUtama;
        foto.innerHTML = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
        return;
    }
    info.innerHTML = `<p class="text-xs text-slate-500">ID ${formatIdPersonel(dr.id_driver)}</p>` +
        `<p class="font-semibold text-slate-700">${escapeHtml(dr.nama)}</p><p>NIK: ${escapeHtml(dr.nik)}</p>` +
        (dr.is_blacklisted ? '<p class="mt-1"><span class="px-2 py-0.5 rounded bg-red-600 text-white text-xs font-bold">BLACKLIST</span></p>' : '') +
        (dr.is_updated ? '<p class="text-amber-600 text-xs">⚠ Data Pernah Diperbarui</p>' : '') + barisUtama;
    foto.innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
}

// ===== STATUS FORM PENDAFTARAN TIKET =====
let statusForm = 'draft';
let supirTerverifikasi = false;
// Jenis / customer / produk terisi otomatis dari DO tetapi tetap bisa diubah (tanpa DO diisi sendiri)
const FIELD_KENDARAAN = ['formNoPlat', 'formNoStnk', 'formNoDo', 'formJenisTransaksi', 'formSupplier', 'formProduk'];

// blacklist: plat masuk blacklist, hanya kolom plat yang bisa diganti
function aturStatusForm(status) {
    statusForm = status;
    FIELD_KENDARAAN.forEach(id => {
        document.getElementById(id).disabled = status !== 'draft';
    });
    document.getElementById('sectionInfoDriver').classList.toggle('section-disabled', status === 'draft');

    const btn = document.getElementById('btnMulaiValidasi');
    const beku = status === 'validasi';      // beku sampai scan wajah + Buat Tiket
    btn.textContent = status === 'selesai' ? 'Sudah Validasi' : 'Mulai Validasi Awal';
    btn.disabled = status !== 'draft';
    btn.classList.toggle('btn-primary', status !== 'selesai');
    btn.classList.toggle('btn-secondary', status === 'selesai');
    btn.classList.toggle('opacity-60', beku);
    btn.classList.toggle('cursor-not-allowed', beku);

    ['btnTambahSupir', 'btnUpdateSupir', 'btnScanWajah']
        .forEach(id => document.getElementById(id).disabled = status !== 'validasi');
    document.getElementById('btnCetakQR').classList.toggle('hidden', status !== 'selesai');
    perbaruiTombolSubmit();
}

function perbaruiTombolSubmit() {
    const adaSupir = !!document.getElementById('driverIdDriver').value;
    const siap = statusForm === 'validasi' && adaSupir && (supirTerverifikasi || !WAJIB_SCAN_WAJAH);
    document.getElementById('btnSubmitTiket').disabled = !siap;

    let hint = '';
    if (statusForm === 'selesai') hint = 'Tiket sudah dibuat. Gunakan tombol Cetak QR di atas.';
    else if (statusForm === 'validasi' && !adaSupir) hint = 'Silakan pilih supir: Mulai Scan Wajah, Tambah Supir (supir baru), atau Ubah Supir.';
    else if (statusForm === 'validasi' && !siap) hint = 'Silakan scan wajah supir. Tombol Buat Tiket aktif setelah supir terverifikasi.';
    else if (siap) hint = supirTerverifikasi ? 'Supir terverifikasi. Klik Buat Tiket untuk menyimpan tiket.'
                                            : 'Scan wajah tidak diwajibkan di site ini.';
    document.getElementById('hintSubmit').textContent = hint;
}

function setSupirTerverifikasi(ok) {
    supirTerverifikasi = ok;
    perbaruiTombolSubmit();
}

function resetValidasiForm() {
    saranDriver = null;
    ['driverIdDriver', 'driverIdTampil', 'driverNama', 'driverNik', 'driverSim']
        .forEach(id => document.getElementById(id).value = '');
    document.getElementById('driverStatusBadge').innerHTML = '';
    document.getElementById('fotoDriverBox').innerHTML = '<i class="fa-solid fa-user text-slate-300 text-5xl"></i>';
    document.getElementById('statusScanWajah').textContent = '';
    tandaiBorderDriver(null);
    kotakMerah(document.getElementById('fotoDriverBox'), false);
    document.getElementById('driverBadgeUpdate').classList.add('hidden');
    aturBlacklist('supir', null);
    supirTerverifikasi = false;
    aturStatusForm('draft');
}

function tandaiSudahValidasi() {
    supirTerverifikasi = true;
    aturStatusForm('selesai');
}

// ===== DO (Delivery Order, diisi HO di menu Kontrak & DO) =====
// Ada DO -> jenis transaksi, customer, produk terisi otomatis (tetap bisa diubah). Tidak ada -> isi sendiri.
let kontrakAktif = [];                 // kontrak truk (modal Update -> Kontrak Truk), hanya informasi
let doTerakhir = '';

function sinkronKontrakKeForm(listAktif) {
    kontrakAktif = listAktif;
}

function teksPilihan(id) {
    const sel = document.getElementById(id);
    return sel.value ? sel.options[sel.selectedIndex].text : '';
}

// Info bar mengikuti isian form (dari DO maupun diisi sendiri)
function sinkronInfoBarForm() {
    document.getElementById('infoNoDO').value = document.getElementById('formNoDo').value.trim().toUpperCase();
    document.getElementById('infoSupplier').value = teksPilihan('formSupplier');
    document.getElementById('infoProduk').value = teksPilihan('formProduk');
    const jenis = document.getElementById('formJenisTransaksi').value;
    document.getElementById('infoJenis').value = jenis ? labelKode(jenis) : '';
}
['formJenisTransaksi', 'formSupplier', 'formProduk']
    .forEach(id => document.getElementById(id).addEventListener('change', sinkronInfoBarForm));

function isiDariDO(d) {
    if (d) document.getElementById('formNoDo').value = d.no_do;
    document.getElementById('formJenisTransaksi').value = d ? d.jenis_transaksi : '';
    document.getElementById('formSupplier').value = d ? d.id_customer : '';
    document.getElementById('formProduk').value = d ? d.id_produk : '';
    sinkronInfoBarForm();
}

async function cariDO(noDo, diam = false) {
    noDo = (noDo || '').trim().toUpperCase();
    const info = document.getElementById('infoDO');
    if (!noDo) return;
    doTerakhir = noDo;
    const d = await ambilJson(`/api/do/${encodeURIComponent(noDo)}`);
    if (d.error) {                      // DO belum ada dari HO: isian yang sudah ada dibiarkan, diisi sendiri
        info.className = 'text-xs mt-1 text-amber-600';
        info.textContent = `No. DO ${noDo} belum terdaftar di HO atau tidak aktif. Silakan isi jenis transaksi, customer, dan produk secara manual.`;
        sinkronInfoBarForm();
        return;
    }
    if (!diam) isiDariDO(d);
    info.className = 'text-xs mt-1 text-emerald-600';
    info.textContent = `✓ DO dari HO (kontrak ${d.no_kontrak}): ${d.nama_customer} · ${d.nama_produk}` +
        (d.berlaku_sampai ? ` · berlaku s/d ${d.berlaku_sampai}` : '') + '. Masih bisa diubah.';
}

// Lupa menekan Tab: DO juga dicari saat kotak ditinggalkan
document.getElementById('formNoDo').addEventListener('blur', e => {
    const v = e.target.value.trim().toUpperCase();
    if (v && v !== doTerakhir && !e.target.disabled) cariDO(v);
    if (!v) document.getElementById('infoDO').classList.add('hidden');
});
document.getElementById('formNoDo').addEventListener('input', () => { doTerakhir = ''; sinkronInfoBarForm(); });

window.addEventListener('platLookup', (e) => {
    const d = e.detail;
    const inputPlatAscend = document.getElementById('ascendVehicleNo');
    if (inputPlatAscend && d.no_plat) {
        const nilaiInput = inputPlatAscend.value.replace(/\s+/g, '').toUpperCase();
        const nilaiHasil = d.no_plat.replace(/\s+/g, '').toUpperCase();

        if (nilaiInput === nilaiHasil) {
            inputPlatAscend.value = d.no_plat;
        }
    }
    if (!['ADA_TIKET', 'DRAFT'].includes(d.status)) return;

    document.getElementById('formNoPlat').value = d.no_plat;
    document.getElementById('formNoTiket').value = d.no_tiket || d.no_tiket_reserved || '';
    document.getElementById('formNoStnk').value = d.no_stnk || '';
    tampilkanPengemudiTerakhir(d.driver, d.driver_utama);
    // Peringatan blacklist selalu tampil, juga untuk plat yang sudah punya tiket (mis. diblacklist setelah tiket dibuat)
    aturBlacklist('kendaraan', d.kendaraan_blacklist ? { siapa: d.no_plat, info: d.kendaraan_blacklist } : null);

    if (d.status === 'ADA_TIKET') {
        document.getElementById('formNoDo').value = d.no_do || '';
        document.getElementById('formJenisTransaksi').value = d.jenis_transaksi;
        document.getElementById('formSupplier').value = d.id_supplier;
        document.getElementById('formProduk').value = d.id_produk;
        sinkronInfoBarForm();
        if (d.no_do) cariDO(d.no_do, true);             // keterangan DO saja, isian tiket tidak ditimpa
        if (d.driver) isiDriver(d.driver);
        tandaiSudahValidasi();
        document.getElementById('btnCetakQR').classList.remove('hidden');
    } else {
        resetValidasiForm();
        saranDriver = d.driver_utama || d.driver;   // supir utama (menu Update Truk) didahulukan
        kontrakAktif = d.kontrak_aktif || [];
        isiDariDO(null);
        document.getElementById('formNoDo').value = '';
        document.getElementById('infoDO').classList.add('hidden');
    }
    // Tiket yang sudah ada: supir tiket itu. Draft: supir terakhir / utama yang blacklist ikut diperingatkan
    aturBlacklistSupir(d.status === 'ADA_TIKET' ? (d.driver && d.driver.is_blacklisted ? d.driver : null)
        : [d.driver_utama, d.driver].find(x => x && x.is_blacklisted) || null);
});

// ===== VALIDASI AWAL (buka section Informasi Supir) =====
function mulaiValidasiAwal() {
    const wajib = ['formNoPlat', 'formNoTiket', 'formNoStnk', 'formJenisTransaksi', 'formSupplier', 'formProduk'];
    for (const id of wajib) {
        if (!document.getElementById(id).value.trim()) {
            Notif.peringatan('Lengkapi plat, No. STNK, jenis transaksi, customer, dan produk (isi No. DO lalu tekan Tab untuk mengisi otomatis).');
            return;
        }
    }
    supirTerverifikasi = false;
    aturStatusForm('validasi');
    if (saranDriver) {                          // saran supir (utama / terakhir), tetap wajib scan wajah
        isiDriver(saranDriver);
        tandaiBorderDriver('biru');
        document.getElementById('statusScanWajah').textContent = 'Saran supir truk ini. Lakukan scan wajah untuk verifikasi.';
    }
    perbaruiTombolSubmit();
}

// ===== SCAN WAJAH SUPIR (webcam browser di PC Security) =====
// Tantangan wajib / tidak diatur per area (Admin › Pengaturan Site › TANTANGAN_SECURITY).
let scanWajahBerjalan = false;

function selesaiScanWajah(pesan) {
    scanWajahBerjalan = false;
    Kamera.stop();
    document.getElementById('videoScanWajah').classList.add('hidden');
    document.getElementById('fotoDriverBox').classList.remove('hidden');
    document.getElementById('instruksiScanWajah').classList.add('hidden');
    document.getElementById('btnScanWajah').disabled = statusForm !== 'validasi';
    if (pesan) document.getElementById('statusScanWajah').textContent = pesan;
}

async function mulaiScanWajah() {
    if (scanWajahBerjalan) return;
    const status = document.getElementById('statusScanWajah');
    const video = document.getElementById('videoScanWajah');
    const instruksi = document.getElementById('instruksiScanWajah');
    scanWajahBerjalan = true;
    document.getElementById('btnScanWajah').disabled = true;
    status.textContent = 'Menyalakan kamera...';
    try {
        await Kamera.mulai(video);
    } catch (err) {
        selesaiScanWajah(window.isSecureContext
            ? 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.'
            : 'Kamera diblokir browser karena alamat bukan HTTPS / localhost (lihat Dokumentasi: kamera browser).');
        return;
    }
    document.getElementById('fotoDriverBox').classList.add('hidden');
    video.classList.remove('hidden');
    instruksi.classList.remove('hidden');
    status.textContent = 'Minta supir menghadap kamera.';

    const { security: wajib } = await aturanTantangan();
    const hasil = await rekamWajah(video, {
        wajib,
        tampil: (teks, angka) => { instruksi.textContent = angka ? `${teks} (${angka})` : teks; },
        batal: () => !scanWajahBerjalan || statusForm !== 'validasi',
    });
    if (!hasil) { selesaiScanWajah('Scan dibatalkan.'); return; }
    instruksi.textContent = 'Memproses...';
    const formData = new FormData();
    hasil.frames.forEach((blob, i) => formData.append('frames', blob, `frame${i}.jpg`));
    formData.append('tantangan', hasil.tantangan);
    hasil.frames.length = 0;
    selesaiScanWajah('Memproses wajah...');
    document.getElementById('btnScanWajah').disabled = true;

    const data = await kirimForm('/api/security/scan-wajah', formData, { timeout: TIMEOUT_WAJAH_MS });
    document.getElementById('btnScanWajah').disabled = statusForm !== 'validasi';
    if (data.error && !data.terverifikasi) {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(data.error)}</span>`;
        return;
    }
    terapkanHasilScanWajah(data);
}

function terapkanHasilScanWajah(data) {
    const status = document.getElementById('statusScanWajah');
    const nama = formatNamaPersonel(data.id_driver, data.nama);
    if (data.is_blacklisted) Notif.peringatan(`${nama} terdaftar dalam daftar blacklist`);   // banner diisi isiDriver()
    if (data.kategori && data.kategori !== 'DRIVER') {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(nama)} terdaftar sebagai ${escapeHtml((LABEL_KATEGORI[data.kategori] || [labelKode(data.kategori)])[0])}, bukan supir.</span>`;
        return;
    }
    const dipilih = document.getElementById('driverIdDriver').value;
    if (dipilih && String(dipilih) !== String(data.id_driver)) {
        status.innerHTML = `<span class="text-red-600">Wajah terbaca sebagai <b>${escapeHtml(nama)}</b>, tidak cocok dengan supir terpilih. Pilih supir yang benar lewat "Update", lalu scan ulang.</span>`;
        return;
    }
    isiDriver(data);
    tandaiBorderDriver('hijau');
    status.textContent = 'Terverifikasi: ' + nama;
    setSupirTerverifikasi(true);
}


// ===== REKAM WAJAH SEDERHANA (modal Tambah/Update) =====
const streamState = {};

async function toggleRekamWajah(konteks) {
    const btn = document.getElementById(`btnRekam${konteks === 'tambah' ? 'Tambah' : 'Update'}`);
    const video = document.getElementById(`${konteks}Video`);
    const canvas = document.getElementById(`${konteks}Canvas`);
    const preview = document.getElementById(`${konteks}FotoPreview`);

    // Status tombol disimpan di data-tahap, bukan dibaca dari tulisannya (tulisan bisa diterjemahkan browser)
    if (btn.dataset.tahap !== 'ambil') {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        streamState[konteks] = stream;
        video.srcObject = stream;
        video.classList.remove('hidden');
        preview.classList.add('hidden');
        btn.textContent = 'Ambil Foto';
        btn.dataset.tahap = 'ambil';
    } else {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(blob => {
            streamState[`${konteks}Blob`] = blob;
            const url = URL.createObjectURL(blob);
            preview.innerHTML = `<img src="${url}" class="w-full h-full object-cover rounded-full">`;
            preview.classList.remove('hidden');
        }, 'image/jpeg');

        streamState[konteks].getTracks().forEach(t => t.stop());
        video.classList.add('hidden');
        btn.textContent = 'Rekam Wajah';
        btn.dataset.tahap = 'rekam';
    }
}

// ===== SIMPAN SUPIR BARU =====
// Modal yang sama dipakai dari form tiket ('tiket') dan dari menu Update Truk ('kendaraan')
let konteksTambahSupir = 'tiket';

function bukaTambahSupir(konteks) {
    konteksTambahSupir = konteks;
    if (konteks === 'kendaraan') {
        if (!pastikanTrukDipilih()) return;
        tutupModalUpdate();                            // modal Tambah dibuka di atas, Update dibuka lagi setelah simpan
    }
    ['tambahNama', 'tambahNik', 'tambahSim'].forEach(id => document.getElementById(id).value = '');
    streamState['tambahBlob'] = null;
    document.getElementById('tambahFotoPreview').innerHTML = '<i class="fa-solid fa-camera text-slate-300 text-2xl"></i>';
    openModal('modalTambahSupir');
}

async function simpanSupirBaru(btn) {
    const formData = new FormData();
    formData.append('nama', document.getElementById('tambahNama').value.trim());
    formData.append('nik', document.getElementById('tambahNik').value.trim());
    formData.append('no_sim', document.getElementById('tambahSim').value.trim());
    if (streamState['tambahBlob']) {
        formData.append('foto', streamState['tambahBlob'], 'capture.jpg');
    }

    const data = await denganTombol(btn, () => kirimForm('/api/driver/tambah', formData, { timeout: TIMEOUT_WAJAH_MS }),
                                    'Memeriksa wajah...');
    if (tampilkanHasil(data)) {
        closeModal('modalTambahSupir');
        if (konteksTambahSupir === 'kendaraan') {      // dari modal Update -> tab Supir Truk
            await daftarkanSupirKeTruk(data.id_driver);
            openModal('modalUpdateData');
            setModeUpdate('truk');
            return;
        }
        isiDriver({ id_driver: data.id_driver, nik: document.getElementById('tambahNik').value.trim(),
                    nama: document.getElementById('tambahNama').value.trim(),
                    no_sim: document.getElementById('tambahSim').value.trim(),
                    is_updated: false, foto_path: data.foto_path });
        tandaiBorderDriver('hijau');                   // wajah baru saja direkam -> terverifikasi
        document.getElementById('statusScanWajah').textContent = 'Supir baru terdaftar & terverifikasi: ' + data.message;
        setSupirTerverifikasi(true);
    }
}

// ===== MODAL UPDATE =====
function bukaModalUpdate() {
    document.getElementById('cariNik').value = '';
    document.getElementById('hasilCariNik').classList.add('hidden');
    document.getElementById('tidakDitemukan').classList.add('hidden');
    document.getElementById('btnPakaiSupirIni').disabled = true;
    driverHasilCari = null;

    const id = document.getElementById('driverIdDriver').value;
    document.getElementById('updateNama').value = document.getElementById('driverNama').value;
    document.getElementById('updateNik').value = document.getElementById('driverNik').value;
    document.getElementById('updateSim').value = document.getElementById('driverSim').value;
    document.getElementById('editTanpaDriver').classList.toggle('hidden', !!id);
    document.getElementById('btnSimpanEdit').disabled = !id;
    resetFotoUpdate();

    setModeUpdate('cari');
    document.getElementById('updJudulPlat').textContent = '';
    muatDataKendaraan(document.getElementById('formNoPlat').value);   // untuk tab Supir Truk & Kontrak Truk
    openModal('modalUpdateData');
}

const MODE_UPDATE = { cari: 'Cari', edit: 'Ubah', truk: 'Truk', kontrak: 'Kontrak' };

function setModeUpdate(mode) {
    Object.entries(MODE_UPDATE).forEach(([m, nama]) => {
        document.getElementById(`tabMode${nama}`).className = 'modal-tab ' + (m === mode ? 'modal-tab-active' : '');
        document.getElementById(`panelMode${nama}`).classList.toggle('hidden', m !== mode);
    });
}

function resetFotoUpdate() {
    if (streamState['update']) {
        streamState['update'].getTracks().forEach(t => t.stop());
        streamState['update'] = null;
    }
    streamState['updateBlob'] = null;
    document.getElementById('updateVideo').classList.add('hidden');
    const preview = document.getElementById('updateFotoPreview');
    preview.classList.remove('hidden');
    preview.innerHTML = '<i class="fa-solid fa-camera text-slate-300 text-2xl"></i>';
    document.getElementById('btnRekamUpdate').textContent = 'Rekam Wajah';
    document.getElementById('btnRekamUpdate').dataset.tahap = 'rekam';
}

function tutupModalUpdate() {
    resetFotoUpdate();
    closeModal('modalUpdateData');
}

// --- mode Ganti Supir ---
let driverHasilCari = null;

async function cariSupirByNik(inputEl) {
    const nik = inputEl.value.trim();
    if (!nik) return;
    const data = await kirimForm('/api/driver/cari-by-nik', { nik });
    if (data.error) { Notif.gagal(data.error); return; }

    if (data.status === 'DITEMUKAN') {
        driverHasilCari = data;             // id_driver, nik, nama, no_sim, is_blacklisted, ...
        document.getElementById('hasilNama').textContent = formatNamaPersonel(data.id_driver, data.nama);
        document.getElementById('hasilNik').textContent = data.nik;
        document.getElementById('hasilSim').textContent = data.no_sim;
        document.getElementById('hasilBadgeUpdate').classList.toggle('hidden', !data.is_updated);
        document.getElementById('hasilCariNik').classList.remove('hidden');
        document.getElementById('tidakDitemukan').classList.add('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = false;
    } else {
        driverHasilCari = null;
        document.getElementById('hasilCariNik').classList.add('hidden');
        document.getElementById('tidakDitemukan').classList.remove('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = true;
    }
}

function pakaiSupirIni() {
    if (driverHasilCari) gantiSupirTiket(driverHasilCari);
}

// Ganti supir untuk tiket ini (dari Cari NIK atau daftar Supir Truk). Wajib scan wajah ulang.
function gantiSupirTiket(dr) {
    isiDriver(dr);
    tandaiBorderDriver('biru');      // biru = supir dipilih manual, belum terverifikasi wajah
    document.getElementById('statusScanWajah').textContent = 'Supir diganti. Lakukan scan wajah untuk verifikasi.';
    setSupirTerverifikasi(false);
    tutupModalUpdate();
}

// --- mode Edit Data Diri / SIM ---
async function simpanEditIdentitas(btn) {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) return;

    const nama = document.getElementById('updateNama').value.trim();
    const nik = document.getElementById('updateNik').value.trim();
    const sim = document.getElementById('updateSim').value.trim();
    if (!nama || !nik || !sim) { Notif.peringatan('Nama, NIK, dan SIM wajib diisi'); return; }

    const berubah = nama !== document.getElementById('driverNama').value
        || nik !== document.getElementById('driverNik').value
        || sim !== document.getElementById('driverSim').value
        || streamState['updateBlob'];
    if (!berubah) { Notif.info('Tidak ada perubahan yang perlu disimpan'); return; }
    const ok = await Dialog.konfirmasi({ judul: 'Simpan perubahan identitas?', teksYa: 'Simpan',
        pesan: 'Perubahan identitas supir tercatat permanen di Log Audit dan supir ditandai "Pernah Diperbarui".' });
    if (!ok) return;

    const formData = new FormData();
    formData.append('id_driver', idDriver);
    formData.append('nama', nama);
    formData.append('nik', nik);
    formData.append('no_sim', sim);
    if (streamState['updateBlob']) formData.append('foto', streamState['updateBlob'], 'capture.jpg');

    const data = await denganTombol(btn, () => kirimForm('/api/driver/update-identitas', formData, { timeout: TIMEOUT_WAJAH_MS }));
    if (!data.driver) { Notif.gagal(data.error || 'Gagal menyimpan perubahan'); return; }

    Notif.sukses(data.message);
    isiDriver(data.driver);
    perbaruiTombolSubmit();
    document.getElementById('infoSupir').value = data.driver.nama;
    tampilkanFotoDriver(data.driver.foto_path);
    tampilkanPengemudiTerakhir(data.driver);
    tutupModalUpdate();
}

// ===== SUBMIT CREATE TICKET =====
async function submitCreateTiket(btn) {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) { Notif.peringatan('Silakan scan wajah atau pilih supir terlebih dahulu'); return; }
    const kenaBlacklist = ['kendaraan', 'supir'].filter(j => blacklistForm[j]).map(j => blacklistForm[j].siapa);
    if (kenaBlacklist.length && !await Dialog.konfirmasi({
        judul: 'Masuk daftar blacklist', teksYa: 'Tetap buat tiket', teksBatal: 'Batal', bahaya: true,
        pesan: `${kenaBlacklist.join(' dan ')} masuk daftar blacklist. Tetap buat tiket? Tercatat di Log Audit.` })) return;

    const formData = new FormData();
    ['no_tiket:formNoTiket', 'no_plat:formNoPlat', 'no_stnk:formNoStnk', 'no_do:formNoDo',
     'jenis_transaksi:formJenisTransaksi', 'id_supplier:formSupplier', 'id_produk:formProduk']
        .forEach(p => { const [k, id] = p.split(':'); formData.append(k, document.getElementById(id).value.trim()); });
    formData.append('id_driver', idDriver);
    if (saranDriver) formData.append('id_driver_saran', saranDriver.id_driver);   // beda supir -> OVERRIDE_DRIVER

    const data = await denganTombol(btn, () => kirimForm('/api/security/buat-tiket', formData), 'Membuat tiket...');
    perbaruiTombolSubmit();                  // kembalikan status aktif/nonaktif tombol Submit
    if (!data.no_tiket) { Notif.gagal(data.error || 'Tiket gagal dibuat'); return; }

    Notif.sukses(data.message);
    lookupPlat(document.getElementById('formNoPlat').value);  // base bar jadi ADA_TIKET lengkap
    const cetak = await Dialog.konfirmasi({ judul: 'Tiket berhasil dibuat', teksYa: 'Cetak QR', teksBatal: 'Nanti',
        pesan: `No. tiket ${data.no_tiket}. Cetak QR tiket sekarang?` });
    if (cetak) bukaHalamanCetak(data.no_tiket);
}

// ===== TAMPILAN DRIVER (Section 2) =====
function tandaiBorderDriver(warna) {   // 'biru' | 'hijau' | null
    const box = document.getElementById('fotoDriverBox');
    box.classList.remove('border-blue-500', 'border-emerald-500', 'border-slate-300', 'border-dashed', 'border-solid');
    if (warna === 'biru') box.classList.add('border-blue-500', 'border-solid');
    else if (warna === 'hijau') box.classList.add('border-emerald-500', 'border-solid');
    else box.classList.add('border-slate-300', 'border-dashed');
}

function isiDriver(dr) {
    document.getElementById('driverIdDriver').value = dr.id_driver;
    document.getElementById('driverIdTampil').value = formatIdPersonel(dr.id_driver);
    document.getElementById('driverStatusBadge').innerHTML = badgeStatusPersonel(dr.is_blacklisted);
    document.getElementById('driverNama').value = dr.nama;
    document.getElementById('driverNik').value = dr.nik;
    document.getElementById('driverSim').value = dr.no_sim;
    document.getElementById('fotoDriverBox').innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
    document.getElementById('driverBadgeUpdate').classList.toggle('hidden', !dr.is_updated);
    kotakMerah(document.getElementById('fotoDriverBox'), !!dr.is_blacklisted);
    aturBlacklistSupir(dr);
    tandaiPengemudiCocok(dr);
}

// Ringkasan perbandingan: supir sekarang sama (hijau) atau berbeda (kuning) dari supir terakhir truk ini.
// Hanya keterangan; data supir utama truk tetap diubah lewat Ubah Supir.
function tandaiPengemudiCocok(dr) {
    const el = document.getElementById('pengemudiCocok');
    const ada = dr && pengemudiTerakhir;
    el.classList.toggle('hidden', !ada);
    if (!ada) return;
    const sama = String(dr.id_driver) === String(pengemudiTerakhir.id_driver);
    el.className = `mt-2 text-xs font-semibold px-2 py-1 rounded-md ${sama ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`;
    el.innerHTML = sama ? '<i class="fa-solid fa-circle-check mr-1"></i>Sama dengan supir terakhir truk ini'
        : `<i class="fa-solid fa-triangle-exclamation mr-1"></i>Supir berbeda: ${escapeHtml(pengemudiTerakhir.nama)} → ${escapeHtml(dr.nama)}`;
}

// ===== CETAK QR =====
// Tombol Cetak QR di Form (setelah tiket dibuat)
function cetakQRDariForm() {
    openCetakQRDariTabel(document.getElementById('formNoPlat').value);
}

function openCetakQRDariTabel(noPlat) {
    document.getElementById('qrNoPlat').value = noPlat;
    lookupPlatUntukQR(document.getElementById('qrNoPlat'));
    openModal('modalCetakQR');
}

async function lookupPlatUntukQR(inputEl) {
    const noPlat = inputEl.value.trim().toUpperCase();
    const data = await kirimForm('/api/plat/lookup', { no_plat: noPlat });
    if (data.error) { Notif.gagal(data.error); return; }
    if (data.status === 'ADA_TIKET') {
        inputEl.value = data.no_plat;
        document.getElementById('qrNama').textContent = data.driver.nama;
        document.getElementById('qrNik').textContent = data.driver.nik;
        document.getElementById('qrSim').textContent = data.driver.no_sim;
        document.getElementById('qrStnk').textContent = data.no_stnk || '-';
        document.getElementById('qrStatus').textContent = labelStatusTiket(data.status_alur);

        document.getElementById('printAreaQR').classList.remove('hidden');
        document.getElementById('qrTiketText').textContent = data.no_tiket;
        // QR dibuat di server (tidak butuh internet / CDN)
        document.getElementById('qrcodeContainer').innerHTML =
            `<img src="/api/qr/${encodeURIComponent(data.no_tiket)}" alt="QR ${escapeHtml(data.no_tiket)}" width="150" height="150">`;
        qrTiketAktif = data.no_tiket;
    } else {
        qrTiketAktif = null;
        document.getElementById('printAreaQR').classList.add('hidden');
        Notif.peringatan('Plat tidak ditemukan / belum ada tiket aktif');
    }
}

let qrTiketAktif = null;

function bukaHalamanCetak(noTiket) {
    const w = window.open(`/cetak/tiket/${encodeURIComponent(noTiket)}`, '_blank', 'width=420,height=720');
    if (!w) Notif.peringatan('Pop-up diblokir browser. Izinkan pop-up untuk alamat ini, lalu klik Cetak QR lagi.');
}

function cetakQR() {
    if (!qrTiketAktif) { Notif.peringatan('Silakan masukkan plat, lalu tekan Tab'); return; }
    bukaHalamanCetak(qrTiketAktif);
}

// ===== FORM TIKET KOSONG ASCEND =====
let daftarDOAscend = [];
let daftarShipperAscend = [];

const MILL_MANUAL_ASCEND = {
    produk: {
        cpo: 1034,
        janjangkosong: 1034,
        pfad: 1034,
        'r.pome': 1034,
        'rbd palm stearin': 1034,
        'spent bleaching earth (sbe)': 1034,
    },
    tbsluar: {
        pfad: 1034,
        'r.pome': 1034,
        uco: 1034,
    },
};

function terapkanMillManualAscend() {
    const jenis = document.getElementById('ascendTicketType').value.toLowerCase();
    const produk = document.getElementById('ascendProduk').value.trim().toLowerCase();
    const mill = document.getElementById('ascendMill');

    if (!jenis || !produk) {
        mill.disabled = false;
        return;
    }

    let millId = 250; // PKS sebagai tujuan bawaan
    if (produk === 'kernel') {
        millId = 1035;
    } else if (MILL_MANUAL_ASCEND[jenis]?.[produk]) {
        millId = MILL_MANUAL_ASCEND[jenis][produk];
    }

    mill.value = String(millId);
    mill.disabled = true;
}

async function muatShipperKendaraan(doData = null) {
    const jenis = document.getElementById('ascendTicketType').value;
    const shipper = document.getElementById('ascendShipper');
    const kendaraan = document.getElementById('ascendVehicleNo');

    daftarShipperAscend = [];
    isiPilihanAscend(shipper, [], x => x.shipper_id, x => x.shipper_name);
    isiPilihanAscend(kendaraan, [], x => x.vehicle_no, x => x.vehicle_no);

    if (!jenis) return;

    const params = new URLSearchParams({ ticket_type: jenis });
    if (doData && doData.id_do) {
        params.set('id_do', doData.id_do);
    }

    const data = await ambilJson(
        `/api/security/ascend/shipper-kendaraan?${params.toString()}`
    );

    if (data.error) {
        document.getElementById('ascendInfoDO').textContent = data.error;
        return;
    }

    daftarShipperAscend = data;
    isiPilihanAscend(
        shipper,
        daftarShipperAscend,
        x => x.shipper_id,
        x => x.shipper_name
    );
}

function pilihShipperAscend() {
    const shipperId = document.getElementById('ascendShipper').value;
    const shipper = daftarShipperAscend.find(
        x => String(x.shipper_id) === shipperId
    );

    isiPilihanAscend(
        document.getElementById('ascendVehicleNo'),
        shipper ? shipper.vehicles : [],
        x => x.vehicle_no,
        x => x.driver_name
            ? `${x.vehicle_no} · ${x.driver_name}`
            : x.vehicle_no
    );
}

function tanggalLokalHariIni() {
    const sekarang = new Date();
    const tahun = sekarang.getFullYear();
    const bulan = String(sekarang.getMonth() + 1).padStart(2, '0');
    const hari = String(sekarang.getDate()).padStart(2, '0');
    return `${tahun}-${bulan}-${hari}`;
}

function isiPilihanAscend(select, daftar, nilai, label) {
    const pilihanAwal = select.querySelector('option[value=""]');
    select.replaceChildren(pilihanAwal || new Option('-- Pilih --', ''));

    daftar.forEach(item => {
        select.add(new Option(label(item), String(nilai(item))));
    });

    select.value = '';
}
 
async function muatDOAscend() {
    const jenis = document.getElementById('ascendTicketType').value;
    document.getElementById('ascendShipper').required = jenis === 'Produk';
    const info = document.getElementById('ascendInfoDO');
    const pilihanDO = document.getElementById('ascendNoDoChoice');
    const manualWrap = document.getElementById('ascendNoDoManualWrap');
    const manualInput = document.getElementById('ascendNoDoManual');
    const noDO = document.getElementById('ascendNoDoValue');
    const associate = document.getElementById('ascendAssociate');
    const produk = document.getElementById('ascendProduk');

    daftarDOAscend = [];
    pilihanDO.replaceChildren(new Option('-- Pilih --', ''));
    document.getElementById('ascendNoDoManualToggle').checked = false;
    document.getElementById('ascendNoDoSelectWrap').classList.remove('hidden');
    pilihanDO.required = true;
    manualWrap.classList.add('hidden');
    manualInput.required = false;
    manualInput.value = '';
    noDO.value = '';

    isiPilihanAscend(associate, [], x => x.id, x => x.nama);
    isiPilihanAscend(produk, [], x => x.id, x => x.nama);
    if (jenis === 'TBSLuar') {
        isiPilihanAscend(
            produk,
            [{ id: 'TBS', nama: 'TBS' }],
            x => x.id,
            x => x.nama
        );
    }

    document.getElementById('ascendMill').value = '';
    document.getElementById('ascendMill').disabled = false; 

    if (!jenis) {
        info.textContent = 'Pilih jenis tiket untuk mencari DO outstanding.';
        return;
    }


    info.textContent = 'Memuat DO outstanding dari Ascend...';
    const data = await ambilJson(
        `/api/security/ascend/do?ticket_type=${encodeURIComponent(jenis)}`
    );

    if (data.error) {
        info.textContent = data.error;
        return;
    }

    daftarDOAscend = data;

    const dataAssociate = await ambilJson(
        `/api/security/ascend/associate?ticket_type=${encodeURIComponent(jenis)}`
    );

    if (dataAssociate.error) {
        info.textContent = dataAssociate.error;
        return;
    }

    const formatAssociate = a =>
        `${a.associate_code || "-"}: ${a.associate_name}`;

    const daftarAssociate = dataAssociate.map(a => ({
        id: a.associate_id,
        nama: formatAssociate(a),
    }));

    const labelAssociateById = new Map(
        dataAssociate.map(a => [
            String(a.associate_id),
            formatAssociate(a),
        ])
    );

    data.forEach(d => {
        const labelAssociate =
            labelAssociateById.get(String(d.associate_id)) || d.associate_name || "";

        pilihanDO.add(new Option(
            `${d.no_do} · ${labelAssociate} · ${d.produk}`,
            d.no_do
        ));
    });

    const namaProduk = new Set(data.map(d => d.produk));

    if (jenis === 'TBSLuar') {
        namaProduk.add('TBS');
    }

    const daftarProduk = [...namaProduk]
        .map(nama => ({ id: nama, nama }));

    isiPilihanAscend(
        associate, daftarAssociate, x => x.id, x => x.nama
    );
    isiPilihanAscend(
        produk, daftarProduk, x => x.id, x => x.nama
    );

    info.textContent = data.length
        ? `${data.length} DO outstanding tersedia. Cari dengan mengetik pada daftar, atau pilih input manual.`
        : 'Tidak ada DO outstanding. Kamu masih bisa mengetik nomor secara manual.';
}

function pilihInfoDOAscend() {
    const pilihan = document.getElementById('ascendNoDoChoice');
    const manualWrap = document.getElementById('ascendNoDoManualWrap');
    const manualInput = document.getElementById('ascendNoDoManual');
    const noDO = document.getElementById('ascendNoDoValue');
    const info = document.getElementById('ascendInfoDO');

    if (document.getElementById('ascendNoDoManualToggle').checked) {
        manualWrap.classList.remove('hidden');
        manualInput.required = true;
        manualInput.focus();
        noDO.value = manualInput.value.trim().toUpperCase();
        info.textContent = 'Ketik Nomor DO / SP. Associate dan Produk tetap harus dipilih dari Ascend.';
        document.getElementById('ascendAssociate').disabled = false;
        document.getElementById('ascendProduk').disabled = false;
        document.getElementById('ascendMill').disabled = false;
        terapkanMillManualAscend();
        muatShipperKendaraan();
        return;
    }

    manualWrap.classList.add('hidden');
    manualInput.required = false;

    const d = daftarDOAscend.find(x => x.no_do === pilihan.value);
    if (!d) {
        noDO.value = '';
        document.getElementById('ascendAssociate').disabled = false;
        document.getElementById('ascendProduk').disabled = false;
        document.getElementById('ascendMill').disabled = false;
        terapkanMillManualAscend();
        return;
    }

    noDO.value = d.no_do;
    document.getElementById('ascendAssociate').value = String(d.associate_id);
    document.getElementById('ascendProduk').value = d.produk;
    muatShipperKendaraan(d);
    document.getElementById('ascendMill').value =   
        d.mill_id == null ? '' : String(d.mill_id);

    document.getElementById('ascendAssociate').disabled = true;
    document.getElementById('ascendProduk').disabled = true;
    document.getElementById('ascendMill').disabled = true;

    const labelAssociate = d.associate_name
        ? `${d.associate_name} · ID ${d.associate_id}`
        : `ID ${d.associate_id}`;

    info.textContent = `DO ditemukan · ${labelAssociate} · ${d.produk}`;
}

function filterDOUntukAssociate() {
    const associate = document.getElementById('ascendAssociate');
    const pilihanDO = document.getElementById('ascendNoDoChoice');

    Array.from(pilihanDO.options).forEach(option => {
        if (!option.value) {
            option.hidden = false;
            return;
        }

        const doData = daftarDOAscend.find(d => d.no_do === option.value);

        option.hidden = Boolean(
            associate.value &&
            doData &&
            String(doData.associate_id) !== associate.value
        );
    });

    const doTerpilih = daftarDOAscend.find(
        d => d.no_do === pilihanDO.value
    );

    if (
        associate.value &&
        doTerpilih &&
        String(doTerpilih.associate_id) !== associate.value
    ) {
        pilihanDO.value = '';
        document.getElementById('ascendNoDoValue').value = '';
    }
}

const formTiketAscend = document.getElementById('formTiketAscend');
if (formTiketAscend) {
    const inputTanggal = document.getElementById('ascendTanggal');
    const hariIni = tanggalLokalHariIni();

    const tanggalBesok = new Date();
    tanggalBesok.setDate(tanggalBesok.getDate() + 1);
    const besok = [
        tanggalBesok.getFullYear(),
        String(tanggalBesok.getMonth() + 1).padStart(2, '0'),
        String(tanggalBesok.getDate()).padStart(2, '0'),
    ].join('-');

    inputTanggal.min = hariIni;
    inputTanggal.max = besok;
    inputTanggal.value = hariIni;

    document.getElementById('ascendShipper')
        .addEventListener('change', pilihShipperAscend);

    document.getElementById('ascendVehicleNo')
        .addEventListener('change', muatSupirTerakhirAscend);
    
    document.getElementById('ascendVehicleManualToggle')
        .addEventListener('change', e => {
            const manual = e.target.checked;
            const pilihan = document.getElementById('ascendVehicleNo');
            const input = document.getElementById('ascendVehicleManual');

            document.getElementById('ascendVehicleSelectWrap')
                .classList.toggle('hidden', manual);
            document.getElementById('ascendVehicleManualWrap')
                .classList.toggle('hidden', !manual);

            pilihan.disabled = manual;
            pilihan.required = !manual;
            input.disabled = !manual;
            input.required = manual;

            muatSupirTerakhirAscend();
        });

    document.getElementById('ascendVehicleManual')
        .addEventListener('blur', e => {
            e.target.value = e.target.value.trim().toUpperCase();
            muatSupirTerakhirAscend();
        });

    document.getElementById('ascendTicketType')
        .addEventListener('change', muatDOAscend);

    document.getElementById('ascendNoDoChoice')
        .addEventListener('change', pilihInfoDOAscend);
    
    document.getElementById('ascendNoDoManualToggle')
        .addEventListener('change', e => {
            const manual = e.target.checked;
            const pilihan = document.getElementById('ascendNoDoChoice');
            const manualWrap = document.getElementById('ascendNoDoManualWrap');

            document.getElementById('ascendNoDoSelectWrap')
                .classList.toggle('hidden', manual);

            pilihan.value = '';
            pilihan.required = !manual;
            document.getElementById('ascendNoDoManual').required = manual;
            pilihan.dispatchEvent(new Event('change'));
        });

    document.getElementById('ascendProduk')
        .addEventListener('change', terapkanMillManualAscend);

    document.getElementById('ascendNoDoManual')
        .addEventListener('input', e => {
            document.getElementById('ascendNoDoValue').value =
                e.target.value.trim().toUpperCase();
        });

    document.getElementById('ascendAssociate')
        .addEventListener('change', filterDOUntukAssociate);

    formTiketAscend.addEventListener('submit', async e => {
        e.preventDefault();

        const tombol = document.getElementById('btnBuatTiketAscend');
        const hasil = document.getElementById('hasilTiketAscend');
        tombol.disabled = true;
        hasil.textContent = 'Membuat tiket di Ascend...';

        const payload = new FormData(formTiketAscend);
        payload.set('associate_id', document.getElementById('ascendAssociate').value);
        payload.set('produk', document.getElementById('ascendProduk').value);
        payload.set('mill_id', document.getElementById('ascendMill').value);

        const data = await kirimForm(
            '/api/security/ascend/buat-tiket',
            payload
        );

        tombol.disabled = false;

        if (data.error) {
            hasil.className = 'text-sm font-semibold text-red-600';
            hasil.textContent = data.error;
            return;
        }

        const noTiketBerhasil = data.no_tiket;
        formTiketAscend.reset();

        document.getElementById('ascendNoDoSelectWrap').classList.remove('hidden');
        document.getElementById('ascendNoDoManualWrap').classList.add('hidden');
        document.getElementById('ascendNoDoValue').value = '';
        document.getElementById('ascendNoDoChoice').required = true;
        document.getElementById('ascendNoDoManual').required = false;

        document.getElementById('ascendVehicleSelectWrap').classList.remove('hidden');
        document.getElementById('ascendVehicleManualWrap').classList.add('hidden');
        document.getElementById('ascendVehicleNo').disabled = false;
        document.getElementById('ascendVehicleNo').required = true;
        document.getElementById('ascendVehicleManual').disabled = true;
        document.getElementById('ascendVehicleManual').required = false;

        document.getElementById('ascendAssociate').disabled = false;
        document.getElementById('ascendProduk').disabled = false;
        document.getElementById('ascendMill').disabled = false;
        document.getElementById('ascendTanggal').value = tanggalLokalHariIni();

        await muatDOAscend();
        await muatShipperKendaraan();

        hasil.className = 'text-sm font-semibold text-emerald-700';
        hasil.textContent = `Tiket berhasil dibuat: ${noTiketBerhasil}`;
            });
}

async function muatSupirTerakhirAscend() {
    const manual = document.getElementById('ascendVehicleManualToggle').checked;
    const plat = (
        manual
            ? document.getElementById('ascendVehicleManual').value
            : document.getElementById('ascendVehicleNo').value
    ).trim().toUpperCase();
    const hasil = document.getElementById('ascendSupirTerakhir');

    if (!plat) {
        hasil.textContent = 'Isi nomor kendaraan untuk melihat riwayat supir.';
        return;
    }

    hasil.textContent = 'Mencari riwayat supir...';
    const data = await ambilJson(
        `/api/security/supir-terakhir?no_plat=${encodeURIComponent(plat)}`
    );

    if (data.error) {
        hasil.textContent = data.error;
        return;
    }

    if (!data.driver) {
        hasil.textContent = 'Belum ada riwayat supir untuk kendaraan ini.';
        return;
    }

    const d = data.driver;
    const foto = document.getElementById('ascendSupirFoto');

    foto.innerHTML = d.foto_path
        ? `<img src="${escapeHtml(urlBerkas(d.foto_path))}"
                class="w-full h-full object-cover rounded-lg" alt="">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
    hasil.innerHTML =
        `<b>${escapeHtml(d.nama)}</b>` +
        `<span class="text-slate-500"> · NIK ${escapeHtml(d.nik || '-')} · SIM ${escapeHtml(d.no_sim || '-')}</span>`;
}
