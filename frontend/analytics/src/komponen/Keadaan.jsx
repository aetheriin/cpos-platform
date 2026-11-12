// Keadaan kosong dan memuat, sama di semua laporan. Kosong mengikuti barisKosong di CPOS (ikon folder + teks).
export function Kosong({ teks }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <svg viewBox="0 0 24 24" className="h-7 w-7 text-slate-300" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />
      </svg>
      <p className="text-sm text-slate-500">{teks}</p>
    </div>
  )
}

const batang = 'block animate-pulse rounded bg-slate-400/20'

export function Memuat({ teks = 'Memuat data...' }) {
  return (
    <div role="status" className="space-y-3 py-4">
      <p className="text-sm text-slate-500">{teks}</p>
      {['w-full', 'w-11/12', 'w-4/5'].map((lebar) => (
        <span key={lebar} className={`${batang} h-3 ${lebar}`} aria-hidden="true" />
      ))}
    </div>
  )
}

// Kerangka kartu dan grafik selama laporan pertama kali diambil, supaya tidak tampil area kosong
export function MemuatLaporan({ teks = 'Memuat laporan...' }) {
  return (
    <div role="status" className="space-y-3">
      <p className="text-sm text-slate-500">{teks}</p>
      <div className="grid gap-3 sm:grid-cols-3" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-2 rounded-lg border border-slate-200 bg-white px-4 py-3">
            <span className={`${batang} h-3 w-1/2`} />
            <span className={`${batang} h-6 w-2/3`} />
          </div>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-2" aria-hidden="true">
        {[0, 1].map((i) => (
          <div key={i} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
            <span className={`${batang} h-3 w-1/3`} />
            <span className={`${batang} h-52 w-full`} />
          </div>
        ))}
      </div>
    </div>
  )
}
