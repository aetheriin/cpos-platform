// ===== FORM SERAGAM: pesan galat di bawah isian & tanda wajib (*) =====
// Berlaku otomatis untuk semua form, tanpa kode tambahan di tiap halaman.
// - Galat browser (wajib diisi, terlalu pendek, format salah) tidak lagi muncul sebagai gelembung bawaan browser,
//   melainkan teks merah tepat di bawah isian + bingkai merah; hilang begitu isiannya diperbaiki.
// - Galat dari server: respons { error, kolom } -> pesan di bawah isian bernama `kolom` (utils/galat_isian.py).
//   Tanpa `kolom`, isian dicari dari nama label yang disebut pesan (mis. "NIK harus 16 digit" -> isian NIK).
//   Notifikasi pop-up tetap muncul seperti biasa.
// - Tanda * merah di label semua isian wajib (required), juga yang wajibnya berubah lewat JS / Pengaturan Site.

const Galat = {
    formTerakhir: null,
    waktuKirim: 0,

    // Tempat pesan: setelah pembungkus isian (kotak password dengan tombol mata, pilihan dengan pencarian)
    jangkar(el) {
        const induk = el.parentElement;
        return induk && induk.classList.contains('relative') && induk.children.length <= 4 ? induk : el;
    },

    tampil(el, pesan) {
        if (!el) return;
        this.hapus(el);
        const p = document.createElement('p');
        p.className = 'galat-isian';
        p.setAttribute('role', 'alert');
        p.textContent = typeof t === 'function' ? t(pesan) : pesan;
        el.classList.add('isian-galat');
        el.setAttribute('aria-invalid', 'true');
        this.jangkar(el).insertAdjacentElement('afterend', p);
        el._galat = p;
    },

    hapus(el) {
        if (!el || !el._galat) return;
        el._galat.remove();
        el._galat = null;
        el.classList.remove('isian-galat');
        el.removeAttribute('aria-invalid');
    },

    bersihkan(form) {
        if (form) [...form.elements].forEach(el => this.hapus(el));
    },

    pesanBrowser(el) {
        const v = el.validity;
        if (v.valueMissing) return el.tagName === 'SELECT' || el.type === 'checkbox' || el.type === 'radio' ? 'Wajib dipilih' : 'Wajib diisi';
        if (v.tooShort) return `Minimal ${el.minLength} karakter`;
        if (v.tooLong) return `Maksimal ${el.maxLength} karakter`;
        if (v.typeMismatch) return el.type === 'email' ? 'Format email belum benar (contoh: nama@perusahaan.com)' : 'Format belum benar';
        if (v.patternMismatch) return el.title || 'Format belum benar';
        if (v.rangeUnderflow) return `Minimal ${el.min}`;
        if (v.rangeOverflow) return `Maksimal ${el.max}`;
        if (v.stepMismatch) return 'Angka tidak sesuai kelipatannya';
        if (v.badInput) return 'Isi dengan angka';
        return el.validationMessage || 'Isian belum benar';
    },

    // Isian untuk galat server: nama `kolom`, atau label terpanjang yang disebut di pesan
    cariIsian(form, data) {
        if (!form) return null;
        if (data.kolom && form.elements[data.kolom]) {
            const el = form.elements[data.kolom];
            return el instanceof RadioNodeList ? el[0] : el;
        }
        const pesan = String(data.error || '').toLowerCase();
        let terbaik = null, panjang = 0;
        [...form.elements].forEach(el => {
            if (!el.id || el.type === 'hidden' || el.disabled) return;
            const label = form.querySelector(`label[for="${el.id}"]`);
            const teks = label && label.textContent.replace(/[*:]|\(.*?\)/g, '').trim().toLowerCase();
            if (teks && teks.length > panjang && new RegExp(`(^|[^a-z])${teks.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z]|$)`).test(pesan)) {
                terbaik = el; panjang = teks.length;
            }
        });
        return terbaik;
    },

    // Dipanggil api.js untuk setiap respons gagal
    dariServer(data, status) {
        if (!data || !data.error || status !== 400 || Date.now() - this.waktuKirim > 20000) return;
        const form = this.formTerakhir;
        if (!form || !document.contains(form)) return;
        const el = this.cariIsian(form, data);
        if (!el) return;
        this.tampil(el, data.error);
        if (!el.offsetParent) return;
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
        el.focus({ preventScroll: true });
    },
};

// Gelembung browser diganti pesan di bawah isian; isian salah pertama yang mendapat fokus
let fokusGalatDiatur = false;
document.addEventListener('invalid', e => {
    const el = e.target;
    e.preventDefault();
    Galat.tampil(el, Galat.pesanBrowser(el));
    if (fokusGalatDiatur) return;
    fokusGalatDiatur = true;
    setTimeout(() => { fokusGalatDiatur = false; }, 0);
    const tujuan = el.offsetParent ? el : Galat.jangkar(el).querySelector('button, input');
    if (tujuan) { tujuan.scrollIntoView({ block: 'center', behavior: 'smooth' }); tujuan.focus({ preventScroll: true }); }
}, true);

['input', 'change'].forEach(jenis => document.addEventListener(jenis, e => {
    const el = e.target;
    if (el && el._galat && (!el.willValidate || el.checkValidity())) Galat.hapus(el);
}, true));

document.addEventListener('submit', e => {
    Galat.formTerakhir = e.target;
    Galat.waktuKirim = Date.now();
    Galat.bersihkan(e.target);
}, true);

document.addEventListener('reset', e => Galat.bersihkan(e.target), true);

// ---------- tanda wajib ----------
function tandaiWajib(el) {
    if (!el || !el.id || !/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) || el.type === 'hidden') return;
    const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (!label) return;
    const tanda = label.querySelector('.tanda-wajib');
    if (el.required && !tanda) label.insertAdjacentHTML('beforeend', ' <span class="tanda-wajib" aria-hidden="true">*</span>');
    else if (!el.required && tanda) tanda.remove();
}

function tandaiWajibSemua(akar) {
    (akar.querySelectorAll ? akar.querySelectorAll('input[id], select[id], textarea[id]') : []).forEach(tandaiWajib);
}

document.addEventListener('DOMContentLoaded', () => {
    tandaiWajibSemua(document);
    new MutationObserver(daftar => daftar.forEach(m => {
        if (m.type === 'attributes') tandaiWajib(m.target);
        else m.addedNodes.forEach(n => { if (n.nodeType === 1) { tandaiWajib(n); tandaiWajibSemua(n); } });
    })).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['required'] });
});
