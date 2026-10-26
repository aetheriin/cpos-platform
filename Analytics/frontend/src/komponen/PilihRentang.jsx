// Tombol bersebelahan untuk memilih satu dari beberapa pintasan (mis. 7 hari, 30 hari, Semua). opsi: [{ nilai, label, judul }].
export default function PilihRentang({ opsi, nilai, onUbah, label = 'Rentang tren' }) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full flex-wrap rounded-md border border-slate-200 bg-white p-0.5 text-xs">
      {opsi.map((o) => {
        const aktif = o.nilai === nilai
        return (
          <button
            key={String(o.nilai)}
            type="button"
            title={o.judul}
            aria-pressed={aktif}
            onClick={() => !aktif && onUbah(o.nilai)}
            className={
              'rounded px-2 py-1 whitespace-nowrap tabular-nums ' + (aktif ? 'bg-sky-50 font-medium text-sky-800' : 'text-slate-600 hover:bg-slate-100')
            }
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
