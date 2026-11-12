import TickMinggu from './TickMinggu'
import { GARIS_PR_PO, WARNA } from './warna'
import { angka, barisMinggu, BATAS_PADAT, jedaLabel } from '../lib/data'
import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Titik pada garis. Memakai nama prop 'warna' karena Recharts menimpa prop 'fill'.
function Titik({ cx, cy, payload, warna, terpilih, onPilih }) {
  if (cx == null || cy == null) return null
  const aktif = terpilih === payload.indeks
  const redup = terpilih != null && !aktif
  return (
    <circle
      cx={cx}
      cy={cy}
      r={aktif ? 5.5 : 3.5}
      fill={warna}
      opacity={redup ? 0.3 : 1}
      style={{ cursor: 'pointer' }}
      onClick={() => onPilih(payload.indeks)}
    />
  )
}

export default function WeeklyChart({ data, minggu, onPilihMinggu, garis = GARIS_PR_PO }) {
  const baris = barisMinggu(data)
  const padat = baris.length > BATAS_PADAT
  const opasitas = (indeks) => (minggu != null && minggu !== indeks ? 0.3 : 1)

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={baris} margin={{ top: 8, right: 12, bottom: 4, left: 0 }} barGap={0} barCategoryGap="25%">
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="singkat"
            interval={jedaLabel(baris.length, 16)}
            height={padat ? 76 : 46}
            tickLine={false}
            axisLine={{ stroke: '#cbd5e1' }}
            tick={<TickMinggu data={baris} terpilih={minggu} onPilih={onPilihMinggu} padat={padat} />}
          />
          <YAxis
            width={44}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: '#475569' }}
            tickFormatter={(v) => angka.format(v)}
          />
          <Tooltip
            formatter={(v) => angka.format(v)}
            labelFormatter={(_, p) => p?.[0]?.payload?.lengkap ?? ''}
            cursor={{ fill: 'rgba(14,165,233,0.08)' }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          <Bar dataKey="outstanding_awal" name="Outstanding awal" fill={WARNA.awal} radius={[3, 3, 0, 0]} className="cursor-pointer" onClick={(_, i) => onPilihMinggu(i)}>
            {baris.map((d) => (
              <Cell key={d.indeks} fillOpacity={opasitas(d.indeks)} />
            ))}
          </Bar>
          <Bar dataKey="outstanding_akhir" name="Outstanding akhir" fill={WARNA.akhir} radius={[3, 3, 0, 0]} className="cursor-pointer" onClick={(_, i) => onPilihMinggu(i)}>
            {baris.map((d) => (
              <Cell key={d.indeks} fillOpacity={opasitas(d.indeks)} />
            ))}
          </Bar>

          {garis.map((g) => (
            <Line
              key={g.kunci}
              type="linear"
              dataKey={g.kunci}
              name={g.nama}
              stroke={g.warna}
              strokeWidth={2}
              dot={baris.length > 26 ? false : <Titik warna={g.warna} terpilih={minggu} onPilih={onPilihMinggu} />}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
