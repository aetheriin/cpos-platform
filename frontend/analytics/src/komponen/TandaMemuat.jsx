import { useEffect, useState } from 'react'
import { useSedangMemuat } from '../lib/ambil'

const JEDA = 250 // ms; permintaan yang lebih cepat dari ini tidak memunculkan tanda, supaya tidak berkedip

// Tanda memuat di tengah layar selama grafik, kartu, atau tabel mengambil data karena filter, cross filter, atau halaman tabel berubah.
// Tidak menghalangi klik: filter tetap bisa diubah selama memuat.
export default function TandaMemuat() {
  const memuat = useSedangMemuat()
  const [tampil, setTampil] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setTampil(memuat), memuat ? JEDA : 0)
    return () => clearTimeout(t)
  }, [memuat])
  if (!tampil) return null
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center">
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-lg">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600" aria-hidden="true" />
        Memuat data...
      </div>
    </div>
  )
}
