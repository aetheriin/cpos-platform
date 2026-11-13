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

// Token form login (CSRF) berlaku 1 jam. Halaman login sering dibiarkan terbuka lama di PC pos, jadi token diperbarui
// diam-diam tiap 30 menit, dan sekali lagi sebelum mengirim bila sudah lama (mis. PC sempat tidur). Isian tidak hilang.
const formLogin = document.querySelector('form[action="/login"]');
const SEGARKAN_MS = 30 * 60 * 1000;
let tokenDiambil = Date.now();

async function segarkanToken() {
    const res = await fetch('/login', { credentials: 'same-origin', cache: 'no-store' });
    if (res.redirected) { window.location.reload(); return false; }    // sudah login di tab lain
    const baru = new DOMParser().parseFromString(await res.text(), 'text/html').querySelector('input[name="csrf_token"]');
    if (!baru) return false;
    formLogin.elements.csrf_token.value = baru.value;
    tokenDiambil = Date.now();
    return true;
}

if (formLogin) {
    setInterval(() => segarkanToken().catch(() => {}), SEGARKAN_MS);
    let terkirim = false;
    formLogin.addEventListener('submit', async e => {
        // Klik ganda: kiriman kedua diabaikan, tombol dikunci sampai halaman berikutnya terbuka
        if (terkirim) { e.preventDefault(); return; }
        const tombol = formLogin.querySelector('button[type="submit"]');
        const kunci = () => {
            terkirim = true;
            tombol.disabled = true;
            tombol.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Memproses...</span>';
        };
        if (Date.now() - tokenDiambil < SEGARKAN_MS) { kunci(); return; }
        e.preventDefault();
        kunci();
        try { await segarkanToken(); } catch { /* tetap dikirim; server menjawab bila token memang habis */ }
        formLogin.submit();
    });
}
