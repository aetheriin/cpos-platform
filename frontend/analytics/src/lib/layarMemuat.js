import { useEffect, useSyncExternalStore } from 'react'

// Jumlah layar "Memuat data laporan" yang sedang tampil. Tombol AkasaBot disembunyikan selama ada, karena laporannya belum bisa ditanyakan.
let jumlah = 0
const pendengar = new Set()
const kabari = () => pendengar.forEach((f) => f())
const dengar = (f) => {
  pendengar.add(f)
  return () => pendengar.delete(f)
}

export function useDaftarLayarMemuat() {
  useEffect(() => {
    jumlah += 1
    kabari()
    return () => {
      jumlah -= 1
      kabari()
    }
  }, [])
}

export const useAdaLayarMemuat = () => useSyncExternalStore(dengar, () => jumlah > 0)
