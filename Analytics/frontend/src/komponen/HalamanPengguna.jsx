import { useEffect, useState } from 'react'
import { daftarPengguna, hapusPengguna, opsiPengguna, tambahPengguna } from '../api'
import Avatar from './Avatar'
import { IkonCari, IkonEdit, IkonHapus, IkonMata, IkonMataCoret, IkonTambahUser } from './Ikon'
import Modal from './Modal'
import PilihCompany from './PilihCompany'
import PopupEditPengguna from './PopupEditPengguna'
import Select from './Select'

const FORM_AWAL = { username: '', sandi: '', nama: '', role: '', divisi: '', company: [] }

// "2026-10-15 09:30:00" -> "15/10/2026 09:30"
const tglJam = (t) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(t ?? '')
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : (t ?? '')
}

// Company sengaja belum dicentang: admin harus memilih sendiri.
const awalForm = (opsi) => ({
  ...FORM_AWAL,
  role: opsi.role_bawaan && opsi.role.includes(opsi.role_bawaan) ? opsi.role_bawaan : (opsi.role[0] ?? ''),
  divisi: opsi.divisi[0] ?? '',
})

const kolomInput =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500'

// admin: penanda dari server (role admin menurut .env ROLE_ADMIN), bukan nama role yang ditulis di sini
const pilRole = (admin) =>
  'inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ' +
  (admin ? 'bg-sky-50 text-sky-800 ring-sky-200' : 'bg-slate-100 text-slate-700 ring-slate-200')

function Isian({ label, untuk, kelas = '', children }) {
  return (
    <div className={kelas}>
      <label htmlFor={untuk} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

// pengguna: akun yang sedang masuk. onSendiriBerubah: admin mengedit akunnya sendiri, supaya nama di bilah atas ikut berubah.
export default function HalamanPengguna({ pengguna, onSendiriBerubah }) {
  const [daftar, setDaftar] = useState(null)
  const [opsi, setOpsi] = useState({ role: [], divisi: [], company: [] })
  const [galat, setGalat] = useState('')
  const [pesan, setPesan] = useState('')
  const [form, setForm] = useState(FORM_AWAL)
  const [mengirim, setMengirim] = useState(false)
  const [dialog, setDialog] = useState(false)
  const [galatForm, setGalatForm] = useState('')
  const [lihatSandi, setLihatSandi] = useState(false)
  const [kata, setKata] = useState('')
  const [hapusTarget, setHapusTarget] = useState(null)
  const [menghapus, setMenghapus] = useState(false)
  const [editTarget, setEditTarget] = useState(null)

  // Daftar akun dan pilihan formulir dimuat terpisah: kalau pilihan role atau company gagal dibaca, daftar akun tetap tampil.
  const muat = () =>
    Promise.allSettled([daftarPengguna(), opsiPengguna()]).then(([d, o]) => {
      if (d.status === 'fulfilled') setDaftar(d.value)
      if (o.status === 'fulfilled') setOpsi(o.value)
      const gagal = [d, o].find((x) => x.status === 'rejected')
      if (gagal) setGalat(gagal.reason.message)
    })

  useEffect(() => {
    muat()
  }, [])

  const bisaTambah = opsi.role.length > 0 && opsi.company.length > 0
  const ubah = (kunci) => (e) => setForm((f) => ({ ...f, [kunci]: e.target.value }))
  // Isian yang belum memenuhi syarat, ditampilkan sebagai pesan kalau Buat akun ditekan sebelum semuanya terisi
  const kurang = [
    !form.username.trim() && 'Username belum diisi.',
    form.sandi.length === 0 ? 'Password belum diisi.' : form.sandi.length < 8 && 'Password minimal 8 karakter.',
    !form.nama.trim() && 'Nama lengkap belum diisi.',
    !form.role && 'Role belum dipilih.',
    !form.divisi.trim() && 'Division belum diisi.',
    form.company.length === 0 && 'Pilih minimal satu company.',
  ].filter(Boolean)
  const lengkap = kurang.length === 0

  const bukaForm = () => {
    setForm(awalForm(opsi))
    setGalatForm('')
    setLihatSandi(false)
    setGalat('')
    setPesan('')
    setDialog(true)
  }
  const tutupForm = () => {
    if (mengirim) return
    setDialog(false)
    setForm(FORM_AWAL) // password tidak tertinggal di memori
    setLihatSandi(false)
    setGalatForm('')
  }

  const kirim = async (e) => {
    e.preventDefault()
    if (mengirim) return
    if (!lengkap) {
      setGalatForm(kurang)
      return
    }
    setMengirim(true)
    setGalatForm('')
    try {
      const baru = await tambahPengguna(form)
      setPesan(`Akun "${baru.username}" dibuat.`)
      setDialog(false)
      setForm(FORM_AWAL)
      setLihatSandi(false)
      await muat()
    } catch (err) {
      setGalatForm(err.message)
    } finally {
      setMengirim(false)
    }
  }

  const konfirmasiHapus = async () => {
    if (!hapusTarget || menghapus) return
    const p = hapusTarget
    setMenghapus(true)
    setGalat('')
    setPesan('')
    try {
      await hapusPengguna(p.id)
      setPesan(`Akun "${p.username}" dihapus.`)
      setHapusTarget(null)
      await muat()
    } catch (err) {
      setGalat(err.message)
      setHapusTarget(null)
    } finally {
      setMenghapus(false)
    }
  }

  const simpanEdit = async (hasil, { passwordDiganti }) => {
    const sendiri = String(hasil.id) === String(pengguna.id)
    setEditTarget(null)
    setGalat('')
    setPesan(`Akun "${hasil.username}" diperbarui.${passwordDiganti && !sendiri ? ' Akun itu keluar dari semua perangkat dan harus masuk lagi dengan password yang baru.' : ''}`)
    if (sendiri && onSendiriBerubah) onSendiriBerubah(hasil)
    await muat()
  }

  const cariKata = kata.trim().toLowerCase()
  const terlihat = (daftar ?? []).filter(
    (p) => !cariKata || [p.username, p.nama, p.role, p.divisi, p.company].some((v) => String(v ?? '').toLowerCase().includes(cariKata)),
  )

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Pengguna</h1>
          <p className="text-sm text-slate-500">Kelola akun yang bisa masuk ke dashboard.</p>
        </div>
        <button
          type="button"
          onClick={bukaForm}
          disabled={!bisaTambah}
          title={bisaTambah ? undefined : 'Pilihan role dan company belum termuat'}
          className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40"
        >
          <IkonTambahUser className="h-4 w-4" />
          Tambah User
        </button>
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

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-medium">
            Daftar Pengguna{' '}
            {daftar && (
              <span className="font-normal text-slate-500">({terlihat.length === daftar.length ? daftar.length : `${terlihat.length} dari ${daftar.length}`})</span>
            )}
          </h2>
          {daftar && daftar.length > 0 && (
            <div className="relative">
              <IkonCari className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={kata}
                onChange={(e) => setKata(e.target.value)}
                placeholder="Masukkan pencarian..."
                aria-label="Cari pengguna"
                className="w-64 rounded-md border border-slate-300 py-1.5 pl-8 pr-2 text-sm"
              />
            </div>
          )}
        </div>
        {daftar === null && !galat && <p className="text-sm text-slate-500">Memuat...</p>}
        {daftar && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs text-slate-500">
                <tr>
                  <th className="px-2 py-2">Username</th>
                  <th className="px-2 py-2">Nama Lengkap</th>
                  <th className="px-2 py-2">Role</th>
                  <th className="px-2 py-2">Division</th>
                  <th className="px-2 py-2">Company</th>
                  <th className="px-2 py-2">Dibuat</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {terlihat.map((p) => (
                  <tr key={p.id} className="border-b border-slate-100">
                    <td className="px-2 py-2">
                      <span className="flex items-center gap-2 font-medium">
                        <Avatar nama={p.nama || p.username} ukuran="h-7 w-7 text-[11px]" />
                        {p.username}
                      </span>
                    </td>
                    <td className="px-2 py-2">{p.nama}</td>
                    <td className="px-2 py-2">
                      <span className={pilRole(p.admin)}>{p.role}</span>
                    </td>
                    <td className="px-2 py-2">{p.divisi || '–'}</td>
                    <td className="px-2 py-2">{p.company || '–'}</td>
                    <td className="px-2 py-2 text-slate-500">{tglJam(p.dibuat) || '–'}</td>
                    <td className="px-2 py-2 text-right">
                      <span className="inline-flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setEditTarget(p)}
                          aria-label={`Edit akun ${p.username}`}
                          className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                        >
                          <IkonEdit className="h-3.5 w-3.5" />
                          Edit
                        </button>
                        {String(p.id) === String(pengguna.id) ? (
                          <span className="text-xs text-slate-400">akun Anda</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setHapusTarget(p)}
                            aria-label={`Hapus akun ${p.username}`}
                            className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                          >
                            <IkonHapus className="h-3.5 w-3.5" />
                            Hapus
                          </button>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
                {terlihat.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-2 py-6 text-center text-sm text-slate-500">
                      Tidak ada akun yang cocok dengan pencarian.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {dialog && (
        <Modal kecil="Akun baru" judul="Tambah user" onTutup={tutupForm}>
          <form onSubmit={kirim} autoComplete="off" className="space-y-4">
            {galatForm && !(Array.isArray(galatForm) && lengkap) && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {/* Daftar isian yang kurang ikut berkurang saat diisi, jadi yang tampil selalu yang masih kurang */}
                {Array.isArray(galatForm) ? (
                  <>
                    <p className="font-medium">Akun belum bisa dibuat:</p>
                    <ul className="mt-1 list-disc pl-5">
                      {kurang.map((t) => (
                        <li key={t}>{t}</li>
                      ))}
                    </ul>
                  </>
                ) : (
                  galatForm
                )}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Isian label="Username" untuk="f-username">
                <input id="f-username" type="text" autoFocus autoComplete="off" placeholder="Username" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value.toUpperCase() }))} className={kolomInput} />
              </Isian>
              <Isian label="Password" untuk="f-sandi">
                <div className="relative">
                  <input
                    id="f-sandi"
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
              <Isian label="Nama lengkap" untuk="f-nama" kelas="sm:col-span-2">
                <input id="f-nama" type="text" autoComplete="off" placeholder="Nama lengkap user" value={form.nama} onChange={ubah('nama')} className={kolomInput} />
              </Isian>
              <Isian label="Role" untuk="f-role">
                <Select id="f-role" value={form.role} onChange={ubah('role')}>
                  {opsi.role.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </Select>
              </Isian>
              <Isian label="Division" untuk="f-divisi">
                {opsi.divisi.length > 0 ? (
                  <Select id="f-divisi" value={form.divisi} onChange={ubah('divisi')}>
                    {opsi.divisi.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <input id="f-divisi" type="text" autoComplete="off" placeholder="Nama division" value={form.divisi} onChange={ubah('divisi')} className={kolomInput} />
                )}
              </Isian>
              <PilihCompany kelas="sm:col-span-2" opsi={opsi.company} terpilih={form.company} onUbah={(company) => setForm((f) => ({ ...f, company }))} />
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
              <button type="button" onClick={tutupForm} disabled={mengirim} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-40">
                Batal
              </button>
              <button
                type="submit"
                disabled={mengirim}
                className="inline-flex items-center gap-2 rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-40"
              >
                <IkonTambahUser className="h-4 w-4" />
                {mengirim ? 'Menyimpan...' : 'Buat akun'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editTarget && (
        <PopupEditPengguna
          key={editTarget.id}
          akun={editTarget}
          opsi={opsi}
          sendiri={String(editTarget.id) === String(pengguna.id)}
          onTutup={() => setEditTarget(null)}
          onSimpan={simpanEdit}
        />
      )}

      {hapusTarget && (
        <Modal kecil="Konfirmasi" judul="Hapus akun?" lebar="max-w-md" onTutup={() => !menghapus && setHapusTarget(null)}>
          <p className="text-sm text-slate-600">
            Akun <strong className="text-slate-900">{hapusTarget.username}</strong> ({hapusTarget.nama}) akan dihapus dan tidak bisa dipakai masuk lagi. Tindakan ini tidak bisa dibatalkan.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setHapusTarget(null)} disabled={menghapus} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-40">
              Batal
            </button>
            <button type="button" onClick={konfirmasiHapus} disabled={menghapus} className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40">
              {menghapus ? 'Menghapus...' : 'Hapus akun'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
