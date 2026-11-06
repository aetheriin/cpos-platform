// Sama dengan tombol Excel laporan TBS di CPOS (.btn-secondary, kecil: .btn-sm)
export default function TombolExcel({ sibuk = false, kecil = false, ...sisa }) {
  return (
    <button
      type="button"
      aria-busy={sibuk}
      className={'inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 ' + (kecil ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm')}
      {...sisa}
    >
      <svg viewBox="0 0 24 24" height="1.1em" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-600" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="m9.5 12.5 5 5m0-5-5 5" />
      </svg>
      {sibuk ? 'Menyiapkan...' : 'Excel'}
    </button>
  )
}
