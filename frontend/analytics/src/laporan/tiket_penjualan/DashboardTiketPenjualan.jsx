import { useMemo, useState } from 'react'
import BatangTonase from '../../grafik/BatangTonase'
import SebaranWaktu from '../../grafik/SebaranWaktu'
import { rentangTgl, tambahDariEvent, ubahPilihan } from '../../lib/data'
import { chipDaftar, useDashboard } from '../../lib/filter'
import { useTataLetak } from '../../lib/tampilan'
import FilterMulti from '../../komponen/FilterMulti'
import { KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import { MemuatLaporan } from '../../komponen/Keadaan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import PilihPeriode from './PilihPeriode'
import Ringkasan from './Ringkasan'
import { batasData, geser, judulPeriode, rentangData, tglPanjang } from './periode'

const LAPORAN = 'tiket_penjualan'
const FILTER_AWAL = {}
const KOSONG = []
const WARNA = '#0369a1'
const TAB = [
  {
    kunci: 'tiket',
    nama: 'Per tiket',
    ket: (h) => `Satu baris untuk satu tiket timbang, ${rentangTgl(h.periode.mulai, h.periode.akhir)}.`,
  },
  { kunci: 'pengangkut', nama: 'Per pengangkut', ket: (h) => `Satu baris untuk satu pengangkut, berisi jumlah pengiriman dan total beratnya, ${rentangTgl(h.periode.mulai, h.periode.akhir)}.` },
]

// Grafik tanpa data: satu baris pendek, tidak memenuhi kartu.
const KosongKecil = ({ teks }) => <p className="py-3 text-sm text-slate-500">{teks}</p>

// Keadaan kosong: menyebut sebabnya dan memberi jalan keluar.
function Kosong({ teks, adaFilter, onLepas, onSebelumnya }) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <p className="max-w-sm text-sm text-slate-700">{teks}</p>
      <div className="flex flex-wrap justify-center gap-2">
        {adaFilter && (
          <button type="button" onClick={onLepas} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
            Hapus semua filter
          </button>
        )}
        {onSebelumnya && (
          <button type="button" onClick={onSebelumnya} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
            Lihat periode sebelumnya
          </button>
        )}
      </div>
    </div>
  )
}

export default function DashboardTiketPenjualan({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, panel, setPanel, togglePanel } = useDashboard(LAPORAN, dataId, FILTER_AWAL, onDataHilang)
  // Periode tampilan. Sebelum data pertama datang: bulan dari tanggal data terakhir (bawaan server).
  const [periode, setPeriode] = useState({ mode: 'bulan', acuan: null })
  const batas = data ? batasData(data.dataset) : null
  const acuan = periode.acuan ?? data?.periode.akhir ?? null
  const padat = useTataLetak(LAPORAN)[0] === 'padat'

  // Ganti periode: rentang dikirim ke server, pilihan tanggal dan jam dari grafik dilepas karena menunjuk periode lama
  const ubahPeriode = (mode, a) => {
    const r = rentangData(mode, a, batas)
    if (!r) return
    setPeriode({ mode, acuan: a })
    setFilter((f) => ({ ...f, dari: r.dari, sampai: r.sampai, tanggal: [], jam: [] }))
  }

  const pilih = useMemo(() => {
    const dari = (jenis) => (nilai, e) => setFilter((f) => ({ ...f, [jenis]: ubahPilihan(f[jenis] ?? [], nilai, tambahDariEvent(e)) }))
    return { produk: dari('produk'), pengangkut: dari('pengangkut'), pembeli: dari('pembeli'), tanggal: dari('tanggal'), jam: dari('jam') }
  }, [setFilter])

  const daftarFilter = data?.filter ?? KOSONG
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglPanjang(nilai, { hari: true }) : kunci === 'jam' ? `pukul ${nilai}.00–${nilai}.59` : nilai)
  const aktif = chipDaftar(daftarFilter, terpilih, tampil)
  // Hapus filter melepas semua pilihan; periode tetap
  const reset = () => setFilter((f) => ({ dari: f.dari, sampai: f.sampai }))

  const kpi = data?.kpi
  const sebaran = data?.sebaran
  const harian = periode.mode === 'hari'
  const namaPeriode = acuan ? judulPeriode(periode.mode, acuan) : ''
  const sebelumnya = acuan && batas && rentangData(periode.mode, geser(periode.mode, acuan, -1), batas) ? () => ubahPeriode(periode.mode, geser(periode.mode, acuan, -1)) : null
  const kosongBesar = (teks) => <Kosong teks={teks} adaFilter={aktif.length > 0} onLepas={reset} onSebelumnya={aktif.length > 0 ? null : sebelumnya} />

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        {/* data tidak diteruskan: periode dan pembandingnya sudah ditulis di bar periode, jadi tidak ditulis dua kali */}
        <KepalaLaporan judul="Tiket Penjualan" data={null} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {data && acuan && <PilihPeriode mode={periode.mode} acuan={acuan} batas={batas} onUbah={ubahPeriode} pembanding={data.banding} />}

        {galat && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Halaman belum bisa ditampilkan: {galat.message}</div>}
        {!data && !galat && <MemuatLaporan teks="Memuat tiket penjualan..." />}

        {data && kpi.rit === 0 && (
          <section className="rounded-xl border border-slate-200 bg-white">
            {kosongBesar(aktif.length > 0 ? `Tidak ada tiket penjualan ${namaPeriode} yang cocok dengan filter yang dipilih.` : `Tidak ada tiket penjualan ${namaPeriode}.`)}
          </section>
        )}

        {data && kpi.rit > 0 && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <Ringkasan kpi={kpi} banding={data.banding} />

            <KisiGrafik>
              {/* Tanpa nama pengangkutan sama sekali: kartu tidak ditampilkan, ringkasan sudah menulis 0 pengangkut */}
              {data.per_pengangkut.data.length > 0 && (
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Pengangkut terbesar">
                  <BatangTonase data={data.per_pengangkut.data} lainnya={data.per_pengangkut.lainnya} satuanLain="pengangkut" warna={WARNA}
                    terpilih={terpilih('pengangkut')} onPilih={pilih.pengangkut} kosong={<KosongKecil teks="Belum ada nama pengangkutan di tiket." />} />
                </KartuGrafik>
              </Petak>
              )}
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Pembeli terbesar">
                  <BatangTonase data={data.per_pembeli.data} lainnya={data.per_pembeli.lainnya} satuanLain="pembeli" persen warna={WARNA}
                    terpilih={terpilih('pembeli')} onPilih={pilih.pembeli} kosong={<KosongKecil teks="Belum ada nama pembeli di tiket." />} />
                </KartuGrafik>
              </Petak>
              <Petak padat={harian ? 'lg:col-span-6' : 'lg:col-span-5'}>
                <KartuGrafik judul="Produk">
                  <BatangTonase data={data.per_produk.data} lainnya={data.per_produk.lainnya} satuanLain="produk" persen warna={WARNA}
                    terpilih={terpilih('produk')} onPilih={pilih.produk} kosong={<KosongKecil teks="Tidak ada produk." />} />
                </KartuGrafik>
              </Petak>
              {/* Harian tidak memakai grafik per jam: truk sehari terlalu sedikit untuk membentuk pola */}
              {!harian && (
                <Petak padat="lg:col-span-7">
                  <KartuGrafik judul="Berat keluar per hari (ton)">
                    <SebaranWaktu tinggi={padat ? 'h-52' : 'h-72'} satuan={sebaran.satuan} data={sebaran.data} warna={WARNA}
                      terpilih={terpilih('tanggal')} onPilih={pilih.tanggal} kosong={<KosongKecil teks="Tidak ada tiket." />} />
                  </KartuGrafik>
                </Petak>
              )}
            </KisiGrafik>

            <TabelDetail judul="Daftar tiket" laporanId={LAPORAN} dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB} onDataHilang={onDataHilang} />
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
