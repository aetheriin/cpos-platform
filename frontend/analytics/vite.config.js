import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Aplikasi dilayani di bawah /analytics/ (satu situs dengan CPOS: CPOS di /, Analytics di /analytics). VITE_BASE=/ untuk berdiri sendiri.
// Semua permintaan ke <base>api diteruskan ke backend FastAPI (yang tetap melayani /api/...).
// Dengan begitu browser hanya bicara ke satu alamat dan tidak ada masalah CORS.
// Alamat backend diatur lewat VITE_API_TARGET di frontend/.env.local (atau variabel lingkungan); bawaannya backend lokal di port 8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '') // '' = ambil semua variabel, bukan hanya yang berawalan VITE_ yang dikirim ke browser
  const backend = env.VITE_API_TARGET || 'http://localhost:8000'
  const base = env.VITE_BASE || '/analytics/'
  return {
    base,
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        [`${base}api`]: { target: backend, rewrite: (p) => p.slice(base.length - 1) },
      },
    },
  }
})
