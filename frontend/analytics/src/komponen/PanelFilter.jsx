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
        'tombol-filter group fixed top-1/3 z-40 flex h-9 w-9 items-center justify-center rounded-l-md ' +
        'bg-sky-700 text-white shadow-[-4px_4px_14px_-6px_rgb(15_23_42/0.4)] transition-[right,background-color,padding] duration-200 ease-out ' +
        'hover:bg-sky-800 hover:w-10 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 focus-visible:ring-offset-2'
      }
    >
      {/* ikon saja, tapi berwarna penuh: tetap mudah terlihat di tepi kanan tanpa memakan tempat */}
      {terbuka ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden="true">
          <path d="M9 6l6 6-6 6" />
        </svg>
      ) : (
        <IkonFilter className="h-3.5 w-3.5" />
      )}
      {jumlahAktif > 0 && !terbuka && (
        <span aria-hidden="true" className="absolute -top-1.5 -left-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-white px-1 text-[10px] leading-none font-bold text-sky-800 tabular-nums ring-1 ring-sky-700">
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
        'gulir-halus panel-filter fixed top-14 right-0 bottom-0 z-40 w-80 max-w-[calc(100vw-2rem)] overflow-y-auto border-l border-slate-200 bg-white p-4 shadow-xl transition-transform duration-200 ease-out ' +
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
