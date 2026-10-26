import { memo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useLebar } from '../lib/lebar'
import TickKlik from './TickKlik'
import { warnaRisiko } from './risiko'
import { angka } from '../lib/data'

function Petunjuk({ active, payload, indikator }) {
  const d = active && payload?.[0]?.payload
  if (!d) return null
  return (
    <div className="max-w-80 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-medium text-slate-800">{d.supplier}</div>
      {indikator.map((i) => (
        <div key={i.kunci} className="mt-0.5 flex gap-2 text-slate-600">
          <span aria-hidden="true" className="mt-1 h-2 w-2 shrink-0 rounded-sm" style={{ background: warnaRisiko(i.kunci) }} />
          <span className="min-w-0 flex-1 truncate">{i.nama}</span>
          <span className="tabular-nums">{angka.format(d[i.kunci])}</span>
        </div>
      ))}
      <div className="mt-1 border-t border-slate-100 pt-1 text-slate-700">
        {d.total > 0 && `${(((d.total - d.normal) / d.total) * 100).toFixed(1).replace('.', ',')}% berisiko`}
      </div>
    </div>
  )
}

// Klik segmen memfilter supplier dan indikatornya sekaligus; klik nama supplier di sumbu atau indikator di legenda memfilter itu saja.
// Mode Persentase: batang 100% diurutkan menurut porsi berisiko, supaya supplier kecil yang berisiko tinggi tidak tertutup yang besar.
function BatangRisikoSupplier({ risiko_supplier: rs, indikator, terpilih, risikoTerpilih, onPilih, onPilihRisiko, onPilihSupplier }) {
  const [mode, setMode] = useState('jumlah')
  const [ref, lebar] = useLebar()
  if (rs.data.length === 0) return <div className="py-10 text-center text-sm text-slate-500">Tidak ada transaksi untuk filter ini</div>
  const persenMode = mode === 'persen'
  const data = persenMode ? rs.data_persen : rs.data
  const lebarLabel = Math.round(Math.min(230, Math.max(96, (lebar || 600) * 0.38)))
  const opasitas = (supplier, risiko) =>
    (terpilih.length > 0 && !terpilih.includes(supplier)) || (risikoTerpilih.length > 0 && !risikoTerpilih.includes(risiko)) ? 0.2 : 1
  return (
    <div ref={ref} className="min-w-0">
      <div role="radiogroup" aria-label="Tampilan" className="mb-2 inline-flex rounded-lg border border-slate-300 p-0.5">
        {[['jumlah', 'Jumlah'], ['persen', 'Persentase']].map(([k, nama]) => (
          <button key={k} type="button" role="radio" aria-checked={mode === k} onClick={() => setMode(k)} className={'rounded-md px-3 py-1 text-sm ' + (mode === k ? 'bg-sky-700 text-white' : 'text-slate-700 hover:bg-slate-100')}>
            {nama}
          </button>
        ))}
      </div>
      {data.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">Tidak ada supplier dengan minimal {angka.format(rs.min_transaksi)} transaksi untuk filter ini.</p>
      ) : (
      <div className="w-full" style={{ height: data.length * 26 + 60 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" stackOffset={persenMode ? 'expand' : undefined} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
            <XAxis type="number" allowDecimals={persenMode} domain={persenMode ? [0, 1] : [0, 'auto']} ticks={persenMode ? [0, 0.25, 0.5, 0.75, 1] : undefined} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => (persenMode ? `${Math.round(v * 100)}%` : angka.format(v))} />
            <YAxis type="category" dataKey="supplier" width={lebarLabel} interval={0} tickLine={false} axisLine={false} tick={<TickKlik onPilih={onPilihSupplier} terpilih={terpilih} maks={Math.floor(lebarLabel / 6.3)} />} />
            <Tooltip content={<Petunjuk indikator={indikator} />} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
            <Legend
              verticalAlign="top"
              height={30}
              wrapperStyle={{ fontSize: 11, cursor: 'pointer' }}
              onClick={(item, _, e) => onPilihRisiko(item.value, e)}
              formatter={(nama) => <span style={{ opacity: risikoTerpilih.length > 0 && !risikoTerpilih.includes(nama) ? 0.4 : 1 }}>{nama}</span>}
            />
            {indikator.map((i) => (
              <Bar key={i.kunci} dataKey={i.kunci} name={i.nama} stackId="risiko" fill={warnaRisiko(i.kunci)} barSize={14} isAnimationActive={false} className="cursor-pointer" onClick={(_, idx, e) => onPilih(data[idx].supplier, i.nama, e)}>
                {data.map((d) => (
                  <Cell key={d.supplier} fillOpacity={opasitas(d.supplier, i.nama)} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      )}
      <p className="mt-1 text-xs text-slate-500">
        {persenMode
          ? `Supplier dengan persentase berisiko tertinggi, dari ${angka.format(rs.jumlah_supplier_persen)} supplier yang punya minimal ${angka.format(rs.min_transaksi)} transaksi.`
          : `${angka.format(rs.data.length)} supplier dengan transaksi terbanyak dari ${angka.format(rs.jumlah_supplier)} supplier.`}
      </p>
    </div>
  )
}

export default memo(BatangRisikoSupplier)
