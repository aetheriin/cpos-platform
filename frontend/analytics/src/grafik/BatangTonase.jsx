import { memo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka } from '../lib/data'

const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const HURUF_PER_BARIS = 24
const LEBAR_NAMA = 180 // px

// Nama dipecah per kata menjadi paling banyak dua baris, supaya nama pengangkut yang panjang tetap terbaca utuh tanpa diarahkan kursor.
function pecah(nama) {
  const baris = ['']
  for (const kata of nama.split(' ')) {
    const kini = baris.at(-1)
    if (kini && (kini + ' ' + kata).length > HURUF_PER_BARIS) baris.push(kata)
    else baris[baris.length - 1] = kini ? `${kini} ${kata}` : kata
  }
  if (baris.length <= 2) return baris
  const kedua = baris.slice(1).join(' ')
  return [baris[0], kedua.length > HURUF_PER_BARIS ? `${kedua.slice(0, HURUF_PER_BARIS - 1)}…` : kedua]
}

function TickNama({ x, y, payload }) {
  const baris = pecah(payload.value)
  const awal = baris.length === 1 ? 4 : -2
  return (
    <text x={x - 8} y={y} textAnchor="end" fontSize={11} fill="#334155">
      <title>{payload.value}</title>
      {baris.map((b, i) => (
        <tspan key={i} x={x - 8} dy={i === 0 ? awal : 12}>
          {b}
        </tspan>
      ))}
    </text>
  )
}

function IsiTooltip({ active, payload, persen }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="max-w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-900">{d.nama}</p>
      <p className="mt-0.5 tabular-nums text-slate-700">
        {satu.format(d.netto / 1000)} ton dalam {angka.format(d.rit)} pengiriman
      </p>
      {persen && <p className="tabular-nums text-slate-600">{satu.format(d.persen * 100)}% dari total berat</p>}
    </div>
  )
}

// Peringkat berat (produk, pengangkut) sebagai grafik batang mendatar: nama di kiri (dua baris kalau panjang), berat di ujung batang.
// Klik batang untuk melihat nama itu saja; Ctrl/Shift menambah pilihan. lainnya: { jumlah, netto } untuk nama di luar peringkat.
function BatangTonase({ data, terpilih, onPilih, warna = '#0369a1', persen = false, lainnya = null, satuanLain = 'lainnya', kosong }) {
  if (data.length === 0) return kosong
  const baris = data.map((d) => ({ ...d, ton: d.netto / 1000 }))
  const adaPilihan = terpilih.length > 0
  const tinggiBaris = baris.some((d) => d.nama.length > HURUF_PER_BARIS) ? 34 : 26
  return (
    <div>
      <div className="w-full" style={{ height: baris.length * tinggiBaris + 8 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={baris} layout="vertical" margin={{ top: 0, right: 76, bottom: 0, left: 0 }} barCategoryGap="24%">
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis type="category" dataKey="nama" width={LEBAR_NAMA} tickLine={false} axisLine={false} interval={0} tick={<TickNama />} />
            <Tooltip content={<IsiTooltip persen={persen} />} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
            <Bar dataKey="ton" radius={[0, 3, 3, 0]} maxBarSize={16} isAnimationActive={false} className="cursor-pointer" onClick={(d, _, e) => onPilih((d.payload ?? d).nama, e)}>
              {baris.map((d) => (
                <Cell key={d.nama} fill={warna} fillOpacity={adaPilihan && !terpilih.includes(d.nama) ? 0.25 : 0.9} />
              ))}
              <LabelList dataKey="ton" position="right" fontSize={11} fill="#334155" formatter={(v) => `${satu.format(v)} ton`} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {lainnya && (
        <p className="mt-2 text-xs text-slate-600">
          Masih ada {angka.format(lainnya.jumlah)} {satuanLain} lain dengan total {satu.format(lainnya.netto / 1000)} ton. Cari namanya lewat tombol Filter.
        </p>
      )}
    </div>
  )
}

export default memo(BatangTonase)
