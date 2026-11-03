import { useMemo } from 'react'
import { angka, bandingKpi, persen, tambahDariEvent, tglLengkap, ubahPilihan } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterTanggal from '../../komponen/FilterTanggal'
import PelanggarBerulang from '../../grafik/PelanggarBerulang'
import PetaOperatorJam from '../../grafik/PetaOperatorJam'
import TrenHarian from '../../grafik/TrenHarian'
import BatangKendaraan from '../../grafik/BatangKendaraan'
import BatangRisiko from '../../grafik/BatangRisiko'
import BatangRisikoSupplier from '../../grafik/BatangRisikoSupplier'
import SebaranTara from '../../grafik/SebaranTara'
import FilterMulti from '../../komponen/FilterMulti'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'

const angka2 = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Tampilan awal dan hasil Reset filter. Data tanpa penjualan: server mengabaikan filter ini.
const FILTER_AWAL = { transaksi: ['Penjualan'] }
const KOSONG = []
const TAB = [
  { kunci: 'semua', nama: 'Semua transaksi', ket: (h) => `Transaksi timbang ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}.` },
  { kunci: 'berisiko', nama: 'Berisiko', ket: () => 'Transaksi dengan indikator WARNING pada periode yang sama.' },
]

// Penjualan / Pembelian / Semua: pilihan utama laporan, selalu terlihat. Angka = jumlah transaksi tiap jenis dengan filter lain yang berlaku.
const URUT_JENIS = ['Penjualan', 'Pembelian']
// Filter yang tidak berlaku untuk jenis itu (server juga menyembunyikannya): dikosongkan saat berpindah, supaya tidak menyaring diam-diam
const SEMBUNYI_PER_JENIS = { Penjualan: { supplier: [] }, Pembelian: { customer: [] } }
function PengalihJenis({ jenis, jumlah, terpilih, onUbah }) {
  if (jenis.length < 2) return null
  const opsi = [...jenis].sort((a, b) => (URUT_JENIS.indexOf(a) + 1 || 99) - (URUT_JENIS.indexOf(b) + 1 || 99))
  const semua = terpilih.length !== 1
  const tombol = (label, aktif, onClick, n) => (
    <button
      key={label}
      type="button"
      role="radio"
      aria-checked={aktif}
      onClick={onClick}
      className={
        'flex items-baseline gap-2 rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
        (aktif ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-800')
      }
    >
      {label}
      {n != null && <span className={'text-xs tabular-nums ' + (aktif ? 'text-slate-500' : 'text-slate-400')}>{angka.format(n)}</span>}
    </button>
  )
  return (
    <div role="radiogroup" aria-label="Jenis transaksi" className="inline-flex gap-0.5 rounded-lg bg-slate-100 p-1">
      {opsi.map((j) => tombol(j, !semua && terpilih[0] === j, () => onUbah([j]), jumlah[j] ?? 0))}
      {tombol('Semua', semua, () => onUbah([]), null)}
    </div>
  )
}

export default function DashboardPalm({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('palm_weighbridge', dataId, FILTER_AWAL, onDataHilang)

  // Dibuat sekali supaya grafik (memo) tidak digambar ulang tanpa perlu
  const pilih = useMemo(() => {
    const dari = (jenis) => (nilai, e) => setFilter((f) => ({ ...f, [jenis]: ubahPilihan(f[jenis] ?? [], nilai, tambahDariEvent(e)) }))
    const tambahkan = (daftar, nilai) => (daftar.includes(nilai) ? daftar : [...daftar, nilai])
    // Sel yang mewakili dua dimensi sekaligus: supplier x indikator, operator x jam
    const pasangan = (ja, jb) => (a, b, e) =>
      setFilter((f) => {
        const da = f[ja] ?? [], db = f[jb] ?? []
        if (tambahDariEvent(e)) return { ...f, [ja]: tambahkan(da, a), [jb]: tambahkan(db, b) }
        const sama = da.length === 1 && da[0] === a && db.length === 1 && db[0] === b
        return { ...f, [ja]: sama ? [] : [a], [jb]: sama ? [] : [b] }
      })
    return {
      risiko: dari('risiko'), kendaraan: dari('kendaraan'), tiket: dari('tiket'), supplier: dari('supplier'), supplierRisiko: pasangan('supplier', 'risiko'),
      customer: dari('customer'), customerRisiko: pasangan('customer', 'risiko'),
      tanggal: dari('tanggal'), jam: dari('jam'), operator: dari('operator'), operatorJam: pasangan('operator', 'jam'),
      pelanggar: (jenis, nilai, e) => dari(jenis)(nilai, e),
      baris: (b, e) => dari('tiket')(b.ticket_no, e),
    }
  }, [setFilter])
  const tiketTerpilih = filter.tiket ?? KOSONG
  const barisTerpilih = useMemo(() => (b) => tiketTerpilih.includes(b.ticket_no), [tiketTerpilih])

  // Jenis Transaksi dipilih lewat pengalih di kepala laporan, bukan di panel / chip filter
  const daftarFilter = useMemo(() => (data?.filter ?? []).filter((f) => f.kunci !== 'transaksi'), [data?.filter])
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglLengkap(nilai) : kunci === 'jam' ? `${nilai}.00 sampai ${nilai}.59` : nilai)
  const aktif = [...chipRentang(filter), ...chipDaftar(daftarFilter, terpilih, tampil)]
  const pelanggarTerpilih = useMemo(
    () => ({ kendaraan: filter.kendaraan ?? KOSONG, supir: filter.supir ?? KOSONG, supplier: filter.supplier ?? KOSONG }),
    [filter.kendaraan, filter.supir, filter.supplier],
  )

  const kpi = data?.kpi
  const mitra = data?.risiko_supplier?.dimensi ?? 'supplier'   // Penjualan: customer
  const tren = data?.tren ?? KOSONG
  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Weighbridge Fraud Early Detector" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />
        {data && <PengalihJenis jenis={data.pilihan.transaksi ?? KOSONG} jumlah={data.jumlah_jenis ?? {}} terpilih={filter.transaksi ?? KOSONG} onUbah={(v) => ubah({ transaksi: v, ...SEMBUNYI_PER_JENIS[v.length === 1 ? v[0] : ''] })} />}

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Grafik tidak bisa dimuat: {galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat grafik timbangan...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu>
              <Kartu judul="Transaksi" nilai={angka.format(kpi.transaksi)} info="transaksi timbang dalam periode" banding={bandingKpi(kpi.transaksi, data.banding, (k) => k.transaksi)} />
              <Kartu
                judul="Transaksi Berisiko"
                nilai={angka.format(kpi.berisiko)}
                banding={bandingKpi(kpi.berisiko, data.banding, (k) => k.berisiko, { naikBaik: false })}
                catatan={kpi.transaksi > 0 ? `${persen(kpi.berisiko / kpi.transaksi)} dari transaksi` : null}
                info="transaksi dengan indikator WARNING"
              />
              <Kartu judul="Rata-rata Selisih Tara" nilai={`${angka2.format(kpi.rata_selisih_tara)} kg`} info="selisih tara aktual dari tara historis tertinggi kendaraannya" banding={bandingKpi(kpi.rata_selisih_tara, data.banding, (k) => k.rata_selisih_tara)} />
              <Kartu judul="Rata-rata Potongan" nilai={`${angka2.format(kpi.rata_potongan)} kg`} info="potongan per transaksi" banding={bandingKpi(kpi.rata_potongan, data.banding, (k) => k.rata_potongan)} />
            </GridKartu>

            <KisiGrafik>
              <Petak padat="lg:order-1 lg:col-span-8">
                <KartuGrafik
                  judul="Tren Harian Transaksi Berisiko" perbesar
                  petunjuk={tren.length > 0 ? `${tglLengkap(tren[0].hari)} sampai ${tglLengkap(tren.at(-1).hari)}` : null}
                >
                  <TrenHarian data={tren} indikator={data.indikator} terpilih={terpilih('tanggal')} onPilih={pilih.tanggal} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-10 lg:col-span-4" padat="lg:order-2 lg:col-span-4">
                <KartuGrafik judul="Indikator Risiko">
                  <BatangRisiko data={data.risiko} terpilih={terpilih('risiko')} onPilih={pilih.risiko} />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-10 lg:col-span-6" padat="lg:order-3 lg:col-span-6">
                <KartuGrafik judul="Selisih Tara per Kendaraan" petunjuk="Rata-rata selisih dari tara historis tertinggi, yang paling menyimpang lebih dulu">
                  <BatangKendaraan data={data.tara_kendaraan} terpilih={terpilih('kendaraan')} onPilih={pilih.kendaraan} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-10 lg:col-span-4" padat="lg:order-5 lg:col-span-5">
                <KartuGrafik judul="Pelanggar Berulang" petunjuk="WARNING terbanyak; persentase menunjukkan seberapa sering dari semua transaksinya">
                  <PelanggarBerulang data={data.pelanggar} terpilih={pelanggarTerpilih} onPilih={pilih.pelanggar} />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-10 lg:col-span-6" padat="lg:order-6 lg:col-span-7">
                <KartuGrafik judul={mitra === 'customer' ? 'Indikator Risiko per Customer' : 'Indikator Risiko per Supplier'}>
                  <BatangRisikoSupplier
                    risiko_supplier={data.risiko_supplier}
                    indikator={data.indikator}
                    label={mitra}
                    terpilih={terpilih(mitra)}
                    risikoTerpilih={terpilih('risiko')}
                    onPilih={pilih[`${mitra}Risiko`]}
                    onPilihRisiko={pilih.risiko}
                    onPilihSupplier={pilih[mitra]}
                  />
                </KartuGrafik>
              </Petak>

              {/* Urutan padat: grafik berpasangan dengan grafik (kendaraan + sebaran tara), daftar dengan daftar (pelanggar + supplier), peta operator paling bawah */}
              <Petak padat="lg:order-7 lg:col-span-12">
                <KartuGrafik judul="Operator per Jam Masuk" petunjuk="Angka: transaksi WARNING. Makin pekat, makin tinggi persentase berisiko pada jam itu">
                  <PetaOperatorJam
                    data={data.operator_jam}
                    operatorTerpilih={terpilih('operator')}
                    jamTerpilih={terpilih('jam')}
                    onPilihSel={pilih.operatorJam}
                    onPilihOperator={pilih.operator}
                    onPilihJam={pilih.jam}
                  />
                </KartuGrafik>
              </Petak>

              <Petak padat="lg:order-4 lg:col-span-6">
                <KartuGrafik judul="Durasi Timbang vs Selisih Tara" perbesar petunjuk="Satu titik satu transaksi. Garis putus-putus: ambang WARNING">
                  <SebaranTara
                    sebaran={data.sebaran}
                    indikator={data.indikator}
                    ambang={data.ambang}
                    terpilih={terpilih('tiket')}
                    onPilih={pilih.tiket}
                    risikoTerpilih={terpilih('risiko')}
                    onPilihRisiko={pilih.risiko}
                  />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail
              laporanId="palm_weighbridge"
              dataId={dataId}
              filter={filter}
              jumlah={{ semua: kpi.transaksi, berisiko: kpi.berisiko }}
              tab={TAB}
              onDataHilang={onDataHilang}
              onPilihBaris={pilih.baris}
              barisTerpilih={barisTerpilih}
            />
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
