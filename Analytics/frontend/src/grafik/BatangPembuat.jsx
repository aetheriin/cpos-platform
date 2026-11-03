import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { WARNA } from './warna'
import { angka } from '../lib/data'

export default function BatangPembuat({ data, terpilih = [], onPilih }) {
  if (data.length === 0 || data.every((d) => d.jumlah === 0)) {
    return <div className="py-10 text-center text-sm text-slate-500">Tidak ada outstanding untuk filter ini</div>
  }
  const opasitas = (nama) => (terpilih.length > 0 && !terpilih.includes(nama) ? 0.3 : 1)
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 16, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="pembuat" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} />
          <YAxis width={40} allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => angka.format(v)} />
          <Tooltip formatter={(v) => [angka.format(v), 'Outstanding akhir']} cursor={{ fill: 'rgba(14,165,233,0.08)' }} />
          <Bar dataKey="jumlah" name="Outstanding akhir" fill={WARNA.akhir} radius={[3, 3, 0, 0]} className="cursor-pointer" onClick={(_, i, e) => onPilih(data[i].pembuat, e)}>
            {data.map((d) => (
              <Cell key={d.pembuat} fillOpacity={opasitas(d.pembuat)} />
            ))}
            <LabelList dataKey="jumlah" position="top" fontSize={11} fill="#334155" formatter={(v) => angka.format(v)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
