import { useEffect, useState } from 'react'
import { daftarStruktur, tambahDivisi, tambahRole } from '../api'
import Modal from './Modal'
import Select from './Select'
import { Memuat } from './Keadaan'

const kolomInput =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500'
const tombolUtama = 'rounded-lg bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40'
const tombolKedua = 'rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40'

function Isian({ label, untuk, bantuan, children }) {
  return (
    <div>
      <label htmlFor={untuk} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {bantuan && <p className="mt-1 text-xs text-slate-500">{bantuan}</p>}
    </div>
  )
}

const namaCompany = (c) => (c ? `${c.nama} · ${c.jenis}` : '–')

// Form tambah divisi atau role. isian: [{ kunci, label, ... }]; nilai awal dari `awal`.
function FormTambah({ kecil, judul, awal, isian, kirim, onTutup, onSelesai }) {
  const [form, setForm] = useState(awal)
  const [galat, setGalat] = useState('')
  const [menyimpan, setMenyimpan] = useState(false)

  const simpan = async (e) => {
    e.preventDefault()
    setGalat('')
    setMenyimpan(true)
    try {
      onSelesai(await kirim(form))
    } catch (err) {
      setGalat(err.message)
      setMenyimpan(false)
    }
  }

  return (
    <Modal kecil={kecil} judul={judul} onTutup={onTutup}>
      <form onSubmit={simpan} autoComplete="off" className="space-y-4">
        {galat && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {galat}
          </div>
        )}
        {isian.map(({ kunci, label, bantuan, pilihan, panjang, ...lain }) => (
          <Isian key={kunci} label={label} untuk={`s-${kunci}`} bantuan={bantuan}>
            {pilihan ? (
              <Select id={`s-${kunci}`} value={form[kunci]} onChange={(e) => setForm({ ...form, [kunci]: e.target.value })}>
                {pilihan.map(([nilai, teks]) => (
                  <option key={nilai} value={nilai}>
                    {teks}
                  </option>
                ))}
              </Select>
            ) : (
              <input id={`s-${kunci}`} type="text" maxLength={panjang} value={form[kunci]} onChange={(e) => setForm({ ...form, [kunci]: e.target.value })} className={kolomInput} {...lain} />
            )}
          </Isian>
        ))}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onTutup} className={tombolKedua}>
            Batal
          </button>
          <button type="submit" disabled={menyimpan} className={tombolUtama}>
            {menyimpan ? 'Menyimpan...' : 'Simpan'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// Divisi dan role dibaca dari tabel DIVISION dan role. Halaman ini hanya menambah; mengubah dan menghapus tetap lewat database.
export default function HalamanStruktur() {
  const [data, setData] = useState(null)
  const [galat, setGalat] = useState('')
  const [pesan, setPesan] = useState('')
  const [dialog, setDialog] = useState(null) // 'divisi' | 'role' | null

  const muat = () =>
    daftarStruktur()
      .then((d) => {
        setData(d)
        setGalat('')
      })
      .catch((e) => setGalat(e.message))

  useEffect(() => {
    muat()
  }, [])

  const selesai = (teks) => {
    setDialog(null)
    setPesan(teks)
    muat()
  }

  const company = Object.fromEntries((data?.company ?? []).map((c) => [c.id, c]))
  const divisiAktif = (data?.divisi ?? []).filter((d) => d.aktif)
  const tanpaDivisi = (data?.role ?? []).filter((r) => !data.divisi.some((d) => d.id === r.divisi_id))

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Role &amp; Divisi</h1>
          <p className="text-sm text-slate-500">Divisi dan role yang bisa dipilih saat membuat atau mengubah akun.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setDialog('divisi')} disabled={!data || data.company.length === 0} className={tombolKedua}>
            Tambah divisi
          </button>
          <button type="button" onClick={() => setDialog('role')} disabled={divisiAktif.length === 0} title={data && divisiAktif.length === 0 ? 'Buat divisi dulu' : undefined} className={tombolUtama}>
            Tambah role
          </button>
        </div>
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
      {data === null && !galat && <Memuat />}

      {data &&
        [...data.divisi.map((d) => ({ ...d, role: data.role.filter((r) => r.divisi_id === d.id) })), ...(tanpaDivisi.length ? [{ id: 'lain', nama: 'Tanpa divisi', role: tanpaDivisi, aktif: true }] : [])].map((d) => (
          <section key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 pb-2">
              <h2 className="font-medium">
                {d.nama}
                {d.kode && <span className="ml-2 text-xs font-normal text-slate-500">{d.kode}</span>}
                {!d.aktif && <span className="ml-2 text-xs font-normal text-amber-700">nonaktif</span>}
              </h2>
              {d.comp_id != null && <span className="text-xs text-slate-500">{namaCompany(company[d.comp_id])}</span>}
            </div>
            {d.role.length === 0 ? (
              <p className="py-2 text-sm text-slate-500">Belum ada role.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {d.role.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2 text-sm">
                    <span className="font-medium text-slate-800">
                      {r.nama}
                      {!r.aktif && <span className="ml-2 text-xs font-normal text-amber-700">nonaktif</span>}
                    </span>
                    <span className="text-slate-500">{r.deskripsi || '–'}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}

      {dialog === 'divisi' && (
        <FormTambah
          kecil="Divisi baru"
          judul="Tambah divisi"
          awal={{ nama: '', kode: '', company_id: String(data.company[0].id) }}
          isian={[
            { kunci: 'nama', label: 'Nama divisi', panjang: 50, placeholder: 'mis. Supply Chain', autoFocus: true },
            { kunci: 'kode', label: 'Kode', panjang: 20, placeholder: 'mis. SC', bantuan: 'Singkatan unik, otomatis huruf besar.' },
            { kunci: 'company_id', label: 'Company', pilihan: data.company.map((c) => [String(c.id), namaCompany(c)]) },
          ]}
          kirim={(f) => tambahDivisi({ ...f, company_id: Number(f.company_id) })}
          onTutup={() => setDialog(null)}
          onSelesai={(d) => selesai(`Divisi "${d.nama}" dibuat.`)}
        />
      )}
      {dialog === 'role' && (
        <FormTambah
          kecil="Role baru"
          judul="Tambah role"
          awal={{ nama: '', deskripsi: '', divisi_id: String(divisiAktif[0].id) }}
          isian={[
            { kunci: 'nama', label: 'Nama role', panjang: 30, placeholder: 'mis. Buyer', autoFocus: true },
            { kunci: 'divisi_id', label: 'Divisi', pilihan: divisiAktif.map((d) => [String(d.id), d.nama]) },
            { kunci: 'deskripsi', label: 'Deskripsi', panjang: 255, placeholder: 'Opsional' },
          ]}
          kirim={(f) => tambahRole({ ...f, divisi_id: Number(f.divisi_id) })}
          onTutup={() => setDialog(null)}
          onSelesai={(r) => selesai(`Role "${r.nama}" dibuat. Atur laporan yang boleh dibukanya di Permission Control.`)}
        />
      )}
    </div>
  )
}
