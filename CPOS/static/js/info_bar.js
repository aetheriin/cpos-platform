// ===== INFO BAR (kontainer atas halaman site) =====
let statusValidasi = 'none'; // none | draft | done
const ICON_USER = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';

// Tab Security: info bar hanya No. Tiket + Bruto / Tara / Netto. Tab lain: info bar lengkap.
// Yang disembunyikan tetap ada di halaman (security.js dan lookup masih mengisinya), hanya tidak terlihat.
function aturInfoBarPerTab() {
    const security = getTabAktif() === 'security';
    document.querySelectorAll('[data-info="umum"]').forEach(el => el.classList.toggle('hidden', security));
    document.querySelectorAll('[data-info="security"]').forEach(el => el.classList.toggle('hidden', !security));
}

window.addEventListener('tabChange', aturInfoBarPerTab);

// Bruto / Tara / Netto tiket untuk info bar Security (sumber sama dengan tab Timbangan); tanpa tiket atau belum ditimbang = '-'
let noTiketBerat = null;
async function isiBeratInfoBar(noTiket) {
    noTiketBerat = noTiket;
    ['infoBruto', 'infoTara', 'infoNetto'].forEach(id => document.getElementById(id).value = '-');
    if (!noTiket) return;
    const tb = await ambilJson(`/api/timbang/data/${encodeURIComponent(noTiket)}`);
    if (tb.error || noTiketBerat !== noTiket) return;          // jawaban lama: plat sudah ganti
    const kg = v => v == null ? '-' : Number(v).toLocaleString('id-ID');
    document.getElementById('infoBruto').value = kg(tb.berat_bruto);
    document.getElementById('infoTara').value = kg(tb.berat_tara);
    document.getElementById('infoNetto').value = kg(tb.berat_netto);
}

// ===== INPUT PLAT =====
const POLA_PLAT = /^[A-Z]{1,2}[\s.\-]*[1-9][0-9]{0,3}[\s.\-]*[A-Z]{0,3}$/;
let platTerakhirDicari = '';

function platPerluDicari(input) {
    const val = input.value.trim().toUpperCase();
    if (!val || val === platTerakhirDicari) return false;
    return val.startsWith('TKT-') || POLA_PLAT.test(val);
}

function cariPlatOtomatis(e) {
    const input = e.target;
    // mouseleave saat kotak tidak sedang diketik (tidak fokus) diabaikan
    if (e.type === 'mouseleave' && document.activeElement !== input) return;
    if (platPerluDicari(input)) lookupPlat(input.value);
}

document.querySelectorAll('[data-plat-otomatis]').forEach(input => {
    input.addEventListener('mouseleave', cariPlatOtomatis);
    input.addEventListener('blur', cariPlatOtomatis);
    input.addEventListener('input', () => { platTerakhirDicari = ''; });   // diketik ulang -> boleh dicari lagi
});

// No. Tiket (hasil scanner barcode / QR) -> cari tiket aktif
async function lookupTiket(noTiket) {
    const data = await kirimForm('/api/timbang/scan-qr', { no_tiket: noTiket });
    if (data.status === 'ADA_TIKET') terapkanHasilLookup(data);
    else Notif.gagal(data.error || 'Tiket tidak ditemukan');
}

async function lookupPlat(noPlatRaw) {
    const noPlat = (noPlatRaw || '').trim().toUpperCase();
    if (!noPlat) return;
    platTerakhirDicari = noPlat;
    // Scanner barcode yang diarahkan ke kolom plat akan mengetik No. Tiket
    if (noPlat.startsWith('TKT-')) { await lookupTiket(noPlat); return; }

    const data = await kirimForm('/api/plat/lookup', { no_plat: noPlat });
    if (data.error) { Notif.gagal(data.error); return; }

    data.no_plat = data.no_plat || noPlat;   // server mengembalikan format baku, mis. 'BM 1455 JJ'
    platTerakhirDicari = data.no_plat;
    terapkanHasilLookup(data);
}

function terapkanHasilLookup(data) {
    const tab = getTabAktif();

    // Tiket hanya boleh dibuat di Security
    if (data.status === 'DRAFT' && tab !== 'security') {
        kosongkanInfoBar();
        document.getElementById('infoPlat').value = data.no_plat;
        Notif.peringatan('Plat ini belum memiliki tiket aktif. Silakan daftarkan melalui tab Security.');
        window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
        return;
    }

    document.getElementById('infoPlat').value = data.no_plat;

    if (data.status === 'ADA_TIKET') {
        document.getElementById('infoNoTiket').value = data.no_tiket || '';
        document.getElementById('infoNoDO').value = data.no_do || '';
        document.getElementById('infoSupplier').value = data.supplier || '';
        document.getElementById('infoProduk').value = data.produk || '';
        document.getElementById('infoJenis').value = labelKode(data.jenis_transaksi);
        statusValidasi = 'done';
    } else {
        document.getElementById('infoNoTiket').value = data.no_tiket_reserved || '';
        document.getElementById('infoNoDO').value = '';
        ['infoSupplier', 'infoProduk', 'infoJenis'].forEach(id => document.getElementById(id).value = '');
        statusValidasi = 'draft';
    }
    document.getElementById('infoSupir').value = data.driver
        ? formatNamaPersonel(data.driver.id_driver, data.driver.nama) : '';
    // Blacklist ditandai merah + label di info bar (terlihat di semua tab); detail & banner ada di tab Security
    const supirBlacklist = !!(data.driver && data.driver.is_blacklisted);
    document.getElementById('infoPlat').classList.toggle('border-red-500', !!data.kendaraan_blacklist);
    document.getElementById('infoSupir').classList.toggle('border-red-500', supirBlacklist);
    tandaiBlacklistInfoBar([data.kendaraan_blacklist && 'Kendaraan', supirBlacklist && 'Supir'].filter(Boolean));
    tampilkanFotoDriver(data.driver ? data.driver.foto_path : null);
    isiBeratInfoBar(data.status === 'ADA_TIKET' ? data.no_tiket : null);

    window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
}

function kosongkanInfoBar() {
    ['infoNoTiket', 'infoNoDO', 'infoSupplier', 'infoProduk', 'infoJenis', 'infoSupir'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('infoPlat').classList.remove('border-red-500');
    document.getElementById('infoSupir').classList.remove('border-red-500');
    tandaiBlacklistInfoBar([]);
    tampilkanFotoDriver(null);
    statusValidasi = 'none';
    isiBeratInfoBar(null);
}

function tandaiBlacklistInfoBar(siapa) {
    const label = document.getElementById('infoBlacklist');
    label.classList.toggle('hidden', !siapa.length);
    label.textContent = siapa.length ? `BLACKLIST: ${siapa.join(' & ')}` : '';
    label.title = siapa.length ? 'Masuk daftar blacklist. Detail tersedia di tab Security.' : '';
}

function tampilkanFotoDriver(path) {
    const box = document.getElementById('infoFotoBox');
    box.innerHTML = path
        ? `<img src="${escapeHtml(urlBerkas(path))}" class="w-full h-full object-cover" alt="">`
        : ICON_USER;
}

// ===== 3 JALUR MENUJU CREATE FORM =====

// Dari halaman List (tombol Buka): /weighbridge?view=form&tab=...&plat=BM 1455 JJ -> plat langsung dicari
document.addEventListener('DOMContentLoaded', () => {
    const plat = new URLSearchParams(window.location.search).get('plat');
    if (plat) lookupPlat(plat);
});