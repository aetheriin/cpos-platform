import { memo } from 'react'
import { angka } from '../lib/data'
import { WARNA_RATA } from './pigt'

const skor = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

// Tabel bobot (sheet BOBOT di Excel) beserta hasilnya: bobot x jumlah yang dinilai = skor. Urut dari bobot terbesar. Klik untuk memfilter.
function KategoriPvr({ data, voucher = 'PVR', terpilih, onPilih }) {
  if (data.length === 0) return <div className="py-10 text-center text-sm text-slate-500">Belum ada {voucher} untuk filter ini</div>
  const urut = [...data].sort((a, b) => b.bobot - a.bobot || b.skor - a.skor)
  const maks = Math.max(...data.map((d) => d.skor), 1)
  return (
    <div>
      <div className="mb-1 grid grid-cols-[2.75rem_minmax(5rem,1fr)_minmax(5rem,1.2fr)] gap-3 px-1 text-[11px] text-slate-500">
        <span className="text-right">Bobot</span>
        <span>Kategori</span>
        <span>Skor</span>
      </div>
      <ul className="divide-y divide-slate-100">
        {urut.map((d) => {
          const aktif = terpilih.includes(d.nama)
          return (
            <li key={d.nama}>
              <button type="button" onClick={(e) => onPilih(d.nama, e)} aria-pressed={aktif}
                className="grid w-full grid-cols-[2.75rem_minmax(5rem,1fr)_minmax(5rem,1.2fr)] items-center gap-3 px-1 py-1.5 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                style={{ opacity: terpilih.length && !aktif ? 0.45 : 1 }}>
                <span className="text-right text-base font-semibold tabular-nums text-slate-900">{skor.format(d.bobot)}</span>
                <span className="min-w-0">
                  <span className={'block truncate text-xs ' + (aktif ? 'font-semibold text-slate-900' : 'text-slate-800')}>{d.nama}</span>
                  <span className="block text-[11px] tabular-nums text-slate-500">
                    {angka.format(d.dinilai)} {d.nama === 'Angkutan' ? 'item' : voucher}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="h-2.5 min-w-0.5 rounded-sm" style={{ width: `${(d.skor / maks) * 65}%`, background: WARNA_RATA }} />
                  <span className="shrink-0 text-xs tabular-nums text-slate-700">{skor.format(d.skor)}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-[11px] text-slate-500">Skor = bobot × jumlah dinilai. Angkutan dinilai per item, kategori lain sekali per {voucher}.</p>
    </div>
  )
}

export default memo(KategoriPvr)
