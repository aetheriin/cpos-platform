import { rentangTgl } from '../lib/data'
import Info from './Info'
import { TombolFilter } from './PanelFilter'
import PilihTataLetak from './PilihTataLetak'

const CARA_FILTER = 'Klik batang, titik, label, legenda, atau baris tabel untuk memfilter. Tahan Ctrl (Cmd di Mac) untuk memilih lebih dari satu.'

// Kepala yang sama untuk semua dashboard: judul, satu baris periode (dengan periode pembanding), pilihan tata letak, tombol filter,
// lalu chip filter aktif. aktif: daftar [jenis, nilai, teks]; klik chip memanggil onLepas(jenis, nilai).
export default function KepalaLaporan({ judul, data, aktif, onLepas, onReset, panelTerbuka, onTogglePanel }) {
  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold">
            {judul}
            <Info teks={CARA_FILTER} label="cara memfilter" />
          </h1>
          {data && (
            <p className="text-sm text-slate-500">
              {rentangTgl(data.periode.mulai, data.periode.akhir)}
              {data.banding && <span className="text-slate-400"> · dibanding {rentangTgl(data.banding.mulai, data.banding.akhir)}</span>}
            </p>
          )}
        </div>
        <PilihTataLetak />
        <TombolFilter jumlahAktif={aktif.length} terbuka={panelTerbuka} onToggle={onTogglePanel} />
      </header>

      {aktif.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {aktif.map(([jenis, nilai, teks]) => (
            <button
              key={`${jenis}:${nilai ?? ''}`}
              type="button"
              aria-label={`Lepas filter ${teks}`}
              className="max-w-full truncate rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-100"
              onClick={() => onLepas(jenis, nilai)}
            >
              {teks} ×
            </button>
          ))}
          <button type="button" className="rounded-md px-2 py-1 text-xs text-slate-600 underline" onClick={onReset}>
            Reset filter
          </button>
        </div>
      )}
    </>
  )
}
