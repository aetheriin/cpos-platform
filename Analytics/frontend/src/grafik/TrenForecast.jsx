import { memo, useMemo, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { lintasTahun, persen, tgl, tglLengkap } from '../lib/data'
import { kgRingkas, rupiah, sumbu } from './tbs'

const WARNA_AKTUAL = '#0369a1'
const WARNA_FORECAST = '#d97706'

function Petunjuk({ active, payload, ukuran }) {
  const d = active && payload?.[0]?.payload
  if (!d) return null
  const f = ukuran === 'netto' ? kgRingkas : rupiah
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-medium text-slate-800">
        {tglLengkap(d.hari)} ({['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'][new Date(d.hari + 'T00:00:00').getDay()]})
      </div>
      {d.aktual != null && <div className="text-slate-600">Aktual: {f(d.aktual)}</div>}
      {d.forecast != null && !d.sambung && <div className="text-slate-600">Forecast: {f(d.forecast)}</div>}
      {d.rentang && !d.sambung && (
        <div className="text-slate-500">
          Kemungkinan: {f(d.rentang[0])} sampai {f(d.rentang[1])}
        </div>
      )}
    </div>
  )
}

// Garis padat: aktual harian. Garis putus-putus: forecast setelah hari aktual terakhir, disambung dari titik aktual terakhir. Pita: interval
// kepercayaan forecast (dari kesalahan forecast yang sama di minggu-minggu sebelumnya). Pilihan Netto/Nilai mengganti ukuran.
// Klik titik mana pun untuk memfilter hari itu.
function TrenForecast({ tren, forecast, terpilih, onPilih }) {
  const [ukuran, setUkuran] = useState('netto')
  const iv = forecast?.interval
  const data = useMemo(() => {
    const baris = tren.map((d) => ({ hari: d.hari, aktual: d[ukuran] }))
    if (!forecast) return baris
    const akhir = baris.find((b) => b.hari === forecast.akhir_aktual)
    if (akhir) Object.assign(akhir, { forecast: akhir.aktual, sambung: true, ...(iv && { rentang: [akhir.aktual, akhir.aktual] }) })
    const ke = (d, v) => (ukuran === 'netto' || !d.netto ? v : (v * d.nilai) / d.netto) // batas interval dalam Rp: harga sama dengan forecast-nya
    return [
      ...baris.filter((b) => b.hari <= forecast.akhir_aktual),
      ...forecast.hari.map((d) => ({ hari: d.hari, forecast: d[ukuran], ...(iv && { rentang: [ke(d, d.bawah), ke(d, d.atas)] }) })),
    ]
  }, [tren, forecast, ukuran, iv])
  const uji = forecast?.uji // forecast yang dibuat 7 hari lalu, dibandingkan dengan aktualnya (selalu dalam kg)
  const titik = (warna) => (data.length > 62 ? false : { r: 2.5, fill: warna, strokeWidth: 0 }) // rentang panjang: garis saja, titik muncul saat disorot
  const tickTgl = lintasTahun(data) ? tglLengkap : tgl
  const persenIv = iv ? `${Math.round(iv.tingkat * 100)}%` : ''

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label="Ukuran" className="inline-flex rounded-lg border border-slate-300 p-0.5">
          {[['netto', 'Netto (kg)'], ['nilai', 'Nilai (Rp)']].map(([k, nama]) => (
            <button key={k} type="button" role="radio" aria-checked={ukuran === k} onClick={() => setUkuran(k)} className={'rounded-md px-3 py-1 text-sm ' + (ukuran === k ? 'bg-sky-700 text-white' : 'text-slate-700 hover:bg-slate-100')}>
              {nama}
            </button>
          ))}
        </div>
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }} onClick={(s, e) => s?.activeLabel && data.some((d) => d.hari === s.activeLabel && d.aktual != null) && onPilih(s.activeLabel, e)} className="cursor-pointer">
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="hari" tickFormatter={tickTgl} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 10, fill: '#475569' }} minTickGap={12} />
            <YAxis width={52} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={sumbu} />
            <Tooltip content={<Petunjuk ukuran={ukuran} />} cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} />
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 11 }} />
            {iv && <Area dataKey="rentang" name={`Interval ${persenIv}`} stroke="none" fill={WARNA_FORECAST} fillOpacity={0.15} isAnimationActive={false} connectNulls={false} legendType="square" />}
            {forecast && <ReferenceLine x={forecast.akhir_aktual} stroke="#94a3b8" strokeDasharray="2 3" />}
            {terpilih.map((h) => (
              <ReferenceLine key={h} x={h} stroke={WARNA_AKTUAL} strokeWidth={2} strokeOpacity={0.35} />
            ))}
            <Line dataKey="aktual" name="Aktual" stroke={WARNA_AKTUAL} strokeWidth={2} dot={titik(WARNA_AKTUAL)} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls={false} />
            {forecast && <Line dataKey="forecast" name="Forecast" stroke={WARNA_FORECAST} strokeWidth={2} strokeDasharray="5 4" dot={titik(WARNA_FORECAST)} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls={false} />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {!forecast ? (
        <p className="mt-2 text-xs text-slate-500">Forecast butuh data minggu yang sama tahun lalu.</p>
      ) : (
        uji && (
          <p className="mt-2 text-xs text-slate-600">
            Forecast minggu lalu ({tgl(uji.mulai)}–{tgl(uji.akhir)}): {kgRingkas(uji.forecast)}, aktual {kgRingkas(uji.aktual)}{' '}
            <span className="font-medium text-slate-800">
              ({Math.abs(uji.selisih) < 0.0005 ? 'tepat' : `${persen(Math.abs(uji.selisih))} ${uji.selisih > 0 ? 'lebih tinggi' : 'lebih rendah'}`})
            </span>
            . Meleset rata-rata {persen(uji.meleset_harian)} per hari.
          </p>
        )
      )}
    </div>
  )
}

export default memo(TrenForecast)
