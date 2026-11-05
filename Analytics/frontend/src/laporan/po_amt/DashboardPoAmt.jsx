import { useState } from 'react'
import { angka, tambahDariEvent, tglLengkap, ubahPilihan } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import FilterTanggal from '../../komponen/FilterTanggal'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import Select from '../../komponen/Select'
import TabelDetail from '../../komponen/TabelDetail'
import { formatPersen, PoNilai, PoNilaiPersen, rupiahPendek, BandingTahun, SeriBulan } from '../../grafik/PoAmt'

const FILTER_AWAL = { dari: null, sampai: null, minggu: null, perusahaan: [], tahun: [], bulan: [], mata_uang: [], kategori: [] }
const RENTANG_KOSONG = { dari: null, sampai: null, minggu: null }
const JENIS = [
  { kunci: 'perusahaan', nama: 'Perusahaan' },
  { kunci: 'tahun', nama: 'Tahun' },
  { kunci: 'bulan', nama: 'Bulan' },
  { kunci: 'mata_uang', nama: 'Mata Uang' },
  { kunci: 'kategori', nama: 'Kategori' },
]
const TAB = [
  { kunci: 'po', nama: 'Semua PO', ket: (h) => `PO tidak void yang dibuat ${tglLengkap(h.periode.mulai)} sampai ${tglLengkap(h.periode.akhir)}, nilai terbesar di atas.` },
]
const miliar = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const rp = (v) => `Rp ${miliar.format(v / 1e9)} M`
const UKURAN = [['po', 'Jumlah PO'], ['nilai', 'Nilai']]

function PilihUkuran({ nilai, onUbah }) {
  return (
    <div role="radiogroup" aria-label="Ukuran perbandingan" className="inline-flex gap-0.5 rounded-md bg-slate-100 p-0.5">
      {UKURAN.map(([k, nama]) => (
        <button key={k} type="button" role="radio" aria-checked={nilai === k} onClick={() => onUbah(k)}
          className={'rounded px-2 py-0.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
            (nilai === k ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-800')}>
          {nama}
        </button>
      ))}
    </div>
  )
}

export default function DashboardPoAmt({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('po_amt', dataId, FILTER_AWAL, onDataHilang, RENTANG_KOSONG)
  const pilihKategori = (nilai, e) => ubah({ kategori: ubahPilihan(filter.kategori, nilai, tambahDariEvent(e)) })
  const aktif = [...chipRentang(filter), ...chipDaftar(JENIS, terpilih)]
  const kpi = data?.kpi
  const kecil = data?.kategori[0]
  const [ukuran, setUkuran] = useState('po')
  const formatUkuran = ukuran === 'nilai' ? rupiahPendek : angka.format
  const [ukuranSeri, setUkuranSeri] = useState('po')
  const [kategoriSeri, setKategoriSeri] = useState('0')
  const formatSeri = ukuranSeri === 'nilai' ? rupiahPendek : angka.format

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="PO Spend Analysis" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />
        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <GridKartu kolom={3}>
              <Kartu judul="Total Nilai PO" nilai={rp(kpi.nilai)} />
              <Kartu judul="Jumlah PO" nilai={angka.format(kpi.po)} />
              <Kartu judul="PO di Bawah 1 Juta" nilai={angka.format(kecil.po)}
                catatan={`${formatPersen(kecil.pct_po)} dari total PO, ${formatPersen(kecil.pct_nilai)} dari total nilai`} />
            </GridKartu>

            <KisiGrafik>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Persentase Jumlah dan Nilai PO per Kategori" perbesar>
                  <PoNilaiPersen data={data.kategori} onPilih={pilihKategori} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Jumlah dan Nilai PO per Kategori" perbesar>
                  <PoNilai data={data.kategori} onPilih={pilihKategori} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul={`${ukuranSeri === 'nilai' ? 'Nilai' : 'Jumlah'} PO per Bulan`} perbesar
                  aksi={<>
                    <Select otomatis kecil aria-label="Kategori" value={kategoriSeri} onChange={(e) => setKategoriSeri(e.target.value)}>
                      {data.nama_kategori.map((k, i) => <option key={k} value={i}>{k}</option>)}
                      <option value="semua">Semua kategori</option>
                    </Select>
                    <PilihUkuran nilai={ukuranSeri} onUbah={setUkuranSeri} />
                  </>}>
                  <SeriBulan data={data.seri_bulan} kunci={kategoriSeri === 'semua' ? ukuranSeri : `${ukuranSeri}_${kategoriSeri}`}
                    nama={data.nama_kategori[kategoriSeri] ?? 'Semua kategori'} format={formatSeri} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul={`${ukuran === 'nilai' ? 'Nilai' : 'Jumlah'} PO Antar Tahun`} perbesar aksi={<PilihUkuran nilai={ukuran} onUbah={setUkuran} />}>
                  <BandingTahun data={data.banding_tahun} ukuran={ukuran} format={formatUkuran} />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId="po_amt" dataId={dataId} filter={filter} jumlah={data.jumlah} tab={TAB} onDataHilang={onDataHilang} />
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
