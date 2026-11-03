import { useEffect, useState } from 'react'
import { ambilPengaturanSesi, simpanPengaturanSesi } from '../api'

const PILIHAN = [15, 30, 60, 120]

// Server langsung memakai batas baru; halaman yang sedang terbuka baru memakainya setelah dimuat ulang atau login lagi.
export default function PengaturanIdle({ onBerubah }) {
  const [awal, setAwal] = useState(null) // { idle_menit, sesi_jam } dari server
  const [isian, setIsian] = useState('')
  const [menyimpan, setMenyimpan] = useState(false)
  const [pesan, setPesan] = useState('')
  const [galat, setGalat] = useState('')

  useEffect(() => {
    ambilPengaturanSesi()
      .then((p) => {
        setAwal(p)
        setIsian(String(p.idle_menit))
      })
      .catch((e) => setGalat(`Pengaturan tidak bisa dimuat: ${e.message}`))
  }, [])

  const menit = Number(isian)
  const sah = isian.trim() !== '' && Number.isInteger(menit) && menit >= 0 && menit <= 1440
  const berubah = awal && sah && menit !== awal.idle_menit

  const simpan = async (e) => {
    e.preventDefault()
    if (!berubah || menyimpan) return
    setMenyimpan(true)
    setGalat('')
    setPesan('')
    try {
      const p = await simpanPengaturanSesi(menit)
      setAwal(p)
      setIsian(String(p.idle_menit))
      setPesan(p.idle_menit ? `Disimpan. Pengguna keluar otomatis setelah ${p.idle_menit} menit tanpa aktivitas.` : 'Disimpan. Tidak ada batas idle.')
      onBerubah?.(p)
    } catch (err) {
      setGalat(err.message)
    } finally {
      setMenyimpan(false)
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="font-medium">Keluar otomatis saat idle</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Pengguna yang tidak aktif selama batas ini otomatis logout. Isi 0 untuk mematikan.
        {awal && ` Maksimal ${awal.sesi_jam} jam per login.`}
      </p>
      <form onSubmit={simpan} className="mt-3 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Batas
          <input
            type="number"
            min={0}
            max={1440}
            step={1}
            inputMode="numeric"
            value={isian}
            onChange={(e) => setIsian(e.target.value)}
            disabled={!awal}
            aria-invalid={isian !== '' && !sah}
            className="w-20 rounded-md border border-slate-300 px-2 py-1.5 text-sm tabular-nums focus:border-sky-500 focus:ring-1 focus:ring-sky-500 focus:outline-none"
          />
          menit
        </label>
        <span className="flex flex-wrap gap-1">
          {PILIHAN.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setIsian(String(m))}
              disabled={!awal}
              className={'rounded-md border px-2 py-1 text-xs ' + (menit === m && sah ? 'border-sky-300 bg-sky-50 text-sky-800' : 'border-slate-300 text-slate-600 hover:bg-slate-50')}
            >
              {m < 60 ? `${m} mnt` : `${m / 60} jam`}
            </button>
          ))}
        </span>
        <button type="submit" disabled={!berubah || menyimpan} className="ml-auto rounded-md bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40">
          {menyimpan ? 'Menyimpan...' : 'Simpan'}
        </button>
      </form>
      {isian !== '' && !sah && <p className="mt-2 text-xs text-red-700">Isi bilangan bulat 0 sampai 1440 menit.</p>}
      {pesan && <p role="status" className="mt-2 text-xs text-emerald-700">{pesan}</p>}
      {galat && <p role="alert" className="mt-2 text-xs text-red-700">{galat}</p>}
    </section>
  )
}
