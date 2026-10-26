import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Semua permintaan ke /api diteruskan ke backend FastAPI.
// Dengan begitu browser hanya bicara ke satu alamat dan tidak ada masalah CORS.
// Alamat backend diatur lewat VITE_API_TARGET di frontend/.env.local (atau variabel lingkungan); bawaannya backend lokal di port 8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '') // '' = ambil semua variabel, bukan hanya yang berawalan VITE_ yang dikirim ke browser
  const backend = env.VITE_API_TARGET || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': backend,
      },
    },
  }
})
