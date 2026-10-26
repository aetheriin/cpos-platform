import { useEffect, useRef, useState } from 'react'

// Lebar elemen dalam piksel, diperbarui saat ukurannya berubah (layar mengecil, panel filter dibuka, menu samping disembunyikan).
export function useLebar() {
  const ref = useRef(null)
  const [lebar, setLebar] = useState(0)
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === 'undefined') return undefined
    const amati = new ResizeObserver(([e]) => setLebar(e.contentRect.width))
    amati.observe(ref.current)
    return () => amati.disconnect()
  }, [])
  return [ref, lebar]
}
