import { useEffect, useState } from 'react'
import { aturIzin, daftarIzin } from '../api'
import { IkonInfo, IkonKunci, IkonLaporan, IkonPerisai } from './Ikon'
import Saklar from './Saklar'
import Select from './Select'

const teksHak = (boleh) => (boleh ? 'Akses' : '–')

const jumlahAkses = (role, laporan, halaman) =>
  laporan.filter((l) => (halaman.some((h) => h.id === l.id) ? role.izin_halaman?.[l.id] : role.izin[l.id])).length

// Berlaku langsung, tanpa pengguna harus login ulang. Role admin selalu penuh.
export default function HalamanIzin() {
  const [data, setData] = useState(null)
  const [galat, setGalat] = useState('')
  const [pilih, setPilih] = useState('')
  const [menyimpan, setMenyimpan] = useState('')
  const [pesan, setPesan] = useState('')

  const muat = () =>
    daftarIzin()
      .then((d) => {
        setData(d)
        setGalat('')
        setPilih((sekarang) => (d.role.some((r) => r.nama === sekarang) ? sekarang : (d.role.find((r) => !r.admin) ?? d.role[0])?.nama ?? ''))
      })
      .catch((e) => setGalat(e.message))

  useEffect(() => {
    muat()
  }, [])

  const role = data?.role.find((r) => r.nama === pilih)
  const namaAdmin = data?.role.find((r) => r.admin)?.nama
  const semuaHalaman = [...(data?.laporan ?? []), ...(data?.halaman ?? [])]

  // Tampilan baru berubah setelah server menyimpan, jadi yang terlihat selalu yang tersimpan.
  const ubah = async (lap, nilai) => {
    setMenyimpan(`${role.id}|${lap.id}`)
    setGalat('')
    setPesan('')
    try {
      const h = await aturIzin({ role: role.nama, laporan: lap.id, akses: nilai })
      const izinHalaman = semuaHalaman.some((h) => h.id === lap.id)
      setData((d) => ({
        ...d,
        role: d.role.map((r) => (r.id !== role.id ? r : izinHalaman
          ? { ...r, izin_halaman: { ...r.izin_halaman, [lap.id]: h.akses } }
          : { ...r, izin: { ...r.izin, [lap.id]: h.akses } })),
      }))
      setPesan(`Akses ${role.nama} ke ${lap.nama} ${h.akses ? 'diizinkan' : 'dicabut'}.`)
    } catch (e) {
      setGalat(e.message)
    } finally {
      setMenyimpan('')
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs font-medium text-slate-500">Akses berbasis role</p>
        <h1 className="text-2xl font-semibold">Permission Control</h1>
        <p className="text-sm text-slate-500">Atur role mana yang boleh membuka setiap laporan.</p>
      </header>

      {galat && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {galat}
        </div>
      )}
      {pesan && (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {pesan}
        </div>
      )}
      {data === null && !galat && <p className="text-sm text-slate-500">Memuat...</p>}

      {data && (
        <>
          <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <label htmlFor="pilih-role" className="text-xs font-medium text-slate-600">
                Pilih role
              </label>
              <Select id="pilih-role" value={pilih} onChange={(e) => setPilih(e.target.value)} className="min-w-52">
                {data.role.map((r) => (
                  <option key={r.id} value={r.nama}>
                    {r.nama}
                  </option>
                ))}
              </Select>
            </div>
            {role && (
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-sky-700">
                  <IkonPerisai className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-medium">{role.nama}</p>
                  <p className="text-xs text-slate-500">
                    {role.admin ? 'Akses penuh ke semua halaman' : `${jumlahAkses(role, semuaHalaman, data.halaman ?? [])} dari ${semuaHalaman.length} halaman aktif`}
                  </p>
                </div>
              </div>
            )}
          </section>

          {role && (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <p className="text-xs font-medium text-slate-500">Konfigurasi hak akses</p>
                  <h2 className="text-lg font-semibold">Hak per halaman</h2>
                </div>
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <IkonKunci className="h-3.5 w-3.5" />
                  Role {role.nama}
                </span>
              </div>

              <ul className="divide-y divide-slate-100">
                {semuaHalaman.map((l) => {
                  const boleh = Boolean(data.halaman?.some((h) => h.id === l.id) ? role.izin_halaman?.[l.id] : role.izin[l.id])
                  return (
                    <li key={l.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                          <IkonLaporan className="h-5 w-5" />
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-medium">{l.nama}</p>
                          <p className="text-xs text-slate-500">{l.deskripsi}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {menyimpan === `${role.id}|${l.id}` && (
                          <span role="status" className="text-xs text-slate-500">
                            Menyimpan...
                          </span>
                        )}
                        <div className="flex flex-col items-center gap-1.5">
                          <span className="text-[11px] text-slate-500">Akses</span>
                          <Saklar nyala={boleh} nonaktif={role.admin || Boolean(menyimpan)} label={`Akses ${l.nama} untuk ${role.nama}`} onUbah={(v) => ubah(l, v)} />
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>

              <p className="mt-3 flex items-start gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
                <IkonInfo className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {namaAdmin ? `Role ${namaAdmin}` : 'Role admin'} selalu memiliki akses penuh dan tidak bisa dibatasi dari halaman ini. Halaman baru tertutup bagi semua role lain sampai
                  diberi akses di sini.
                </span>
              </p>
            </section>
          )}

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-1 font-medium">Ringkasan: siapa bisa membuka apa</h2>
            <p className="mb-3 text-xs text-slate-500">Hak semua role sekaligus, sesuai yang tersimpan.</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[28rem] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Role</th>
                    {semuaHalaman.map((l) => (
                      <th key={l.id} className="px-2 py-2">
                        {l.nama}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.role.map((r) => (
                    <tr key={r.id} className="border-b border-slate-100">
                      <td className="px-2 py-2 font-medium">{r.nama}</td>
                      {semuaHalaman.map((l) => (
                        <td key={l.id} className={'px-2 py-2 ' + ((data.halaman?.some((h) => h.id === l.id) ? r.izin_halaman?.[l.id] : r.izin[l.id]) ? 'text-slate-800' : 'text-slate-400')}>
                          {teksHak(data.halaman?.some((h) => h.id === l.id) ? r.izin_halaman?.[l.id] : r.izin[l.id])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
