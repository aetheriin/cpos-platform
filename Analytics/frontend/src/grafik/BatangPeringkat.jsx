import { memo } from 'react'
import { hargaKg, kgRingkas } from './tbs'

// Peringkat netto (tipe, business group, supplier) sebagai daftar batang HTML: nama panjang membungkus dan batang selalu terlihat di kartu sempit.
// Klik baris untuk memfilter; nilai yang tidak dipilih diredupkan.
function BatangPeringkat({ data, terpilih, onPilih, warna = '#0369a1', keterangan }) {
  if (data.length === 0) return <div className="py-10 text-center text-sm text-slate-500">Tidak ada pembelian untuk filter ini</div>
  const maks = Math.max(...data.map((d) => d.netto), 1)
  return (
    <div>
      <ul className="space-y-1.5">
        {data.map((d) => {
          const aktif = terpilih.includes(d.nama)
          return (
            <li key={d.nama}>
              <button
                type="button"
                onClick={(e) => onPilih(d.nama, e)}
                aria-pressed={aktif}
                title={`${d.nama}: ${kgRingkas(d.netto)}, harga rata-rata ${hargaKg(d.harga)}`}
                className="w-full rounded-md px-1 py-1 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                style={{ opacity: terpilih.length && !aktif ? 0.45 : 1 }}
              >
                <span className="flex items-baseline justify-between gap-2 text-xs">
                  <span className={'min-w-0 truncate ' + (aktif ? 'font-semibold text-slate-900' : 'text-slate-700')}>{d.nama}</span>
                  <span className="shrink-0 tabular-nums text-slate-500">{hargaKg(d.harga)}</span>
                </span>
                <span className="mt-0.5 flex items-center gap-2">
                  <span className="h-3 min-w-1 rounded-sm" style={{ width: `${(d.netto / maks) * 80}%`, background: warna }} />
                  <span className="shrink-0 text-xs tabular-nums text-slate-700">{kgRingkas(d.netto)}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {keterangan && <p className="mt-2 text-xs text-slate-500">{keterangan}</p>}
    </div>
  )
}

export default memo(BatangPeringkat)
