import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka } from '../lib/data'
import { LEGENDA } from './legenda'
import { ANIMASI, DURASI_ANIMASI } from './animasi'
import { Kosong } from '../komponen/Keadaan'

// Warna teks mengikuti tema lewat currentColor
const sumbu = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: 'currentColor' } }
const persen = new Intl.NumberFormat('id-ID', { style: 'percent', maximumFractionDigits: 1 })
const persenBulat = new Intl.NumberFormat('id-ID', { style: 'percent', maximumFractionDigits: 0 })
const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const WARNA_PO = '#0284c7'
const WARNA_NILAI = '#ea580c'

export const rupiahPendek = (v) => (v >= 1e9 ? `${satu.format(v / 1e9)} M` : v >= 1e6 ? `${satu.format(v / 1e6)} jt` : angka.format(Math.round(v)))

// '10JT - 50JT' menjadi '10-50 jt' supaya label tidak bertabrakan di petak sempit
const labelPendek = (k) => k.replace('JT - ', '-').replace('JT', ' jt')

function Kanvas({ kosong = false, children }) {
  if (kosong) return <Kosong teks="Tidak ada PO pada periode dan filter ini" />
  return <div className="h-64 text-slate-700"><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>
}

// Batang PO dan garis nilai per kategori, seperti TOTAL PO VS TOTAL NET PO (%) di Excel. Satu sumbu karena keduanya persen.
export function PoNilaiPersen({ data, onPilih }) {
  return (
    <Kanvas kosong={data.length === 0}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }} onClick={(e) => e?.activeLabel && onPilih?.(e.activeLabel, e)}>
        <CartesianGrid vertical={false} stroke="#94a3b8" strokeOpacity={0.25} />
        <XAxis dataKey="nama" {...sumbu} interval={0} tickFormatter={labelPendek} />
        <YAxis {...sumbu} width={48} tickFormatter={persenBulat.format} />
        <Tooltip formatter={(v, n) => [persen.format(v), n]} />
        <Legend {...LEGENDA} />
        <Bar isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} dataKey="pct_po" name="% PO" fill={WARNA_PO} maxBarSize={72} cursor="pointer" />
        <Line isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} dataKey="pct_nilai" name="% nilai PO" stroke={WARNA_NILAI} strokeWidth={3} dot={{ r: 4 }} />
      </ComposedChart>
    </Kanvas>
  )
}

// Jumlah PO dan nilainya, seperti TOTAL PO VS TOTAL NET PO di Excel. Satuan berbeda, jadi dua sumbu; nilai diringkas supaya sumbu kanan sempit.
export function PoNilai({ data, onPilih }) {
  return (
    <Kanvas kosong={data.length === 0}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} onClick={(e) => e?.activeLabel && onPilih?.(e.activeLabel, e)}>
        <CartesianGrid yAxisId="po" vertical={false} stroke="#94a3b8" strokeOpacity={0.25} />
        <XAxis dataKey="nama" {...sumbu} interval={0} tickFormatter={labelPendek} />
        <YAxis yAxisId="po" {...sumbu} width={56} tickFormatter={angka.format} />
        <YAxis yAxisId="nilai" orientation="right" {...sumbu} width={64} tickFormatter={rupiahPendek} />
        <Tooltip formatter={(v, n) => [n === 'PO' ? angka.format(v) : `Rp ${angka.format(Math.round(v))}`, n]} />
        <Legend {...LEGENDA} />
        <Bar isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} yAxisId="po" dataKey="po" name="PO" fill={WARNA_PO} maxBarSize={72} cursor="pointer" />
        <Line isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} yAxisId="nilai" dataKey="nilai" name="Nilai PO" stroke={WARNA_NILAI} strokeWidth={3} dot={{ r: 4 }} />
      </ComposedChart>
    </Kanvas>
  )
}

// Tahun lama pudar, tahun terbaru paling kuat
// Tiap tahun minimal kontras 3:1 di latar putih; tahun berjalan oranye supaya menonjol
const WARNA_TAHUN = ['#64748b', '#0f766e', '#0284c7', '#1e3a8a', '#ea580c']
const warnaTahun = (i, n) => WARNA_TAHUN[WARNA_TAHUN.length - n + i] ?? WARNA_TAHUN[0]

// Satu kelompok batang per bulan, satu batang per tahun. ukuran: 'po' atau 'nilai'.
export function BandingTahun({ data, ukuran, format }) {
  const { tahun, baris } = data
  return (
    <Kanvas kosong={baris.length === 0}>
      <BarChart data={baris} barGap={1} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#94a3b8" strokeOpacity={0.25} />
        <XAxis dataKey="bulan" {...sumbu} interval={0} />
        <YAxis {...sumbu} width={64} tickFormatter={format} />
        <Tooltip formatter={(v, n) => [format(v), n]} cursor={{ fill: 'rgba(100,116,139,.1)' }} />
        <Legend {...LEGENDA} />
        {tahun.map((y, i) => <Bar isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} key={y} dataKey={`${ukuran}_${y}`} name={y} fill={warnaTahun(i, tahun.length)} />)}
      </BarChart>
    </Kanvas>
  )
}

// Satu garis bulan berjalan untuk kategori yang dipilih
export function SeriBulan({ data, kunci, nama, format }) {
  return (
    <Kanvas kosong={data.length === 0}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" {...sumbu} minTickGap={32} />
        <YAxis {...sumbu} width={64} tickFormatter={format} />
        <Tooltip formatter={(v) => [format(v), nama]} />
        <Line isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} dataKey={kunci} stroke={WARNA_PO} strokeWidth={2.5} dot={false} />
      </LineChart>
    </Kanvas>
  )
}

export const formatPersen = persen.format
