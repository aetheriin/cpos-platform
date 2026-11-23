import { useEffect, useRef, useState } from 'react'
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

// Tabel rincian ber-buka (dari server): baris diklik ganda membuka rincian dokumennya di jendela yang sama
function bukaDariBaris(buka, baris) {
  const kunci = { ...buka.kunci }
  for (const k of buka.dari_baris) kunci[k] = baris[k] ?? ''
  return { jenis: buka.jenis, kunci, judul: baris[buka.judul] ?? '' }
}

// Rincian satu baris tabel detail. buka: { jenis, kunci, judul } atau null.
// Dari rincian supplier/customer bisa turun ke rincian dokumennya; tombol Kembali naik lagi, Esc menutup seluruh jendela.
export default function JendelaRincian({ laporanId, dataId, filter, buka, onTutup, onDataHilang }) {
  // riwayat: tingkat yang dibuka, yang terakhir sedang tampil. Saat turun, tingkat asal menyimpan isinya (supaya Kembali langsung
  // tampil) dan baris yang dibuka (supaya fokus kembali ke baris itu).
  const [riwayat, setRiwayat] = useState([{ buka, isi: null, asal: null }])
  const tingkat = riwayat[riwayat.length - 1]
  const sekarang = tingkat.buka
  const { data, galat, memuat } = useAmbil(
    JSON.stringify([laporanId, dataId, filter, sekarang]),
    // Kembali ke tingkat yang isinya tersimpan: tidak perlu bertanya ke server lagi (rincian Supplier PO memanggil SP ERP)
    (sinyal) => (tingkat.isi ? Promise.resolve(tingkat.isi) : ambilRincian(laporanId, dataId, filter, sekarang.jenis, sekarang.kunci, sinyal)),
    onDataHilang,
  )
  // Selama tingkat baru dimuat atau gagal, data tingkat sebelumnya (yang masih dipegang useAmbil) jangan ikut tampil
  const isi = memuat ? tingkat.isi : galat ? null : data
  const gagal = memuat ? null : galat

  const [cari, setCari] = useState('')
  const kata = cari.trim().toLowerCase()
  const tabel = isi?.tabel ?? []
  const bisaCari = tabel.some((t) => t.baris.length >= MIN_BARIS_CARI)

  const wadah = useRef(null)
  const tombolKembali = useRef(null)
  const fokusBerikut = useRef(null)   // 'kembali' setelah turun, { tabel, baris } setelah naik

  const turun = (t, ti, b) => {
    fokusBerikut.current = 'kembali'
    setRiwayat((r) => [
      ...r.slice(0, -1),
      { ...r[r.length - 1], isi, asal: { tabel: ti, baris: t.baris.indexOf(b) } },
      { buka: bukaDariBaris(t.buka, b), isi: null, asal: null },
    ])
    setCari('')
  }
  const naik = () => {
    fokusBerikut.current = riwayat[riwayat.length - 2].asal
    setRiwayat((r) => r.slice(0, -1))
    setCari('')
  }

  // Baris yang diklik ganda hilang dari layar saat turun: fokus pindah ke Kembali. Saat naik, fokus kembali ke baris itu.
  useEffect(() => {
    const target = fokusBerikut.current
    if (target === 'kembali') {
      tombolKembali.current?.focus()
      fokusBerikut.current = null
    } else if (target && isi) {
      wadah.current?.querySelectorAll(`[data-tabel="${target.tabel}"] tbody tr`)[target.baris]?.focus()
      fokusBerikut.current = null
    }
  }, [riwayat, isi])

  const induk = riwayat.length > 1 ? riwayat[riwayat.length - 2].buka : null
  return (
    <Modal judul={isi?.judul ?? sekarang.judul} kecil={isi?.kecil} onTutup={onTutup} lebar="max-w-6xl">
      <div ref={wadah} className="space-y-5">
        {induk && (
          <button ref={tombolKembali} type="button" onClick={naik}
            className="-mt-2 inline-flex max-w-full items-center gap-1 rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50 pointer-coarse:min-h-11">
            <span aria-hidden="true">‹</span>
            <span className="truncate">Kembali ke {induk.judul}</span>
          </button>
        )}
        {gagal && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{gagal.message}</div>}
        {!isi && !gagal && <Memuat teks="Memuat rincian…" />}
        {isi && (
          <>
            {isi.bagian.length > 0 && (
              <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                {isi.bagian.map((b) => (
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
            {tabel.map((t, ti) => {
              const baris = kata ? t.baris.filter((b) => cocok(b, t.kolom, kata)) : t.baris
              return (
                <section key={t.judul} data-tabel={ti} className="min-w-0">
                  <h3 className="mb-1.5 text-xs font-medium text-slate-500">
                    {t.judul} ({kata ? `${angka.format(baris.length)} dari ${angka.format(t.baris.length)}` : angka.format(t.baris.length)})
                    {t.buka && baris.length > 0 && <span className="font-normal"> · Klik ganda baris (ketuk sekali di layar sentuh) untuk melihat rincian dokumennya.</span>}
                  </h3>
                  {baris.length > 0
                    ? <TabelBaris kolom={t.kolom} baris={baris} onBukaBaris={t.buka ? (b) => turun(t, ti, b) : undefined} />
                    : <p className="text-sm text-slate-600">{kata && t.baris.length > 0 ? `Tidak ada yang cocok dengan "${cari.trim()}".` : 'Belum ada.'}</p>}
                </section>
              )
            })}
            {isi.catatan && <p className="text-xs text-amber-800">{isi.catatan}</p>}
          </>
        )}
      </div>
    </Modal>
  )
}
