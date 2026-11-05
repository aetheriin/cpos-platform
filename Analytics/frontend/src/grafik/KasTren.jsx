import { memo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, lintasTahun, tgl, tglLengkap } from '../lib/data'
import { sumbuUang, uangPenuh, WARNA_KELUAR, WARNA_MASUK } from './kas'

const NAMA_BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const sumbu = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: '#64748b' } }
// Garis: kontras di latar terang maupun gelap, dan berbeda dari batang debit (biru) dan credit (oranye)
const WARNA_SALDO = '#16a34a'
const WARNA_TD = '#db2777'
const labelBulan = (b) => `${NAMA_BULAN[Number(b.slice(5, 7)) - 1]} ${b.slice(2, 4)}`
// Lebar sumbu mengikuti angka terbesar di data, dengan cadangan karena tick bisa dibulatkan ke atas, supaya angka lengkap tidak terpotong
const lebarSumbu = (data, ...kunci) => {
  const nilai = data.flatMap((d) => kunci.map((k) => d[k] ?? 0))
  const minus = nilai.some((v) => v < 0) ? 1 : 0
  return Math.max(56, (sumbuUang(Math.max(...nilai.map(Math.abs), 1) * 1.5).length + minus) * 7 + 12)
}

// Pilihan Harian / Bulanan untuk grafik deret waktu (hanya ditampilkan kalau rentangnya lebih dari sebulan)
export function PilihPeriode({ nilai, onUbah }) {
  return (
    <div role="radiogroup" aria-label="Periode grafik" className="inline-flex gap-0.5 rounded-md bg-slate-100 p-0.5">
      {[['hari', 'Harian'], ['bulan', 'Bulanan']].map(([k, nama]) => (
        <button key={k} type="button" role="radio" aria-checked={nilai === k} onClick={() => onUbah(k)}
          className={'rounded px-2 py-0.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
            (nilai === k ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-800')}>
          {nama}
        </button>
      ))}
    </div>
  )
}

function Kunci({ isi }) {
  return (
    <div className="mb-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
      {isi.map(([nama, gaya]) => (
        <span key={nama} className="inline-flex items-center gap-1.5">
          <span className="inline-block" style={gaya} />
          {nama}
        </span>
      ))}
    </div>
  )
}

const kotak = (warna) => ({ width: 10, height: 10, borderRadius: 2, background: warna })
const garis = (warna) => ({ width: 16, height: 2, background: warna })

function KotakInfo({ judul, baris }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-sm">
      <div className="mb-0.5 font-medium text-slate-900">{judul}</div>
      {baris.filter(([, v]) => v != null).map(([nama, v]) => (
        <div key={nama} className="flex justify-between gap-4 tabular-nums text-slate-600"><span>{nama}</span><span>{v}</span></div>
      ))}
    </div>
  )
}

const kosong = <div className="py-10 text-center text-sm text-slate-500">Tidak ada data</div>
const redup = (terpilih, nilai) => (terpilih.length && !terpilih.includes(nilai) ? 0.3 : 1)

// Ending balance (garis, sumbu kiri) dengan debit dan credit (batang, sumbu kanan) per bulan.
export const SaldoBerjalan = memo(function SaldoBerjalan({ bulanan, satuan }) {
  if (bulanan.length === 0) return kosong
  const data = bulanan.map((r) => ({ ...r, label: labelBulan(r.bulan), kreditNeg: r.kredit ? -r.kredit : null }))
  return (
    <div className="flex h-full flex-col">
      <Kunci isi={[['Balance', garis(WARNA_SALDO)], ['Debit', kotak(WARNA_MASUK)], ['Credit', kotak(WARNA_KELUAR)]]} />
      <div className="min-h-64 w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} stackOffset="sign" margin={{ top: 6, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-slate-200)" />
            <XAxis dataKey="label" {...sumbu} />
            <YAxis yAxisId="saldo" width={lebarSumbu(data, 'saldo')} {...sumbu} tickFormatter={sumbuUang} domain={['auto', 'auto']} />
            <YAxis yAxisId="arus" orientation="right" width={lebarSumbu(data, 'debit', 'kreditNeg')} {...sumbu} tickFormatter={sumbuUang} />
            <Tooltip cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} content={({ active, payload }) => {
              const d = active && payload?.[0]?.payload
              if (!d) return null
              return <KotakInfo judul={d.label} baris={[['Debit', uangPenuh(d.debit, satuan)], ['Credit', uangPenuh(d.kredit, satuan)], ['Ending balance', uangPenuh(d.saldo, satuan)]]} />
            }} />
            <Bar yAxisId="arus" dataKey="debit" stackId="arus" fill={WARNA_MASUK} maxBarSize={36} isAnimationActive={false} />
            <Bar yAxisId="arus" dataKey="kreditNeg" stackId="arus" fill={WARNA_KELUAR} maxBarSize={36} isAnimationActive={false} />
            <Line yAxisId="saldo" dataKey="saldo" stroke={WARNA_SALDO} strokeWidth={2.5} dot={{ r: 3, fill: WARNA_SALDO }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})

// Credit per periode (batang) dan credit to date (garis, sumbu kanan), dijumlahkan sejak awal data.
export const KreditToDate = memo(function KreditToDate({ harian, bulanan, periode, satuan }) {
  const perHari = periode === 'hari'
  const sumber = perHari ? harian : bulanan
  if (sumber.length === 0) return kosong
  const label = perHari ? (lintasTahun(harian) ? tglLengkap : tgl) : labelBulan
  const data = sumber.map((b) => ({ ...b, label: label(perHari ? b.hari : b.bulan) }))
  return (
    <div className="flex h-full flex-col">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <Kunci isi={[['Credit', kotak(WARNA_KELUAR)], ['Credit to date', garis(WARNA_TD)]]} />
        <span className="text-xs tabular-nums text-slate-600">{uangPenuh(data.at(-1).kredit_td, satuan)}</span>
      </div>
      <div className="min-h-56 w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-slate-200)" />
            <XAxis dataKey="label" {...sumbu} tick={{ fontSize: 10, fill: '#64748b' }} minTickGap={12} />
            <YAxis yAxisId="periode" width={lebarSumbu(data, 'kredit')} {...sumbu} tickFormatter={sumbuUang} />
            <YAxis yAxisId="td" orientation="right" width={lebarSumbu(data, 'kredit_td')} {...sumbu} tickFormatter={sumbuUang} domain={['auto', 'auto']} />
            <Tooltip cursor={{ fill: 'rgba(100,116,139,0.08)' }} content={({ active, payload }) => {
              const d = active && payload?.[0]?.payload
              if (!d) return null
              return <KotakInfo judul={perHari ? tglLengkap(d.hari) : d.label} baris={[
                ['Credit', uangPenuh(d.kredit, satuan)], ['Credit to date', uangPenuh(d.kredit_td, satuan)]]} />
            }} />
            <Bar yAxisId="periode" dataKey="kredit" fill={WARNA_KELUAR} radius={[2, 2, 0, 0]} maxBarSize={perHari ? 14 : 28} isAnimationActive={false} />
            <Line yAxisId="td" dataKey="kredit_td" stroke={WARNA_TD} strokeWidth={2.5} dot={!perHari && { r: 3, fill: WARNA_TD }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})

// Debit dan credit per jenis dokumen (batang mendatar). Klik untuk memfilter laporan ke jenis itu.
export const JenisDokumen = memo(function JenisDokumen({ dokumen, satuan, terpilih = [], onPilih }) {
  if (dokumen.length === 0) return kosong
  const tinggi = Math.max(160, dokumen.length * 38 + 30)
  return (
    <div className="flex h-full flex-col">
      <Kunci isi={[['Debit', kotak(WARNA_MASUK)], ['Credit', kotak(WARNA_KELUAR)]]} />
      <div className="w-full flex-1" style={{ minHeight: tinggi }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={dokumen} layout="vertical" margin={{ top: 4, right: 44, bottom: 0, left: 0 }} barGap={1} className="cursor-pointer"
            onClick={(st, e) => { const d = dokumen[Number(st?.activeTooltipIndex)]; if (d && onPilih) onPilih(d.jenis, e) }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-slate-200)" />
            <XAxis type="number" {...sumbu} tickFormatter={sumbuUang} minTickGap={24} />
            <YAxis type="category" dataKey="jenis" width={150} {...sumbu} />
            <Tooltip cursor={{ fill: 'rgba(100,116,139,0.08)' }} content={({ active, payload }) => {
              const d = active && payload?.[0]?.payload
              if (!d) return null
              return <KotakInfo judul={d.jenis} baris={[['Debit', uangPenuh(d.debit, satuan)], ['Credit', uangPenuh(d.kredit, satuan)],
                ['Jumlah transaksi', angka.format(d.jumlah)]]} />
            }} />
            <Bar dataKey="debit" fill={WARNA_MASUK} maxBarSize={12} isAnimationActive={false}>
              {dokumen.map((d) => <Cell key={d.jenis} fillOpacity={redup(terpilih, d.jenis)} />)}
            </Bar>
            <Bar dataKey="kredit" fill={WARNA_KELUAR} maxBarSize={12} isAnimationActive={false}>
              {dokumen.map((d) => <Cell key={d.jenis} fillOpacity={redup(terpilih, d.jenis)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})
