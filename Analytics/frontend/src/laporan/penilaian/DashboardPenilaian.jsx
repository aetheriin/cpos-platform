import { angka, tambahDariEvent, ubahPilihan } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import FilterTanggal from '../../komponen/FilterTanggal'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KategoriPvr from '../../grafik/KategoriPvr'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import RekapPvr from '../../grafik/RekapPvr'
import TabelDetail from '../../komponen/TabelDetail'
import TrenPenilaian from '../../grafik/TrenPenilaian'

const skor = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

// Dashboard PVR KPI dan PV KPI (isi sama, hanya voucher dan pembuat yang dinilai berbeda). Buat sekali per laporan di luar komponen,
// supaya filter awal tetap objek yang sama.
// voucher: 'PVR' atau 'PV'. dinilai: nama pembuat tampilan awal, sama dengan *_PENILAIAN_PEMBUAT di backend. Nama lain lewat panel filter.
export default function buatDashboardPenilaian({ laporanId, judul, voucher, tabelBobot, dinilai }) {
  const FILTER_AWAL = { dari: null, sampai: null, perusahaan: [], pembuat: dinilai, kategori: [] }
  const JENIS = [
    { kunci: 'perusahaan', nama: 'Perusahaan' },
    { kunci: 'pembuat', nama: `Pembuat ${voucher}` },
    { kunci: 'kategori', nama: 'Kategori' },
  ]

  return function DashboardPenilaian({ dataId, onDataHilang }) {
    const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard(laporanId, dataId, FILTER_AWAL, onDataHilang)
    const pilihDari = (jenis) => (nilai, e) => ubah({ [jenis]: ubahPilihan(filter[jenis], nilai, tambahDariEvent(e)) })
    // Klik nama pembuat: hanya orang itu; klik lagi: kembali ke tampilan awal
    const pilihPembuat = (nama) => ubah({ pembuat: filter.pembuat.length === 1 && filter.pembuat[0] === nama ? dinilai : [nama] })
    const aktif = [...chipRentang(filter), ...chipDaftar(JENIS, terpilih)]
    const kpi = data?.kpi

    const tab = data
      ? [
          { kunci: 'dinilai', nama: 'Baris dinilai', ket: () => `Tiap baris menambah skor sebesar bobotnya. Angkutan dihitung per item, kategori lain sekali per ${voucher}.` },
          { kunci: 'kosong', nama: 'Tanpa kategori', ket: () => `${voucher} tanpa Check Number, dan supplier-nya juga belum pernah punya Check Number. Bernilai 0.` },
        ]
      : []

    return (
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1 space-y-4">
          <KepalaLaporan judul={judul} data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

          {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
          {!data && !galat && <p className="text-sm text-slate-500">Memuat...</p>}

          {data && (
            <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
              <GridKartu kolom={3}>
                <Kartu judul="Total skor" nilai={skor.format(kpi.skor)} catatan={`${angka.format(kpi.pembuat)} pembuat`} info="jumlah bobot dari semua baris yang dinilai" />
                <Kartu judul={`${voucher} dibuat`} nilai={angka.format(kpi.pvr)} catatan={`${angka.format(kpi.angkutan)} item Angkutan`} info={`nomor ${voucher} unik menurut tanggal voucher, tanpa void`} />
                <Kartu judul={`${voucher} tanpa kategori`} nilai={angka.format(kpi.tanpa_kategori)} catatan="bernilai 0" info={`${voucher} tanpa Check Number dan supplier-nya belum pernah punya Check Number`} />
              </GridKartu>

              <KisiGrafik>
                <Petak panjang="md:col-span-10" padat="lg:col-span-8">
                  <KartuGrafik judul={`${voucher} Penilaian`} petunjuk="Skor (jumlah bobot) per bulan untuk tiap pembuat. Klik nama di legenda untuk melihat satu orang saja.">
                    <TrenPenilaian data={data.rekap} voucher={voucher} onPilih={pilihPembuat} />
                  </KartuGrafik>
                </Petak>
                <Petak panjang="md:col-span-10" padat="lg:col-span-4">
                  <KartuGrafik judul="Bobot" petunjuk={`Bobot tiap kategori (tabel ${tabelBobot}) dan skor yang dihasilkannya. Klik kategori untuk memfilter.`}>
                    <KategoriPvr data={data.kategori} voucher={voucher} terpilih={filter.kategori} onPilih={pilihDari('kategori')} />
                  </KartuGrafik>
                </Petak>
                <Petak panjang="md:col-span-10" padat="lg:col-span-12">
                  <KartuGrafik judul="Rekap Skor per Bulan" petunjuk="Angka di balik grafik di atas: skor tiap pembuat per bulan. Klik nama untuk melihat satu orang saja.">
                    <RekapPvr data={data.rekap} voucher={voucher} terpilih={filter.pembuat.length === 1 ? filter.pembuat : []} onPilih={pilihPembuat} />
                  </KartuGrafik>
                </Petak>
              </KisiGrafik>

              <TabelDetail laporanId={laporanId} dataId={dataId} filter={filter} jumlah={data.jumlah} tab={tab} onDataHilang={onDataHilang} />
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
}
