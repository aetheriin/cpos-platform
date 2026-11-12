/** @type {import('tailwindcss').Config} */
const warnaBawaan = require('tailwindcss/colors')
const plugin = require('tailwindcss/plugin')

// Mode gelap (html.dark, static/js/tema.js). Warna berwarna yang dirancang untuk latar terang dibalik lewat variabel, jadi ikut berubah
// di semua halaman, termasuk komponen yang memakai @apply:
//   50 / 100 / 200 (latar & garis lembut: badge, kotak info) -> warna tua yang redup
//   700 / 800 / 900 (teks di atas latar lembut)             -> warna muda supaya terbaca di latar gelap
// Shade 300-600 (tombol, ikon, titik status) tidak dibalik. Pengecualian yang memakai 700 sebagai latar ada di tailwind-source.css.
const WARNA = ['red', 'rose', 'orange', 'amber', 'yellow', 'lime', 'green', 'emerald', 'teal', 'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple', 'pink']
const DIBALIK = [50, 100, 200, 700, 800, 900]
const LATAR_GELAP = '#121a2b'   // sama dengan latar kartu mode gelap

const rgb = (hex) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
const campur = (atas, bawah, porsi) => rgb(atas).map((v, i) => Math.round(v * porsi + rgb(bawah)[i] * (1 - porsi))).join(' ')
// shade terang -> versi gelapnya: [shade sumber, porsi warna di atas latar gelap]
const PASANGAN_GELAP = { 50: [900, 0.35], 100: [800, 0.45], 200: [700, 0.6], 700: [300, 1], 800: [200, 1], 900: [100, 1] }

const variabel = (gelap) => Object.fromEntries(WARNA.flatMap(w => DIBALIK.map(n => {
  const [sumber, porsi] = gelap ? PASANGAN_GELAP[n] : [n, 1]
  return [`--${w}-${n}`, campur(warnaBawaan[w][sumber], LATAR_GELAP, porsi)]
})))

module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js", "./static/rekapin/**/*.js", "./static/item_request/**/*.js", "./static/item_dashboard/**/*.js"],
  theme: {
    extend: {
      // Warna utama aplikasi: nilainya di static/css/tailwind-source.css (:root --utama-*), ganti di sana saja
      colors: {
        utama: {
          50: 'rgb(var(--utama-50) / <alpha-value>)', 100: 'rgb(var(--utama-100) / <alpha-value>)',
          200: 'rgb(var(--utama-200) / <alpha-value>)', 300: 'rgb(var(--utama-300) / <alpha-value>)',
          400: 'rgb(var(--utama-400) / <alpha-value>)', 500: 'rgb(var(--utama-500) / <alpha-value>)',
          600: 'rgb(var(--utama-600) / <alpha-value>)', 700: 'rgb(var(--utama-700) / <alpha-value>)',
          800: 'rgb(var(--utama-800) / <alpha-value>)',
        },
        // Abu-abu (slate) lewat variabel supaya mode gelap cukup membalik skalanya di satu tempat (tailwind-source.css, html.dark)
        slate: Object.fromEntries([50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map(n => [n, `rgb(var(--slate-${n}) / <alpha-value>)`])),
        ...Object.fromEntries(WARNA.map(w => [w, { ...warnaBawaan[w], ...Object.fromEntries(DIBALIK.map(n => [n, `rgb(var(--${w}-${n}) / <alpha-value>)`])) }])),
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [
    plugin(({ addBase }) => addBase({ ':root': variabel(false), 'html.dark': variabel(true) })),
  ],
}
