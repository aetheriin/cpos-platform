import { angka, rentangTgl } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import FilterTanggal from '../../komponen/FilterTanggal'
import { GridKartu, Kartu } from '../../komponen/Kartu'
import PanelFilter, { TombolFilter } from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import { MemuatLaporan } from '../../komponen/Keadaan'

const FILTER_AWAL = { dari: null, sampai: null, perusahaan: [], sumber: [] }
const JENIS = [{ kunci: 'perusahaan', nama: 'Perusahaan' }, { kunci: 'sumber', nama: 'Sumber' }]
const TAB_HUTANG = [
  { kunci: 'hutang', nama: 'Per dokumen', ket: () => 'Tagihan yang belum lunas. Potongan (AP Discount Notes dll) bernilai negatif. Yang paling lama di atas.' },
  { kunci: 'supplier', nama: 'Per supplier', ket: () => 'Sisa bersih = tagihan dikurangi potongan. Yang terbesar di atas.' },
]
const TAB_PIUTANG = [
  { kunci: 'piutang', nama: 'Per dokumen', ket: () => 'Invoice dan nota yang belum dibayar customer. Yang paling lama di atas.' },
  { kunci: 'customer', nama: 'Per customer', ket: () => 'Sisa piutang per customer. Yang terbesar di atas.' },
]
const TAB_PR = [{ kunci: 'pr', nama: 'Per item', ket: () => 'Item PR berstatus Open yang belum seluruhnya dibuatkan PO. Yang paling lama di atas.' }]
const TAB_PO = [{ kunci: 'po', nama: 'Per item', ket: () => 'Item PO berstatus Open yang belum seluruhnya diterima. Yang paling lama di atas.' }]

// "113 PR" + catatan jumlah item dan yang lewat 30 hari
function catatanPengadaan(item, lama) {
  return `${angka.format(item)} item, ${angka.format(lama)} lewat 30 hari`
}
// Judul kecil di atas sekelompok kartu
function Kelompok({ judul, kolom, children }) {
  return (
    <section className="min-w-0">
      <h2 className="mb-1.5 text-xs font-medium text-slate-500">{judul}</h2>
      <GridKartu kolom={kolom}>{children}</GridKartu>
    </section>
  )
}
const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

function rupiah(x) {
  const n = Math.abs(x)
  const [bagi, satuan] = n >= 1e12 ? [1e12, ' triliun'] : n >= 1e9 ? [1e9, ' miliar'] : n >= 1e6 ? [1e6, ' juta'] : [1, '']
  return `Rp ${satu.format(x / bagi)}${satuan}`
}
const rupiahPenuh = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 })

// Report tabel saja, menurut tanggal dokumen. Semua nilai dalam rupiah (valas memakai kurs dokumen ERP).
export default function LaporanOutstanding({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('outstanding', dataId, FILTER_AWAL, onDataHilang)
  const aktif = [...chipRentang(filter), ...chipDaftar(JENIS, terpilih)]
  const k = data?.kpi

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">Outstanding</h1>
            {data && <p className="text-sm text-slate-500">Tanggal dokumen {rentangTgl(data.periode.mulai, data.periode.akhir)}</p>}
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
        {!data && !galat && <MemuatLaporan />}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <Kelompok judul="Hutang" kolom={4}>
              <Kartu judul="Hutang belum lunas" nilai={rupiah(k.hutang)} catatan={`${angka.format(k.hutang_dok)} dokumen`}
                info={`sisa bersih setelah potongan ${rupiahPenuh.format(k.potongan)}. Total ${rupiahPenuh.format(k.hutang)}`} />
              <Kartu judul="Supplier belum dibayar" nilai={angka.format(k.supplier)}
                catatan={k.supplier_teratas ? `terbesar ${rupiah(k.supplier_teratas_nilai)}` : ''}
                info={k.supplier_teratas ? `supplier dengan sisa terbesar: ${k.supplier_teratas}` : 'tidak ada'} />
              <Kartu judul="Sudah diajukan PVR" nilai={rupiah(k.dalam_pvr)} catatan="menunggu PV"
                info={`bagian hutang yang sudah masuk PVR tapi belum dibuatkan PV. Total ${rupiahPenuh.format(k.dalam_pvr)}`} />
              <Kartu judul="PV belum jatuh tempo" nilai={rupiah(k.pv_depan)} catatan="tanggal PV setelah hari ini"
                info={`PV sudah dibuat tapi tanggalnya belum lewat, jadi dihitung belum dibayar. Total ${rupiahPenuh.format(k.pv_depan)}`} />
            </Kelompok>
            <div className="grid gap-4 lg:grid-cols-2">
              <Kelompok judul="Piutang" kolom={2}>
                <Kartu judul="Piutang belum lunas" nilai={rupiah(k.piutang)} catatan={`${angka.format(k.piutang_dok)} dokumen`}
                  info={`total ${rupiahPenuh.format(k.piutang)}`} />
                <Kartu judul="Customer belum bayar" nilai={angka.format(k.customer)}
                  catatan={k.customer_teratas ? `terbesar ${rupiah(k.customer_teratas_nilai)}` : ''}
                  info={k.customer_teratas ? `customer dengan sisa terbesar: ${k.customer_teratas}` : 'tidak ada'} />
              </Kelompok>
              <Kelompok judul="Pengadaan" kolom={2}>
                <Kartu judul="PR outstanding" nilai={`${angka.format(k.pr_dok)} PR`} catatan={catatanPengadaan(k.pr_item, k.pr_lama)}
                  info={k.pr_umur_maks == null ? 'tidak ada' : `PR yang belum seluruhnya dibuatkan PO. Paling lama ${angka.format(k.pr_umur_maks)} hari`} />
                <Kartu judul="PO outstanding" nilai={`${angka.format(k.po_dok)} PO`} catatan={catatanPengadaan(k.po_item, k.po_lama)}
                  info={k.po_umur_maks == null ? 'tidak ada' : `PO yang barangnya belum seluruhnya diterima. Paling lama ${angka.format(k.po_umur_maks)} hari`} />
              </Kelompok>
            </div>
            {k.tanpa_kurs > 0 && (
              <p className="text-xs text-amber-700">{angka.format(k.tanpa_kurs)} dokumen valas belum punya kurs dan tidak ikut dijumlahkan.</p>
            )}
            <TabelDetail judul="Hutang" laporanId="outstanding" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_HUTANG} onDataHilang={onDataHilang} />
            <TabelDetail judul="Piutang" laporanId="outstanding" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_PIUTANG} onDataHilang={onDataHilang} />
            <TabelDetail judul="PR outstanding" laporanId="outstanding" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_PR} onDataHilang={onDataHilang} />
            <TabelDetail judul="PO outstanding" laporanId="outstanding" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB_PO} onDataHilang={onDataHilang} />
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
