import { memo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import TickKlik from './TickKlik'
import { WARNA_TARA_BERAT, WARNA_TARA_RINGAN, redup } from './risiko'
import { angka } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

const angka2 = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 })

function Petunjuk({ active, payload }) {
  const d = active && payload?.[0]?.payload
  if (!d) return null
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-medium text-slate-800">{d.kendaraan}</div>
      <div className="text-slate-600">{angka.format(d.jumlah)} transaksi</div>
      <div className="text-slate-600">Rata-rata selisih: {angka2.format(d.rata)} kg</div>
      <div className="text-slate-600">
        Rentang: {angka2.format(d.min)} sampai {angka2.format(d.maks)} kg
      </div>
    </div>
  )
}

function BatangKendaraan({ data, terpilih, onPilih }) {
  if (data.length === 0) return <Kosong teks="Tidak ada transaksi untuk filter ini" />
  return (
    <div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="kendaraan" interval={0} height={60} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={<TickKlik onPilih={onPilih} terpilih={terpilih} miring />} />
            <YAxis width={52} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => angka.format(v)} />
            <ReferenceLine y={0} stroke="#94a3b8" />
            <Tooltip content={<Petunjuk />} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
            <Bar dataKey="rata" name="Rata-rata selisih tara" radius={[3, 3, 0, 0]} isAnimationActive={false} className="cursor-pointer" onClick={(_, i, e) => onPilih(data[i].kendaraan, e)}>
              {data.map((d) => (
                <Cell key={d.kendaraan} fill={d.rata < 0 ? WARNA_TARA_RINGAN : WARNA_TARA_BERAT} fillOpacity={redup(terpilih, d.kendaraan)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default memo(BatangKendaraan)
