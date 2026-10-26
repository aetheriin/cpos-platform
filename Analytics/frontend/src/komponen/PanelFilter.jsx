import { useEffect, useRef } from 'react'

export function IkonFilter({ className = 'h-4 w-4' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 4h18l-7 8.5V19l-4 2v-8.5L3 4z" />
    </svg>
  )
}

const LEBAR_LACI = 'min(20rem, calc(100vw - 2rem))' // sama dengan lebar laci (w-80, max-w-[calc(100vw-2rem)])

// Tab Filter yang menempel di tepi kanan layar, jadi tetap terlihat saat halaman digulir. Saat laci terbuka, tab ikut bergeser ke tepi kiri laci.
export function TombolFilter({ jumlahAktif, terbuka, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={terbuka}
      aria-controls="panel-filter"
      aria-label={jumlahAktif > 0 ? `Filter, ${jumlahAktif} aktif` : 'Filter'}
      style={{ right: terbuka ? LEBAR_LACI : 0 }}
      className={
        'group fixed top-1/3 z-40 flex h-11 w-10 items-center justify-center rounded-l-xl border border-r-0 ' +
        'shadow-[-4px_4px_16px_-6px_rgb(15_23_42/0.25)] transition-[right,background-color,color] duration-200 ease-out ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
        (terbuka || jumlahAktif > 0 ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-slate-200 bg-white text-slate-600 hover:text-sky-700')
      }
    >
      {/* garis aksen di tepi kiri tab: penanda halus bahwa tab ini bisa ditarik/dibuka */}
      <span aria-hidden="true" className={'absolute inset-y-3 left-0 w-0.5 rounded-full transition-colors ' + (terbuka || jumlahAktif > 0 ? 'bg-sky-500' : 'bg-slate-300 group-hover:bg-sky-400')} />
      {terbuka ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
          <path d="M9 6l6 6-6 6" />
        </svg>
      ) : (
        <IkonFilter className="h-4 w-4 transition-transform group-hover:-translate-x-px" />
      )}
      {/* label muncul di kiri tab saat disorot atau difokus, supaya arti ikonnya jelas tanpa tulisan miring */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute right-full mr-2 hidden rounded-md bg-[#1e293b] px-2 py-1 text-xs font-medium whitespace-nowrap text-white shadow group-hover:block group-focus-visible:block"
      >
        {terbuka ? 'Tutup filter' : jumlahAktif > 0 ? `Filter (${jumlahAktif} aktif)` : 'Filter'}
      </span>
      {jumlahAktif > 0 && !terbuka && (
        <span className="absolute -top-1.5 -left-1.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-sky-600 px-1 text-[10px] leading-none font-semibold text-white tabular-nums ring-2 ring-white">
          {jumlahAktif}
        </span>
      )}
    </button>
  )
}

const JEDA_TUTUP = 400 // ms setelah kursor keluar laci; kembali masuk sebelum itu membatalkan penutupan

// Laci di sisi kanan, di bawah bilah atas. Menutupi tepi kanan halaman tanpa menggeser isinya. Dibuka hanya dengan klik tab Filter.
// Ditutup dengan tombol ×, tab Filter, Esc, klik di luar laci, atau kursor mouse keluar dari laci. Penutupan karena kursor ditunda sebentar
// dan dilewati selama isian tanggal atau pilihan di laci sedang aktif, karena kalender dan daftar bawaan browser tampil di luar laci.
export default function PanelFilter({ terbuka, onTutup, jumlahAktif, onReset, children }) {
  const waktu = useRef(null)
  const batalTutup = () => clearTimeout(waktu.current)
  const keluar = (e) => {
    if (e.pointerType !== 'mouse') return
    batalTutup()
    waktu.current = setTimeout(() => {
      const aktif = document.activeElement
      if (aktif?.closest?.('#panel-filter') && aktif.matches('input[type="date"], select')) return
      onTutup()
    }, JEDA_TUTUP)
  }
  useEffect(() => batalTutup, [])
  useEffect(() => {
    if (!terbuka) batalTutup()
  }, [terbuka])
  useEffect(() => {
    if (!terbuka) return undefined
    const tombol = (e) => e.key === 'Escape' && onTutup()
    const klik = (e) => !e.target.closest?.('#panel-filter, [aria-controls="panel-filter"]') && onTutup()
    window.addEventListener('keydown', tombol)
    document.addEventListener('pointerdown', klik)
    return () => {
      window.removeEventListener('keydown', tombol)
      document.removeEventListener('pointerdown', klik)
    }
  }, [terbuka, onTutup])
  return (
    <aside
      id="panel-filter"
      aria-label="Filter"
      aria-hidden={!terbuka}
      inert={!terbuka}
      onPointerLeave={terbuka ? keluar : undefined}
      onPointerEnter={batalTutup}
      className={
        'gulir-halus fixed top-14 right-0 bottom-0 z-40 w-80 max-w-[calc(100vw-2rem)] overflow-y-auto border-l border-slate-200 bg-white p-4 shadow-xl transition-transform duration-200 ease-out ' +
        (terbuka ? 'translate-x-0' : 'pointer-events-none translate-x-full shadow-none')
      }
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-medium">
          <IkonFilter className="h-4 w-4 text-sky-700" />
          Filter
        </h2>
        <button type="button" onClick={onTutup} aria-label="Tutup filter" className="rounded-md px-2 py-0.5 text-lg leading-none text-slate-500 hover:bg-slate-100">
          ×
        </button>
      </div>
      <div className="space-y-3">{children}</div>
      {jumlahAktif > 0 && (
        <button type="button" onClick={onReset} className="mt-4 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
          Hapus semua filter ({jumlahAktif})
        </button>
      )}
    </aside>
  )
}
