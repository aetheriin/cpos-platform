import { memo } from 'react'
import { CartesianGrid, Legend, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { WARNA_TARA_RINGAN, warnaRisiko } from './risiko'
import { angka } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

function PetunjukTitik({ active, payload }) {
  const t = active && payload?.[0]?.payload
  if (!t) return null
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-medium text-slate-800">{t.tiket}</div>
      <div className="text-slate-600">Kendaraan: {t.kendaraan}</div>
      <div className="text-slate-600">Durasi: {angka.format(t.durasi)} menit</div>
      <div className="text-slate-600">Selisih tara: {angka.format(t.tara)} kg</div>
    </div>
  )
}

// Durasi timbang lawan selisih tara per transaksi. Garis putus-putus = ambang WARNING; area merah = timbang lama dan tara lebih ringan.
function SebaranTara({ sebaran, indikator, ambang, terpilih, onPilih, risikoTerpilih, onPilihRisiko }) {
  if (sebaran.titik.length === 0) return <Kosong teks="Tidak ada transaksi untuk filter ini" />
  const ada = terpilih.length > 0
  let xMaks = ambang.durasi_menit * 1.2
  let yMin = -ambang.tara_kg * 1.2
  for (const t of sebaran.titik) {
    if (t.durasi > xMaks) xMaks = t.durasi
    if (t.tara < yMin) yMin = t.tara
  }
  const pilihan = sebaran.titik.filter((t) => terpilih.includes(t.tiket))
  return (
    <div>
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" dataKey="durasi" name="Durasi (menit)" domain={[0, 'auto']} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => angka.format(v)} label={{ value: 'Durasi timbang (menit)', position: 'insideBottom', offset: -12, fontSize: 11, fill: '#475569' }} />
            <YAxis type="number" dataKey="tara" name="Selisih tara (kg)" width={56} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => angka.format(v)} />
            <ReferenceArea x1={ambang.durasi_menit} x2={xMaks} y1={yMin} y2={-ambang.tara_kg} fill={WARNA_TARA_RINGAN} fillOpacity={0.06} stroke="none" ifOverflow="hidden" />
            <ReferenceLine y={0} stroke="#94a3b8" />
            <ReferenceLine y={ambang.tara_kg} stroke={warnaRisiko('tara')} strokeDasharray="4 4" />
            <ReferenceLine y={-ambang.tara_kg} stroke={warnaRisiko('tara')} strokeDasharray="4 4" />
            <ReferenceLine x={ambang.durasi_menit} stroke={warnaRisiko('durasi')} strokeDasharray="4 4" />
            <Tooltip content={<PetunjukTitik />} cursor={{ stroke: '#94a3b8' }} isAnimationActive={false} />
            <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 11, cursor: 'pointer' }} onClick={(item, _, e) => item.value && onPilihRisiko(item.value, e)} formatter={(nama) => <span style={{ opacity: risikoTerpilih.length > 0 && !risikoTerpilih.includes(nama) ? 0.4 : 1 }}>{nama}</span>} />
            {indikator.map((i) => (
              <Scatter
                key={i.kunci}
                name={i.nama}
                data={sebaran.titik.filter((t) => t.risiko === i.kunci)}
                fill={warnaRisiko(i.kunci)}
                fillOpacity={ada ? 0.15 : i.kunci === 'normal' ? 0.35 : 0.75}
                isAnimationActive={false}
                className="cursor-pointer"
                onClick={(t, _, e) => onPilih((t.payload ?? t).tiket, e)}
              />
            ))}
            {ada && (
              <Scatter data={pilihan} legendType="none" fill="#0f172a" stroke="#ffffff" strokeWidth={2} shape="circle" isAnimationActive={false} className="tinta-grafik cursor-pointer" onClick={(t, _, e) => onPilih((t.payload ?? t).tiket, e)} />
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {sebaran.ditampilkan < sebaran.total && (
        <p className="mt-1 text-xs text-slate-500">
          Menampilkan {angka.format(sebaran.ditampilkan)} dari {angka.format(sebaran.total)} transaksi (sampel merata; yang paling ekstrem dan yang dipilih selalu tampil).
        </p>
      )}
    </div>
  )
}

export default memo(SebaranTara)
