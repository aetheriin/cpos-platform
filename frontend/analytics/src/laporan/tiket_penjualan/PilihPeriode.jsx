import Select from '../../komponen/Select'
import { rentangTgl } from '../../lib/data'
import { IkonPanahKanan } from '../../komponen/Ikon'
import { MODE, daftarPeriode, geser, judulPeriode, kunciPeriode, rentangData, tglPendek } from './periode'

const NAMA_SATUAN = { hari: 'hari', minggu: 'minggu', bulan: 'bulan' }
const kapital = (t) => t.charAt(0).toUpperCase() + t.slice(1)

function TombolGeser({ arah, mati, judul, onKlik }) {
  return (
    <button
      type="button"
      onClick={onKlik}
      disabled={mati}
      title={judul}
      aria-label={judul}
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-35"
    >
      <IkonPanahKanan className={'h-4 w-4 ' + (arah < 0 ? 'rotate-180' : '')} />
    </button>
  )
}

// Pilih jenis periode (harian, mingguan, bulanan), lalu hari, minggu, atau bulannya. Tombol panah pindah ke periode sebelum atau sesudahnya.
// batas: data yang dimuat { mulai, akhir }; periode di luar batas tidak bisa dipilih (pakai Ganti periode di bar atas).
export default function PilihPeriode({ mode, acuan, batas, onUbah, pembanding = null }) {
  const pilih = (m, a) => onUbah(m, a)
  const sebelum = geser(mode, acuan, -1)
  const sesudah = geser(mode, acuan, 1)
  const adaSebelum = rentangData(mode, sebelum, batas) != null
  const adaSesudah = rentangData(mode, sesudah, batas) != null
  const r = rentangData(mode, acuan, batas)
  const satuan = NAMA_SATUAN[mode]

  let catatan = null
  if (r?.terpotong) {
    if (r.sampai === batas.akhir && mode !== 'hari') catatan = `${kapital(satuan)} ini belum selesai, data sampai ${tglPendek(batas.akhir)}.`
    else if (r.dari === batas.mulai) catatan = `Data yang tersedia mulai ${tglPendek(batas.mulai)}.`
  }
  let banding = 'Tidak ada data pembanding untuk periode ini.'
  if (pembanding) {
    banding = `Dibandingkan dengan ${rentangTgl(pembanding.mulai, pembanding.akhir)}`
    banding += pembanding.sampai_jam ? ` sampai pukul ${pembanding.sampai_jam}.59, sama dengan jam sekarang.` : '.'
  }

  return (
    <section aria-label="Periode" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div role="radiogroup" aria-label="Jenis periode" className="inline-flex rounded-lg border border-slate-300 p-0.5">
        {MODE.map((m) => (
          <button
            key={m.kunci}
            type="button"
            role="radio"
            aria-checked={mode === m.kunci}
            onClick={() => mode !== m.kunci && pilih(m.kunci, acuan)}
            className={
              'rounded-md px-3.5 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
              (mode === m.kunci ? 'bg-sky-600 font-medium text-white' : 'text-slate-700 hover:bg-slate-100')
            }
          >
            {m.nama}
          </button>
        ))}
      </div>

      <div className="flex min-w-0 items-center gap-2">
        <TombolGeser arah={-1} mati={!adaSebelum} onKlik={() => pilih(mode, sebelum)}
          judul={adaSebelum ? `${kapital(satuan)} sebelumnya` : `Data yang tersedia mulai ${tglPendek(batas.mulai)}. Untuk tanggal sebelumnya, klik Ganti periode di bagian atas.`} />
        {mode === 'hari' ? (
          <input
            type="date"
            aria-label="Tanggal"
            value={acuan}
            min={batas.mulai}
            max={batas.akhir}
            onChange={(e) => e.target.value && rentangData('hari', e.target.value, batas) && pilih('hari', e.target.value)}
            className="h-9 rounded-md border border-slate-300 bg-white px-2.5 text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
        ) : (
          <Select
            aria-label={mode === 'minggu' ? 'Minggu' : 'Bulan'}
            value={kunciPeriode(mode, acuan)}
            onChange={(e) => pilih(mode, e.target.value)}
            className="min-w-0 sm:w-64"
          >
            {daftarPeriode(mode, batas).map((p) => (
              <option key={p.nilai} value={p.nilai}>
                {p.label}
              </option>
            ))}
          </Select>
        )}
        <TombolGeser arah={1} mati={!adaSesudah} onKlik={() => pilih(mode, sesudah)}
          judul={adaSesudah ? `${kapital(satuan)} sesudahnya` : 'Belum ada data sesudahnya'} />
      </div>

      {/* Daftar minggu dan bulan sudah menuliskan periodenya; tanggal hanya ditulis lengkap dengan nama harinya */}
      <div className="min-w-0 text-sm leading-snug">
        {mode === 'hari' && <p className="font-medium text-slate-900">{judulPeriode(mode, acuan)}</p>}
        {catatan && <p className="text-xs text-slate-600">{catatan}</p>}
        <p className="text-xs text-slate-600">{banding}</p>
      </div>
    </section>
  )
}
