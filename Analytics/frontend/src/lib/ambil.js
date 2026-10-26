import { useEffect, useState } from 'react'

// Ambil data setiap `kunci` berubah. Permintaan lama dibatalkan; saat memuat atau gagal, data terakhir tetap dipakai.
// memuat dihitung dari kunci yang terakhir selesai, jadi tidak perlu setState di dalam effect.
export function useAmbil(kunci, ambil, onDataHilang) {
  const [hasil, setHasil] = useState({ kunci: null, data: null, galat: null })

  useEffect(() => {
    const kontrol = new AbortController()
    ambil(kontrol.signal)
      .then((data) => setHasil({ kunci, data, galat: null }))
      .catch((e) => {
        if (e.name === 'AbortError') return
        if (e.status === 404) return onDataHilang?.()
        setHasil((h) => ({ kunci, data: h.data, galat: e }))
      })
    return () => kontrol.abort()
  }, [kunci]) // eslint-disable-line react-hooks/exhaustive-deps

  return { data: hasil.data, galat: hasil.galat, memuat: hasil.kunci !== kunci }
}
