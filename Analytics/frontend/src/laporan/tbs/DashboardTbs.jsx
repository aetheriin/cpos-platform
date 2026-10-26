import { useMemo } from 'react'
import BatangPeringkat from '../../grafik/BatangPeringkat'
import HargaTipe from '../../grafik/HargaTipe'
import RataHari from '../../grafik/RataHari'
import TrenForecast from '../../grafik/TrenForecast'
import { hargaKg, rupiah, ton } from '../../grafik/tbs'
import { angka, bandingKpi, tambahDariEvent, tglLengkap, ubahPilihan } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterTanggal from '../../komponen/FilterTanggal'
import FilterMulti from '../../komponen/FilterMulti'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'

const FILTER_AWAL = {}
const KOSONG = []
const TAB = [
  { kunci: 'pembelian', nama: 'Per pembelian', ket: (h) => `Detail pembelian TBS ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}.` },
  { kunci: 'supplier', nama: 'Per supplier', ket: () => 'Total per supplier pada periode yang sama.' },
]

export default function DashboardTbs({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('penerimaan_tbs', dataId, FILTER_AWAL, onDataHilang)

  const pilih = useMemo(() => {
    const dari = (jenis) => (nilai, e) => setFilter((f) => ({ ...f, [jenis]: ubahPilihan(f[jenis] ?? [], nilai, tambahDariEvent(e)) }))
    return { tanggal: dari('tanggal'), tipe: dari('tipe'), grup: dari('grup'), supplier: dari('supplier'), hari: dari('hari_minggu') }
  }, [setFilter])

  const daftarFilter = data?.filter ?? []
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglLengkap(nilai) : nilai)
  const aktif = [...chipRentang(filter), ...chipDaftar(daftarFilter, terpilih, tampil)]

  const kpi = data?.kpi
  const b = data?.banding
  const fc = data?.forecast
  const fcTotal = fc ? fc.hari.reduce((a, d) => a + d.netto, 0) : null
  const tren = data?.tren ?? KOSONG
  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Forecast Penerimaan TBS" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Grafik tidak bisa dimuat: {galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat penerimaan TBS...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={3}>
              <Kartu judul="Total Netto" nilai={ton(kpi.netto)} info="berat bersih TBS yang diterima" banding={bandingKpi(kpi.netto, b, (k) => k.netto, { naikBaik: true })} />
              <Kartu judul="Total Nilai" nilai={rupiah(kpi.nilai)} info="nilai pembelian TBS" banding={bandingKpi(kpi.nilai, b, (k) => k.nilai)} />
              <Kartu judul="Harga Rata-rata" nilai={hargaKg(kpi.harga)} info="tertimbang: total nilai dibagi total kg" banding={bandingKpi(kpi.harga, b, (k) => k.harga, { naikBaik: false })} />
              <Kartu judul="Rata-rata per Truk" nilai={kpi.per_truk == null ? '–' : `${angka.format(Math.round(kpi.per_truk))} kg`} info="netto per pengiriman" banding={bandingKpi(kpi.per_truk, b, (k) => k.per_truk)} />
              <Kartu judul="Supplier Aktif" nilai={angka.format(kpi.supplier)} info="supplier yang mengirim dalam periode" banding={bandingKpi(kpi.supplier, b, (k) => k.supplier, { naikBaik: true })} />
              <Kartu
                judul={fc ? `Forecast ${fc.hari.length} Hari` : 'Forecast'}
                nilai={fcTotal == null ? '–' : ton(fcTotal)}
                catatan={fc ? `mulai ${tglLengkap(fc.hari[0].hari)}` : 'riwayat belum cukup'}
                info={fc ? 'rata-rata harian 2 minggu terakhir (hari tanpa penerimaan tidak dihitung) x 7 x proporsi hari yang sama tahun lalu terhadap total 7 harinya' : null}
              />
            </GridKartu>

            {/* Urutan padat: forecast dan rata-rata per hari di baris pertama, tiga peringkat di baris kedua, harga per tipe paling bawah */}
            <KisiGrafik>
              <Petak padat="lg:order-1 lg:col-span-8">
                <KartuGrafik
                  judul="Netto & Forecast"
                  petunjuk={tren.length > 0 ? `${tglLengkap(tren[0].hari)} sampai ${tglLengkap(tren.at(-1).hari)}${fc ? `, lalu ${fc.hari.length} hari ke depan` : ''}` : null}
                >
                  <TrenForecast tren={tren} forecast={fc} terpilih={terpilih('tanggal')} onPilih={pilih.tanggal} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-10 lg:col-span-4" padat="lg:order-3 lg:col-span-4">
                <KartuGrafik judul="Netto per Tipe" petunjuk="Angka kanan: harga rata-rata">
                  <BatangPeringkat
                    data={data.per_tipe.data}
                    terpilih={terpilih('tipe')}
                    onPilih={pilih.tipe}
                    keterangan={data.per_tipe.jumlah > data.per_tipe.data.length ? `${data.per_tipe.data.length} tipe dengan netto terbesar dari ${angka.format(data.per_tipe.jumlah)} tipe.` : null}
                  />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-10 lg:col-span-6" padat="lg:order-6 lg:col-span-12">
                <KartuGrafik judul="Harga per Tipe" petunjuk="Rp/kg tertimbang per hari">
                  <HargaTipe data={data.harga_tipe} mulai={tren[0]?.hari ?? data.tren_mulai} akhir={tren.at(-1)?.hari ?? data.periode.akhir} terpilih={terpilih('tipe')} onPilih={pilih.tipe} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-10 lg:col-span-5" padat="lg:order-4 lg:col-span-4">
                <KartuGrafik judul="Supplier Teratas">
                  <BatangPeringkat
                    data={data.per_supplier.data}
                    terpilih={terpilih('supplier')}
                    onPilih={pilih.supplier}
                    warna="#0f766e"
                    keterangan={data.per_supplier.jumlah > data.per_supplier.data.length ? `${data.per_supplier.data.length} supplier dengan netto terbesar dari ${angka.format(data.per_supplier.jumlah)} supplier.` : null}
                  />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-10 lg:col-span-5" padat="lg:order-5 lg:col-span-4">
                <KartuGrafik judul="Business Group">
                  <BatangPeringkat
                    data={data.per_grup.data}
                    terpilih={terpilih('grup')}
                    onPilih={pilih.grup}
                    warna="#6d28d9"
                    keterangan={data.per_grup.jumlah > data.per_grup.data.length ? `${data.per_grup.data.length} business group dengan netto terbesar dari ${angka.format(data.per_grup.jumlah)}.` : null}
                  />
                </KartuGrafik>
              </Petak>

              <Petak padat="lg:order-2 lg:col-span-4">
                <KartuGrafik judul="Rata-rata per Hari" petunjuk="Hari tanpa pembelian tidak dihitung">
                  <RataHari data={data.per_hari_minggu} terpilih={terpilih('hari_minggu')} onPilih={pilih.hari} />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId="penerimaan_tbs" dataId={dataId} filter={filter} jumlah={{ pembelian: kpi.baris, supplier: kpi.supplier_baris }} tab={TAB} onDataHilang={onDataHilang} />
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <FilterTanggal dari={filter.dari} sampai={filter.sampai} efektif={data.rentang} satuan={data.rentang.satuan} bawaan={data.rentang.bawaan} dataset={data.dataset} onUbah={ubah} />}
        {daftarFilter
          .filter((f) => f.panel)
          .map(({ kunci, nama }) => (
            <FilterMulti key={kunci} sebaris label={nama} opsi={data.pilihan[kunci] ?? KOSONG} terpilih={terpilih(kunci)} onUbah={(v) => ubah({ [kunci]: v })} />
          ))}
      </PanelFilter>
    </div>
  )
}
