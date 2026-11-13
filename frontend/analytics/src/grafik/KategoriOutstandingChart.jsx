import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, potong, teratas } from '../lib/data'
import { useTataLetak } from '../lib/tampilan'
import { WARNA } from './warna'
import { Kosong } from '../komponen/Keadaan'

const BARIS_MAKS = 2
const LEBAR_HURUF = 6.2   // perkiraan lebar satu huruf pada ukuran 11 px
// Nilai "(kosong)" tetap dipakai untuk filter; yang tampil "Tanpa kategori"
const tampil = (kategori) => (kategori === '(kosong)' ? 'Tanpa kategori' : kategori)

// Pecah label per kata menjadi paling banyak BARIS_MAKS baris; baris terakhir baru dipotong kalau masih kepanjangan
function bungkus(teks, perBaris) {
  const baris = []
  let kini = ''
  for (const kata of teks.split(/\s+/)) {
    if (!kini) kini = kata
    else if ((kini + ' ' + kata).length <= perBaris) kini += ' ' + kata
    else {
      baris.push(kini)
      kini = kata
    }
  }
  if (kini) baris.push(kini)
  if (baris.length <= BARIS_MAKS) return baris.map((b) => potong(b, perBaris))
  return [...baris.slice(0, BARIS_MAKS - 1), potong(baris.slice(BARIS_MAKS - 1).join(' '), perBaris)]
}

// Label kategori: dibungkus dua baris supaya nama panjang tetap terbaca, nama lengkap muncul saat disorot, klik untuk memfilter
function TickKategori({ x, y, payload, perBaris, terpilih, onPilih }) {
  const nilai = String(payload.value)
  const baris = bungkus(tampil(nilai), perBaris)
  const aktif = terpilih.includes(nilai)
  return (
    <g transform={`translate(${x},${y})`} style={{ cursor: 'pointer' }} onClick={(e) => onPilih(nilai, e)}>
      <title>{tampil(nilai)}</title>
      <text x={-6} y={0} textAnchor="end" fontSize={11} fill={aktif ? '#0f172a' : '#475569'} fontWeight={aktif ? 600 : 400}
        opacity={terpilih.length > 0 && !aktif ? 0.45 : 1}>
        {baris.map((b, i) => (
          <tspan key={i} x={-6} dy={i === 0 ? (baris.length > 1 ? -2 : 4) : 12}>{b}</tspan>
        ))}
      </text>
    </g>
  )
}

export default function KategoriOutstandingChart({ daftar, terpilih = [], onPilih }) {
  const padat = useTataLetak()[0] === 'padat'
  const data = teratas(daftar, 10, terpilih, 'kategori')

  if (data.length === 0) {
    return <Kosong teks="Tidak ada outstanding untuk filter ini" />
  }

  const opasitas = (kategori) => (terpilih.length > 0 && !terpilih.includes(kategori) ? 0.3 : 1)
  // Tata letak padat: baris lebih rapat dan label lebih sempit supaya tingginya mendekati grafik di sebelahnya
  const tebal = padat ? 8 : 12
  const lebarLabel = padat ? 140 : 180
  const perBaris = Math.floor((lebarLabel - 8) / LEBAR_HURUF)
  const duaBaris = data.some((d) => tampil(d.kategori).length > perBaris)
  const tinggiBaris = padat ? (duaBaris ? 36 : 28) : 46

  return (
    <div className="w-full" style={{ height: data.length * tinggiBaris + 60 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 0 }} barGap={0} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: '#475569' }}
            tickFormatter={(v) => angka.format(v)}
          />
          <YAxis
            type="category"
            dataKey="kategori"
            width={lebarLabel}
            interval={0}
            tickLine={false}
            axisLine={false}
            tick={<TickKategori perBaris={perBaris} terpilih={terpilih} onPilih={onPilih} />}
          />
          <Tooltip formatter={(v) => angka.format(v)} labelFormatter={tampil} cursor={{ fill: 'rgba(14,165,233,0.08)' }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          <Bar dataKey="outstanding_awal" name="Outstanding awal" fill={WARNA.awal} barSize={tebal} radius={[0, 3, 3, 0]} className="cursor-pointer" onClick={(_, i, e) => onPilih(data[i].kategori, e)}>
            {data.map((d) => (
              <Cell key={d.kategori} fillOpacity={opasitas(d.kategori)} />
            ))}
          </Bar>
          <Bar dataKey="outstanding_akhir" name="Outstanding akhir" fill={WARNA.akhir} barSize={tebal} radius={[0, 3, 3, 0]} className="cursor-pointer" onClick={(_, i, e) => onPilih(data[i].kategori, e)}>
            {data.map((d) => (
              <Cell key={d.kategori} fillOpacity={opasitas(d.kategori)} />
            ))}
            <LabelList dataKey="outstanding_akhir" position="right" fontSize={11} fill="#334155" formatter={(v) => angka.format(v)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
