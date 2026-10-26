import { angka, rentangTgl } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import FilterTanggal from '../../komponen/FilterTanggal'
import { GridKartu, Kartu } from '../../komponen/Kartu'
import PanelFilter, { TombolFilter } from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'

const FILTER_AWAL = { dari: null, sampai: null, perusahaan: [], status: [] }
const JENIS = [{ kunci: 'perusahaan', nama: 'Perusahaan' }, { kunci: 'status', nama: 'Status' }]
const TAB_BELUM = [
  { kunci: 'belum', nama: 'Belum PVR & PV', ket: () => 'PI yang belum ada PVR dan belum dibayar PV. Yang paling lama di atas.' },
  { kunci: 'pv_tanpa_pvr', nama: 'PV tanpa PVR', ket: () => 'PI yang sudah dibayar PV tanpa lewat PVR.' },
]
const TAB_SUDAH = [{ kunci: 'sudah', nama: 'Sudah PVR', ket: () => 'PI yang sudah ada PVR, dengan PV-nya kalau sudah dibayar.' }]
const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

// Rupiah ringkas dengan satuan ditulis lengkap, mis. "Rp 7,7 miliar", supaya besarnya terbaca sekilas
function rupiah(x) {
  const [bagi, satuan] = x >= 1e12 ? [1e12, ' triliun'] : x >= 1e9 ? [1e9, ' miliar'] : x >= 1e6 ? [1e6, ' juta'] : [1, '']
  return `Rp ${satu.format(x / bagi)}${satuan}`
}
const rupiahPenuh = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 })

// Report tabel saja, menurut tanggal PI. Ganti periode di bar atas menarik data baru; filter Tanggal mempersempit data yang sudah dimuat.
export default function LaporanPiPvr({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('pi_pvr', dataId, FILTER_AWAL, onDataHilang)
  const aktif = [...chipRentang(filter), ...chipDaftar(JENIS, terpilih)]
  const k = data?.kpi

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">Purchase Invoice</h1>
            {data && <p className="text-sm text-slate-500">Tanggal PI {rentangTgl(data.periode.mulai, data.periode.akhir)}</p>}
          </div>
          <TombolFilter jumlahAktif={aktif.length} terbuka={panel} onToggle={togglePanel} />
        </header>

        {aktif.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {aktif.map(([jenis, nilai, teks]) => (
              <button key={`${jenis}:${nilai}`} type="button" aria-label={`Lepas filter ${teks}`} onClick={() => lepas(jenis, nilai)}
                className="max-w-full truncate rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-100">
                {teks} ×
              </button>
            ))}
            <button type="button" className="rounded-md px-2 py-1 text-xs text-slate-600 underline" onClick={reset}>
              Reset filter
            </button>
          </div>
        )}

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={6}>
              <Kartu judul="Belum PVR & PV" nilai={rupiah(k.nilai_belum)} catatan={`${angka.format(k.belum)} dokumen PI`} info={`total Line Total, ${rupiahPenuh.format(k.nilai_belum)}`} />
              <Kartu judul={`Belum PVR & PV > ${k.ambang} hari`} nilai={angka.format(k.belum_lama)} catatan="dokumen PI" />
              <Kartu judul="Belum PVR & PV paling lama" nilai={k.umur_maks == null ? 'tidak ada' : `${angka.format(k.umur_maks)} hari`} />
              <Kartu judul="PV tanpa PVR" nilai={rupiah(k.nilai_pv_tanpa_pvr)} catatan={`${angka.format(k.pv_tanpa_pvr)} dokumen PI`}
                info={`PI yang sudah dibayar PV tanpa lewat PVR. Total ${rupiahPenuh.format(k.nilai_pv_tanpa_pvr)}`} />
              <Kartu judul="PI sudah PVR" nilai={rupiah(k.nilai_sudah)} catatan={`${angka.format(k.sudah)} dokumen PI`} info={`total Line Total, ${rupiahPenuh.format(k.nilai_sudah)}`} />
              <Kartu judul="PI sampai PVR" nilai={k.lama_pvr.median == null ? 'belum ada' : `${satu.format(k.lama_pvr.median)} hari`}
                catatan={k.lama_pvr.rata == null ? '' : `rata-rata ${satu.format(k.lama_pvr.rata)} hari`} info="nilai tengah hari dari PI dibuat sampai PVR pertama dibuat di sistem" />
            </GridKartu>
            <TabelDetail judul="PI belum PVR" laporanId="pi_pvr" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_BELUM} onDataHilang={onDataHilang} />
            <TabelDetail judul="PI sudah PVR" laporanId="pi_pvr" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_SUDAH} onDataHilang={onDataHilang} />
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <FilterTanggal dari={filter.dari} sampai={filter.sampai} efektif={data.rentang} satuan="hari" bawaan={null} dataset={data.dataset} onUbah={ubah} />}
        {JENIS.map(({ kunci, nama }) => (
          <FilterMulti key={kunci} sebaris label={nama} opsi={data?.pilihan[kunci] ?? []} terpilih={filter[kunci]} onUbah={(v) => ubah({ [kunci]: v })} />
        ))}
      </PanelFilter>
    </div>
  )
}
