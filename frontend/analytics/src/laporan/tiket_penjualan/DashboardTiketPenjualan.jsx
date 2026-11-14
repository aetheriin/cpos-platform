import { useMemo, useState } from 'react'
import BatangTonase from '../../grafik/BatangTonase'
import SebaranWaktu from '../../grafik/SebaranWaktu'
import { ton } from '../../grafik/tbs'
import { angka, bandingKpi, rentangTgl, tambahDariEvent, ubahPilihan } from '../../lib/data'
import { chipDaftar, useDashboard } from '../../lib/filter'
import { useTataLetak } from '../../lib/tampilan'
import FilterMulti from '../../komponen/FilterMulti'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import { MemuatLaporan } from '../../komponen/Keadaan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import PilihPeriode from './PilihPeriode'
import { batasData, rentangData, tglPanjang } from './periode'

const LAPORAN = 'tiket_penjualan'
const FILTER_AWAL = {}
const KOSONG = []
const TAB = [
  { kunci: 'tiket', nama: 'Per tiket', ket: (h) => `Tiket ${rentangTgl(h.periode.mulai, h.periode.akhir)}. Kolom sama dengan ekspor tiket timbangan Ascend, ditambah Split dan Perusahaan.` },
  { kunci: 'pengangkut', nama: 'Per pengangkut', ket: () => 'Total per nama pengangkutan pada periode yang sama.' },
]
const kg = (x) => (x == null ? '–' : `${angka.format(Math.round(x))} kg`)

export default function DashboardTiketPenjualan({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, panel, setPanel, togglePanel } = useDashboard(LAPORAN, dataId, FILTER_AWAL, onDataHilang)
  // Periode tampilan. Sebelum data pertama datang: bulan dari tanggal data terakhir (bawaan server).
  const [periode, setPeriode] = useState({ mode: 'bulan', acuan: null })
  const batas = data ? batasData(data.dataset) : null
  const acuan = periode.acuan ?? data?.periode.akhir ?? null

  // Ganti periode: rentang dikirim ke server, filter tanggal dan jam dari grafik dilepas karena menunjuk periode lama
  const ubahPeriode = (mode, a) => {
    const r = rentangData(mode, a, batas)
    if (!r) return
    setPeriode({ mode, acuan: a })
    setFilter((f) => ({ ...f, dari: r.dari, sampai: r.sampai, tanggal: [], jam: [] }))
  }

  const pilih = useMemo(() => {
    const dari = (jenis) => (nilai, e) => setFilter((f) => ({ ...f, [jenis]: ubahPilihan(f[jenis] ?? [], nilai, tambahDariEvent(e)) }))
    return { produk: dari('produk'), pengangkut: dari('pengangkut'), tanggal: dari('tanggal'), jam: dari('jam') }
  }, [setFilter])

  const daftarFilter = data?.filter ?? KOSONG
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglPanjang(nilai, { hari: true }) : kunci === 'jam' ? `${nilai}.00–${nilai}.59` : nilai)
  const aktif = chipDaftar(daftarFilter, terpilih, tampil)
  // Reset melepas semua pilihan, periode tetap
  const reset = () => setFilter((f) => ({ dari: f.dari, sampai: f.sampai }))

  const kpi = data?.kpi
  const b = data?.banding
  const sebaran = data?.sebaran
  const harian = sebaran?.satuan === 'jam'
  const padat = useTataLetak(LAPORAN)[0] === 'padat'

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Tiket Penjualan" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {data && acuan && <PilihPeriode mode={periode.mode} acuan={acuan} batas={batas} onUbah={ubahPeriode} sampaiJam={data.banding?.sampai_jam ?? null} />}

        {galat && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Laporan tidak bisa ditampilkan: {galat.message}</div>}
        {!data && !galat && <MemuatLaporan teks="Memuat tiket penjualan..." />}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={5}>
              <Kartu judul="Total Berat Bersih" nilai={ton(kpi.netto)} info="berat bersih (netto) semua produk yang keluar pada periode ini" banding={bandingKpi(kpi.netto, b, (k) => k.netto)} />
              <Kartu judul="Jumlah Pengiriman" nilai={angka.format(kpi.rit)} info="satu truk keluar dengan satu tiket timbang dihitung satu pengiriman" banding={bandingKpi(kpi.rit, b, (k) => k.rit)} />
              <Kartu judul="Rata-rata Muatan per Truk" nilai={kg(kpi.per_rit)} info="total berat bersih dibagi jumlah pengiriman" banding={bandingKpi(kpi.per_rit, b, (k) => k.per_rit)} />
              <Kartu judul="Jumlah Pengangkut" nilai={angka.format(kpi.pengangkut)} info="perusahaan pengangkutan yang mengirim pada periode ini" banding={bandingKpi(kpi.pengangkut, b, (k) => k.pengangkut)} />
              <Kartu judul="Jumlah Pembeli" nilai={angka.format(kpi.pembeli)} info="pembeli yang menerima kiriman pada periode ini" banding={bandingKpi(kpi.pembeli, b, (k) => k.pembeli)} />
            </GridKartu>

            <KisiGrafik>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Peringkat Produk" petunjuk="Urut dari yang paling berat. Persen terhadap total berat bersih periode ini.">
                  <BatangTonase data={data.per_produk.data} lainnya={data.per_produk.lainnya} satuanLain="produk" persen terpilih={terpilih('produk')} onPilih={pilih.produk} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Peringkat Pengangkut" petunjuk="Menurut nama pengangkutan di tiket timbangan.">
                  <BatangTonase data={data.per_pengangkut.data} lainnya={data.per_pengangkut.lainnya} satuanLain="pengangkut" warna="#0f766e"
                    terpilih={terpilih('pengangkut')} onPilih={pilih.pengangkut} kosong="Tidak ada nama pengangkutan untuk filter ini" />
                </KartuGrafik>
              </Petak>
              <Petak>
                <KartuGrafik
                  judul={harian ? 'Berat Keluar per Jam (ton)' : 'Berat Keluar per Hari (ton)'}
                  petunjuk={harian ? 'Menurut jam truk keluar dari timbangan. Klik batang untuk memfilter jam itu.' : 'Klik batang untuk memfilter tanggal itu.'}
                >
                  <SebaranWaktu tinggi={padat ? 'h-52' : 'h-72'} satuan={sebaran.satuan} data={sebaran.data} terpilih={terpilih(harian ? 'jam' : 'tanggal')} onPilih={harian ? pilih.jam : pilih.tanggal} />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId={LAPORAN} dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB} onDataHilang={onDataHilang} />
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {daftarFilter
          .filter((f) => f.panel)
          .map(({ kunci, nama }) => (
            <FilterMulti key={kunci} sebaris label={nama} opsi={data?.pilihan[kunci] ?? KOSONG} terpilih={terpilih(kunci)} onUbah={(v) => ubah({ [kunci]: v })} />
          ))}
      </PanelFilter>
    </div>
  )
}
