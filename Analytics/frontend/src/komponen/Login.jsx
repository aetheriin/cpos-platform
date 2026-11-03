import { useState } from 'react'
import { masuk } from '../api'
import { IkonKunci, IkonMata, IkonMataCoret, IkonPengguna } from './Ikon'
import Logo from './Logo'

// Kolom isian dengan ikon di kiri. kanan: tombol kecil di sisi kanan kolom (mis. tampilkan password).
function Kolom({ id, label, ikon: Ikon, kanan, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <Ikon className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          id={id}
          {...props}
          className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pr-10 pl-9 text-sm text-slate-900 transition-colors placeholder:text-slate-400 focus:border-sky-600 focus:ring-2 focus:ring-sky-600/20 focus:outline-none"
        />
        {kanan}
      </div>
    </div>
  )
}

// Halaman masuk. nama: nama aplikasi dari server. pesan: alasan kembali ke halaman ini (mis. sesi berakhir, masuk di perangkat lain).
export default function Login({ onMasuk, nama = '', pesan = '' }) {
  const [username, setUsername] = useState('')
  const [sandi, setSandi] = useState('')
  const [lihat, setLihat] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [memuat, setMemuat] = useState(false)
  const [galat, setGalat] = useState('')

  const kirim = async (e) => {
    e.preventDefault()
    if (memuat) return
    setMemuat(true)
    setGalat('')
    try {
      onMasuk(await masuk(username.trim(), sandi))
    } catch (err) {
      setGalat(err.message)
      setSandi('')
      setMemuat(false)
    }
  }
  const cekCaps = (e) => setCapsLock(Boolean(e.getModifierState?.('CapsLock')))

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10 text-slate-800">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <Logo className="h-10 w-10 shrink-0" />
          <span className="text-lg font-semibold text-slate-900">{nama}</span>
        </div>

        <form onSubmit={kirim} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7" noValidate>
          <h1 className="text-xl font-semibold text-slate-900">Sign In</h1>
          <p className="mt-1 text-sm text-slate-500">Masuk untuk melanjutkan.</p>

          {pesan && (
            <div role="status" className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {pesan}
            </div>
          )}
          {galat && (
            <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {galat}
            </div>
          )}

          <div className="mt-5 space-y-4">
            <Kolom
              id="masuk-username"
              label="Username"
              ikon={IkonPengguna}
              type="text"
              placeholder="Masukkan username"
              autoFocus
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(e) => setUsername(e.target.value.toUpperCase())}
            />
            <div>
              <Kolom
                id="masuk-sandi"
                label="Password"
                ikon={IkonKunci}
                type={lihat ? 'text' : 'password'}
                placeholder="Masukkan password"
                autoComplete="current-password"
                value={sandi}
                onChange={(e) => setSandi(e.target.value)}
                onKeyDown={cekCaps}
                onKeyUp={cekCaps}
                onBlur={() => setCapsLock(false)}
                kanan={
                  <button
                    type="button"
                    onClick={() => setLihat((v) => !v)}
                    aria-label={lihat ? 'Sembunyikan password' : 'Tampilkan password'}
                    aria-pressed={lihat}
                    className="absolute top-1/2 right-1.5 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-600/40"
                  >
                    {lihat ? <IkonMataCoret className="h-4 w-4" /> : <IkonMata className="h-4 w-4" />}
                  </button>
                }
              />
              {capsLock && <p className="mt-1.5 text-xs text-amber-700">Caps Lock aktif.</p>}
            </div>
          </div>

          <button
            type="submit"
            disabled={memuat || !username.trim() || !sandi}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-600/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {memuat && <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
            {memuat ? 'Memeriksa...' : 'Masuk'}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-500">Lupa password atau belum punya akun? Hubungi System Administrator.</p>
      </div>
    </div>
  )
}
