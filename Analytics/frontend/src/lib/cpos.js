// Gabungan dengan CPOS. Laporan dibuka di dalam halaman CPOS (/an/<id> memuat aplikasi ini dengan ?embed=1 dalam bingkai):
// sidebar & bilah atas Analytics disembunyikan, login & hak akses mengikuti CPOS (backend: CPOS_URL di .env).
const dariAlamat = () => new URLSearchParams(window.location.search).get('embed') === '1'

// Diingat selama tab terbuka, karena alamat berganti (?embed hilang) saat pengguna berpindah laporan di dalam bingkai
export const SEMATAN = (() => {
  try {
    if (dariAlamat()) sessionStorage.setItem('sematan', '1')
    return sessionStorage.getItem('sematan') === '1' || window.self !== window.top
  } catch {
    return dariAlamat() || window.self !== window.top
  }
})()

// Penanda untuk CSS (index.css): di dalam bingkai halaman tidak menggulir sendiri, CPOS yang menggulir
if (SEMATAN) document.documentElement.dataset.sematan = '1'

// Ukuran dasar huruf mengikuti CPOS (13px sampai 16px menurut lebar layar), jadi teks, tombol, dan jarak sebanding dengan halaman CPOS
function samakanRem() {
  try {
    document.documentElement.style.fontSize = getComputedStyle(window.parent.document.documentElement).fontSize
  } catch {
    // bingkai beda alamat saat pengembangan: ukuran bawaan
  }
}
if (SEMATAN && window.parent !== window) {
  samakanRem()
  window.addEventListener('resize', samakanRem)
}

// Klik / ketik di dalam bingkai tidak terlihat oleh halaman CPOS; kabari supaya sesi CPOS tidak dianggap diam
// (CPOS static/js/analytics/sematan.js). Paling sering satu pesan per menit.
let terakhir = 0
function laporAktif() {
  if (Date.now() - terakhir < 60_000) return
  terakhir = Date.now()
  window.parent.postMessage({ tipe: 'cpos-aktif' }, '*') // isinya tidak rahasia; CPOS memeriksa pengirimnya
}

export function pasangLaporAktif() {
  if (!SEMATAN || window.parent === window) return
  for (const ev of ['click', 'keydown', 'wheel']) window.addEventListener(ev, laporAktif, { passive: true })
}

// Sesi CPOS berakhir: halaman masuk CPOS dibuka di jendela utama (bukan di dalam bingkai)
export function keLoginCpos() {
  window.top.location.href = '/login'
}
