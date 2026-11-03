import { useState } from 'react'
import { ubahPengguna } from '../api'
import { IkonEdit, IkonMata, IkonMataCoret } from './Ikon'
import Modal from './Modal'
import PilihCompany, { pisahCompany } from './PilihCompany'
import Select from './Select'

const kolomInput =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:bg-slate-50 disabled:text-slate-500'

// Pilihan untuk dropdown, ditambah nilai akun saat ini kalau sudah tidak ada di pilihan (mis. role dinonaktifkan), supaya yang tampil tetap
// nilai sebenarnya dan tidak diam-diam berubah ke pilihan pertama.
const denganNilai = (pilihan, nilai) => (!nilai || pilihan.some((p) => p.toLowerCase() === nilai.toLowerCase()) ? pilihan : [nilai, ...pilihan])

function Isian({ label, untuk, bantuan, kelas = '', children }) {
  return (
    <div className={kelas}>
      <label htmlFor={untuk} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {bantuan && <p className="mt-1 text-xs text-slate-500">{bantuan}</p>}
    </div>
  )
}

// Password kosong = tidak diganti. sendiri: akun admin yang sedang dipakai, rolenya tidak bisa diubah.
export default function PopupEditPengguna({ akun, opsi, sendiri, onTutup, onSimpan }) {
  const [form, setForm] = useState({ nama: akun.nama, role: akun.role, divisi: akun.divisi ?? '', company: pisahCompany(akun.company), sandi: '' })
  const [mengirim, setMengirim] = useState(false)
  const [galat, setGalat] = useState('')
  const [lihatSandi, setLihatSandi] = useState(false)

  const ubah = (kunci) => (e) => setForm((f) => ({ ...f, [kunci]: e.target.value }))
  const berubah = form.nama.trim() !== akun.nama || form.role !== akun.role || form.divisi.trim() !== (akun.divisi ?? '') || [...form.company].sort().join() !== pisahCompany(akun.company).sort().join() || form.sandi !== ''
  const sah = form.nama.trim() && form.divisi.trim() && form.company.length > 0 && form.role && (form.sandi === '' || form.sandi.length >= 8)

  const kirim = async (e) => {
    e.preventDefault()
    if (mengirim || !sah || !berubah) return
    setMengirim(true)
    setGalat('')
    try {
      const hasil = await ubahPengguna(akun.id, { nama: form.nama, role: form.role, divisi: form.divisi, company: form.company, sandi: form.sandi || null })
      onSimpan(hasil, { passwordDiganti: form.sandi !== '' })
    } catch (err) {
      setGalat(err.message)
    } finally {
      setMengirim(false)
    }
  }
  const tutup = () => {
    if (!mengirim) onTutup()
  }

  return (
    <Modal kecil="Ubah akun" judul="Edit user" onTutup={tutup}>
      <form onSubmit={kirim} autoComplete="off" className="space-y-4">
        {galat && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {galat}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Isian label="Username" untuk="e-username" bantuan="Username tidak bisa diubah." kelas="sm:col-span-2">
            <input id="e-username" type="text" value={akun.username} disabled className={kolomInput} />
          </Isian>
          <Isian label="Nama lengkap" untuk="e-nama" kelas="sm:col-span-2">
            <input id="e-nama" type="text" autoFocus autoComplete="off" value={form.nama} onChange={ubah('nama')} className={kolomInput} />
          </Isian>
          <Isian label="Role" untuk="e-role" bantuan={sendiri ? 'Anda tidak bisa mengubah role akun Anda sendiri.' : undefined}>
            <Select id="e-role" value={form.role} onChange={ubah('role')} disabled={sendiri}>
              {denganNilai(opsi.role, akun.role).map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </Isian>
          <Isian label="Division" untuk="e-divisi">
            {opsi.divisi.length > 0 ? (
              <Select id="e-divisi" value={form.divisi} onChange={ubah('divisi')}>
                {denganNilai(opsi.divisi, akun.divisi).map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </Select>
            ) : (
              <input id="e-divisi" type="text" autoComplete="off" value={form.divisi} onChange={ubah('divisi')} className={kolomInput} />
            )}
          </Isian>
          <PilihCompany kelas="sm:col-span-2" opsi={opsi.company} terpilih={form.company} onUbah={(company) => setForm((f) => ({ ...f, company }))} />
          <Isian
            label="Password baru"
            untuk="e-sandi"
            kelas="sm:col-span-2"
            bantuan={
              form.sandi === ''
                ? 'Kosongkan kalau password tidak diganti.'
                : sendiri
                  ? 'Password akun Anda akan diganti.'
                  : 'Akun ini akan keluar dari semua perangkat dan harus masuk lagi dengan password yang baru.'
            }
          >
            <div className="relative">
              <input
                id="e-sandi"
                type={lihatSandi ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="Minimal 8 karakter"
                value={form.sandi}
                onChange={ubah('sandi')}
                className={kolomInput + ' pr-10'}
              />
              <button
                type="button"
                onClick={() => setLihatSandi((v) => !v)}
                aria-label={lihatSandi ? 'Sembunyikan password' : 'Tampilkan password'}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:bg-slate-100"
              >
                {lihatSandi ? <IkonMataCoret className="h-4 w-4" /> : <IkonMata className="h-4 w-4" />}
              </button>
            </div>
          </Isian>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
          <button type="button" onClick={tutup} disabled={mengirim} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-40">
            Batal
          </button>
          <button
            type="submit"
            disabled={mengirim || !sah || !berubah}
            className="inline-flex items-center gap-2 rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40"
          >
            <IkonEdit className="h-4 w-4" />
            {mengirim ? 'Menyimpan...' : 'Simpan perubahan'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
