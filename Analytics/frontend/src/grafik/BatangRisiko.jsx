import { memo } from 'react'
import { redup, warnaRisiko } from './risiko'
import { angka } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

// Daftar batang HTML (bukan sumbu Recharts berlebar tetap) supaya label panjang membungkus dan batang tetap terlihat di kartu yang sempit.
// Tinggi mengikuti kartu (h-full) agar sejajar dengan grafik di sebelahnya. Klik baris untuk memfilter indikator.
function BatangRisiko({ data, terpilih, onPilih }) {
  if (data.length === 0 || data.every((d) => d.jumlah === 0)) {
    return <Kosong teks="Tidak ada transaksi untuk filter ini" />
  }
  const maks = Math.max(...data.map((d) => d.jumlah))
  return (
    <ul className="flex h-full min-h-48 flex-col justify-around gap-3">
      {data.map((d) => (
        <li key={d.kunci}>
          <button
            type="button"
            onClick={(e) => onPilih(d.nama, e)}
            aria-pressed={terpilih.includes(d.nama)}
            className="w-full rounded-md px-1 py-1 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            style={{ opacity: redup(terpilih, d.nama) === 1 ? 1 : 0.45 }}
          >
            <span className={'block text-xs ' + (terpilih.includes(d.nama) ? 'font-semibold text-slate-900' : 'text-slate-600')}>{d.nama}</span>
            <span className="mt-1 flex items-center gap-2">
              <span className="h-5 min-w-1 rounded-sm" style={{ width: `${(d.jumlah / maks) * 85}%`, background: warnaRisiko(d.kunci) }} />
              <span className="shrink-0 text-xs tabular-nums text-slate-700">{angka.format(d.jumlah)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

export default memo(BatangRisiko)
