import { memo } from 'react'
import { angka, persen } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

// Operator x jam masuk. Isi sel: jumlah transaksi WARNING; warna makin pekat makin tinggi persentase berisikonya. Sel kosong: tidak ada transaksi.
// Klik sel memfilter operator dan jam itu; klik nama operator atau jam memfilter itu saja.
function PetaOperatorJam({ data, operatorTerpilih, jamTerpilih, onPilihSel, onPilihOperator, onPilihJam }) {
  if (data.operator.length === 0) return <Kosong teks="Tidak ada transaksi dengan jam masuk untuk filter ini" />
  const sel = new Map(data.sel.map((s) => [`${s.operator}|${s.jam}`, s]))
  const ada = operatorTerpilih.length > 0 || jamTerpilih.length > 0
  const dipilih = (o, j) => (!operatorTerpilih.length || operatorTerpilih.includes(o)) && (!jamTerpilih.length || jamTerpilih.includes(j))
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0.5 text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-white" />
            {data.jam.map((j) => (
              <th key={j} scope="col" className="min-w-8 p-0 font-normal">
                <button type="button" onClick={(e) => onPilihJam(j, e)} className={'w-full rounded px-1 py-1 tabular-nums hover:bg-slate-100 ' + (jamTerpilih.includes(j) ? 'font-semibold text-slate-900' : 'text-slate-500')}>
                  {j}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.operator.map((o) => (
            <tr key={o}>
              <th scope="row" className="sticky left-0 z-10 bg-white p-0 text-left font-normal">
                <button type="button" onClick={(e) => onPilihOperator(o, e)} className={'w-full max-w-40 truncate rounded px-2 py-1 text-left hover:bg-slate-100 ' + (operatorTerpilih.includes(o) ? 'font-semibold text-slate-900' : 'text-slate-700')}>
                  {o}
                </button>
              </th>
              {data.jam.map((j) => {
                const s = sel.get(`${o}|${j}`)
                if (!s) return <td key={j} className="rounded bg-slate-50" />
                const porsi = s.berisiko / s.total
                return (
                  <td key={j} className="p-0">
                    <button
                      type="button"
                      onClick={(e) => onPilihSel(o, j, e)}
                      title={`${o}, jam ${j}.00: ${angka.format(s.berisiko)} WARNING dari ${angka.format(s.total)} transaksi (${persen(porsi)})`}
                      aria-label={`${o} jam ${j}: ${s.berisiko} WARNING dari ${s.total} transaksi`}
                      className="h-7 w-full rounded tabular-nums"
                      style={{
                        background: `rgba(234, 88, 12, ${0.08 + porsi * 0.82})`,
                        color: porsi > 0.8 ? '#ffffff' : 'var(--color-slate-700)',
                        opacity: ada && !dipilih(o, j) ? 0.3 : 1,
                      }}
                    >
                      {s.berisiko || ''}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default memo(PetaOperatorJam)
