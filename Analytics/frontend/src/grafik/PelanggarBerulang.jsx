import { memo, useState } from 'react'
import { WARNA_RISIKO } from './risiko'
import { angka, persen } from '../lib/data'

const TAB = [
  { kunci: 'kendaraan', nama: 'Kendaraan' },
  { kunci: 'supir', nama: 'Supir' },
  { kunci: 'supplier', nama: 'Supplier' },
]

// Nilai dengan transaksi WARNING terbanyak per dimensi. Batang di belakang angka membandingkan jumlah WARNING antarbaris. Klik baris untuk memfilter.
function PelanggarBerulang({ data, terpilih, onPilih }) {
  const [tab, setTab] = useState('kendaraan')
  const daftar = data[tab]
  const maks = Math.max(1, ...daftar.map((d) => d.berisiko))
  const pilihan = terpilih[tab]
  return (
    <div>
      <div role="tablist" className="mb-3 inline-flex rounded-lg border border-slate-300 p-0.5">
        {TAB.map((t) => (
          <button
            key={t.kunci}
            type="button"
            role="tab"
            aria-selected={tab === t.kunci}
            onClick={() => setTab(t.kunci)}
            className={'rounded-md px-3 py-1 text-sm ' + (tab === t.kunci ? 'bg-sky-700 text-white' : 'text-slate-700 hover:bg-slate-100')}
          >
            {t.nama}
          </button>
        ))}
      </div>
      {daftar.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">Tidak ada transaksi WARNING untuk filter ini.</p>
      ) : (
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b border-slate-200 text-xs text-slate-500">
            <tr>
              <th className="py-2 pr-2 font-medium">{TAB.find((t) => t.kunci === tab).nama}</th>
              <th className="w-[34%] px-2 py-2 font-medium">WARNING</th>
              <th className="w-[22%] py-2 pl-2 text-right font-medium">Persen</th>
            </tr>
          </thead>
          <tbody>
            {daftar.map((d) => {
              const aktif = pilihan.includes(d.nama)
              return (
                <tr
                  key={d.nama}
                  tabIndex={0}
                  aria-selected={aktif}
                  onClick={(e) => onPilih(tab, d.nama, e)}
                  onKeyDown={(e) => e.key === 'Enter' && onPilih(tab, d.nama, e)}
                  title={`WARNING tara ${angka.format(d.tara)}, WARNING durasi ${angka.format(d.durasi)}`}
                  className={'cursor-pointer border-b border-slate-100 focus:outline-none focus-visible:bg-sky-50 ' + (aktif ? 'bg-sky-50' : pilihan.length ? 'opacity-50 hover:opacity-100' : 'hover:bg-slate-50')}
                >
                  <td className="truncate py-1.5 pr-2 font-medium text-slate-800" title={d.nama}>
                    {d.nama}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="h-2 min-w-1 shrink rounded-sm" style={{ width: `${(d.berisiko / maks) * 70}%`, background: WARNA_RISIKO.tara }} />
                      <span className="shrink-0 tabular-nums">{angka.format(d.berisiko)}</span>
                    </span>
                  </td>
                  <td className="py-1.5 pl-2 text-right tabular-nums leading-tight text-slate-600">
                    <span className="block">{persen(d.persen)}</span>
                    <span className="block text-xs text-slate-400">dari {angka.format(d.total)}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default memo(PelanggarBerulang)
