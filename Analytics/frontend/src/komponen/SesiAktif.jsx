import { useEffect, useState } from 'react'
import { cabutSesi, daftarSesi } from '../api'
import { useAmbil } from '../lib/ambil'
import Avatar from './Avatar'
import { IkonSegarkan } from './Ikon'

const jam = (iso) => (iso ? new Date(iso).toLocaleString('id-ID', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '–')

// Lama sejak waktu itu sampai sekarang: "baru saja", "12 mnt", "2 jam 5 mnt"
function lama(iso, sekarang) {
  if (!iso) return '–'
  const menit = Math.floor((sekarang - new Date(iso).getTime()) / 60000)
  if (menit < 1) return 'baru saja'
  if (menit < 60) return `${menit} mnt`
  return `${Math.floor(menit / 60)} jam${menit % 60 ? ` ${menit % 60} mnt` : ''}`
}

// Siapa yang sedang masuk (sesi yang masih berlaku) dan tombol untuk mengeluarkannya. Perangkat yang dikeluarkan diberi tahu alasannya.
// batasIdle: menit (0 = tanpa batas), untuk menandai sesi yang hampir keluar otomatis.
export default function SesiAktif({ batasIdle = 0 }) {
  const [muatUlang, setMuatUlang] = useState(0)
  // Lama masuk dan lama idle dihitung ulang tiap 30 detik tanpa meminta ke server; daftar sesinya diperbarui lewat tombol Perbarui
  const [sekarang, setSekarang] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setSekarang(Date.now()), 30000)
    return () => clearInterval(t)
  }, [])
  useEffect(() => setSekarang(Date.now()), [muatUlang])
  const [konfirmasi, setKonfirmasi] = useState(null)
  const [pesan, setPesan] = useState('')
  const [galatAksi, setGalatAksi] = useState('')
  const { data, galat, memuat } = useAmbil(String(muatUlang), (sinyal) => daftarSesi(sinyal))

  const keluarkan = async (s) => {
    setGalatAksi('')
    try {
      await cabutSesi(s.id)
      setPesan(`${s.nama || s.username} dikeluarkan.`)
    } catch (e) {
      setGalatAksi(e.message)
    }
    setKonfirmasi(null)
    setMuatUlang((n) => n + 1)
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-medium">
          Sedang masuk {data && <span className="font-normal text-slate-500">({data.length})</span>}
        </h2>
        <button type="button" onClick={() => setMuatUlang((n) => n + 1)} className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50">
          <IkonSegarkan className={'h-3.5 w-3.5 ' + (memuat ? 'animate-spin' : '')} />
          Perbarui
        </button>
      </div>
      {pesan && <p role="status" className="mb-2 text-sm text-emerald-700">{pesan}</p>}
      {(galat || galatAksi) && <p role="alert" className="mb-2 text-sm text-red-700">{galatAksi || `Daftar sesi tidak bisa dimuat: ${galat.message}`}</p>}
      {!data && !galat && <p className="text-sm text-slate-500">Memuat sesi...</p>}
      {data && data.length === 0 && <p className="py-4 text-center text-sm text-slate-500">Tidak ada yang sedang masuk.</p>}
      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="border-b border-slate-200 text-xs text-slate-500">
              <tr>
                <th className="py-2 pr-2 font-medium">Pengguna</th>
                <th className="px-2 py-2 font-medium">Masuk</th>
                <th className="px-2 py-2 font-medium">Lama masuk</th>
                <th className="px-2 py-2 font-medium">Idle</th>
                <th className="px-2 py-2 font-medium">Asal</th>
                <th className="py-2 pl-2" />
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="border-b border-slate-100">
                  <td className="py-2 pr-2">
                    <span className="flex items-center gap-2">
                      <Avatar nama={s.nama || s.username} ukuran="h-7 w-7 text-[11px]" />
                      <span className="min-w-0">
                        <span className="block font-medium text-slate-800">{s.nama || s.username}</span>
                        <span className="block text-xs text-slate-500">
                          {s.username}
                          {s.role && ` · ${s.role}`}
                        </span>
                      </span>
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-2 py-2 tabular-nums text-slate-600">{jam(s.masuk)}</td>
                  <td className="whitespace-nowrap px-2 py-2 tabular-nums text-slate-600">{lama(s.masuk, sekarang)}</td>
                  <td className="whitespace-nowrap px-2 py-2 tabular-nums" title={s.terakhir ? `Aktivitas terakhir ${jam(s.terakhir)}` : undefined}>
                    {(() => {
                      const idleMenit = s.terakhir ? (sekarang - new Date(s.terakhir).getTime()) / 60000 : 0
                      const hampir = batasIdle > 0 && idleMenit >= batasIdle * 0.75
                      return <span className={hampir ? 'font-medium text-amber-700' : 'text-slate-600'}>{s.sesi_ini ? 'aktif' : lama(s.terakhir, sekarang)}</span>
                    })()}
                  </td>
                  <td className="whitespace-nowrap px-2 py-2 tabular-nums text-slate-500">{s.asal?.replace(/^IP /, '') || '–'}</td>
                  <td className="whitespace-nowrap py-2 pl-2 text-right">
                    {s.sesi_ini ? (
                      <span className="text-xs text-slate-400">sesi Anda</span>
                    ) : konfirmasi === s.id ? (
                      <span className="inline-flex items-center gap-2 text-xs">
                        <span className="text-slate-600">Keluarkan?</span>
                        <button type="button" onClick={() => keluarkan(s)} className="rounded-md bg-red-700 px-2 py-1 text-white hover:bg-red-800">
                          Ya, keluarkan
                        </button>
                        <button type="button" onClick={() => setKonfirmasi(null)} className="rounded-md border border-slate-300 px-2 py-1 text-slate-700 hover:bg-slate-50">
                          Batal
                        </button>
                      </span>
                    ) : (
                      <button type="button" onClick={() => setKonfirmasi(s.id)} className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50">
                        Paksa keluar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
