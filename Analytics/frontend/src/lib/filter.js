import { useState } from 'react'
import { ambilDashboard } from '../api'
import { useAmbil } from './ambil'
import { tglLengkap } from './data'

const KOSONG = []
const RENTANG_KOSONG = { dari: null, sampai: null }

// Kerangka yang sama untuk semua dashboard: filter, panel filter, dan data dashboard yang mengikuti filter.
// rentangKosong: isian yang dikosongkan saat chip tanggal dilepas (laporan mingguan ikut mengosongkan minggu).
export function useDashboard(laporan, dataId, awal, onDataHilang, rentangKosong = RENTANG_KOSONG) {
  const [filter, setFilter] = useState(awal)
  const [panel, setPanel] = useState(false)
  const hasil = useAmbil(JSON.stringify([dataId, filter]), (sinyal) => ambilDashboard(laporan, dataId, filter, sinyal), onDataHilang)

  const ubah = (bagian) => setFilter((f) => ({ ...f, ...bagian }))
  const terpilih = (k) => filter[k] ?? KOSONG
  // Chip tanpa nilai (mis. minggu) mengosongkan isian itu; chip daftar membuang satu nilainya.
  const lepas = (jenis, nilai) =>
    ubah(jenis === 'rentang' ? rentangKosong : { [jenis]: nilai == null ? null : terpilih(jenis).filter((v) => v !== nilai) })

  return {
    ...hasil, filter, setFilter, ubah, terpilih, lepas,
    reset: () => setFilter(awal),
    panel, setPanel, togglePanel: () => setPanel((p) => !p),
  }
}

export const chipRentang = (filter) =>
  filter.dari && filter.sampai ? [['rentang', null, `Tanggal ${tglLengkap(filter.dari)} sampai ${tglLengkap(filter.sampai)}`]] : []

// daftar: [{ kunci, nama }]. tampil(kunci, nilai) mengubah nilai menjadi teks chip.
export const chipDaftar = (daftar, terpilih, tampil = (_, v) => v) =>
  daftar.flatMap(({ kunci, nama }) => terpilih(kunci).map((nilai) => [kunci, nilai, `${nama}: ${tampil(kunci, nilai)}`]))
