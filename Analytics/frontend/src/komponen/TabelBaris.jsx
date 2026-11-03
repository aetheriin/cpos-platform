import { formatSel } from '../lib/data'

const WARNA_STATUS = {
  Open: 'bg-amber-100 text-amber-800',
  Completed: 'bg-emerald-100 text-emerald-800',
  Closed: 'bg-slate-200 text-slate-700',
  Void: 'bg-red-100 text-red-700',
  NAIK: 'bg-emerald-100 text-emerald-800',   // atensi Pembelian TBS Mingguan
  TURUN: 'bg-red-100 text-red-700',
}

// Kolom bertulisan panjang dipotong dengan titik-titik; isi lengkap ada di tooltip.
const KOLOM_PANJANG = new Set(['itemname', 'supplier_name', 'category', 'po_number'])

// onPilihBaris dan terpilih opsional: kalau ada, klik baris (atau Enter) memfilter semua grafik dan kartu.
export default function TabelBaris({ kolom, baris, urut, arah, onUrut, onPilihBaris, terpilih }) {
  return (
    <div className="max-h-[30rem] overflow-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 z-10 bg-slate-50">
          <tr>
            {kolom.map((k, i) => {
              const aktif = urut === k.kunci
              return (
                <th
                  key={k.kunci}
                  aria-sort={aktif ? (arah === 'asc' ? 'ascending' : 'descending') : 'none'}
                  className={
                    'whitespace-nowrap border-b border-slate-200 px-2 py-2 font-medium text-slate-600 ' +
                    (k.tipe === 'angka' ? 'text-right ' : 'text-left ') +
                    (i === 0 ? 'sticky left-0 z-20 bg-slate-50 ' : '')
                  }
                >
                  <button type="button" className="inline-flex items-center gap-1 hover:text-slate-900" onClick={() => onUrut(k.kunci)}>
                    {k.judul}
                    <span className="text-slate-400">{aktif ? (arah === 'asc' ? '▲' : '▼') : ''}</span>
                  </button>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {baris.map((b, n) => {
            const aktif = terpilih?.(b) ?? false
            const latar = aktif ? 'bg-sky-50' : 'bg-white'
            return (
            <tr
              key={`${b.prnumber ?? b.ticket_no}-${b.itemcode ?? ''}-${n}`}
              aria-selected={onPilihBaris ? aktif : undefined}
              tabIndex={onPilihBaris ? 0 : undefined}
              onClick={onPilihBaris ? (e) => onPilihBaris(b, e) : undefined}
              onKeyDown={onPilihBaris ? (e) => e.key === 'Enter' && onPilihBaris(b, e) : undefined}
              className={'border-b border-slate-100 ' + (aktif ? 'bg-sky-50 ' : 'hover:bg-slate-50 ') + (onPilihBaris ? 'cursor-pointer focus:outline-none focus-visible:bg-sky-50' : '')}
            >
              {kolom.map((k, i) => {
                const teks = formatSel(b[k.kunci], k.tipe)
                const kosong = teks === '–'
                const dasar =
                  'whitespace-nowrap px-2 py-1.5 tabular-nums ' +
                  (k.tipe === 'angka' ? 'text-right ' : '') +
                  (kosong ? 'text-slate-300 ' : '') +
                  (i === 0 ? `sticky left-0 z-[5] ${latar} font-medium ` : '')
                if (k.kunci === 'status' && !kosong) {
                  return (
                    <td key={k.kunci} className={dasar}>
                      <span className={'rounded-full px-2 py-0.5 ' + (WARNA_STATUS[teks] ?? 'bg-slate-100 text-slate-700')}>{teks}</span>
                    </td>
                  )
                }
                if (KOLOM_PANJANG.has(k.kunci)) {
                  return (
                    <td key={k.kunci} className={dasar + 'max-w-56 truncate'} title={kosong ? undefined : teks}>
                      {teks}
                    </td>
                  )
                }
                return (
                  <td key={k.kunci} className={dasar}>
                    {teks}
                  </td>
                )
              })}
            </tr>
            )
          })}
          {baris.length === 0 && (
            <tr>
              <td colSpan={kolom.length} className="px-2 py-8 text-center text-slate-500">
                Tidak ada baris yang cocok dengan filter ini.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
