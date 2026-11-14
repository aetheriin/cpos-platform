import { memo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'
import { namaHariSingkat, tglPanjang } from '../laporan/tiket_penjualan/periode'

const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const ringkas = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
const tonPenuh = (kg) => `${satu.format(kg / 1000)} ton`
const BATAS_LABEL = 8 // label nilai di atas batang hanya kalau batangnya sedikit (seminggu)

function label(satuan, kunci, jumlah) {
  if (satuan === 'jam') return kunci
  const hari = Number(kunci.slice(8, 10))
  return jumlah <= 7 ? `${namaHariSingkat(kunci)} ${hari}` : String(hari)
}

function IsiTooltip({ active, payload, satuan }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const judul = satuan === 'jam' ? `Jam ${d.kunci}.00–${d.kunci}.59` : tglPanjang(d.kunci, { hari: true })
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-900">{judul}</p>
      <p className="mt-0.5 tabular-nums text-slate-700">
        {tonPenuh(d.netto)} · {angka.format(d.rit)} pengiriman
      </p>
    </div>
  )
}

// Berat keluar per jam (satu hari) atau per tanggal (satu minggu atau bulan). Klik batang untuk memfilter jam atau tanggal itu.
function SebaranWaktu({ satuan, data, terpilih, onPilih, warna = '#0369a1' }) {
  if (data.every((d) => d.rit === 0)) return <Kosong teks="Tidak ada tiket untuk filter ini" />
  const baris = data.map((d) => ({ ...d, label: label(satuan, d.kunci, data.length), ton: d.netto / 1000 }))
  const adaPilihan = terpilih.length > 0
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={baris} margin={{ top: data.length <= BATAS_LABEL ? 22 : 10, right: 8, bottom: 0, left: 0 }} barCategoryGap="18%">
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="label" interval={0} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} />
          <YAxis width={44} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => ringkas.format(v)} />
          <Tooltip content={<IsiTooltip satuan={satuan} />} cursor={{ fill: 'rgba(15,23,42,0.05)' }} />
          <Bar dataKey="ton" radius={[3, 3, 0, 0]} isAnimationActive={false} className="cursor-pointer" onClick={(d, _, e) => onPilih((d.payload ?? d).kunci, e)}>
            {baris.map((d) => {
              const redup = adaPilihan && !terpilih.includes(d.kunci)
              return <Cell key={d.kunci} fill={warna} fillOpacity={redup ? 0.25 : 0.9} />
            })}
            {data.length <= BATAS_LABEL && (
              <LabelList dataKey="ton" position="top" fontSize={11} fill="#334155" formatter={(v) => (v > 0 ? satu.format(v) : '')} />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default memo(SebaranWaktu)
