import { useState } from 'react'

// Tema tampilan: 'terang' atau 'gelap'. Pilihan disimpan di browser; tanpa pilihan, mengikuti pengaturan sistem.
// index.html sudah menerapkannya sebelum React dimuat, jadi halaman tidak sempat berkedip putih.
const KUNCI = 'tema'

export const temaAwal = () => document.documentElement.dataset.tema === 'gelap' ? 'gelap' : 'terang'

export function useTema() {
  const [tema, setTema] = useState(temaAwal)
  const ganti = () => {
    const baru = tema === 'gelap' ? 'terang' : 'gelap'
    // Matikan semua transisi selama tema berganti, supaya sidebar dan isi berubah warna bersamaan (tanpa jeda transition-colors)
    const akar = document.documentElement
    akar.classList.add('ganti-tema')
    document.documentElement.dataset.tema = baru
    void akar.offsetHeight   // paksa gaya baru diterapkan sebelum transisi dinyalakan lagi
    requestAnimationFrame(() => requestAnimationFrame(() => akar.classList.remove('ganti-tema')))
    try {
      localStorage.setItem(KUNCI, baru)
    } catch {
      // penyimpanan browser tidak tersedia: tema tetap berganti untuk halaman ini
    }
    setTema(baru)
  }
  return [tema, ganti]
}
