import { useState } from 'react'
import { ambilRincian } from '../api'
import { useAmbil } from '../lib/ambil'
import { angka, formatSel } from '../lib/data'
import Modal from './Modal'
import TabelBaris from './TabelBaris'
import { Memuat } from './Keadaan'

const MIN_BARIS_CARI = 6   // kotak cari baru muncul kalau ada tabel yang cukup panjang untuk dicari

// Baris cocok kalau teks yang tampil di salah satu kolomnya memuat kata yang dicari (besar kecil huruf diabaikan)
function cocok(baris, kolom, kata) {
  return kolom.some((k) => String(formatSel(baris[k.kunci], k.tipe) ?? '').toLowerCase().includes(kata))
}

// Rincian satu baris tabel detail. buka: { jenis, kunci, judul } atau null.
export default function JendelaRincian({ laporanId, dataId, filter, buka, onTutup, onDataHilang }) {
  const { data, galat } = useAmbil(
    JSON.stringify([laporanId, dataId, filter, buka]),
    (sinyal) => ambilRincian(laporanId, dataId, filter, buka.jenis, buka.kunci, sinyal),
    onDataHilang,
  )
  const [cari, setCari] = useState('')
  const kata = cari.trim().toLowerCase()
  const tabel = data?.tabel ?? []
  const bisaCari = tabel.some((t) => t.baris.length >= MIN_BARIS_CARI)
  return (
    <Modal judul={data?.judul ?? buka.judul} kecil={data?.kecil} onTutup={onTutup} lebar="max-w-6xl">
      {galat && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
      {!data && !galat && <Memuat teks="Memuat rincian..." />}
      {data && (
        <div className="space-y-5">
          {data.bagian.length > 0 && (
            <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              {data.bagian.map((b) => (
                <section key={b.judul} className="min-w-0">
                  <h3 className="mb-1.5 border-b border-slate-200 pb-1 text-xs font-medium text-slate-500">{b.judul}</h3>
                  <dl className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-3 gap-y-1 text-sm">
                    {b.isian.map((i) => (
                      <div key={i.label} className="contents">
                        <dt className="text-slate-600">{i.label}</dt>
                        <dd className="break-words tabular-nums text-slate-900">{formatSel(i.nilai, i.tipe)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          )}
          {bisaCari && (
            <label className="block">
              <span className="sr-only">Cari di tabel rincian</span>
              <input
                type="search"
                value={cari}
                onChange={(e) => setCari(e.target.value)}
                placeholder="Cari nomor dokumen, nama barang, keterangan..."
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm sm:max-w-md pointer-coarse:min-h-11"
              />
            </label>
          )}
          {tabel.map((t) => {
            const baris = kata ? t.baris.filter((b) => cocok(b, t.kolom, kata)) : t.baris
            return (
              <section key={t.judul} className="min-w-0">
                <h3 className="mb-1.5 text-xs font-medium text-slate-500">
                  {t.judul} ({kata ? `${angka.format(baris.length)} dari ${angka.format(t.baris.length)}` : angka.format(t.baris.length)})
                </h3>
                {baris.length > 0
                  ? <TabelBaris kolom={t.kolom} baris={baris} />
                  : <p className="text-sm text-slate-600">{kata && t.baris.length > 0 ? `Tidak ada yang cocok dengan "${cari.trim()}".` : 'Belum ada.'}</p>}
              </section>
            )
          })}
          {data.catatan && <p className="text-xs text-amber-800">{data.catatan}</p>}
        </div>
      )}
    </Modal>
  )
}
