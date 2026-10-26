import { useState } from 'react'
import { IkonLaporan, IkonPanah, IkonPengguna, IkonPerisai, IkonRiwayat, IkonStruktur, IkonTabel } from './Ikon'
import Logo from './Logo'
import MenuAkun from './MenuAkun'

const KUNCI_LIPAT = 'menu-terlipat'
const bacaLipat = () => {
  try {
    return JSON.parse(localStorage.getItem(KUNCI_LIPAT)) ?? []
  } catch {
    return []
  }
}

// Titik status di sebelah nama laporan: hanya muncul saat sedang memuat atau datanya sudah siap (arti tampil sebagai petunjuk saat disorot)
const TITIK = {
  memuat: { kelas: 'bg-amber-400', arti: 'Sedang memuat' },
  siap: { kelas: 'bg-emerald-500', arti: 'Data siap' },
}

export const ID_PENGGUNA = '__pengguna'
export const ID_STRUKTUR = '__struktur'
export const ID_IZIN = '__izin'
export const ID_AKTIVITAS = '__aktivitas'

// Satu grup menu yang bisa dilipat. Saat terlipat, judulnya tetap ditandai kalau halaman yang terbuka ada di dalamnya.
function Grup({ judul, terlipat, onLipat, berisiAktif, children }) {
  const id = `grup-${judul.replace(/\W+/g, '-').toLowerCase()}`
  return (
    <div className="mt-4 first:mt-0">
      <button
        type="button"
        onClick={onLipat}
        aria-expanded={!terlipat}
        aria-controls={id}
        className={
          'flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
          (terlipat && berisiAktif ? 'text-sky-700' : 'text-slate-500 hover:text-slate-800')
        }
      >
        <span className="truncate">{judul}</span>
        <IkonPanah className={'h-3.5 w-3.5 shrink-0 transition-transform ' + (terlipat ? '-rotate-90' : '')} />
      </button>
      {!terlipat && (
        <ul id={id} className="mt-1 space-y-0.5">
          {children}
        </ul>
      )}
    </div>
  )
}

const butir = ({ kunci, aktif, Ikon, label, onClick, titik }) => (
  <li key={kunci}>
    <button
      type="button"
      onClick={onClick}
      aria-current={aktif ? 'page' : undefined}
      title={label}
      className={
        'group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
        (aktif ? 'bg-sky-50 font-medium text-sky-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900')
      }
    >
      {aktif && <span aria-hidden="true" className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r bg-sky-600" />}
      <Ikon className={'h-[18px] w-[18px] shrink-0 ' + (aktif ? 'text-sky-700' : 'text-slate-400 group-hover:text-slate-600')} />
      <span className="min-w-0 flex-1 truncate text-left">{label}</span>
      {titik && <span role="img" aria-label={titik.arti} title={titik.arti} className={'h-2 w-2 shrink-0 rounded-full ' + titik.kelas} />}
    </button>
  </li>
)

// Bisa disembunyikan lewat tombol di bilah atas. nama: nama aplikasi dari server. tanpaAkses: akun belum punya akses ke laporan mana pun, jadi menunya
// dikosongkan dan yang tersisa hanya menu akun (untuk keluar).
export default function Sidebar({ nama = '', laporan, aktif, status, onPilih, admin = false, pengguna = null, onKeluar = () => {}, tanpaAkses = false }) {
  const [terlipat, setTerlipat] = useState(bacaLipat)
  const lipat = (judul) =>
    setTerlipat((lama) => {
      const baru = lama.includes(judul) ? lama.filter((j) => j !== judul) : [...lama, judul]
      try {
        localStorage.setItem(KUNCI_LIPAT, JSON.stringify(baru))
      } catch {
        // tetap berfungsi tanpa penyimpanan; hanya tidak diingat
      }
      return baru
    })

  // Grup mengikuti urutan laporan dari server
  const grup = []
  for (const l of laporan ?? []) {
    const nama = l.grup || 'Laporan'
    const ada = grup.find((g) => g.nama === nama)
    if (ada) ada.laporan.push(l)
    else grup.push({ nama, laporan: [l] })
  }
  const menuAdmin = [
    { kunci: ID_PENGGUNA, Ikon: IkonPengguna, label: 'Pengguna' },
    { kunci: ID_STRUKTUR, Ikon: IkonStruktur, label: 'Role & Divisi' },
    { kunci: ID_IZIN, Ikon: IkonPerisai, label: 'Permission Control' },
    { kunci: ID_AKTIVITAS, Ikon: IkonRiwayat, label: 'Log Aktivitas' },
  ]

  return (
    <nav aria-label="Menu utama" className="sticky top-0 flex h-screen w-64 shrink-0 flex-col self-start border-r border-slate-200 bg-white">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-slate-200 px-4">
        <Logo className="h-8 w-8 shrink-0" />
        <span className="truncate text-sm font-semibold text-slate-900">{nama}</span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        {tanpaAkses ? (
          <p className="px-3 text-sm text-slate-500">Tidak ada menu yang bisa diakses.</p>
        ) : (
          <>
            {laporan === null && <p className="px-3 text-sm text-slate-500">Memuat daftar...</p>}
            {grup.map((g) => (
              <Grup key={g.nama} judul={g.nama} terlipat={terlipat.includes(g.nama)} onLipat={() => lipat(g.nama)} berisiAktif={g.laporan.some((l) => l.id === aktif)}>
                {g.laporan.map((l) =>
                  butir({
                    kunci: l.id,
                    aktif: aktif === l.id,
                    Ikon: g.nama === 'Reports' ? IkonTabel : IkonLaporan,
                    label: l.nama,
                    onClick: () => onPilih(l.id),
                    titik: TITIK[status[l.id]],
                  }),
                )}
              </Grup>
            ))}
            {admin && (
              <Grup judul="Administrasi" terlipat={terlipat.includes('Administrasi')} onLipat={() => lipat('Administrasi')} berisiAktif={menuAdmin.some((m) => m.kunci === aktif)}>
                {menuAdmin.map((m) => butir({ ...m, aktif: aktif === m.kunci, onClick: () => onPilih(m.kunci) }))}
              </Grup>
            )}
          </>
        )}
      </div>

      {pengguna && (
        <div className="shrink-0 border-t border-slate-200 p-2">
          <MenuAkun pengguna={pengguna} onKeluar={onKeluar} arah="atas" penuh />
        </div>
      )}
    </nav>
  )
}
