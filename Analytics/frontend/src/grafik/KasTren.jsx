import { memo } from 'react'
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, lintasTahun, tgl, tglLengkap } from '../lib/data'
import { sumbuUang, uangPenuh, uangRingkas, WARNA_KELUAR, WARNA_MASUK } from './kas'

const NAMA_BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const sumbu = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: '#64748b' } }
// Garis: kontras di latar terang maupun gelap, dan berbeda dari batang debit (biru) dan credit (oranye)
const WARNA_SALDO = '#16a34a'
const WARNA_TD = '#db2777'
const labelBulan = (b) => `${NAMA_BULAN[Number(b.slice(5, 7)) - 1]} ${b.slice(2, 4)}`

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
const garis = (warna, putus) => (putus ? { width: 16, borderTop: `2px dashed ${warna}` } : { width: 16, height: 2, background: warna })

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

// Balance (garis, sumbu kiri) dengan debit dan credit per periode (batang, sumbu kanan). Harian: ditambah forecast beberapa hari
// ke depan; klik tanggal untuk memfilter laporan. Bulanan (rentang panjang): ending balance tiap bulan.
export const SaldoBerjalan = memo(function SaldoBerjalan({ running, bulanan, periode, satuan, terpilih = [], onPilih }) {
  const harian = periode === 'hari'
  const sumber = harian ? running : bulanan
  if (sumber.length === 0) return kosong
  const label = harian ? (lintasTahun(running) ? tglLengkap : tgl) : labelBulan
  const data = sumber.map((r) => {
    const debit = r.debit ?? r.masuk
    const kredit = r.kredit ?? r.keluar
    return { ...r, label: label(harian ? r.hari : r.bulan), debit, kredit, kreditNeg: kredit ? -kredit : null, pita: r.bawah != null ? [r.bawah, r.atas] : null }
  })
  const proyeksi = harian && data.some((d) => d.ramal != null)
  const klik = (st, e) => {
    const d = data[Number(st?.activeTooltipIndex)]
    if (harian && onPilih && d?.saldo != null) onPilih(d.hari, e)
  }
  return (
    <div className="flex h-full flex-col">
      <Kunci isi={[
        ['Balance', garis(WARNA_SALDO)], ['Debit', kotak(WARNA_MASUK)], ['Credit', kotak(WARNA_KELUAR)],
        ...(proyeksi ? [['Forecast', garis(WARNA_SALDO, true)]] : []),
      ]} />
      <div className="min-h-64 w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} stackOffset="sign" margin={{ top: 6, right: 0, bottom: 0, left: 0 }} onClick={klik}
            className={harian && onPilih ? 'cursor-pointer' : undefined}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-slate-200)" />
            <XAxis dataKey="label" {...sumbu} tick={{ fontSize: 10, fill: '#64748b' }} minTickGap={12} />
            <YAxis yAxisId="saldo" width={56} {...sumbu} tickFormatter={sumbuUang} domain={['auto', 'auto']} />
            <YAxis yAxisId="arus" orientation="right" width={52} {...sumbu} tickFormatter={sumbuUang} />
            <Tooltip cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} content={({ active, payload }) => {
              const d = active && payload?.[0]?.payload
              if (!d) return null
              return <KotakInfo judul={harian ? tglLengkap(d.hari) : d.label} baris={d.saldo != null
                ? [['Debit', uangPenuh(d.debit, satuan)], ['Credit', uangPenuh(d.kredit, satuan)], ['Ending balance', uangPenuh(d.saldo, satuan)]]
                : [['Forecast', uangPenuh(d.ramal, satuan)], ['Batas bawah', uangPenuh(d.bawah, satuan)], ['Batas atas', uangPenuh(d.atas, satuan)]]} />
            }} />
            <Bar yAxisId="arus" dataKey="debit" stackId="arus" fill={WARNA_MASUK} maxBarSize={harian ? 14 : 28} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.label} fillOpacity={harian ? redup(terpilih, d.hari) : 1} />)}
            </Bar>
            <Bar yAxisId="arus" dataKey="kreditNeg" stackId="arus" fill={WARNA_KELUAR} maxBarSize={harian ? 14 : 28} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.label} fillOpacity={harian ? redup(terpilih, d.hari) : 1} />)}
            </Bar>
            {proyeksi && <Area yAxisId="saldo" dataKey="pita" stroke="none" fill={WARNA_SALDO} fillOpacity={0.12} isAnimationActive={false} />}
            <Line yAxisId="saldo" dataKey="saldo" stroke={WARNA_SALDO} strokeWidth={2.5} dot={!harian && { r: 3, fill: WARNA_SALDO }} isAnimationActive={false} />
            {proyeksi && <Line yAxisId="saldo" dataKey="ramal" stroke={WARNA_SALDO} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {proyeksi && <p className="mt-1 text-xs text-slate-500">Forecast: tren linier 60 hari terakhir; area = rentang 95%.</p>}
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
        <span className="text-xs tabular-nums text-slate-600">{uangRingkas(data.at(-1).kredit_td, satuan)}</span>
      </div>
      <div className="min-h-56 w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-slate-200)" />
            <XAxis dataKey="label" {...sumbu} tick={{ fontSize: 10, fill: '#64748b' }} minTickGap={12} />
            <YAxis yAxisId="periode" width={52} {...sumbu} tickFormatter={sumbuUang} />
            <YAxis yAxisId="td" orientation="right" width={52} {...sumbu} tickFormatter={sumbuUang} domain={['auto', 'auto']} />
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
          <BarChart data={dokumen} layout="vertical" margin={{ top: 4, right: 20, bottom: 0, left: 0 }} barGap={1} className="cursor-pointer"
            onClick={(st, e) => { const d = dokumen[Number(st?.activeTooltipIndex)]; if (d && onPilih) onPilih(d.jenis, e) }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-slate-200)" />
            <XAxis type="number" {...sumbu} tickFormatter={sumbuUang} />
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
