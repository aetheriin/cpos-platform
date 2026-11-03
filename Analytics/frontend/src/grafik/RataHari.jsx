import { memo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { kgRingkas, sumbu } from './tbs'

// Rata-rata netto harian untuk tiap hari dalam seminggu, dari hari yang ada pembeliannya (sama dengan measure Rata-rata di Excel). Klik batang untuk memfilter hari.
function RataHari({ data, terpilih, onPilih }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="nama" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} />
          <YAxis width={48} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={sumbu} />
          <Tooltip formatter={(v, _, item) => [`${kgRingkas(v)} (rata-rata dari ${item.payload.jumlah_hari} hari)`, 'Netto']} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
          <Bar dataKey="rata" name="Rata-rata netto" radius={[3, 3, 0, 0]} isAnimationActive={false} className="cursor-pointer" onClick={(d, _, e) => onPilih((d.payload ?? d).nama, e)}>
            {data.map((d) => (
              <Cell key={d.nama} fill="#0369a1" fillOpacity={terpilih.length && !terpilih.includes(d.nama) ? 0.3 : 0.85} />
            ))}
            <LabelList dataKey="rata" position="top" fontSize={10} fill="#334155" formatter={sumbu} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default memo(RataHari)
