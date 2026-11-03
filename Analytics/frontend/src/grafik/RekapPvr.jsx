import { memo } from 'react'
import { labelBulan } from './pigt'

const skor = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

// Skor per bulan (baris) x pembuat (kolom), seperti pivot REKAP di Excel Penilaian PVR. Sel makin pekat makin tinggi skornya.
// Klik nama pembuat untuk memfilter.
function RekapPvr({ data, voucher = 'PVR', terpilih, onPilih }) {
  if (data.bulan.length === 0) return <div className="py-10 text-center text-sm text-slate-500">Belum ada {voucher} untuk filter ini</div>
  const maks = Math.max(...data.nilai.flat(), 1)
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0.5 text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left font-normal text-slate-500">Bulan</th>
            {data.pembuat.map((p) => (
              <th key={p} className="px-1 py-1 text-right font-medium">
                <button type="button" onClick={(e) => onPilih(p, e)} aria-pressed={terpilih.includes(p)}
                  className="rounded px-1 text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
                  {p}
                </button>
              </th>
            ))}
            <th className="px-2 py-1 text-right font-semibold text-slate-900">Total</th>
          </tr>
        </thead>
        <tbody>
          {data.bulan.map((b, i) => (
            <tr key={b}>
              <th className="whitespace-nowrap px-2 py-1 text-left font-medium text-slate-700">{labelBulan(b)}</th>
              {data.nilai[i].map((v, j) => {
                const kuat = v / maks
                return (
                  <td key={data.pembuat[j]} className="rounded px-2 py-1.5 text-right tabular-nums"
                    style={{ background: v ? `rgba(3, 105, 161, ${0.08 + kuat * 0.8})` : '#f8fafc', color: kuat > 0.5 ? '#fff' : '#0f172a' }}>
                    {v ? skor.format(v) : '–'}
                  </td>
                )
              })}
              <td className="px-2 py-1.5 text-right font-semibold tabular-nums text-slate-900">{skor.format(data.total_bulan[i])}</td>
            </tr>
          ))}
          <tr>
            <th className="border-t border-slate-200 px-2 py-1.5 text-left font-semibold text-slate-900">Total</th>
            {data.total_pembuat.map((v, j) => (
              <td key={data.pembuat[j]} className="border-t border-slate-200 px-2 py-1.5 text-right font-semibold tabular-nums text-slate-900">{skor.format(v)}</td>
            ))}
            <td className="border-t border-slate-200 px-2 py-1.5 text-right font-semibold tabular-nums text-slate-900">
              {skor.format(data.total_pembuat.reduce((s, v) => s + v, 0))}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

export default memo(RekapPvr)
