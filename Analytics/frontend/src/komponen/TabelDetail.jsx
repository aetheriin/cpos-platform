import { useEffect, useState } from 'react'
import { ambilDetail, unduhDetail } from '../api'
import { useAmbil } from '../lib/ambil'
import { angka, rentangBaris } from '../lib/data'
import { IkonUnduh } from './Ikon'
import Select from './Select'
import TabelBaris from './TabelBaris'

export function PanelDetail({ judul = 'Tabel Detail', tab, jenis, onJenis, jumlah, hasil, galat, memuat, cariInput, onCari, ukuran, onUkuran, onHalaman, onUrut, onEkspor, mengekspor = false, galatEkspor = '', onPilihBaris, barisTerpilih }) {
  const acuan = hasil ? tab.find((t) => t.kunci === jenis)?.ket(hasil) ?? '' : ''
  const { dari, sampai } = hasil ? rentangBaris(hasil.halaman, hasil.ukuran, hasil.total) : { dari: 0, sampai: 0 }
  // Export Excel memuat semua baris yang cocok, paling banyak maks_ekspor (dikirim server); sisanya dipotong
  const dipotong = hasil && hasil.maks_ekspor != null && hasil.total > hasil.maks_ekspor
  const jumlahEkspor = hasil ? (hasil.maks_ekspor != null ? Math.min(hasil.total, hasil.maks_ekspor) : hasil.total) : 0

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="font-medium">{judul}</h2>
      <p className="mb-3 text-xs text-slate-500">
        {acuan}
        {onPilihBaris && ' Klik baris untuk memfilter semua grafik dan kartu ke transaksi itu.'}
      </p>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="tablist" className="inline-flex rounded-lg border border-slate-300 p-0.5">
          {tab.map(({ kunci, nama }) => (
            <button
              key={kunci}
              type="button"
              role="tab"
              aria-selected={jenis === kunci}
              onClick={() => onJenis(kunci)}
              className={'rounded-md px-3 py-1 text-sm ' + (jenis === kunci ? 'bg-sky-600 text-white' : 'text-slate-700 hover:bg-slate-100')}
            >
              {nama} <span className="tabular-nums opacity-80">({angka.format(jumlah[kunci])})</span>
            </button>
          ))}
        </div>

        <input
          type="search"
          value={cariInput}
          onChange={(e) => onCari(e.target.value)}
          placeholder="Masukkan pencarian..."
          className="min-w-56 flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
        />

        <label className="text-xs text-slate-600">
          Baris per halaman{' '}
          <Select otomatis kecil value={ukuran} onChange={(e) => onUkuran(Number(e.target.value))}>
            {[25, 50, 100, 200].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
        </label>

        {onEkspor && (
          <button
            type="button"
            onClick={onEkspor}
            disabled={!hasil || hasil.total === 0 || mengekspor}
            aria-busy={mengekspor}
            title={hasil ? `Unduh ${angka.format(jumlahEkspor)} baris yang cocok dengan filter, pencarian, dan urutan saat ini (bukan hanya halaman ini)` : undefined}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            <IkonUnduh className="h-4 w-4" />
            {mengekspor ? 'Menyiapkan...' : 'Export Excel'}
          </button>
        )}
      </div>

      {dipotong && (
        <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          Export Excel dibatasi {angka.format(hasil.maks_ekspor)} baris pertama dari {angka.format(hasil.total)} baris. Persempit dengan filter atau pencarian.
        </p>
      )}
      {galatEkspor && (
        <div role="alert" className="mb-2 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
          Export gagal: {galatEkspor}
        </div>
      )}
      {galat && <div className="mb-2 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">{galat.message}</div>}
      {!hasil && !galat && <p className="py-6 text-center text-sm text-slate-500">Memuat tabel...</p>}

      {hasil && (
        <div className={memuat ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
          <TabelBaris kolom={hasil.kolom} baris={hasil.baris} urut={hasil.urut} arah={hasil.arah} onUrut={onUrut} onPilihBaris={onPilihBaris} terpilih={barisTerpilih} />

          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
            <span>
              {hasil.total === 0
                ? 'Tidak ada baris.'
                : `Menampilkan ${angka.format(dari)}–${angka.format(sampai)} dari ${angka.format(hasil.total)} baris`}
              {hasil.cari && hasil.total !== hasil.total_semua ? ` (hasil pencarian, dari ${angka.format(hasil.total_semua)} baris)` : ''}
            </span>
            <span className="inline-flex items-center gap-2">
              <button
                type="button"
                disabled={hasil.halaman <= 1}
                onClick={() => onHalaman(hasil.halaman - 1)}
                className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40"
              >
                Sebelumnya
              </button>
              <span className="tabular-nums">
                Halaman {hasil.halaman} dari {hasil.jumlah_halaman}
              </span>
              <button
                type="button"
                disabled={hasil.halaman >= hasil.jumlah_halaman}
                onClick={() => onHalaman(hasil.halaman + 1)}
                className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40"
              >
                Berikutnya
              </button>
            </span>
          </div>
        </div>
      )}
    </section>
  )
}

export default function TabelDetail({ judul, laporanId, dataId, filter, jumlah, tab, onDataHilang, onPilihBaris, barisTerpilih }) {
  const [jenis, setJenis] = useState(tab[0].kunci)
  const [cariInput, setCariInput] = useState('')
  const [cari, setCari] = useState('')
  const [urut, setUrut] = useState(null) // { kunci, arah } atau null (urutan bawaan server)
  const [ukuran, setUkuran] = useState(50)
  const [posisi, setPosisi] = useState({ kunci: '', halaman: 1 })
  const [mengekspor, setMengekspor] = useState(false)
  const [galatEkspor, setGalatEkspor] = useState('')

  const kunciFilter = JSON.stringify(filter)
  const kunciCari = JSON.stringify([kunciFilter, jenis, cari, urut, ukuran])
  // Halaman kembali ke 1 setiap filter, tab, pencarian, urutan, atau ukuran berubah
  const halaman = posisi.kunci === kunciCari ? posisi.halaman : 1

  // Pencarian ditunda sebentar supaya tidak memanggil server di setiap ketukan
  useEffect(() => {
    const timer = setTimeout(() => setCari(cariInput.trim()), 300)
    return () => clearTimeout(timer)
  }, [cariInput])

  const { data: hasil, galat, memuat } = useAmbil(
    JSON.stringify([laporanId, dataId, kunciCari, halaman]),
    (sinyal) => ambilDetail(laporanId, dataId, filter, { jenis, cari, urut: urut?.kunci, arah: urut?.arah, halaman, ukuran }, sinyal),
    onDataHilang,
  )

  // Klik judul kolom: kolom baru naik dulu, klik lagi membalik arah
  const ubahUrut = (kunci) => {
    const sekarang = hasil?.urut === kunci ? hasil.arah : null
    setUrut({ kunci, arah: sekarang === 'asc' ? 'desc' : 'asc' })
  }

  const ekspor = async () => {
    if (mengekspor) return
    setMengekspor(true)
    setGalatEkspor('')
    try {
      await unduhDetail(laporanId, dataId, filter, { jenis, cari, urut: urut?.kunci, arah: urut?.arah })
    } catch (e) {
      if (e.status === 404) onDataHilang?.()
      else setGalatEkspor(e.message)
    } finally {
      setMengekspor(false)
    }
  }

  return (
    <PanelDetail
      judul={judul}
      tab={tab}
      jenis={jenis}
      onJenis={(k) => { setJenis(k); setUrut(null) }}   // kolom urutan tab lama belum tentu ada di tab baru
      jumlah={jumlah}
      hasil={hasil}
      galat={galat}
      memuat={memuat}
      cariInput={cariInput}
      onCari={setCariInput}
      ukuran={ukuran}
      onUkuran={setUkuran}
      onHalaman={(n) => setPosisi({ kunci: kunciCari, halaman: n })}
      onUrut={ubahUrut}
      onEkspor={ekspor}
      mengekspor={mengekspor}
      galatEkspor={galatEkspor}
      onPilihBaris={onPilihBaris}
      barisTerpilih={barisTerpilih}
    />
  )
}
