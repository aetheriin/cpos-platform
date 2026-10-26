import { memo } from 'react'
import { angka } from '../lib/data'
import { WARNA_MEDIAN, WARNA_RATA } from './pigt'

const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

// Rata-rata (batang) dan median (garis tegak) lama dalam hari per kelompok, seperti grafik "rata-rata vs lama normal" di Excel.
// Batang jauh melewati garis median berarti ada beberapa barang yang sangat lama. onPilih opsional: klik baris untuk memfilter.
function DurasiBatang({ data, terpilih = [], onPilih, kosong }) {
  if (data.length === 0) return <div className="py-10 text-center text-sm text-slate-500">{kosong}</div>
  // Satu kelompok yang jauh lebih lama (mis. 70 hari, yang lain 1 hari) membuat batang lain tak terlihat: skala dibatasi 3x nilai terbesar
  // berikutnya, dan batang yang melewati batas diberi ujung bergerigi.
  const nilai = data.map((d) => Math.max(d.rata, d.median)).sort((a, b) => b - a)
  const maks = Math.max(nilai.length > 1 && nilai[0] > nilai[1] * 3 ? nilai[1] * 3 : nilai[0], 1)
  const lebar = (x) => `${Math.min(x / maks, 1) * 100}%`
  const Baris = onPilih ? 'button' : 'div'
  return (
    <div>
      <ul className="space-y-2">
        {data.map((d) => {
          const aktif = terpilih.includes(d.nama)
          return (
            <li key={d.nama}>
              <Baris
                {...(onPilih ? { type: 'button', onClick: (e) => onPilih(d.nama, e), 'aria-pressed': aktif } : {})}
                title={`${d.nama}: ${angka.format(d.n)} barang dalam ${angka.format(d.gt)} GT`}
                className={'block w-full rounded-md px-1 py-0.5 text-left text-xs ' + (onPilih ? 'hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500' : '')}
                style={{ opacity: terpilih.length && !aktif ? 0.45 : 1 }}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate">
                    <span className={aktif ? 'font-semibold text-slate-900' : 'text-slate-700'}>{d.nama}</span>
                    <span className="ml-1.5 text-slate-400">{angka.format(d.gt)} GT</span>
                  </span>
                  <span className="shrink-0 tabular-nums text-slate-600">
                    rata-rata {satu.format(d.rata)} <span className="text-slate-500">· nilai tengah {satu.format(d.median)} hari</span>
                  </span>
                </span>
                <span className="relative mt-1 block h-2.5 rounded-sm bg-slate-100">
                  <span
                    className="absolute inset-y-0 left-0 rounded-sm"
                    style={{
                      width: lebar(d.rata),
                      background: d.rata > maks ? `linear-gradient(90deg, ${WARNA_RATA} 92%, transparent 92%, transparent 94%, ${WARNA_RATA} 94%, ${WARNA_RATA} 96%, transparent 96%)` : WARNA_RATA,
                    }}
                  />
                  <span className="absolute -inset-y-0.5 w-0.5" style={{ left: `calc(${lebar(d.median)} - 1px)`, background: WARNA_MEDIAN }} />
                </span>
              </Baris>
            </li>
          )
        })}
      </ul>
      <div className="mt-3 flex gap-4 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-3 rounded-sm" style={{ background: WARNA_RATA }} />
          Rata-rata
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-0.5" style={{ background: WARNA_MEDIAN }} />
          Nilai tengah (median)
        </span>
      </div>
    </div>
  )
}

export default memo(DurasiBatang)
