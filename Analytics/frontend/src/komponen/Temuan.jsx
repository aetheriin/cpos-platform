// Kotak "Yang perlu diperhatikan": kalimat temuan dari backend ({jenis, teks}). aksi opsional: (temuan) => {label, onKlik} atau null.
export default function Temuan({ data, aksi }) {
  if (!data?.length) return null
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">Yang perlu diperhatikan</h2>
      <ol className="mt-2 space-y-1.5 text-sm text-slate-700">
        {data.map((t, i) => {
          const a = aksi?.(t)
          return (
            <li key={t.jenis} className="flex gap-2">
              <span className="w-4 shrink-0 tabular-nums text-slate-400">{i + 1}.</span>
              <span>
                {t.teks}
                {a && (
                  <button type="button" onClick={a.onKlik} className="ml-1.5 text-sky-700 underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
                    {a.label}
                  </button>
                )}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
