import { memo } from 'react'
import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, lintasTahun, persen, tgl, tglLengkap } from '../lib/data'
import { redup, warnaRisiko } from './risiko'

function Petunjuk({ active, payload }) {
  const d = active && payload?.[0]?.payload
  if (!d) return null
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-medium text-slate-800">{tglLengkap(d.hari)}</div>
      <div className="text-slate-600">
        {angka.format(d.berisiko)} berisiko dari {angka.format(d.total)} transaksi{d.total > 0 && ` (${persen(d.porsi)})`}
      </div>
      <div className="text-slate-600">WARNING tara: {angka.format(d.tara)}</div>
      <div className="text-slate-600">WARNING durasi: {angka.format(d.durasi)}</div>
    </div>
  )
}

// Batang: transaksi WARNING per hari menurut indikatornya. Garis: persentase berisiko hari itu (sumbu kanan). Klik batang untuk memfilter hari itu.
function TrenHarian({ data, indikator, terpilih, onPilih }) {
  if (data.every((d) => d.total === 0)) return <div className="py-10 text-center text-sm text-slate-500">Tidak ada transaksi pada periode ini</div>
  const label = lintasTahun(data) ? tglLengkap : tgl
  const baris = data.map((d) => ({ ...d, label: label(d.hari), porsi: d.total ? d.berisiko / d.total : 0 }))
  const warning = indikator.filter((i) => i.kunci !== 'normal')
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={baris} margin={{ top: 8, right: 4, bottom: 4, left: 0 }}>
          <CartesianGrid yAxisId="n" strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 10, fill: '#475569' }} minTickGap={6} />
          <YAxis yAxisId="n" width={44} allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => angka.format(v)} />
          <YAxis yAxisId="p" orientation="right" width={40} domain={[0, 1]} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
          <Tooltip content={<Petunjuk />} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 11 }} />
          {warning.map((i) => (
            <Bar key={i.kunci} yAxisId="n" dataKey={i.kunci} name={i.nama} stackId="w" fill={warnaRisiko(i.kunci)} isAnimationActive={false} className="cursor-pointer" onClick={(_, idx, e) => onPilih(baris[idx].hari, e)}>
              {baris.map((d) => (
                <Cell key={d.hari} fillOpacity={redup(terpilih, d.hari)} />
              ))}
            </Bar>
          ))}
          <Line yAxisId="p" dataKey="porsi" name="% berisiko" type="monotone" stroke="#0f172a" strokeWidth={1.5} dot={false} className="tinta-grafik" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export default memo(TrenHarian)
