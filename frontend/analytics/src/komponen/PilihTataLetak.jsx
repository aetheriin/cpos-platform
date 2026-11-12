import { useTataLetak } from '../lib/tampilan'

const PILIHAN = [
  {
    kunci: 'padat',
    label: 'Padat',
    ikon: (
      <>
        <rect x="2.5" y="2.5" width="6.5" height="4.5" rx="1" />
        <rect x="11" y="2.5" width="2.5" height="4.5" rx="1" />
        <rect x="2.5" y="9" width="4" height="4.5" rx="1" />
        <rect x="8.5" y="9" width="5" height="4.5" rx="1" />
      </>
    ),
  },
  {
    kunci: 'panjang',
    label: 'Memanjang',
    ikon: (
      <>
        <rect x="2.5" y="2.5" width="11" height="4.5" rx="1" />
        <rect x="2.5" y="9" width="11" height="4.5" rx="1" />
      </>
    ),
  },
]

// Sakelar dua posisi di kepala dashboard untuk memilih tata letak grafik.
export default function PilihTataLetak() {
  const [tata, setTata] = useTataLetak()
  return (
    <div role="radiogroup" aria-label="Tata letak" className="inline-flex shrink-0 rounded-lg border border-slate-200 bg-white p-0.5">
      {PILIHAN.map(({ kunci, label, ikon }) => {
        const aktif = tata === kunci
        return (
          <button
            key={kunci}
            type="button"
            role="radio"
            aria-checked={aktif}
            onClick={() => setTata(kunci)}
            className={
              'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
              (aktif ? 'bg-slate-100 font-medium text-slate-900' : 'text-slate-500 hover:text-slate-800')
            }
          >
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
              {ikon}
            </svg>
            {label}
          </button>
        )
      })}
    </div>
  )
}
