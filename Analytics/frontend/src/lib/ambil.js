import { useEffect, useState, useSyncExternalStore } from 'react'

// Jumlah permintaan useAmbil yang sedang berjalan di seluruh aplikasi, untuk tanda memuat di tengah layar (komponen TandaMemuat).
let berjalan = 0
const pendengar = new Set()
const kabari = () => pendengar.forEach((f) => f())
const ubahBerjalan = (n) => {
  berjalan += n
  kabari()
}
const dengar = (f) => {
  pendengar.add(f)
  return () => pendengar.delete(f)
}
export const useSedangMemuat = () => useSyncExternalStore(dengar, () => berjalan > 0)

// Ambil data setiap `kunci` berubah. Permintaan lama dibatalkan; saat memuat atau gagal, data terakhir tetap dipakai.
// memuat dihitung dari kunci yang terakhir selesai, jadi tidak perlu setState di dalam effect.
export function useAmbil(kunci, ambil, onDataHilang) {
  const [hasil, setHasil] = useState({ kunci: null, data: null, galat: null })

  useEffect(() => {
    const kontrol = new AbortController()
    let selesai = false
    const akhiri = () => {
      if (!selesai) ubahBerjalan(-1)
      selesai = true
    }
    ubahBerjalan(1)
    ambil(kontrol.signal)
      .then((data) => setHasil({ kunci, data, galat: null }))
      .catch((e) => {
        if (e.name === 'AbortError') return
        if (e.status === 404) return onDataHilang?.()
        setHasil((h) => ({ kunci, data: h.data, galat: e }))
      })
      .finally(akhiri)
    return () => {
      kontrol.abort()
      akhiri()
    }
  }, [kunci]) // eslint-disable-line react-hooks/exhaustive-deps

  return { data: hasil.data, galat: hasil.galat, memuat: hasil.kunci !== kunci }
}
