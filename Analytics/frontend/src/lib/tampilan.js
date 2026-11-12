import { createContext, useContext, useSyncExternalStore } from 'react'

// Tata letak per laporan: 'padat' (bawaan) atau 'panjang'. Laporannya diketahui dari LaporanAktif, jadi grafik cukup memanggil
// useTataLetak(). Disimpan di browser.
const KUNCI = 'tata-letak'
const BAWAAN = 'padat'
const pendengar = new Set()

export const LaporanAktif = createContext(null)

// { [id laporan]: 'panjang' }. Laporan yang tidak tercatat memakai bawaan. Format lama (satu teks untuk semua laporan) diabaikan.
const baca = () => {
  try {
    const isi = JSON.parse(localStorage.getItem(KUNCI) ?? '{}')
    return isi && typeof isi === 'object' && !Array.isArray(isi) ? isi : {}
  } catch {
    return {}
  }
}
let pilihan = baca()

const simpan = (baru) => {
  pilihan = baru
  try {
    localStorage.setItem(KUNCI, JSON.stringify(baru))
  } catch {
    // tetap berlaku sampai halaman dimuat ulang
  }
  pendengar.forEach((f) => f())
}

const langgan = (f) => {
  pendengar.add(f)
  return () => pendengar.delete(f)
}


// laporan: id laporan; tanpa argumen memakai laporan dari LaporanAktif.
export function useTataLetak(laporan) {
  const dariKonteks = useContext(LaporanAktif)
  const id = laporan ?? dariKonteks
  const semua = useSyncExternalStore(langgan, () => pilihan)
  const tata = semua[id] === 'panjang' ? 'panjang' : BAWAAN
  const ubah = (baru) => simpan({ ...pilihan, [id]: baru })
  return [tata, ubah]
}
