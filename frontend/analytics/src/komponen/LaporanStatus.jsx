import Info from './Info'
import { TENTANG } from './tentang'
import { useMemo, useState } from 'react'
import JendelaRincian from './JendelaRincian'
import { rentangTgl, rupiah, rupiahPenuh } from '../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../lib/filter'
import FilterMulti from './FilterMulti'
import FilterTanggal from './FilterTanggal'
import { GridKartu, Kartu } from './Kartu'
import PanelFilter, { TombolFilter } from './PanelFilter'
import TabelDetail from './TabelDetail'
import { GalatHalaman, MemuatLaporan } from './Keadaan'

// Filter yang ada di semua laporan ini; laporan menambah filternya sendiri lewat prop filterTambahan (kunci sama dengan backend `dim`)
const JENIS_DASAR = [{ kunci: 'perusahaan', nama: 'Perusahaan' }, { kunci: 'status', nama: 'Status' }, { kunci: 'aging', nama: 'Aging' }]
const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

export { rupiah, rupiahPenuh }
export const hari = (x) => (x == null ? 'belum ada' : `${satu.format(x)} hari`)

// Laporan status tindak lanjut dokumen (model Purchase Invoice), dipakai Purchase Request dan Purchase Order.
// kartu(kpi) -> [{judul, nilai, catatan, info}]; tabel: [{judul, tab: [{kunci, nama, ket}]}]
// kolomNomor: kolom nomor dokumen di baris tabel; klik ganda baris membuka rincian dokumen itu
export default function LaporanStatus({ laporanId, judul, teksTanggal, kartu, tabel, filterTambahan = [], kolomNomor, dataId, onDataHilang }) {
  const [rinci, setRinci] = useState(null)
  const buka = (_, b) => setRinci({ jenis: 'dokumen', judul: b[kolomNomor], kunci: { comp: b.comp, no_dok: b[kolomNomor] } })
  const [JENIS, FILTER_AWAL] = useMemo(() => {
    const jenis = [...JENIS_DASAR, ...filterTambahan]
    return [jenis, { dari: null, sampai: null, ...Object.fromEntries(jenis.map((j) => [j.kunci, []])) }]
  }, [filterTambahan])
  const { data, galat, memuat, ulangi, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard(laporanId, dataId, FILTER_AWAL, onDataHilang)
  const aktif = [...chipRentang(filter), ...chipDaftar(JENIS, terpilih)]

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">{judul}<Info teks={TENTANG[judul]} label={`laporan ${judul}`} /></h1>
            {data && <p className="text-sm text-slate-500">{teksTanggal} {rentangTgl(data.periode.mulai, data.periode.akhir)}</p>}
          </div>
          <TombolFilter jumlahAktif={aktif.length} terbuka={panel} onToggle={togglePanel} />
        </header>

        {aktif.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {aktif.map(([jenis, nilai, teks]) => (
              <button key={`${jenis}:${nilai}`} type="button" aria-label={`Lepas filter ${teks}`} onClick={() => lepas(jenis, nilai)}
                className="max-w-full truncate rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-100 pointer-coarse:min-h-11">
                {teks} ×
              </button>
            ))}
            <button type="button" className="rounded-md px-2 py-1 text-xs text-slate-600 underline pointer-coarse:min-h-11" onClick={reset}>
              Reset filter
            </button>
          </div>
        )}

        {galat && <GalatHalaman galat={galat} onUlang={ulangi} sedang={memuat} />}
        {!data && !galat && <MemuatLaporan />}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={6}>
              {kartu(data.kpi).map((k) => <Kartu key={k.judul} {...k} />)}
            </GridKartu>
            {tabel.map((t, i) => (
              <TabelDetail key={t.judul} judul={t.judul} laporanId={laporanId} dataId={dataId} filter={filter} jumlah={data.jumlah} tab={t.tab}
                onDataHilang={onDataHilang} onBukaBaris={kolomNomor ? buka : undefined} petunjukBuka={i === 0} />
            ))}
          </div>
        )}
      </div>
      {rinci && <JendelaRincian laporanId={laporanId} dataId={dataId} filter={filter} buka={rinci} onTutup={() => setRinci(null)} onDataHilang={onDataHilang} />}
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <FilterTanggal dari={filter.dari} sampai={filter.sampai} efektif={data.rentang} satuan="hari" bawaan={null} dataset={data.dataset} onUbah={ubah} />}
        {JENIS.map(({ kunci, nama }) => (
          <FilterMulti key={kunci} sebaris label={nama} opsi={data?.pilihan[kunci] ?? []} terpilih={filter[kunci]} onUbah={(v) => ubah({ [kunci]: v })} />
        ))}
      </PanelFilter>
    </div>
  )
}
