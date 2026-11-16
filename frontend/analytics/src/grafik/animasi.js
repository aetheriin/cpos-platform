// Animasi grafik saat muncul atau data berubah: ringan (dijalankan browser sekali, sekitar 0,4 detik). Dimatikan kalau pengguna
// mengaktifkan "kurangi gerak" di komputernya, dan untuk grafik titik yang bisa berisi ribuan titik (lihat SebaranTara).
const kurangiGerak = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
export const ANIMASI = !kurangiGerak
export const DURASI_ANIMASI = 400
