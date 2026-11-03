import { useState } from 'react'

const tampil = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`

// Dua isian tanggal untuk memilih ulang rentang di dalam data yang sudah dimuat (min..maks, 'YYYY-MM-DD'). Rentang baru dipakai begitu kedua
// tanggal sah dan urut; selama belum sah, rentang lama tetap berlaku dan alasannya ditulis di bawah isian.
export default function RentangTanggal({ dari, sampai, min, maks, onUbah, padat = false }) {
  const [draf, setDraf] = useState({ dari, sampai })
  const [asal, setAsal] = useState({ dari, sampai })
  if (asal.dari !== dari || asal.sampai !== sampai) {
    // rentang diubah dari luar (preset, reset filter): isian ikut
    setAsal({ dari, sampai })
    setDraf({ dari, sampai })
  }

  let salah = null
  if (draf.dari && draf.sampai) {
    if (draf.dari > draf.sampai) salah = 'Tanggal awal setelah tanggal akhir.'
    else if (draf.dari < min || draf.sampai > maks) salah = `Pilih di antara ${tampil(min)} dan ${tampil(maks)}.`
  }

  const ganti = (kunci) => (e) => {
    const baru = { ...draf, [kunci]: e.target.value }
    setDraf(baru)
    if (baru.dari && baru.sampai && baru.dari <= baru.sampai && baru.dari >= min && baru.sampai <= maks) onUbah(baru.dari, baru.sampai)
  }

  const kelas = 'min-w-0 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm tabular-nums text-slate-800'
  return (
    <div>
      <div className={padat ? 'flex items-center gap-1.5' : 'grid grid-cols-[1fr_auto_1fr] items-center gap-1.5'}>
        <input type="date" aria-label="Dari tanggal" className={kelas} value={draf.dari ?? ''} min={min} max={maks} onChange={ganti('dari')} />
        <span className="text-xs text-slate-500">s/d</span>
        <input type="date" aria-label="Sampai tanggal" className={kelas} value={draf.sampai ?? ''} min={min} max={maks} onChange={ganti('sampai')} />
      </div>
      {salah && <p className="mt-1 text-xs text-red-700">{salah}</p>}
    </div>
  )
}
