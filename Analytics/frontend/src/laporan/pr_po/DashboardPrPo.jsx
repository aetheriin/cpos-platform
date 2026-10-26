import DonatKategori from '../../grafik/DonatKategori'
import GarisSeri from '../../grafik/GarisSeri'
import FilterMulti from '../../komponen/FilterMulti'
import KategoriOutstandingChart from '../../grafik/KategoriOutstandingChart'
import KartuKecepatan from '../../komponen/KartuKecepatan'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import FilterTanggal from '../../komponen/FilterTanggal'
import TabelDetail from '../../komponen/TabelDetail'
import WeeklyChart from '../../grafik/WeeklyChart'
import { angka, bandingKpi, labelLengkap, persen, persenKecil, tambahDariEvent, tglLengkap, ubahPilihan, warna } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'

const FILTER_AWAL = { dari: null, sampai: null, minggu: null, perusahaan: [], kategori: [], buyer: [], umur: [] }
const TAB = [
  {
    kunci: 'outstanding',
    nama: 'Outstanding akhir',
    ket: (h) => `Baris PR yang masih outstanding pada akhir ${tglLengkap(h.periode.akhir)}.`,
  },
  {
    kunci: 'po',
    nama: 'Sudah PO',
    ket: (h) => `PO yang dibuat ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}.`,
  },
]
const JENIS = [
  { kunci: 'perusahaan', nama: 'Perusahaan' },
  { kunci: 'kategori', nama: 'Kategori' },
  { kunci: 'buyer', nama: 'Buyer' },
  { kunci: 'umur', nama: 'Aging' },
]
const RENTANG_KOSONG = { dari: null, sampai: null, minggu: null }

export default function DashboardPrPo({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('pr_po', dataId, FILTER_AWAL, onDataHilang, RENTANG_KOSONG)

  const pilihMinggu = (indeks) => ubah({ minggu: filter.minggu === indeks ? null : indeks })
  const pilihDari = (jenis) => (nama, e) => ubah({ [jenis]: ubahPilihan(filter[jenis], nama, tambahDariEvent(e)) })
  const pilihKategori = pilihDari('kategori')
  const pilihPerusahaan = pilihDari('perusahaan')
  const pilihBuyer = pilihDari('buyer')

  const minggu = filter.minggu != null && data ? data.mingguan[filter.minggu] : null
  const aktif = [...chipRentang(filter), ...(minggu ? [['minggu', null, `Minggu ${labelLengkap(minggu)}`]] : []), ...chipDaftar(JENIS, terpilih)]

  const kpi = data?.kpi
  const warnaPerusahaan = (nama) => warna(data.pilihan.perusahaan.indexOf(nama))
  // Dari daftar seluruh nama, bukan yang sedang tampil, supaya warnanya tidak bergeser
  const warnaBuyer = (nama) => warna((data.pilihan.buyer_semua ?? data.pilihan.buyer).indexOf(nama))

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="PR &amp; PO Outstanding" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {galat && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {galat.message}
          </div>
        )}

        {!data && !galat && <p className="text-sm text-slate-500">Memuat...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu>
              <Kartu judul="Outstanding Awal" nilai={angka.format(kpi.outstanding_awal)} info="baris PR yang masih outstanding di awal periode" banding={bandingKpi(kpi.outstanding_awal, data.banding, (k) => k.outstanding_awal)} />
              <Kartu judul="New PR" nilai={angka.format(kpi.new_pr)} info="baris PR yang dibuat dalam periode" banding={bandingKpi(kpi.new_pr, data.banding, (k) => k.new_pr)} />
              <Kartu judul="New PO" nilai={angka.format(kpi.new_po)} info="PO yang dibuat dalam periode; PR yang di-PO dua kali dihitung dua" banding={bandingKpi(kpi.new_po, data.banding, (k) => k.new_po)} />
              <Kartu judul="Outstanding Akhir" nilai={angka.format(kpi.outstanding_akhir)} info="baris PR yang masih outstanding di akhir periode" banding={bandingKpi(kpi.outstanding_akhir, data.banding, (k) => k.outstanding_akhir, { naikBaik: false })} />
              <Kartu judul="Completion Rate" nilai={persen(kpi.completion_rate)} info="PR yang dibuat dalam periode dan sudah selesai" />
              <Kartu
                judul="PO Parsial"
                nilai={persenKecil(kpi.po_partial.persen)}
                banding={bandingKpi(kpi.po_partial.persen, data.banding, (k) => k.po_partial.persen, { jenis: 'poin', naikBaik: false })}
                catatan={`${angka.format(kpi.po_partial.jumlah)} dari ${angka.format(kpi.po_partial.dari)} PO`}
                info="New PO dari PR yang di-PO dengan lebih dari satu nomor PO"
              />
              <Kartu judul="Rata-rata Aging" nilai={`${angka.format(Math.round(kpi.aging_rata_rata))} hari`} info="umur PR yang belum selesai" />
              <Kartu judul="Aging Terlama" nilai={`${angka.format(kpi.aging_maks)} hari`} info="umur PR tertua yang belum selesai" />
              <KartuKecepatan kecepatan={data.kecepatan} satuan="PR" />
            </GridKartu>

            {/* Urutan padat: ringkasan mingguan dan kategori outstanding, lalu dua donat dengan PO per buyer, lalu dua grafik perusahaan */}
            <KisiGrafik>
              <Petak padat="lg:order-1 lg:col-span-8">
                <KartuGrafik judul="Ringkasan Mingguan" petunjuk="Klik bar atau tanggal untuk fokus ke satu minggu.">
                  <WeeklyChart data={data.mingguan} minggu={filter.minggu} onPilihMinggu={pilihMinggu} />
                </KartuGrafik>
              </Petak>

              <Petak padat="lg:order-2 lg:col-span-4">
                <KartuGrafik
                  judul="Kategori Outstanding"
                  petunjuk="Kategori dengan outstanding terbanyak pada periode yang dipilih. Klik satu kategori untuk memfilter semua angka."
                >
                  <KategoriOutstandingChart daftar={data.kategori_outstanding} terpilih={filter.kategori} onPilih={pilihKategori} />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-5" padat="lg:order-3 lg:col-span-3">
                <KartuGrafik judul="Kategori PR" petunjuk="Lima kategori terbesar, sisanya digabung. Klik irisan atau daftar untuk memfilter.">
                  <DonatKategori daftar={data.kategori_new_pr} terpilih={filter.kategori} onPilih={pilihKategori} satuan="baris PR" />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-5" padat="lg:order-4 lg:col-span-3">
                <KartuGrafik judul="Kategori PO" petunjuk="Lima kategori terbesar, sisanya digabung. Klik irisan atau daftar untuk memfilter.">
                  <DonatKategori daftar={data.kategori_new_po} terpilih={filter.kategori} onPilih={pilihKategori} satuan="baris PO" />
                </KartuGrafik>
              </Petak>

              <Petak panjang="md:col-span-5" padat="lg:order-6 lg:col-span-6">
                <KartuGrafik judul="PR per Perusahaan" petunjuk="Klik nama perusahaan untuk memilih. Klik tanggal untuk memilih minggu.">
                  <GarisSeri
                    mingguan={data.mingguan}
                    seri={data.new_pr_per_perusahaan}
                    warnaSeri={warnaPerusahaan}
                    terpilihSeri={filter.perusahaan}
                    minggu={filter.minggu}
                    onPilihSeri={pilihPerusahaan}
                    onPilihMinggu={pilihMinggu}
                  />
                </KartuGrafik>
              </Petak>
              <Petak panjang="md:col-span-5" padat="lg:order-7 lg:col-span-6">
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

              <Petak padat="lg:order-5 lg:col-span-6">
                <KartuGrafik judul="PO per Buyer" petunjuk="Klik nama buyer untuk memilih. Klik tanggal untuk memilih minggu.">
                  <GarisSeri
                    mingguan={data.mingguan}
                    seri={data.new_po_per_buyer}
                    warnaSeri={warnaBuyer}
                    terpilihSeri={filter.buyer}
                    minggu={filter.minggu}
                    onPilihSeri={pilihBuyer}
                    onPilihMinggu={pilihMinggu}
                  />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId="pr_po" dataId={dataId} filter={filter} jumlah={{ outstanding: kpi.outstanding_akhir, po: kpi.new_po }} tab={TAB} onDataHilang={onDataHilang} />
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
          opsi={[...(data?.pilihan.buyer ?? []), '(kosong)']}
          terpilih={filter.buyer}
          onUbah={(v) => ubah({ buyer: v })}
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
