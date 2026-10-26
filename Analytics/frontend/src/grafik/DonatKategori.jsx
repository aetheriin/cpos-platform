import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { angka, itemDonat, potong } from '../lib/data'

const persen = (x) => `${(x * 100).toFixed(0)}%`

export default function DonatKategori({ daftar, terpilih = [], onPilih, satuan }) {
  const { item, total } = itemDonat(daftar, 5, terpilih)

  if (total === 0) {
    return <div className="py-10 text-center text-sm text-slate-500">Tidak ada data untuk filter ini</div>
  }

  const redup = (d) => terpilih.length > 0 && !d.lainnya && !terpilih.includes(d.kategori)
  const klik = (d, e) => {
    if (d && !d.lainnya) onPilih(d.kategori, e)
  }

  return (
    <div>
      <div className="relative mx-auto h-52 w-full max-w-xs">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={item}
              dataKey="jumlah"
              nameKey="kategori"
              innerRadius="62%"
              outerRadius="90%"
              paddingAngle={2}
              stroke="none"
              isAnimationActive={false}
              className="cursor-pointer"
              onClick={(_, i, e) => klik(item[i], e)}
            >
              {item.map((d) => (
                <Cell key={d.kategori} fill={d.warna} fillOpacity={redup(d) ? 0.3 : 1} />
              ))}
            </Pie>
            <Tooltip formatter={(v, nama) => [`${angka.format(v)} (${persen(v / total)})`, nama]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-2xl font-semibold tabular-nums">{angka.format(total)}</div>
          <div className="text-xs text-slate-500">{satuan}</div>
        </div>
      </div>

      <ul className="mt-2 space-y-1">
        {item.map((d) => (
          <li key={d.kategori}>
            <button
              type="button"
              disabled={d.lainnya}
              onClick={(e) => klik(d, e)}
              className={
                'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs enabled:hover:bg-slate-50 ' +
                (redup(d) ? 'opacity-40 ' : '') +
                (terpilih.includes(d.kategori) ? 'bg-sky-50 font-medium ' : '') +
                (d.lainnya ? 'cursor-default' : 'cursor-pointer')
              }
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: d.warna }} />
              <span className="min-w-0 flex-1 truncate" title={d.kategori}>
                {potong(d.kategori, 34)}
              </span>
              <span className="tabular-nums text-slate-600">
                {angka.format(d.jumlah)} · {persen(d.jumlah / total)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
