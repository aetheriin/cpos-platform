import { useEffect, useState } from 'react'
import { IkonAtas } from './Ikon'

// z-30: di bawah panel filter, menu, dan popup
const AMBANG_GULIR = 300

export default function KembaliKeAtas() {
  const [tampil, setTampil] = useState(false)

  useEffect(() => {
    const periksa = () => setTampil(window.scrollY > AMBANG_GULIR)
    periksa() // halaman bisa dibuka dalam keadaan sudah tergulir (mis. dimuat ulang)
    window.addEventListener('scroll', periksa, { passive: true })
    return () => window.removeEventListener('scroll', periksa)
  }, [])

  if (!tampil) return null

  const naik = () => {
    const kurangiGerak = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches // hormati pengaturan "kurangi animasi"
    window.scrollTo({ top: 0, behavior: kurangiGerak ? 'auto' : 'smooth' })
  }

  return (
    <button
      type="button"
      onClick={naik}
      aria-label="Kembali ke atas"
      title="Kembali ke atas"
      className="fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-lg hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500"
    >
      <IkonAtas className="h-5 w-5" />
    </button>
  )
}
