import { angka, bandingKpi, labelLengkap, persen, persenKecil, tambahDariEvent, tglLengkap, ubahPilihan, warna } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import BatangPembuat from '../../grafik/BatangPembuat'
import DonatKategori from '../../grafik/DonatKategori'
import FilterMulti from '../../komponen/FilterMulti'
import GarisSeri from '../../grafik/GarisSeri'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KategoriOutstandingChart from '../../grafik/KategoriOutstandingChart'
import KartuKecepatan from '../../komponen/KartuKecepatan'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import FilterTanggal from '../../komponen/FilterTanggal'
import TabelDetail from '../../komponen/TabelDetail'
import { GARIS_PO_PI } from '../../grafik/warna'
import WeeklyChart from '../../grafik/WeeklyChart'
import { MemuatLaporan } from '../../komponen/Keadaan'

const FILTER_AWAL = { dari: null, sampai: null, minggu: null, perusahaan: [], kategori: [], pembuat: [], umur: [] }
const JENIS = [
  { kunci: 'perusahaan', nama: 'Perusahaan' },
  { kunci: 'kategori', nama: 'Kategori' },
  { kunci: 'pembuat', nama: 'Buyer' },
  { kunci: 'umur', nama: 'Aging' },
]
const RENTANG_KOSONG = { dari: null, sampai: null, minggu: null }
const TAB = [
  {
    kunci: 'outstanding',
    nama: 'Outstanding akhir',
    ket: (h) => `Baris PO yang masih outstanding pada akhir ${tglLengkap(h.periode.akhir)}.`,
  },
  {
    kunci: 'pi',
    nama: 'Sudah PI',
    ket: (h) => `PI yang tercatat ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}.`,
  },
]

export default function DashboardPoPi({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('po_pi', dataId, FILTER_AWAL, onDataHilang, RENTANG_KOSONG)

  const pilihMinggu = (indeks) => ubah({ minggu: filter.minggu === indeks ? null : indeks })
  const pilihDari = (jenis) => (nama, e) => ubah({ [jenis]: ubahPilihan(filter[jenis], nama, tambahDariEvent(e)) })
  const pilihPerusahaan = pilihDari('perusahaan')
  const pilihKategori = pilihDari('kategori')
  const pilihPembuat = pilihDari('pembuat')

  const minggu = filter.minggu != null && data ? data.mingguan[filter.minggu] : null
  const aktif = [...chipRentang(filter), ...(minggu ? [['minggu', null, `Minggu ${labelLengkap(minggu)}`]] : []), ...chipDaftar(JENIS, terpilih)]

  const kpi = data?.kpi
  const warnaPerusahaan = (nama) => warna(data.pilihan.perusahaan.indexOf(nama))
  // Dari daftar seluruh nama, bukan yang sedang tampil, supaya warnanya tidak bergeser
  const warnaPembuat = (nama) => warna((data.pilihan.pembuat_semua ?? data.pilihan.pembuat).indexOf(nama))

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
      <KepalaLaporan judul="PO &amp; PI Outstanding" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

      {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
      {!data && !galat && <MemuatLaporan />}

      {data && (
        <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
          <GridKartu>
            <Kartu judul="Outstanding Awal" nilai={angka.format(kpi.outstanding_awal)} info="baris PO yang masih outstanding di awal periode" banding={bandingKpi(kpi.outstanding_awal, data.banding, (k) => k.outstanding_awal)} />
            <Kartu judul="New PO" nilai={angka.format(kpi.new_po)} info="baris PO yang dibuat dalam periode" banding={bandingKpi(kpi.new_po, data.banding, (k) => k.new_po)} />
            <Kartu judul="New PI" nilai={angka.format(kpi.new_pi)} info="baris PI yang dibuat dalam periode" banding={bandingKpi(kpi.new_pi, data.banding, (k) => k.new_pi)} />
            <Kartu judul="Outstanding Akhir" nilai={angka.format(kpi.outstanding_akhir)} info="baris PO yang masih outstanding di akhir periode" banding={bandingKpi(kpi.outstanding_akhir, data.banding, (k) => k.outstanding_akhir, { naikBaik: false })} />
            <Kartu judul="Completion Rate" nilai={persen(kpi.completion_rate)} info="PO yang dibuat dalam periode dan sudah selesai" />
            <Kartu
              judul="PI Parsial"
              nilai={persenKecil(kpi.pi_partial.persen)}
              banding={bandingKpi(kpi.pi_partial.persen, data.banding, (k) => k.pi_partial.persen, { jenis: 'poin', naikBaik: false })}
              catatan={`${angka.format(kpi.pi_partial.jumlah)} dari ${angka.format(kpi.pi_partial.dari)} PI`}
              info="New PI yang PO-nya punya lebih dari satu PI"
            />
            <Kartu judul="Rata-rata Aging" nilai={`${angka.format(Math.round(kpi.aging_rata_rata))} hari`} info="umur PO yang belum selesai" />
            <Kartu judul="Aging Terlama" nilai={`${angka.format(kpi.aging_maks)} hari`} info="umur PO tertua yang belum selesai" />
            <KartuKecepatan kecepatan={data.kecepatan} satuan="PO" />
          </GridKartu>

          {/* Urutan padat: ringkasan mingguan dan kategori outstanding, lalu dua donat dengan outstanding per pembuat, lalu tiga grafik garis */}
          <KisiGrafik>
            <Petak padat="lg:order-1 lg:col-span-8">
              <KartuGrafik judul="Ringkasan Mingguan" perbesar petunjuk="Klik bar atau tanggal untuk fokus ke satu minggu.">
                <WeeklyChart data={data.mingguan} minggu={filter.minggu} onPilihMinggu={pilihMinggu} garis={GARIS_PO_PI} />
              </KartuGrafik>
            </Petak>

            <Petak padat="lg:order-2 lg:col-span-4">
              <KartuGrafik judul="Kategori Outstanding" petunjuk="Kategori dengan outstanding terbanyak pada periode yang dipilih. Klik satu kategori untuk memfilter semua angka.">
                <KategoriOutstandingChart daftar={data.kategori_outstanding} terpilih={filter.kategori} onPilih={pilihKategori} />
              </KartuGrafik>
            </Petak>

            <Petak panjang="md:col-span-5" padat="lg:order-3 lg:col-span-3">
              <KartuGrafik judul="Kategori PO" petunjuk="Lima kategori terbesar, sisanya digabung. Klik irisan atau daftar untuk memfilter.">
                <DonatKategori daftar={data.kategori_new_po} terpilih={filter.kategori} onPilih={pilihKategori} satuan="baris PO" />
              </KartuGrafik>
            </Petak>
            <Petak panjang="md:col-span-5" padat="lg:order-4 lg:col-span-3">
              <KartuGrafik judul="Kategori PI" petunjuk="Lima kategori terbesar, sisanya digabung. Klik irisan atau daftar untuk memfilter.">
                <DonatKategori daftar={data.kategori_new_pi} terpilih={filter.kategori} onPilih={pilihKategori} satuan="baris PI" />
              </KartuGrafik>
            </Petak>

            <Petak panjang="md:col-span-5" padat="lg:order-6 lg:col-span-4">
              <KartuGrafik judul="PO per Perusahaan" petunjuk="Klik nama perusahaan untuk memilih. Klik tanggal untuk memilih minggu.">
                <GarisSeri
                  mingguan={data.mingguan}
                  seri={data.new_po_per_perusahaan}
                  warnaSeri={warnaPerusahaan}
                  terpilihSeri={filter.perusahaan}
                  minggu={filter.minggu}
                  onPilihSeri={pilihPerusahaan}
                  onPilihMinggu={pilihMinggu}
                />
              </KartuGrafik>
            </Petak>
            <Petak panjang="md:col-span-5" padat="lg:order-7 lg:col-span-4">
              <KartuGrafik judul="PI per Perusahaan" petunjuk="Klik nama perusahaan untuk memilih. Klik tanggal untuk memilih minggu.">
                <GarisSeri
                  mingguan={data.mingguan}
                  seri={data.new_pi_per_perusahaan}
                  warnaSeri={warnaPerusahaan}
                  terpilihSeri={filter.perusahaan}
                  minggu={filter.minggu}
                  onPilihSeri={pilihPerusahaan}
                  onPilihMinggu={pilihMinggu}
                />
              </KartuGrafik>
            </Petak>

            <Petak panjang="md:col-span-5" padat="lg:order-8 lg:col-span-4">
              <KartuGrafik judul="PO per Buyer" petunjuk="New PO per buyer. Klik titik atau nama buyer untuk memilihnya.">
                <GarisSeri
                  mingguan={data.mingguan}
                  seri={data.new_po_per_pembuat}
                  warnaSeri={warnaPembuat}
                  terpilihSeri={filter.pembuat}
                  minggu={filter.minggu}
                  onPilihSeri={pilihPembuat}
                  onPilihMinggu={pilihMinggu}
                />
              </KartuGrafik>
            </Petak>
            <Petak panjang="md:col-span-5" padat="lg:order-5 lg:col-span-6">
              <KartuGrafik judul="Outstanding per Buyer" petunjuk="Outstanding akhir per buyer. Klik batang untuk memilih buyer.">
                <BatangPembuat data={data.outstanding_per_pembuat} terpilih={filter.pembuat} onPilih={pilihPembuat} />
              </KartuGrafik>
            </Petak>
          </KisiGrafik>

          <TabelDetail
            laporanId="po_pi"
            dataId={dataId}
            filter={filter}
            jumlah={{ outstanding: kpi.outstanding_akhir, pi: kpi.new_pi }}
            tab={TAB}
            onDataHilang={onDataHilang}
          />
        </div>
      )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <FilterTanggal dari={filter.dari} sampai={filter.sampai} efektif={data.rentang} satuan={data.rentang.satuan} bawaan={data.rentang.bawaan} dataset={data.dataset} onUbah={(r) => ubah({ ...r, minggu: null })} />}
        <FilterMulti
          sebaris
          label="Perusahaan"
          opsi={data?.pilihan.perusahaan ?? []}
          terpilih={filter.perusahaan}
          onUbah={(v) => ubah({ perusahaan: v })}
        />
        <FilterMulti
          sebaris
          label="Kategori"
          opsi={data?.pilihan.kategori ?? []}
          terpilih={filter.kategori}
          onUbah={(v) => ubah({ kategori: v })}
        />
        <FilterMulti
          sebaris
          label="Buyer"
          opsi={data?.pilihan.pembuat ?? []}
          terpilih={filter.pembuat}
          onUbah={(v) => ubah({ pembuat: v })}
        />
        <FilterMulti
          sebaris
          label="Aging"
          opsi={data?.pilihan.umur ?? []}
          terpilih={filter.umur}
          onUbah={(v) => ubah({ umur: v })}
        />
      </PanelFilter>
    </div>
  )
}
