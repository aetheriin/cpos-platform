// ===== Posisi gulir menu samping tetap saat pindah halaman =====
// Dimuat tepat setelah sidebar (templates/partials/layout/sidebar.html), bukan defer, supaya posisinya dipulihkan sebelum halaman
// tampil: menu tidak terlihat meloncat ke atas lalu turun lagi. Disimpan per tab (sessionStorage).
(function () {
    const nav = document.querySelector('#sidebar .sidebar-nav');
    if (!nav) return;
    const KUNCI = 'sidebar_gulir';
    let simpan = 0;
    try { simpan = Number(sessionStorage.getItem(KUNCI)) || 0; } catch (e) { /* storage diblokir: mulai dari atas */ }
    if (simpan) {
        nav.scrollTop = simpan;
        // base.js membuka / menutup dropdown menu sesuai pilihan terakhir setelah ini, jadi tinggi menu bisa berubah: pulihkan sekali lagi
        document.addEventListener('DOMContentLoaded', () => setTimeout(() => { nav.scrollTop = simpan; }, 0));
    }
    const catat = () => { try { sessionStorage.setItem(KUNCI, String(nav.scrollTop)); } catch (e) { /* abaikan */ } };
    nav.addEventListener('scroll', catat, { passive: true });
    window.addEventListener('pagehide', catat);
})();
