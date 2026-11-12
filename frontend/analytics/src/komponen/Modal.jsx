import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { IkonTutup } from './Ikon'

const ID_JUDUL = 'judul-modal'

// Tertutup dengan X, Esc, atau klik di luar. kecil: keterangan di atas judul.
export default function Modal({ judul, kecil, onTutup, lebar = 'max-w-lg', children }) {
  useEffect(() => {
    const tekan = (e) => {
      if (e.key === 'Escape') onTutup()
    }
    document.addEventListener('keydown', tekan)
    const lama = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', tekan)
      document.body.style.overflow = lama
    }
  }, [onTutup])

  // Dipasang langsung di <body> supaya tidak terkurung lapisan induknya (mis. menu samping) dan tidak tertimpa dropdown halaman.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onTutup()
      }}
    >
      <div role="dialog" aria-modal="true" aria-labelledby={ID_JUDUL} className={'max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white shadow-xl ' + lebar}>
        <div className="flex items-start justify-between px-6 pt-5">
          <div>
            {kecil && <p className="text-xs font-medium text-slate-500">{kecil}</p>}
            <h2 id={ID_JUDUL} className="text-xl font-semibold text-slate-900">
              {judul}
            </h2>
          </div>
          <button type="button" onClick={onTutup} aria-label="Tutup" className="-mr-2 rounded-md p-1.5 text-slate-500 hover:bg-slate-100">
            <IkonTutup className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 pb-6 pt-4">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
