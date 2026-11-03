import { useEffect, useRef } from 'react'
import { tandaAktif } from '../api'

const KEJADIAN = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'scroll', 'touchstart']
const KIRIM_TIAP = 60 * 1000 // paling sering satu tanda aktif per menit
const CEK_TIAP = 15 * 1000

// Server menghitung idle dari permintaan terakhir, padahal membaca grafik tidak meminta apa pun. Jadi selama ada gerakan mouse atau
// ketikan, tanda aktif dikirim (paling sering sekali per menit). Tanpa gerakan selama batasDetik, onHabis dipanggil. 0 = tanpa batas.
export function useJagaIdle(batasDetik, onHabis) {
  const habis = useRef(onHabis)
  habis.current = onHabis

  useEffect(() => {
    if (!batasDetik) return undefined
    let terakhir = Date.now()
    let terkirim = Date.now()
    let selesai = false
    const catat = () => {
      terakhir = Date.now()
    }
    const periksa = () => {
      if (selesai) return
      const sekarang = Date.now()
      if (sekarang - terakhir >= batasDetik * 1000) {
        selesai = true
        habis.current()
        return
      }
      if (terakhir > terkirim && sekarang - terkirim >= KIRIM_TIAP) {
        terkirim = sekarang
        tandaAktif().catch(() => {}) // 401 sudah ditangani aturSesiHabis
      }
    }
    KEJADIAN.forEach((k) => window.addEventListener(k, catat, { passive: true }))
    const timer = setInterval(periksa, CEK_TIAP)
    document.addEventListener('visibilitychange', periksa) // tab dibuka lagi setelah lama ditinggal: langsung diperiksa
    return () => {
      KEJADIAN.forEach((k) => window.removeEventListener(k, catat))
      clearInterval(timer)
      document.removeEventListener('visibilitychange', periksa)
    }
  }, [batasDetik])
}
