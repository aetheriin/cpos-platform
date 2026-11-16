import { useMemo, useState } from 'react'
import BatangTonase from '../../grafik/BatangTonase'
import SebaranWaktu from '../../grafik/SebaranWaktu'
import { angka, bandingKpi, rentangTgl, tambahDariEvent, ubahPilihan } from '../../lib/data'
import { chipDaftar, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import { MemuatLaporan } from '../../komponen/Keadaan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import PilihPeriode from './PilihPeriode'
import { batasData, judulPeriode, rentangData, tglPanjang } from './periode'

const LAPORAN = 'tiket_penjualan'
const FILTER_AWAL = {}
const KOSONG = []
const WARNA = '#0369a1'
const ton = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
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

// Keadaan kosong seluruh halaman: menyebut sebabnya, sama dengan laporan lain (tanpa tombol).
const KosongBesar = ({ teks }) => <p className="py-10 text-center text-sm text-slate-600">{teks}</p>

export default function DashboardTiketPenjualan({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, panel, setPanel, togglePanel } = useDashboard(LAPORAN, dataId, FILTER_AWAL, onDataHilang)
  // Periode tampilan. Sebelum data pertama datang: bulan dari tanggal data terakhir (bawaan server).
  const [periode, setPeriode] = useState({ mode: 'bulan', acuan: null })
  const batas = data ? batasData(data.dataset) : null
  const acuan = periode.acuan ?? data?.periode.akhir ?? null

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
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglPanjang(nilai, { hari: true }) : kunci === 'jam' ? `pukul ${nilai}.00â€“${nilai}.59` : nilai)
  const aktif = chipDaftar(daftarFilter, terpilih, tampil)
  // Hapus filter melepas semua pilihan; periode tetap
  const reset = () => setFilter((f) => ({ dari: f.dari, sampai: f.sampai }))

  const kpi = data?.kpi
  const sebaran = data?.sebaran
  const harian = periode.mode === 'hari'
  const adaPengangkut = (data?.per_pengangkut.data.length ?? 0) > 0
  // Pengangkut dan Pembeli hanya berdampingan kalau jumlah barisnya mirip; kalau jauh beda, masing-masing selebar penuh supaya tidak ada
  // kartu yang setengah kosong di samping kartu yang panjang
  const nPembeli = data?.per_pembeli.data.length ?? 0
  const berdampingan = adaPengangkut && Math.abs(data.per_pengangkut.data.length - nPembeli) <= 3
  const lebarPeringkat = berdampingan ? 'lg:col-span-6' : 'lg:col-span-12'
  const namaPeriode = acuan ? judulPeriode(periode.mode, acuan) : ''

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Tiket Penjualan" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {data && acuan && <PilihPeriode mode={periode.mode} acuan={acuan} batas={batas} onUbah={ubahPeriode} sampaiJam={data.banding?.sampai_jam} />}

        {galat && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Halaman belum bisa ditampilkan: {galat.message}</div>}
        {!data && !galat && <MemuatLaporan teks="Memuat tiket penjualan..." />}

        {data && kpi.rit === 0 && (
          <section className="rounded-xl border border-slate-200 bg-white">
            <KosongBesar teks={aktif.length > 0 ? `Tidak ada tiket penjualan ${namaPeriode} yang cocok dengan filter yang dipilih.` : `Tidak ada tiket penjualan ${namaPeriode}.`} />
          </section>
        )}

        {data && kpi.rit > 0 && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu>
              <Kartu judul="Total Berat Bersih" nilai={`${ton.format(kpi.netto / 1000)} ton`} info="netto semua tiket penjualan dalam periode"
                banding={bandingKpi(kpi.netto, data.banding, (k) => k.netto, { naikBaik: true })} />
              <Kartu judul="Jumlah Pengiriman" nilai={`${angka.format(kpi.rit)} truk`} info="satu truk keluar dengan satu tiket timbang"
                banding={bandingKpi(kpi.rit, data.banding, (k) => k.rit, { naikBaik: true })} />
              <Kartu judul="Rata-rata Muatan" nilai={kpi.per_rit == null ? 'â€“' : `${ton.format(kpi.per_rit / 1000)} ton`} info="berat bersih dibagi jumlah pengiriman"
                banding={bandingKpi(kpi.per_rit, data.banding, (k) => k.per_rit)} />
              <Kartu judul="Pengangkut" nilai={angka.format(kpi.pengangkut)} info="nama pengangkutan berbeda di tiket"
                banding={bandingKpi(kpi.pengangkut, data.banding, (k) => k.pengangkut)} />
              <Kartu judul="Pembeli" nilai={angka.format(kpi.pembeli)} info="nama pembeli berbeda di tiket"
                banding={bandingKpi(kpi.pembeli, data.banding, (k) => k.pembeli)} />
            </GridKartu>

            {/* Urutan: grafik waktu (lebar penuh, seperti grafik utama laporan lain), lalu peringkat berpasangan, lalu produk lebar penuh.
                Harian tanpa grafik waktu: truk sehari terlalu sedikit untuk membentuk pola. */}
            <KisiGrafik>
              {!harian && (
                <Petak>
                  <KartuGrafik judul="Berat Keluar per Hari" perbesar petunjuk="Ton per tanggal timbang. Klik batang untuk memfilter ke tanggal itu.">
                    <SebaranWaktu tinggi="h-64" satuan={sebaran.satuan} data={sebaran.data} warna={WARNA}
                      terpilih={terpilih('tanggal')} onPilih={pilih.tanggal} kosong={<KosongKecil teks="Tidak ada tiket." />} />
                  </KartuGrafik>
                </Petak>
              )}
              {/* Tanpa nama pengangkutan sama sekali: kartunya tidak ditampilkan dan Pembeli memakai lebar penuh */}
              {adaPengangkut && (
                <Petak padat={lebarPeringkat}>
                  <KartuGrafik judul="Pengangkut Terbesar" petunjuk="Sepuluh pengangkut dengan berat terbanyak. Klik batang untuk memfilter.">
                    <BatangTonase data={data.per_pengangkut.data} lainnya={data.per_pengangkut.lainnya} satuanLain="pengangkut" warna={WARNA}
                      terpilih={terpilih('pengangkut')} onPilih={pilih.pengangkut} kosong={null} />
                  </KartuGrafik>
                </Petak>
              )}
              <Petak padat={lebarPeringkat}>
                <KartuGrafik judul="Pembeli Terbesar" petunjuk="Sepuluh pembeli dengan berat terbanyak. Klik batang untuk memfilter.">
                  <BatangTonase data={data.per_pembeli.data} lainnya={data.per_pembeli.lainnya} satuanLain="pembeli" persen warna={WARNA}
                    terpilih={terpilih('pembeli')} onPilih={pilih.pembeli} kosong={<KosongKecil teks="Belum ada nama pembeli di tiket." />} />
                </KartuGrafik>
              </Petak>
              <Petak>
                <KartuGrafik judul="Produk" petunjuk="Berat per produk. Klik batang untuk memfilter.">
                  <BatangTonase data={data.per_produk.data} lainnya={data.per_produk.lainnya} satuanLain="produk" persen warna={WARNA}
                    terpilih={terpilih('produk')} onPilih={pilih.produk} kosong={<KosongKecil teks="Tidak ada produk." />} />
                </KartuGrafik>
              </Petak>
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
