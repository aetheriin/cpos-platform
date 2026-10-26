import { useEffect, useRef, useState } from 'react'
import Avatar from './Avatar'
import { IkonKeluar, IkonKunci, IkonPanah } from './Ikon'
import PopupGantiSandi from './PopupGantiSandi'

// arah: 'atas' (menu muncul di atas tombol, untuk bagian bawah menu samping) atau 'bawah' (untuk bilah atas).
// penuh: tombol selebar tempatnya (menu samping); kalau tidak, nama disembunyikan di layar sempit.
export default function MenuAkun({ pengguna, onKeluar, arah = 'bawah', penuh = false }) {
  const [buka, setBuka] = useState(false)
  const [ganti, setGanti] = useState(false)
  const wadah = useRef(null)

  useEffect(() => {
    if (!buka) return undefined
    const luar = (e) => {
      if (wadah.current && !wadah.current.contains(e.target)) setBuka(false)
    }
    const esc = (e) => {
      if (e.key === 'Escape') setBuka(false)
    }
    document.addEventListener('mousedown', luar)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', luar)
      document.removeEventListener('keydown', esc)
    }
  }, [buka])

  const rincian = [
    ['Role', pengguna.role],
    ['Division', pengguna.divisi],
    ['Company', pengguna.company],
  ].filter(([, v]) => v)

  return (
    <div ref={wadah} className={'relative ' + (penuh ? 'w-full' : '')}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={buka}
        aria-label={`Menu akun ${pengguna.nama}`}
        onClick={() => setBuka((b) => !b)}
        className={'flex items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-slate-100 ' + (penuh ? 'w-full' : '')}
      >
        <Avatar nama={pengguna.nama} />
        <span className={'min-w-0 ' + (penuh ? 'flex-1' : 'hidden sm:block')}>
          <span className="block truncate text-sm font-medium text-slate-800">{pengguna.nama}</span>
          <span className="block truncate text-xs text-slate-500">{pengguna.role}</span>
        </span>
        <IkonPanah className={'h-4 w-4 shrink-0 text-slate-400 transition-transform ' + (buka ? 'rotate-180' : '')} />
      </button>

      {buka && (
        <div
          role="menu"
          className={
            'z-40 w-64 rounded-xl border border-slate-200 bg-white p-1 shadow-lg ' +
            (arah === 'atas' ? 'absolute bottom-full left-0 mb-2' : 'absolute right-0 top-full mt-2')
          }
        >
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{pengguna.nama}</p>
            <p className="truncate text-xs text-slate-500">{pengguna.username}</p>
            {rincian.length > 0 && (
              <dl className="mt-2 space-y-0.5 text-xs">
                {rincian.map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="w-16 shrink-0 text-slate-500">{k}</dt>
                    <dd className="min-w-0 truncate text-slate-700">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setBuka(false)
              setGanti(true)
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
          >
            <IkonKunci className="h-4 w-4" />
            Ganti password
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setBuka(false)
              onKeluar()
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
          >
            <IkonKeluar className="h-4 w-4" />
            Keluar
          </button>
        </div>
      )}
      {ganti && <PopupGantiSandi username={pengguna.username} onTutup={() => setGanti(false)} />}
    </div>
  )
}
