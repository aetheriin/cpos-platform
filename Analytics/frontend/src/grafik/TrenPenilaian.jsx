import { memo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { warna } from '../lib/data'
import { labelBulan } from './pigt'

const skor = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

function Petunjuk({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="mb-0.5 font-medium text-slate-800">{label}</div>
      {payload.filter((p) => p.value != null).sort((a, b) => b.value - a.value).map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-4 text-slate-600">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="tabular-nums">{skor.format(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

// Grafik "PVR PENILAIAN" di Excel: skor (jumlah bobot) per bulan, satu garis per pembuat. Klik nama di legenda untuk melihat satu orang saja.
// Klik bulan di grafik untuk memfilter kartu, grafik Bobot, dan tabel ke bulan itu (Ctrl untuk menambah bulan); bulan terpilih diberi pita.
function TrenPenilaian({ data, voucher = 'PVR', onPilih, terpilihBulan = [], onPilihBulan }) {
  if (data.bulan.length === 0) return <div className="py-10 text-center text-sm text-slate-500">Belum ada {voucher} untuk filter ini</div>
  // Bulan tanpa PVR dibiarkan kosong (garis terputus), seperti sel kosong di pivot Excel
  const baris = data.bulan.map((b, i) => Object.fromEntries([['bulan', b], ['label', labelBulan(b)], ...data.pembuat.map((p, j) => [p, data.nilai[i][j] || null])]))
  const klik = (s, e) => {
    const b = baris.find((r) => r.label === s?.activeLabel)?.bulan
    if (b && onPilihBulan) onPilihBulan(b, e)
  }
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={baris} margin={{ top: 8, right: 16, bottom: 4, left: 0 }} onClick={klik} className={onPilihBulan ? 'cursor-pointer' : undefined}>
          {baris.filter((r) => terpilihBulan.includes(r.bulan)).map((r) => (
            <ReferenceLine key={r.bulan} x={r.label} stroke="#0369a1" strokeOpacity={0.12} strokeWidth={28} />
          ))}
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} />
          <YAxis width={44} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => skor.format(v)}
            label={{ value: 'Bobot', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11, fill: '#64748b' } }} />
          <Tooltip content={<Petunjuk />} />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12, cursor: 'pointer' }} onClick={(e) => onPilih(e.value)} />
          {data.pembuat.map((p, i) => (
            <Line key={p} type="linear" dataKey={p} name={p} stroke={warna(i)} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default memo(TrenPenilaian)
