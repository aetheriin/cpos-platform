import { useCallback, useEffect, useRef, useState } from 'react'
import { aturSesiHabis, daftarLaporan, keluar, sayaSendiri, statusServer } from './api'
import LaporanView from './komponen/LaporanView'
import HalamanAktivitas from './komponen/HalamanAktivitas'
import HalamanIzin from './komponen/HalamanIzin'
import HalamanPengguna from './komponen/HalamanPengguna'
import HalamanStruktur from './komponen/HalamanStruktur'
import KembaliKeAtas from './komponen/KembaliKeAtas'
import TandaMemuat from './komponen/TandaMemuat'
import { IkonBulan, IkonKunci, IkonMatahari, IkonMenu } from './komponen/Ikon'
import Login from './komponen/Login'
import MenuAkun from './komponen/MenuAkun'
import Sidebar, { ID_AKTIVITAS, ID_IZIN, ID_PENGGUNA, ID_STRUKTUR } from './komponen/Sidebar'
import { keLoginCpos, SEMATAN } from './lib/cpos'
import { hariIni, salam } from './lib/data'
import { useJagaIdle } from './lib/idle'
import { idDariAlamat, keLogin, keluarDariLogin, pindahAlamat } from './lib/rute'
import { kembaliKeBawaan } from './lib/tampilan'
import { useTema } from './lib/tema'
import { DASHBOARD } from './laporan'

const ID_ADMIN = [ID_PENGGUNA, ID_STRUKTUR, ID_IZIN, ID_AKTIVITAS]

// Halaman admin hanya untuk admin; laporan hanya yang ada di daftar laporan akun ini (daftar dari server sudah disaring izinnya).
const bolehDibuka = (id, laporan, pengguna) =>
  id != null && (ID_ADMIN.includes(id) ? Boolean(pengguna?.admin) : laporan.some((l) => l.id === id))

export default function App() {
  const [laporan, setLaporan] = useState(null)
  const [galat, setGalat] = useState(null)
  const [aktif, setAktif] = useState(null)
  const [dibuka, setDibuka] = useState([]) // laporan yang pernah dibuka. Tetap terpasang agar tidak dimuat ulang
  const [status, setStatus] = useState({})
  const [menu, setMenu] = useState(true)
  const [pengguna, setPengguna] = useState(null)
  const [cek, setCek] = useState(true)
  const [pesanLogin, setPesanLogin] = useState('')
  const [merek, setMerek] = useState('')
  const [pesanAlamat, setPesanAlamat] = useState('')
  const [batasIdle, setBatasIdle] = useState(0) // detik; dari server (diatur administrator), 0 = tanpa batas
  const [modeCpos, setModeCpos] = useState(SEMATAN) // login & hak akses mengikuti CPOS (backend CPOS_URL); dibuka dari menu CPOS
  const sudahOtomatis = useRef(false)
  const [tema, gantiTema] = useTema()

  // Kembalikan semuanya ke awal supaya data laporan pengguna sebelumnya tidak tersisa di layar
  const bersihkan = () => {
    setPengguna(null)
    setLaporan(null)
    setGalat(null)
    setAktif(null)
    setDibuka([])
    setStatus({})
    setPesanAlamat('')
    sudahOtomatis.current = false
  }

  useEffect(() => {
    // Sesi berakhir di tengah pemakaian (server menjawab 401): kembali ke halaman masuk
    aturSesiHabis((pesan) => {
      bersihkan()
      setPesanLogin(pesan || 'Sesi Anda berakhir. Silakan masuk lagi.')
    })
    // Cookie sesi mungkin masih berlaku (mis. halaman dimuat ulang). Status server ditunggu juga: di mode CPOS tidak ada halaman masuk sendiri.
    Promise.allSettled([sayaSendiri(), statusServer()]).then(([saya, st]) => {
      if (st.status === 'fulfilled') {
        setMerek(st.value.nama ?? '')
        if (st.value.nama && typeof document !== 'undefined') document.title = st.value.nama
        if (st.value.cpos) setModeCpos(true)
      }
      if (saya.status === 'fulfilled') {
        keluarDariLogin() // sudah masuk tetapi membuka /login: langsung ke tujuan
        setBatasIdle(saya.value.batas_idle_detik ?? 0)
        setPengguna(saya.value)
      }
      setCek(false)
    })
  }, [])

  useEffect(() => {
    if (!pengguna) return undefined
    let batal = false
    daftarLaporan()
      .then((d) => {
        if (batal) return
        setLaporan(d)
        if (sudahOtomatis.current) return
        sudahOtomatis.current = true
        // Buka halaman yang ditunjuk alamat kalau akun ini boleh membukanya; selain itu laporan pertama, dan alamatnya dibetulkan
        const tujuan = idDariAlamat()
        if (bolehDibuka(tujuan, d, pengguna)) {
          setAktif(tujuan)
          if (!ID_ADMIN.includes(tujuan)) {
            setDibuka([tujuan])
          }
          return
        }
        if (tujuan !== null) setPesanAlamat('Halaman yang Anda buka tidak ada atau Anda tidak punya akses ke halaman itu.')
        const awal = d[0]?.id ?? null
        setAktif(awal)
        if (awal) {
          setDibuka([awal])
        }
        pindahAlamat(awal, true)
      })
      .catch((e) => {
        if (!batal) {
          setGalat(e)
          setLaporan([])
        }
      })
    return () => {
      batal = true
    }
  }, [pengguna])

  const buka = (id) => {
    setAktif(id)
    setPesanAlamat('')
    if (id && !ID_ADMIN.includes(id)) setDibuka((d) => (d.includes(id) ? d : [...d, id]))
  }
  const pilih = (id) => {
    buka(id)
    pindahAlamat(id)
  }

  // Tombol Back / Forward browser. Alamat yang tidak boleh dibuka akun ini dibetulkan ke halaman yang sedang tampil.
  useEffect(() => {
    if (!pengguna || laporan === null) return undefined
    const saatPindah = () => {
      const id = idDariAlamat()
      if (bolehDibuka(id, laporan, pengguna)) buka(id)
      else pindahAlamat(aktifRef.current, true)
    }
    window.addEventListener('popstate', saatPindah)
    return () => window.removeEventListener('popstate', saatPindah)
  }, [pengguna, laporan])
  const aktifRef = useRef(aktif)
  aktifRef.current = aktif

  const catatStatus = useCallback((id, st) => setStatus((s) => (s[id] === st ? s : { ...s, [id]: st })), [])
  const keluarAkun = () => {
    keluar()
      .catch(() => {})
      .finally(() => {
        bersihkan()
        setPesanLogin('')
        // Keluar sengaja: alamat kembali ke awal, supaya akun berikutnya tidak diarahkan ke halaman akun ini.
        pindahAlamat(null, true)
      })
  }

  // Server juga menolak sesi idle; ini supaya data tidak tertinggal di layar. Alamat tetap, jadi setelah masuk lagi kembali ke sini.
  useJagaIdle(pengguna ? batasIdle : 0, () => {
    keluar()
      .catch(() => {})
      .finally(() => {
        bersihkan()
        setPesanLogin(`Anda keluar otomatis karena tidak ada aktivitas selama ${Math.round(batasIdle / 60)} menit. Masuk lagi untuk melanjutkan.`)
      })
  })

  // Belum masuk (termasuk sesi habis atau baru keluar): alamat apa pun diganti /login, dengan halaman tujuan disimpan di ?ke=
  useEffect(() => {
    if (!cek && !pengguna && !modeCpos) keLogin()
  }, [cek, pengguna, modeCpos])

  if (cek) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Memuat...</div>
  if (!pengguna && modeCpos) {
    return (
      <section role="status" className="mx-auto mt-16 max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <span aria-hidden="true" className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
          <IkonKunci className="h-6 w-6" />
        </span>
        <h1 className="mt-4 text-lg font-semibold">{pesanLogin || 'Sesi CPOS berakhir atau belum masuk.'}</h1>
        <p className="mt-1 text-sm text-slate-600">Laporan Analytics dibuka dari menu CPOS. Masuk lagi di CPOS untuk melanjutkan.</p>
        <button type="button" onClick={keLoginCpos} className="mt-5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700">
          Masuk ke CPOS
        </button>
      </section>
    )
  }
  if (!pengguna) {
    return (
      <Login
        nama={merek}
        pesan={pesanLogin}
        onMasuk={(p) => {
          keluarDariLogin()
          kembaliKeBawaan() // setiap login mulai dari tata letak padat
          setPesanLogin('')
          setPengguna(p)
          sayaSendiri()
            .then((s) => setBatasIdle(s.batas_idle_detik ?? 0))
            .catch(() => {})
        }}
      />
    )
  }

  const tanpaAkses = laporan !== null && laporan.length === 0 && !galat && !pengguna.admin && !pengguna.halaman?.length
  const laporanAktif = laporan?.find((l) => l.id === aktif)
  const halaman =
    aktif === ID_PENGGUNA ? { bagian: 'Administrasi', nama: 'Pengguna' }
    : aktif === ID_STRUKTUR ? { bagian: 'Administrasi', nama: 'Role & Divisi' }
    : aktif === ID_IZIN ? { bagian: 'Administrasi', nama: 'Permission Control' }
    : aktif === ID_AKTIVITAS ? { bagian: 'Administrasi', nama: 'Log Aktivitas' }
    : laporanAktif ? { bagian: laporanAktif.grup || 'Laporan', nama: laporanAktif.nama }
    : null

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-800">
      {menu && !SEMATAN && <Sidebar nama={merek} tanpaAkses={tanpaAkses} laporan={laporan} aktif={aktif} status={status} onPilih={pilih} admin={pengguna.admin} pengguna={pengguna} onKeluar={keluarAkun} />}

      <div className="min-w-0 flex-1">
        {!SEMATAN && (
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
          <button
            type="button"
            onClick={() => setMenu((m) => !m)}
            aria-label={menu ? 'Sembunyikan menu' : 'Tampilkan menu'}
            aria-expanded={menu}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <IkonMenu className="h-5 w-5" />
          </button>
          <nav aria-label="Lokasi halaman" className="min-w-0">
            <ol className="flex items-center gap-1.5 text-sm">
              {[merek, halaman?.bagian].filter(Boolean).map((teks) => (
                <li key={teks} className="hidden items-center gap-1.5 text-slate-500 md:flex">
                  {teks}
                  <span aria-hidden="true" className="text-slate-300">/</span>
                </li>
              ))}
              {halaman && <li aria-current="page" className="truncate font-medium text-slate-900">{halaman.nama}</li>}
            </ol>
          </nav>
          <div className="ml-auto min-w-0 shrink-0 text-right leading-tight">
            <p className="truncate text-sm text-slate-600">
              {salam()}, <span className="font-medium text-slate-900">{pengguna.nama || pengguna.username}</span>
            </p>
            <p className="hidden text-xs tabular-nums text-slate-500 sm:block">{hariIni()}</p>
          </div>
          <button
            type="button"
            onClick={gantiTema}
            aria-label={tema === 'gelap' ? 'Pakai tampilan terang' : 'Pakai tampilan gelap'}
            title={tema === 'gelap' ? 'Tampilan terang' : 'Tampilan gelap'}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            {tema === 'gelap' ? <IkonMatahari className="h-5 w-5" /> : <IkonBulan className="h-5 w-5" />}
          </button>
          {!menu && <MenuAkun pengguna={pengguna} onKeluar={keluarAkun} arah="bawah" />}
        </header>
        )}

        {/* Laporan (padat maupun memanjang) memakai seluruh lebar layar dengan tepi tipis; halaman administrasi tetap selebar biasa */}
        <main className={!ID_ADMIN.includes(aktif) ? 'p-3 sm:px-4' : 'mx-auto max-w-6xl p-4 sm:p-6'}>
          {galat && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              Daftar laporan tidak bisa dimuat: {galat.message}
            </div>
          )}
          {pesanAlamat && (
            <div role="status" className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {pesanAlamat}
              <button type="button" onClick={() => setPesanAlamat('')} className="shrink-0 text-xs underline">
                Tutup
              </button>
            </div>
          )}
          {tanpaAkses && (
            <section role="status" className="mx-auto mt-10 max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
              <span aria-hidden="true" className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                <IkonKunci className="h-6 w-6" />
              </span>
              <h1 className="mt-4 text-lg font-semibold">Tidak dapat mengakses laporan</h1>
              <p className="mt-1 text-sm text-slate-600">
                Akun Anda belum memiliki akses ke laporan mana pun. Hubungi administrator untuk meminta akses. Anda tetap bisa keluar lewat menu akun.
              </p>
            </section>
          )}
          {pengguna.admin && aktif === ID_PENGGUNA && (
            <HalamanPengguna pengguna={pengguna} onSendiriBerubah={(h) => setPengguna((p) => ({ ...p, nama: h.nama, divisi: h.divisi, company: h.company }))} />
          )}
          {pengguna.admin && aktif === ID_STRUKTUR && <HalamanStruktur />}
          {pengguna.admin && aktif === ID_IZIN && <HalamanIzin />}
          {pengguna.admin && aktif === ID_AKTIVITAS && <HalamanAktivitas />}
          {dibuka.map((id) => {
            const l = laporan?.find((x) => x.id === id)
            const Dashboard = DASHBOARD[id]
            if (!l || !Dashboard) return null
            return (
              <div key={id} hidden={id !== aktif}>
                <LaporanView laporan={l} Dashboard={Dashboard} onStatus={catatStatus} />
              </div>
            )
          })}
        </main>
      </div>
      <KembaliKeAtas />
      <TandaMemuat />
    </div>
  )
}
