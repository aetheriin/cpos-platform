// URL tiap halaman lewat History API. Hak akses tetap diperiksa server, jadi menebak alamat tidak membuka apa pun.
//   laporan pr_po           -> /laporan/pr-po
//   halaman admin __pengguna -> /admin/pengguna
const ADMIN = { __pengguna: 'pengguna', __struktur: 'role-divisi', __izin: 'izin', __aktivitas: 'aktivitas' }
const ADMIN_BALIK = Object.fromEntries(Object.entries(ADMIN).map(([id, slug]) => [slug, id]))
// Semua alamat di bawah base aplikasi (vite.config.js), mis. /analytics/laporan/pr-po
const DASAR = import.meta.env.BASE_URL.replace(/\/$/, '')
const tanpaDasar = (path) => (DASAR && path.startsWith(DASAR) ? path.slice(DASAR.length) || '/' : path)

export const alamatDari = (id) =>
  DASAR + (id == null ? '/' : ADMIN[id] ? `/admin/${ADMIN[id]}` : `/laporan/${id.replaceAll('_', '-')}`)

// Halaman yang ditunjuk alamat sekarang: id laporan / id halaman admin, null untuk '/', atau undefined kalau alamatnya tidak dikenal.
export function idDariAlamat(path = window.location.pathname) {
  const bagian = tanpaDasar(path).split('/').filter(Boolean)
  if (bagian.length === 0) return null
  if (bagian.length === 2 && bagian[0] === 'laporan') return bagian[1].replaceAll('-', '_')
  if (bagian.length === 2 && bagian[0] === 'admin' && ADMIN_BALIK[bagian[1]]) return ADMIN_BALIK[bagian[1]]
  return undefined
}

// Halaman masuk: /login?ke=/laporan/pr-po. "ke" menyimpan halaman yang tadi dibuka supaya setelah masuk pengguna langsung ke sana.
export const ALAMAT_LOGIN = `${DASAR}/login`

export function keLogin() {
  const { pathname, search } = window.location
  if (pathname === ALAMAT_LOGIN) return
  const ke = tanpaDasar(pathname) === '/' ? '' : `?ke=${encodeURIComponent(pathname + search)}`
  window.history.replaceState(null, '', ALAMAT_LOGIN + ke)
}

// Setelah masuk: kembali ke "ke" kalau alamatnya alamat di aplikasi ini sendiri (diawali satu "/"), supaya parameter ini tidak bisa
// dipakai untuk mengarahkan pengguna ke situs lain.
export function keluarDariLogin() {
  if (window.location.pathname !== ALAMAT_LOGIN) return
  const ke = new URLSearchParams(window.location.search).get('ke') ?? ''
  const aman = ke.startsWith(`${DASAR}/`) && !ke.startsWith('//') && !ke.startsWith('/\\') && !ke.startsWith(ALAMAT_LOGIN)
  window.history.replaceState(null, '', aman ? ke : alamatDari(null))
}

// ganti: true menimpa entri riwayat (tombol Back tidak kembali ke alamat lama), dipakai untuk membetulkan alamat yang tidak sah.
export function pindahAlamat(id, ganti = false) {
  const tujuan = alamatDari(id)
  if (window.location.pathname === tujuan) return
  window.history[ganti ? 'replaceState' : 'pushState'](null, '', tujuan)
}
