import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, barisMinggu, BATAS_PADAT_KECIL, jedaLabel } from '../lib/data'
import TickMinggu from './TickMinggu'

// Memakai nama prop 'warna' karena Recharts menimpa prop 'fill'.
function TitikSeri({ cx, cy, payload, warna, redup, terpilih, onKlik }) {
  if (cx == null || cy == null) return null
  const mingguAktif = terpilih === payload.indeks
  const mingguRedup = terpilih != null && !mingguAktif
  return (
    <circle
      cx={cx}
      cy={cy}
      r={mingguAktif ? 5 : 3}
      fill={warna}
      opacity={redup ? 0.25 : mingguRedup ? 0.35 : 1}
      style={{ cursor: 'pointer' }}
      onClick={onKlik}
    />
  )
}

// seri: [{ nama, nilai: [angka per minggu] }]
export default function GarisSeri({ mingguan, seri, warnaSeri, terpilihSeri = [], minggu, onPilihSeri, onPilihMinggu }) {
  const baris = barisMinggu(mingguan).map((r) => {
    seri.forEach((s, j) => {
      r['s' + j] = s.nilai[r.indeks]
    })
    return r
  })
  const padat = baris.length > BATAS_PADAT_KECIL
  const mingguTerpilih = minggu != null ? baris[minggu] : null

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1">
        {seri.map((s) => {
          const aktif = terpilihSeri.includes(s.nama)
          const redup = terpilihSeri.length > 0 && !aktif
          // Angka di tombol mengikuti minggu (atau bulan) yang dipilih; tanpa pilihan, jumlah seluruh rentang
          const jumlah = minggu != null ? s.nilai[minggu] ?? 0 : s.nilai.reduce((a, b) => a + b, 0)
          return (
            <button
              key={s.nama}
              type="button"
              onClick={(e) => onPilihSeri(s.nama, e)}
              className={
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ' +
                (aktif ? 'border-slate-500 bg-slate-50 font-medium ' : 'border-transparent hover:border-slate-200 ') +
                (redup ? 'opacity-45' : '')
              }
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: warnaSeri(s.nama) }} />
              {s.nama}
              <span className="tabular-nums text-slate-500">{angka.format(jumlah)}</span>
            </button>
          )
        })}
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={baris} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis
              dataKey="singkat"
              interval={jedaLabel(baris.length, 10)}
              height={padat ? 76 : 46}
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              tick={<TickMinggu data={baris} terpilih={minggu} onPilih={onPilihMinggu} padat={padat} />}
            />
            <YAxis
              width={40}
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: '#475569' }}
              tickFormatter={(v) => angka.format(v)}
            />
            <Tooltip
              formatter={(v, nama) => [angka.format(v), nama]}
              labelFormatter={(_, p) => p?.[0]?.payload?.lengkap ?? ''}
            />
            {mingguTerpilih && (
              <ReferenceLine x={mingguTerpilih.singkat} stroke="#0ea5e9" strokeOpacity={0.15} strokeWidth={28} />
            )}
            {seri.map((s, j) => {
              const aktif = terpilihSeri.includes(s.nama)
              const redup = terpilihSeri.length > 0 && !aktif
              return (
                <Line
                  key={s.nama}
                  type="linear"
                  dataKey={'s' + j}
                  name={s.nama}
                  stroke={warnaSeri(s.nama)}
                  strokeWidth={aktif ? 3 : 2}
                  strokeOpacity={redup ? 0.2 : 1}
                  isAnimationActive={false}
                  dot={
                    baris.length > 26 ? false : <TitikSeri warna={warnaSeri(s.nama)} redup={redup} terpilih={minggu} onKlik={(e) => onPilihSeri(s.nama, e)} />
                  }
                />
              )
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
