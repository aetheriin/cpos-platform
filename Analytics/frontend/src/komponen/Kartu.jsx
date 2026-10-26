import { useLayoutEffect, useRef, useState } from 'react'
import { useTataLetak } from '../lib/tampilan'
import Info from './Info'

// aksi: kontrol kecil di kanan judul. Di tata letak padat, petunjuk pindah ke tooltip (i) supaya kartu lebih pendek.
export function KartuGrafik({ judul, petunjuk, aksi, children }) {
  const padat = useTataLetak()[0] === 'padat'
  return (
    <section className={'flex h-full flex-col rounded-xl border border-slate-200 bg-white ' + (padat ? 'p-3' : 'p-4')}>
      <div className={'flex flex-wrap items-start justify-between gap-x-3 gap-y-1 ' + (padat ? 'mb-2' : '')}>
        <h2 className={padat ? 'text-sm font-medium' : 'font-medium'}>
          {judul}
          {padat && petunjuk && <Info teks={petunjuk} label={judul} />}
        </h2>
        {aksi}
      </div>
      {!padat && petunjuk && <p className="mb-2 text-xs text-slate-500">{petunjuk}</p>}
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  )
}

// Petak membawa lebar untuk dua tata letak: memanjang (kisi 10 kolom) dan padat (kisi 12 kolom). Kelasnya ditulis utuh di pemanggil
// supaya terbaca Tailwind.
export function KisiGrafik({ children }) {
  const padat = useTataLetak()[0] === 'padat'
  return <div className={padat ? 'kisi-padat grid gap-3 lg:grid-cols-12' : 'grid gap-4 md:grid-cols-10'}>{children}</div>
}

export function Petak({ panjang = 'md:col-span-10', padat = 'lg:col-span-12', children }) {
  const tata = useTataLetak()[0]
  return <div className={'min-w-0 ' + (tata === 'padat' ? padat : panjang)}>{children}</div>
}

// Memanjang: paling banyak `kolom` kartu per baris, berkurang kalau sempit (style langsung karena memakai calc()).
// Padat: kolom dihitung dari lebar supaya kartu terbagi rata per baris (10 kartu jadi 5 + 5, bukan 6 + 4). Kartu dihitung dari DOM
// karena satu komponen (mis. KartuKecepatan) bisa menghasilkan beberapa kartu.
const LEBAR_MIN_KARTU = 150 // px
export function GridKartu({ children, kolom = 5 }) {
  const padat = useTataLetak()[0] === 'padat'
  const kisi = useRef(null)
  const [kolomPadat, setKolomPadat] = useState(null)
  useLayoutEffect(() => {
    if (!padat || !kisi.current) return undefined
    const el = kisi.current
    const hitung = () => {
      const n = el.children.length
      const muat = Math.max(1, Math.floor((el.clientWidth + 12) / (LEBAR_MIN_KARTU + 12)))
      const baris = Math.ceil(n / muat)
      setKolomPadat(Math.ceil(n / baris))
    }
    hitung()
    const ro = new ResizeObserver(hitung)
    ro.observe(el)
    return () => ro.disconnect()
  }, [padat, children])
  const kolomKisi =
    padat && kolomPadat
      ? `repeat(${kolomPadat}, minmax(0, 1fr))`
      : `repeat(auto-fit, minmax(max(9.5rem, calc((100% - ${(kolom - 1) * 0.75}rem) / ${kolom})), 1fr))`
  return (
    <section>
      <div ref={kisi} className="grid gap-3" style={{ gridTemplateColumns: kolomKisi }}>
        {children}
      </div>
    </section>
  )
}

// Angka tidak pernah dipotong "...": yang panjang ditulis sedikit lebih kecil.
const ukuranNilai = (nilai) => {
  const n = String(nilai ?? '').length
  return n <= 11 ? 'text-2xl' : n <= 15 ? 'text-xl' : 'text-lg'
}

const NADA = { baik: 'text-emerald-700', buruk: 'text-red-700', netral: 'text-slate-600' }

// info: cara hitung, sebagai tooltip judul. banding: hasil bandingKpi(), atau null.
export function Kartu({ judul, nilai, catatan, banding, info }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs leading-snug text-slate-500">
        {judul}
        {info && <Info teks={`${info[0].toUpperCase()}${info.slice(1)}.`} label={judul} />}
      </div>
      <div className={'mt-0.5 leading-tight font-semibold tabular-nums ' + ukuranNilai(nilai)}>{nilai}</div>
      <div className="mt-0.5 flex min-h-4 flex-wrap items-baseline gap-x-2 text-xs">
        {banding && (
          <span className={'shrink-0 font-medium tabular-nums ' + NADA[banding.nada]} title={banding.judul}>
            {banding.teks}
          </span>
        )}
        {catatan && <span className="text-slate-500">{catatan}</span>}
      </div>
    </div>
  )
}
