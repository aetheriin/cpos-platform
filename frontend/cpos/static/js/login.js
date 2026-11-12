// Halaman login dipulihkan dari cache Back/Forward -> muat ulang, supaya server bisa mengarahkan
// user yang masih login ke halaman kerjanya dan token CSRF selalu baru.
window.addEventListener('pageshow', e => { if (e.persisted) window.location.reload(); });

// Username selalu huruf besar tanpa spasi (sama dengan isian username di common.js; halaman login tidak memuat common.js)
document.addEventListener('input', e => {
    const el = e.target;
    if (!el.matches('input[data-username]')) return;
    const baru = el.value.toUpperCase().replace(/\s+/g, '');
    if (baru === el.value) return;
    const posisi = Math.min(el.selectionStart, baru.length);
    el.value = baru;
    el.setSelectionRange(posisi, posisi);
});
