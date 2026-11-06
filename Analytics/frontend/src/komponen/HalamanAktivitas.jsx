import { useEffect, useState } from 'react'
import { ambilAktivitas, ambilPengaturanSesi } from '../api'
import { useAmbil } from '../lib/ambil'
import Avatar from './Avatar'
import PengaturanIdle from './PengaturanIdle'
import SesiAktif from './SesiAktif'
import Select from './Select'
import { angka } from '../lib/data'
import { Kosong, Memuat } from './Keadaan'

const isoLokal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const hariLalu = (n) => isoLokal(new Date(Date.now() - n * 86400000))
const waktu = (iso) =>
  new Date(iso).toLocaleString('id-ID', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

const AWAL = { mulai: hariLalu(6), akhir: hariLalu(0), pengguna: '', jenis: '', laporan: '', halaman: 1 }
const kelasTanggal = 'rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500'

// Siapa masuk, laporan apa yang dibuka, siapa export Excel, dan perubahan akun atau hak akses. Klik pengguna di tabel kiri untuk memfilter log.
export default function HalamanAktivitas() {
  const [opsi, setOpsi] = useState(AWAL)
  const [batasIdle, setBatasIdle] = useState(0)
  useEffect(() => {
    ambilPengaturanSesi()
      .then((p) => setBatasIdle(p.idle_menit))
      .catch(() => {})
  }, [])
  const { data, galat, memuat } = useAmbil(JSON.stringify(opsi), (sinyal) => ambilAktivitas(opsi, sinyal))
  const ubah = (bagian) => setOpsi((o) => ({ ...o, halaman: 1, ...bagian }))
  const pilihPengguna = (username) => ubah({ pengguna: opsi.pengguna === username ? '' : username })
  const adaFilter = opsi.pengguna || opsi.jenis || opsi.laporan

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Log Aktivitas</h1>
        <p className="text-sm text-slate-500">
          Siapa yang masuk, laporan apa yang dibuka, siapa yang export Excel, dan perubahan akun atau hak akses.
          {data && ` Disimpan ${data.simpan_hari} hari.`}
        </p>
      </header>

      <PengaturanIdle onBerubah={(p) => setBatasIdle(p.idle_menit)} />
      <SesiAktif batasIdle={batasIdle} />

      <section aria-label="Filter log" className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-600">
          Dari
          <input type="date" value={opsi.mulai} max={opsi.akhir} onChange={(e) => e.target.value && ubah({ mulai: e.target.value })} className={'mt-1 block ' + kelasTanggal} />
        </label>
        <label className="text-sm text-slate-600">
          Sampai
          <input type="date" value={opsi.akhir} min={opsi.mulai} max={hariLalu(0)} onChange={(e) => e.target.value && ubah({ akhir: e.target.value })} className={'mt-1 block ' + kelasTanggal} />
        </label>
        <label className="min-w-44 text-sm text-slate-600">
          Aktivitas
          <Select className="mt-1" kecil value={opsi.jenis} onChange={(e) => ubah({ jenis: e.target.value })}>
            <option value="">Semua</option>
            {(data?.pilihan.jenis ?? []).map((j) => (
              <option key={j.kunci} value={j.kunci}>
                {j.nama}
              </option>
            ))}
          </Select>
        </label>
        <label className="min-w-52 text-sm text-slate-600">
          Laporan
          <Select className="mt-1" kecil value={opsi.laporan} onChange={(e) => ubah({ laporan: e.target.value })}>
            <option value="">Semua</option>
            {(data?.pilihan.laporan ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.nama}
              </option>
            ))}
          </Select>
        </label>
        {opsi.pengguna && (
          <button type="button" onClick={() => ubah({ pengguna: '' })} aria-label={`Lepas filter pengguna ${opsi.pengguna}`} className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs hover:bg-slate-100">
            Pengguna: {opsi.pengguna} ×
          </button>
        )}
        {adaFilter && (
          <button type="button" onClick={() => ubah({ pengguna: '', jenis: '', laporan: '' })} className="px-1 py-1.5 text-xs text-slate-600 underline">
            Reset filter
          </button>
        )}
      </section>

      {galat && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Log tidak bisa dimuat: {galat.message}
        </div>
      )}
      {!data && !galat && <Memuat teks="Memuat log aktivitas..." />}

      {data && (
        <div className={'grid items-start gap-4 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] ' + (memuat ? 'opacity-60' : '')}>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="font-medium">Per pengguna</h2>
            <p className="mb-3 text-xs text-slate-500">Klik nama untuk melihat aktivitasnya saja.</p>
            {data.per_pengguna.length === 0 ? (
              <Kosong teks="Tidak ada pengguna aktif pada periode ini." />
            ) : (
              <div className="max-h-[28rem] overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-10 border-b border-slate-200 bg-white text-xs text-slate-500">
                  <tr>
                    <th className="py-2 pr-2 font-medium">Pengguna</th>
                    <th className="px-2 py-2 text-right font-medium" title="Laporan dibuka">Buka</th>
                    <th className="py-2 pl-2 text-right font-medium">Export</th>
                  </tr>
                </thead>
                <tbody>
                  {data.per_pengguna.map((p) => {
                    const aktif = opsi.pengguna === p.username
                    return (
                      <tr
                        key={p.username}
                        tabIndex={0}
                        aria-selected={aktif}
                        onClick={() => pilihPengguna(p.username)}
                        onKeyDown={(e) => e.key === 'Enter' && pilihPengguna(p.username)}
                        title={p.laporan.length ? `Laporan dibuka: ${p.laporan.join(', ')}` : undefined}
                        className={'cursor-pointer border-b border-slate-100 focus:outline-none focus-visible:bg-sky-50 ' + (aktif ? 'bg-sky-50' : 'hover:bg-slate-50')}
                      >
                        <td className="py-2 pr-2">
                          <span className="flex items-center gap-2">
                            <Avatar nama={p.nama || p.username} ukuran="h-7 w-7 text-[11px]" />
                            <span className="min-w-0">
                              <span className="block truncate font-medium text-slate-800">{p.nama || p.username}</span>
                              <span className="block truncate text-xs text-slate-500">terakhir {waktu(p.terakhir)}</span>
                            </span>
                          </span>
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums">{angka.format(p.muat)}</td>
                        <td className="py-2 pl-2 text-right tabular-nums">{angka.format(p.ekspor)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </div>
            )}
          </section>

          <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-medium">
                Aktivitas <span className="font-normal text-slate-500">({angka.format(data.total)})</span>
              </h2>
              {data.jumlah_gagal_masuk > 0 && opsi.jenis !== 'gagal_masuk' && (
                <button type="button" onClick={() => ubah({ jenis: 'gagal_masuk' })} className="text-xs text-red-700 underline">
                  {angka.format(data.jumlah_gagal_masuk)} percobaan masuk gagal
                </button>
              )}
            </div>
            {data.baris.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                {adaFilter ? 'Tidak ada aktivitas yang cocok dengan filter ini.' : 'Belum ada aktivitas pada periode ini.'}
              </p>
            ) : (
              // Tinggi dibatasi supaya halaman tidak memanjang ke bawah; riwayat digulir di dalam kotak, judul kolom tetap terlihat
              <div className="max-h-[28rem] overflow-auto">
                <table className="w-full min-w-[46rem] text-left text-sm">
                  <thead className="sticky top-0 z-10 border-b border-slate-200 bg-white text-xs text-slate-500">
                    <tr>
                      <th className="py-2 pr-2 font-medium">Waktu</th>
                      <th className="px-2 py-2 font-medium">Pengguna</th>
                      <th className="px-2 py-2 font-medium">Aktivitas</th>
                      <th className="px-2 py-2 font-medium">Laporan</th>
                      <th className="px-2 py-2 font-medium">Keterangan</th>
                      <th className="py-2 pl-2 font-medium">IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.baris.map((b, i) => (
                      <tr key={`${b.waktu}-${i}`} className="border-b border-slate-100 align-top">
                        <td className="whitespace-nowrap py-2 pr-2 tabular-nums text-slate-600">{waktu(b.waktu)}</td>
                        <td className="px-2 py-2">
                          <span className="block font-medium text-slate-800">{b.nama || b.username || '–'}</span>
                          {b.nama && <span className="block text-xs text-slate-500">{b.username}</span>}
                        </td>
                        <td className={'whitespace-nowrap px-2 py-2 ' + (b.jenis === 'gagal_masuk' ? 'font-medium text-red-700' : '')}>{b.jenis_nama}</td>
                        <td className="px-2 py-2">{b.laporan_nama || '–'}</td>
                        <td className="max-w-md px-2 py-2 text-slate-600">{b.keterangan || '–'}</td>
                        <td className="whitespace-nowrap py-2 pl-2 tabular-nums text-slate-500">{b.ip || '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {data.jumlah_halaman > 1 && (
              <div className="mt-3 flex items-center justify-end gap-2 text-xs text-slate-600">
                <button type="button" disabled={data.halaman <= 1} onClick={() => setOpsi((o) => ({ ...o, halaman: data.halaman - 1 }))} className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40">
                  Sebelumnya
                </button>
                <span className="tabular-nums">
                  Halaman {data.halaman} dari {data.jumlah_halaman}
                </span>
                <button type="button" disabled={data.halaman >= data.jumlah_halaman} onClick={() => setOpsi((o) => ({ ...o, halaman: data.halaman + 1 }))} className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40">
                  Berikutnya
                </button>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
