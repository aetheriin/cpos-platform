import { useState } from 'react'
import { gantiSandi } from '../api'
import Modal from './Modal'

const kolomInput = 'w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 '
const normal = 'border-slate-300 focus:border-sky-500 focus:ring-sky-500'
const salah = 'border-red-400 focus:border-red-500 focus:ring-red-500'

function KolomSandi({ id, label, nilai, onUbah, lihat, petunjuk, galat, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type={lihat ? 'text' : 'password'}
        value={nilai}
        onChange={(e) => onUbah(e.target.value)}
        aria-invalid={galat ? true : undefined}
        aria-describedby={`${id}-ket`}
        className={'mt-1 ' + kolomInput + (galat ? salah : normal)}
        {...props}
      />
      <p id={`${id}-ket`} className={'mt-1 text-xs ' + (galat ? 'text-red-600' : 'text-slate-500')}>
        {galat || petunjuk}
      </p>
    </div>
  )
}

// Popup Ganti password untuk akun yang sedang dipakai. Kesalahan ditampilkan di bawah kolomnya masing-masing.
export default function PopupGantiSandi({ username, onTutup }) {
  const [lama, setLama] = useState('')
  const [baru, setBaru] = useState('')
  const [ulang, setUlang] = useState('')
  const [lihat, setLihat] = useState(false)
  const [mengirim, setMengirim] = useState(false)
  const [dicoba, setDicoba] = useState(false) // pesan per kolom baru muncul setelah Simpan ditekan sekali
  const [galatServer, setGalatServer] = useState({})
  const [selesai, setSelesai] = useState(false)

  const cek = {
    lama: !lama ? 'Isi password yang sekarang dipakai.' : '',
    baru: !baru ? 'Isi password baru.' : baru.length < 8 ? 'Minimal 8 karakter.' : baru === lama ? 'Harus beda dari password lama.' : '',
    ulang: baru.length >= 8 && ulang !== baru ? 'Belum sama dengan password baru.' : '',
  }
  const galat = {
    lama: (dicoba && cek.lama) || galatServer.lama,
    baru: dicoba && cek.baru,
    ulang: dicoba && cek.ulang,
  }

  const kirim = async (e) => {
    e.preventDefault()
    if (mengirim) return
    setDicoba(true)
    setGalatServer({})
    if (cek.lama || cek.baru || cek.ulang) return
    setMengirim(true)
    try {
      await gantiSandi(lama, baru)
      setSelesai(true)
    } catch (err) {
      setGalatServer(/password lama/i.test(err.message) ? { lama: err.message } : { umum: err.message })
    } finally {
      setMengirim(false)
    }
  }

  return (
    <Modal judul="Ganti password" onTutup={() => !mengirim && onTutup()} lebar="max-w-sm">
      {selesai ? (
        <div>
          <p role="status" className="text-sm text-slate-700">
            Password untuk <span className="font-medium text-slate-900">{username}</span> sudah diganti. Pakai password baru saat masuk berikutnya.
          </p>
          <div className="mt-5 flex justify-end">
            <button type="button" onClick={onTutup} className="rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800">
              Tutup
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={kirim} noValidate autoComplete="off">
          <p className="-mt-2 mb-4 text-sm text-slate-500">
            Akun <span className="font-medium text-slate-700">{username}</span>
          </p>
          {galatServer.umum && (
            <p role="alert" className="mb-4 border-l-2 border-red-500 pl-3 text-sm text-red-700">
              {galatServer.umum}
            </p>
          )}
          <div className="space-y-3">
            <KolomSandi id="g-lama" label="Password lama" nilai={lama} onUbah={setLama} lihat={lihat} galat={galat.lama} autoFocus autoComplete="current-password" />
            <KolomSandi id="g-baru" label="Password baru" nilai={baru} onUbah={setBaru} lihat={lihat} galat={galat.baru} petunjuk="Minimal 8 karakter, beda dari yang lama." autoComplete="new-password" />
            <KolomSandi id="g-ulang" label="Ketik ulang password baru" nilai={ulang} onUbah={setUlang} lihat={lihat} galat={galat.ulang} autoComplete="new-password" />
          </div>
          <label className="mt-3 inline-flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={lihat} onChange={(e) => setLihat(e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
            Tampilkan password
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={onTutup} disabled={mengirim} className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40">
              Batal
            </button>
            <button type="submit" disabled={mengirim} className="rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40">
              {mengirim ? 'Menyimpan…' : 'Simpan'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
