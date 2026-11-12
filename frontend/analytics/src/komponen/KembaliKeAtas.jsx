import { useEffect, useState } from 'react'
import { SEMATAN } from '../lib/cpos'

// Sama dengan tombol CPOS (.tombol-ke-atas). z-30: di bawah panel filter, menu, dan popup
const AMBANG_GULIR = 300

// Di dalam bingkai CPOS: rem CPOS lebih kecil (13px ke atas) dan tombolnya diukur dari tepi jendela, sedangkan di sini tepinya sebelum scrollbar.
function ukuranCpos() {
  try {
    const rem = parseFloat(getComputedStyle(window.parent.document.documentElement).fontSize)
    const scrollbar = window.innerWidth - document.documentElement.clientWidth
    return { width: rem * 2.75, height: rem * 2.75, bottom: rem * 1.5, right: rem * 1.5 - scrollbar, fontSize: rem }
  } catch {
    return undefined // bingkai beda alamat saat pengembangan
  }
}

export default function KembaliKeAtas() {
  const [tampil, setTampil] = useState(false)
  const [ukuran, setUkuran] = useState()

  useEffect(() => {
    const periksa = () => setTampil(window.scrollY > AMBANG_GULIR)
    periksa() // halaman bisa dibuka dalam keadaan sudah tergulir (mis. dimuat ulang)
    window.addEventListener('scroll', periksa, { passive: true })
    return () => window.removeEventListener('scroll', periksa)
  }, [])

  useEffect(() => {
    if (!SEMATAN || !tampil) return undefined
    const ukur = () => setUkuran(ukuranCpos())
    ukur()
    window.addEventListener('resize', ukur)
    return () => window.removeEventListener('resize', ukur)
  }, [tampil])

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
      style={ukuran}
      className="fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-[#127cbf] bg-[#127cbf] text-white shadow-lg hover:border-[#0d66a0] hover:bg-[#0d66a0] focus:outline-none focus:ring-2 focus:ring-[#2997d6] focus:ring-offset-2 opacity-70 transition-opacity hover:opacity-100 focus-visible:opacity-100"
    >
      <svg viewBox="0 0 384 512" height="1em" fill="currentColor" aria-hidden="true">
        <path d="M214.6 41.4c-12.5-12.5-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 141.2V448c0 17.7 14.3 32 32 32s32-14.3 32-32V141.2L329.4 246.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-160-160z" />
      </svg>
    </button>
  )
}
