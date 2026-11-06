import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, potong, teratas } from '../lib/data'
import { useTataLetak } from '../lib/tampilan'
import { WARNA } from './warna'
import { Kosong } from '../komponen/Keadaan'

export default function KategoriOutstandingChart({ daftar, terpilih = [], onPilih }) {
  const padat = useTataLetak()[0] === 'padat'
  const data = teratas(daftar, 10, terpilih, 'kategori')

  if (data.length === 0) {
    return <Kosong teks="Tidak ada outstanding untuk filter ini" />
  }

  const opasitas = (kategori) => (terpilih.length > 0 && !terpilih.includes(kategori) ? 0.3 : 1)
  // Tata letak padat: baris lebih rapat dan label lebih sempit supaya tingginya mendekati grafik di sebelahnya
  const tebal = padat ? 8 : 12

  return (
    <div className="w-full" style={{ height: data.length * (padat ? 28 : 46) + 60 }}>
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
            width={padat ? 140 : 180}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: '#475569' }}
            tickFormatter={(v) => potong(v, padat ? 22 : 28)}
          />
          <Tooltip formatter={(v) => angka.format(v)} cursor={{ fill: 'rgba(14,165,233,0.08)' }} />
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
