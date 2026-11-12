// URL tiap halaman lewat History API (laporan pr_po -> /laporan/pr-po). Hak akses tetap diperiksa server, jadi menebak alamat tidak membuka apa pun.
// Semua alamat di bawah base aplikasi (vite.config.js), mis. /analytics/laporan/pr-po
const DASAR = import.meta.env.BASE_URL.replace(/\/$/, '')
const tanpaDasar = (path) => (DASAR && path.startsWith(DASAR) ? path.slice(DASAR.length) || '/' : path)

export const alamatDari = (id) =>
  DASAR + (id == null ? '/' : `/laporan/${id.replaceAll('_', '-')}`)

// Halaman yang ditunjuk alamat sekarang: id laporan, null untuk '/', atau undefined kalau alamatnya tidak dikenal.
export function idDariAlamat(path = window.location.pathname) {
  const bagian = tanpaDasar(path).split('/').filter(Boolean)
  if (bagian.length === 0) return null
  if (bagian.length === 2 && bagian[0] === 'laporan') return bagian[1].replaceAll('-', '_')
  return undefined
}

// ganti: true menimpa entri riwayat (tombol Back tidak kembali ke alamat lama), dipakai untuk membetulkan alamat yang tidak sah.
export function pindahAlamat(id, ganti = false) {
  const tujuan = alamatDari(id)
  if (window.location.pathname === tujuan) return
  window.history[ganti ? 'replaceState' : 'pushState'](null, '', tujuan)
}
