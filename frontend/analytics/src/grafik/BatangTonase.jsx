import { memo } from 'react'
import { angka } from '../lib/data'
import { Kosong } from '../komponen/Keadaan'

const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const tonTeks = (kg) => `${satu.format(kg / 1000)} t`
const persenTeks = (x) => `${satu.format(x * 100)}%`

// Peringkat tonase (produk, pengangkut) sebagai daftar: nomor urut, nama yang boleh dua baris, tonase dan rit di kanan, batang di bawah nama.
// Klik baris untuk memfilter; Ctrl/Shift menambah pilihan. lainnya: { jumlah, netto, rit } untuk baris di luar peringkat.
function BatangTonase({ data, terpilih, onPilih, warna = '#0369a1', persen = false, lainnya = null, satuanLain = 'lainnya', kosong = 'Tidak ada tiket untuk filter ini' }) {
  if (data.length === 0) return <Kosong teks={kosong} />
  const maks = Math.max(...data.map((d) => d.netto), 1)
  const adaPilihan = terpilih.length > 0
  return (
    <div>
      <ol className="space-y-0.5">
        {data.map((d, i) => {
          const aktif = terpilih.includes(d.nama)
          return (
            <li key={d.nama}>
              <button
                type="button"
                onClick={(e) => onPilih(d.nama, e)}
                aria-pressed={aktif}
                className={
                  'grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-x-2 rounded-md px-1.5 py-1.5 text-left transition-opacity hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
                  (adaPilihan && !aktif ? 'opacity-45' : '')
                }
              >
                <span className="pt-px text-right text-xs tabular-nums text-slate-400">{i + 1}</span>
                <span className="min-w-0">
                  <span className={'line-clamp-2 text-[13px] leading-snug break-words ' + (aktif ? 'font-semibold text-slate-900' : 'text-slate-800')} title={d.nama}>
                    {d.nama}
                  </span>
                  <span className="mt-1 block h-1.5 rounded-full bg-slate-100">
                    <span className="block h-full rounded-full" style={{ width: `${Math.max((d.netto / maks) * 100, 1.5)}%`, background: warna }} />
                  </span>
                </span>
                <span className="text-right leading-tight">
                  <span className="block text-[13px] font-semibold tabular-nums text-slate-900">{tonTeks(d.netto)}</span>
                  <span className="block text-[11px] tabular-nums text-slate-500">
                    {angka.format(d.rit)} kiriman{persen ? ` · ${persenTeks(d.persen)}` : ''}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
      {lainnya && (
        <p className="mt-2 border-t border-slate-100 pt-2 pl-9 text-xs text-slate-500">
          {angka.format(lainnya.jumlah)} {satuanLain} lain: <span className="tabular-nums">{tonTeks(lainnya.netto)}</span>,{' '}
          <span className="tabular-nums">{angka.format(lainnya.rit)} kiriman</span>. Pilih lewat panel filter.
        </p>
      )}
    </div>
  )
}

export default memo(BatangTonase)
