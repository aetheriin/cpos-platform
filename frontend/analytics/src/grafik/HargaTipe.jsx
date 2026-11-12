import { memo } from 'react'
import { tglLengkap } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

const angka = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// Garis kecil harga harian. Skala per baris (min..maks tipe itu) supaya naik-turunnya terlihat; hari tanpa pembelian memutus garis.
function Garis({ harga, warna }) {
  const nilai = harga.map((h) => h.harga).filter((v) => v != null)
  if (nilai.length === 0) return <span className="text-xs text-slate-400">tidak ada pembelian</span>
  const min = Math.min(...nilai), maks = Math.max(...nilai), rentang = maks - min || 1
  const x = (i) => (harga.length > 1 ? (i / (harga.length - 1)) * 100 : 50)
  const y = (v) => 26 - ((v - min) / rentang) * 22
  const ruas = []
  let kini = []
  harga.forEach((h, i) => {
    if (h.harga == null) {
      if (kini.length) ruas.push(kini)
      kini = []
    } else kini.push(`${x(i).toFixed(2)},${y(h.harga).toFixed(2)}`)
  })
  if (kini.length) ruas.push(kini)
  const terakhir = harga.map((h, i) => [h.harga, i]).filter(([v]) => v != null).at(-1)
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="h-9 w-full overflow-visible" aria-hidden="true">
      {ruas.map((r, i) =>
        r.length === 1 ? (
          <circle key={i} cx={r[0].split(',')[0]} cy={r[0].split(',')[1]} r="1.2" fill={warna} />
        ) : (
          <polyline key={i} points={r.join(' ')} fill="none" stroke={warna} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        ),
      )}
      <circle cx={x(terakhir[1])} cy={y(terakhir[0])} r="2.2" fill={warna} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

// Satu baris per tipe: nama, garis harga harian, harga terakhir, dan perubahan sejak hari pertama jendela. Klik baris untuk memfilter tipe.
// Harga naik ditandai merah karena biaya pembelian bertambah.
function HargaTipe({ data, mulai, akhir, terpilih, onPilih }) {
  if (data.data.length === 0) return <Kosong teks="Tidak ada pembelian untuk filter ini" />
  return (
    <div>
      <div className="mb-1 grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto] gap-x-3 text-xs text-slate-500 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto]">
        <span>Tipe</span>
        <span>
          {tglLengkap(mulai)} – {tglLengkap(akhir)}
        </span>
        <span className="text-right">Terakhir</span>
      </div>
      <ul className="space-y-0.5">
        {data.data.map((t) => {
          const aktif = terpilih.includes(t.tipe)
          const beda = t.awal != null && t.akhir != null ? t.akhir - t.awal : null
          const warna = beda == null || beda === 0 ? 'text-slate-500' : beda > 0 ? 'text-red-700' : 'text-emerald-700'
          return (
            <li key={t.tipe}>
              <button
                type="button"
                onClick={(e) => onPilih(t.tipe, e)}
                aria-pressed={aktif}
                title={`${t.tipe}: Rp ${angka.format(t.awal ?? 0)} → Rp ${angka.format(t.akhir ?? 0)} per kg`}
                className="grid w-full grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto] items-center gap-x-3 rounded-md px-1 py-1 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto]"
                style={{ opacity: terpilih.length && !aktif ? 0.45 : 1 }}
              >
                <span className={'truncate text-xs ' + (aktif ? 'font-semibold text-slate-900' : 'text-slate-700')}>{t.tipe}</span>
                <Garis harga={t.harga} warna="#0369a1" />
                <span className="text-right text-xs tabular-nums leading-tight">
                  <span className="block text-slate-800">{t.akhir == null ? '–' : `Rp ${angka.format(t.akhir)}`}</span>
                  <span className={'block ' + warna}>
                    {beda == null ? '' : beda === 0 ? 'tetap' : `${beda > 0 ? '▲' : '▼'} ${satu.format(Math.abs((beda / t.awal) * 100))}%`}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {data.jumlah > data.data.length && (
        <p className="mt-2 text-xs text-slate-500">
          {data.data.length} tipe dengan netto terbesar dari {data.jumlah} tipe.
        </p>
      )}
    </div>
  )
}

export default memo(HargaTipe)
