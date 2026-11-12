import { useEffect, useRef, useState } from 'react'
import { saringOpsi } from '../lib/data'
import { IkonPanah } from './Ikon'

// sebaris: daftar membuka di tempat (dipakai di panel filter), bukan melayang. bukaAwal hanya dipakai untuk pengujian.
export default function FilterMulti({ label, opsi, terpilih, onUbah, sebaris = false, bukaAwal = false }) {
  const [buka, setBuka] = useState(bukaAwal)
  const [cari, setCari] = useState('')
  const kotak = useRef(null)

  useEffect(() => {
    if (!buka || sebaris) return undefined
    const luar = (e) => {
      if (kotak.current && !kotak.current.contains(e.target)) setBuka(false)
    }
    const esc = (e) => {
      if (e.key === 'Escape') setBuka(false)
    }
    document.addEventListener('mousedown', luar)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', luar)
      document.removeEventListener('keydown', esc)
    }
  }, [buka, sebaris])

  const tampil = saringOpsi(opsi, cari)
  const ringkas = terpilih.length === 0 ? 'Semua' : terpilih.length === 1 ? terpilih[0] : `${terpilih.length} dipilih`
  const ganti = (nilai) => onUbah(terpilih.includes(nilai) ? terpilih.filter((v) => v !== nilai) : [...terpilih, nilai])
  const pilihHasil = () => onUbah([...new Set([...terpilih, ...tampil])])

  return (
    <div className="relative" ref={kotak}>
      <button
        type="button"
        aria-haspopup="true"
        aria-expanded={buka}
        onClick={() => setBuka((b) => !b)}
        className={
          'flex items-center gap-1.5 rounded-md border bg-white px-2 py-1 text-sm hover:bg-slate-50 ' +
          (sebaris ? 'w-full ' : '') +
          (terpilih.length > 0 ? 'border-sky-400' : 'border-slate-300')
        }
      >
        <span className="text-slate-500">{label}</span>
        <span className={'truncate font-medium ' + (sebaris ? 'ml-auto max-w-36' : 'max-w-40')}>{ringkas}</span>
        <IkonPanah className={'h-4 w-4 shrink-0 text-slate-500 transition-transform ' + (buka ? 'rotate-180' : '')} />
      </button>

      {buka && (
        <div
          className={
            'mt-1 rounded-lg border border-slate-200 bg-white p-2 ' + (sebaris ? '' : 'absolute left-0 z-20 w-72 shadow-lg')
          }
        >
          <input
            type="search"
            autoFocus
            value={cari}
            onChange={(e) => setCari(e.target.value)}
            placeholder={`Cari ${label.toLowerCase()}...`}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <div className="mt-2 flex items-center justify-between text-xs">
            <button type="button" className="text-sky-700 underline" onClick={pilihHasil}>
              {cari ? 'Pilih hasil pencarian' : 'Pilih semua'}
            </button>
            <button
              type="button"
              className="text-slate-600 underline disabled:opacity-40"
              disabled={terpilih.length === 0}
              onClick={() => onUbah([])}
            >
              Hapus pilihan
            </button>
          </div>
          <ul className="gulir-halus mt-1 max-h-64 overflow-y-auto">
            {tampil.map((v) => (
              <li key={v}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-slate-50">
                  <input type="checkbox" checked={terpilih.includes(v)} onChange={() => ganti(v)} />
                  <span className="min-w-0 flex-1 truncate" title={v}>
                    {v}
                  </span>
                </label>
              </li>
            ))}
            {tampil.length === 0 && <li className="px-1 py-2 text-xs text-slate-500">Tidak ada yang cocok</li>}
          </ul>
        </div>
      )}
    </div>
  )
}
