import { angka, tambahDariEvent, tglLengkap, ubahPilihan, warna } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import DurasiBatang from '../../grafik/DurasiBatang'
import FilterMulti from '../../komponen/FilterMulti'
import FilterTanggal from '../../komponen/FilterTanggal'
import GarisSeri from '../../grafik/GarisSeri'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KategoriOutstandingChart from '../../grafik/KategoriOutstandingChart'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import { GARIS_PI_GT } from '../../grafik/warna'
import WeeklyChart from '../../grafik/WeeklyChart'
import { MemuatLaporan } from '../../komponen/Keadaan'

// Tampilan awal: GT buatan orang Logistik (sama dengan PIGT_LOGISTIK di backend). Pembuat lain bisa ditambah lewat panel filter.
// Filter pembuat dan gudang hanya berlaku untuk angka GT; outstanding dan New PI tidak terpengaruh.
const PEMBUAT_LOGISTIK = ['Ilias', 'Rizky Ramadan', 'Robby', 'Rudianto']
const FILTER_AWAL = { dari: null, sampai: null, minggu: null, perusahaan: [], pembuat: PEMBUAT_LOGISTIK, dari_gudang: [], ke_gudang: [], importance: [] }
const RENTANG_KOSONG = { dari: null, sampai: null, minggu: null }
const JENIS = [
  { kunci: 'perusahaan', nama: 'Perusahaan' },
  { kunci: 'pembuat', nama: 'Pembuat GT' },
  { kunci: 'dari_gudang', nama: 'Gudang asal' },
  { kunci: 'ke_gudang', nama: 'Gudang tujuan' },
  { kunci: 'importance', nama: 'Importance' },
]
const TAB = [
  { kunci: 'outstanding', nama: 'Menunggu GT', ket: (h) => `Barang yang di-PI di HO untuk gudang lain dan belum dibuatkan GT per ${tglLengkap(h.periode.akhir)}. Yang paling lama di atas.` },
  { kunci: 'gt', nama: 'GT dibuat', ket: (h) => `Barang di GT yang dibuat ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}, yang terbaru di atas.` },
  { kunci: 'belum_diterima', nama: 'GT belum diterima', ket: (h) => `GT yang barangnya belum dicatat diterima di gudang tujuan per ${tglLengkap(h.periode.akhir)}. Yang paling lama di atas.` },
]

const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const hari = (d) => (d.median == null ? 'belum ada GT' : `${satu.format(d.median)} hari`)
const rata = (d) => (d.rata == null ? '' : `rata-rata ${satu.format(d.rata)} hari`)

export default function DashboardPiGt({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('pi_gt', dataId, FILTER_AWAL, onDataHilang, RENTANG_KOSONG)
  // Periode laporan ini bulanan; filter-nya tetap bernama `minggu` karena parameter API-nya sama dengan laporan mingguan
  const pilihMinggu = (indeks) => ubah({ minggu: filter.minggu === indeks ? null : indeks })
  const pilihDari = (jenis) => (nilai, e) => ubah({ [jenis]: ubahPilihan(filter[jenis], nilai, tambahDariEvent(e)) })
  // Klik nama pembuat: hanya orang itu; klik lagi: kembali ke tampilan awal
  const pilihPembuat = (nama) => ubah({ pembuat: filter.pembuat.length === 1 && filter.pembuat[0] === nama ? PEMBUAT_LOGISTIK : [nama] })

  const bulan = filter.minggu != null && data ? data.bulanan[filter.minggu] : null
  const aktif = [...chipRentang(filter), ...(bulan ? [['minggu', null, `Bulan ${bulan.label}`]] : []), ...chipDaftar(JENIS, terpilih)]
  const kpi = data?.kpi
  const warnaPerusahaan = (nama) => warna(data.pilihan.perusahaan.indexOf(nama))
  const warnaPembuat = (nama) => warna(data.pilihan.pembuat_semua.indexOf(nama))

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="PI &amp; GT" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
        {!data && !galat && <MemuatLaporan />}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={5}>
              <Kartu judul="Menunggu GT Awal" nilai={angka.format(kpi.outstanding_awal)} catatan="barang"
                info={`barang yang sudah di-PI tetapi belum dibuatkan GT per ${tglLengkap(data.periode.mulai)}. Hanya PI di HO untuk gudang lain`} />
              <Kartu judul="Barang di-PI" nilai={angka.format(kpi.new_pi)} catatan="barang" info="barang yang di-PI pada periode ini dan perlu GT" />
              <Kartu judul="Barang di-GT" nilai={angka.format(kpi.outstanding_awal + kpi.new_pi - kpi.outstanding_akhir)} catatan="barang"
                info="menunggu GT awal ditambah barang di-PI, dikurangi yang masih menunggu GT di akhir periode" />
              <Kartu judul="Menunggu GT Akhir" nilai={angka.format(kpi.outstanding_akhir)} catatan={`${angka.format(kpi.outstanding_lama)} lebih dari ${data.ambang} hari`}
                info={`barang yang belum dibuatkan GT per ${tglLengkap(data.periode.akhir)}`} />
              <Kartu judul="Aging Terlama" nilai={`${angka.format(kpi.aging_maks)} hari`} info="barang yang paling lama menunggu GT, dihitung dari tanggal PI" />
              <Kartu judul="GT Dibuat" nilai={angka.format(kpi.new_gt)} catatan={`dokumen, berisi ${angka.format(kpi.barang_gt)} barang`}
                info="ikut filter pembuat dan gudang" />
              <Kartu judul="Procurement Lead Time" nilai={hari(kpi.lead_pengadaan)} catatan={rata(kpi.lead_pengadaan)}
                info="hari dari PI sampai GT dibuat, nilai tengah. GT tanpa PI tidak dihitung" />
              <Kartu judul="Logistics Lead Time" nilai={hari(kpi.lead_logistik)} catatan={rata(kpi.lead_logistik)}
                info="hari dari GT sampai diterima, nilai tengah. GT yang belum diterima dihitung sampai hari ini" />
              <Kartu judul="Completion Rate"
                nilai={kpi.outstanding_awal + kpi.new_pi ? `${satu.format(((kpi.outstanding_awal + kpi.new_pi - kpi.outstanding_akhir) / (kpi.outstanding_awal + kpi.new_pi)) * 100)}%` : '-'}
                catatan={`${angka.format(kpi.outstanding_awal + kpi.new_pi - kpi.outstanding_akhir)} dari ${angka.format(kpi.outstanding_awal + kpi.new_pi)} barang`}
                info="barang di-GT dibagi semua barang yang perlu GT pada periode ini (menunggu GT awal ditambah barang di-PI)" />
              <Kartu judul="GT Belum Diterima" nilai={angka.format(kpi.belum_diterima)} catatan="dokumen" info="GT yang barangnya belum dicatat diterima di gudang tujuan" />
            </GridKartu>


            <KisiGrafik>
              <Petak padat="lg:col-span-8">
                <KartuGrafik judul="Antrean GT per Bulan" perbesar petunjuk="Barang menunggu GT di awal dan akhir tiap bulan, dengan barang di-PI dan di-GT. Kalau garis Barang di-PI di atas Barang di-GT, antrean bertambah. Klik bulan untuk melihat bulan itu saja.">
                  <WeeklyChart data={data.bulanan} minggu={filter.minggu} onPilihMinggu={pilihMinggu} garis={GARIS_PI_GT} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-4">
                <KartuGrafik judul="Menunggu GT per Perusahaan" petunjuk="Barang yang belum di-GT per perusahaan peminta, di awal dan akhir periode. Klik perusahaan untuk memfilter.">
                  <KategoriOutstandingChart daftar={data.outstanding_perusahaan} terpilih={filter.perusahaan} onPilih={pilihDari('perusahaan')} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-5" padat="lg:col-span-6">
                <KartuGrafik judul="GT per Perusahaan" petunjuk="Jumlah GT dibuat tiap bulan untuk tiap perusahaan. Klik nama untuk memfilter.">
                  <GarisSeri mingguan={data.bulanan} seri={data.gt_per_perusahaan} warnaSeri={warnaPerusahaan} terpilihSeri={filter.perusahaan}
                    minggu={filter.minggu} onPilihSeri={pilihDari('perusahaan')} onPilihMinggu={pilihMinggu} />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-5" padat="lg:col-span-6">
                <KartuGrafik judul="GT per Pembuat" petunjuk="Jumlah GT dibuat tiap bulan oleh tiap orang. Awalnya hanya tim Logistik; nama lain bisa ditambah di filter Pembuat GT.">
                  <GarisSeri mingguan={data.bulanan} seri={data.gt_per_pembuat} warnaSeri={warnaPembuat} terpilihSeri={filter.pembuat.length === 1 ? filter.pembuat : []}
                    minggu={filter.minggu} onPilihSeri={pilihPembuat} onPilihMinggu={pilihMinggu} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-5" padat="lg:col-span-6">
                <KartuGrafik judul="Logistics Lead Time per Rute" petunjuk="Hari dari GT dibuat sampai diterima, per rute gudang. Batang: rata-rata; garis tegak: nilai tengah. Batang jauh melewati garis berarti ada beberapa GT yang sangat lama.">
                  <DurasiBatang data={data.durasi_rute} kosong="Belum ada GT pada periode ini" />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-5" padat="lg:col-span-6">
                <KartuGrafik judul="Procurement Lead Time per Perusahaan" petunjuk="Hari dari PI sampai GT dibuat, per perusahaan. Batang: rata-rata; garis tegak: nilai tengah. GT tanpa PI tidak dihitung.">
                  <DurasiBatang data={data.durasi_perusahaan} terpilih={filter.perusahaan} onPilih={pilihDari('perusahaan')} kosong="Belum ada GT dari PI pada periode ini" />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId="pi_gt" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB} onDataHilang={onDataHilang} />
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <FilterTanggal dari={filter.dari} sampai={filter.sampai} efektif={data.rentang} satuan="hari" bawaan={null} dataset={data.dataset} onUbah={(r) => ubah({ ...r, minggu: null })} />}
        {JENIS.map(({ kunci, nama }) => (
          <FilterMulti key={kunci} sebaris label={nama} opsi={data?.pilihan[kunci] ?? []} terpilih={filter[kunci]} onUbah={(v) => ubah({ [kunci]: v })} />
        ))}
      </PanelFilter>
    </div>
  )
}
