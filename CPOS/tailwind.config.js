/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js", "./modules/*/templates/**/*.html", "./modules/*/static/**/*.js"],
  theme: {
    extend: {
      // Warna utama aplikasi: nilainya di static/css/tailwind-source.css (:root --utama-*), ganti di sana saja
      colors: {
        utama: {
          50: 'rgb(var(--utama-50) / <alpha-value>)', 100: 'rgb(var(--utama-100) / <alpha-value>)',
          200: 'rgb(var(--utama-200) / <alpha-value>)', 500: 'rgb(var(--utama-500) / <alpha-value>)',
          600: 'rgb(var(--utama-600) / <alpha-value>)', 700: 'rgb(var(--utama-700) / <alpha-value>)',
          800: 'rgb(var(--utama-800) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}