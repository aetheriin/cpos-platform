import { useMemo, useState } from 'react'
import { unduhDetail } from '../../api'
import { angka, rentangTgl, tambahDariEvent, tglLengkap, ubahPilihan } from '../../lib/data'
import { chipDaftar, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import { IkonPanahKanan, IkonUnduh } from '../../komponen/Ikon'
import PilihRentang from '../../komponen/PilihRentang'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import { uangPenuh, WARNA_KELUAR, WARNA_MASUK } from '../../grafik/kas'
import { JenisDokumen, KreditToDate, PilihPeriode, SaldoBerjalan } from '../../grafik/KasTren'

const FILTER_AWAL = {}   // tabel dikonversi ke rupiah; tampilan=asli memakai mata uang rekening
const KOSONG = []
const TAB = [
  { kunci: 'bank', nama: 'Rekap saldo bank', ket: (h) => `${tglLengkap(h.periode.mulai)} – ${tglLengkap(h.periode.akhir)}. Saldo akhir tiap hari per perusahaan dan rekening.` },
  { kunci: 'harian', nama: 'Rekap harian', ket: (h) => `${tglLengkap(h.periode.mulai)} – ${tglLengkap(h.periode.akhir)}. Debit/credit to date dihitung sejak awal data.` },
  { kunci: 'mutasi', nama: 'Mutasi', ket: (h) => `${tglLengkap(h.periode.mulai)} – ${tglLengkap(h.periode.akhir)}. Saldo per transaksi, urut tanggal.` },
  { kunci: 'giro', nama: 'Jasa giro', ket: (h) => `${tglLengkap(h.periode.mulai)} – ${tglLengkap(h.periode.akhir)}.` },
]
const persenGiro = (x) => (x == null ? '–' : `${(x * 100).toLocaleString('id-ID', { maximumFractionDigits: 3 })}%`)
const SUMBER_KURS = { CPOS: 'kurs input CPOS', EXC_RATE: 'EXC_RATE', internet: 'kurs ECB' }
const kursRingkas = (v) => v.map((x) => `${x.mata_uang} ${angka.format(x.kurs)} (${x.sumber.filter(Boolean).map((s) => SUMBER_KURS[s] ?? s).join(', ')}; ${x.rekening.length} rekening)`).join('; ')

// Lawan transaksi terbesar: pengalih Keluar / Masuk, satu daftar batang. Klik nama untuk memfilter seluruh laporan.
function LawanTransaksi({ mitra, satuan, terpilih, onPilih }) {
  const [arah, setArah] = useState('keluar')
  const data = mitra[arah] ?? KOSONG
  const maks = Math.max(...data.map((d) => d.nilai), 1)
  const warna = arah === 'keluar' ? WARNA_KELUAR : WARNA_MASUK
  return (
    <div>
      <div role="radiogroup" aria-label="Sisi" className="mb-3 inline-flex gap-0.5 rounded-lg bg-slate-100 p-1">
        {[['keluar', 'Credit'], ['masuk', 'Debit']].map(([k, nama]) => (
          <button key={k} type="button" role="radio" aria-checked={arah === k} onClick={() => setArah(k)}
            className={'rounded-md px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
              (arah === k ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-800')}>
            {nama}
          </button>
        ))}
      </div>
      {data.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">Tidak ada data</p>
      ) : (
        <ul className="space-y-1.5">
          {data.map((d) => {
            const pilih = terpilih.includes(d.nama)
            return (
              <li key={d.nama}>
                <button type="button" onClick={(e) => onPilih(d.nama, e)} aria-pressed={pilih} title={`${d.nama}: ${uangPenuh(d.nilai, satuan)}, ${angka.format(d.jumlah)} transaksi`}
                  className="w-full rounded-md px-1 py-1 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  style={{ opacity: terpilih.length && !pilih ? 0.45 : 1 }}>
                  <span className="flex items-baseline justify-between gap-2 text-xs">
                    <span className={'min-w-0 truncate ' + (pilih ? 'font-semibold text-slate-900' : 'text-slate-700')}>{d.nama}</span>
                    <span className="shrink-0 tabular-nums text-slate-500">{angka.format(d.jumlah)}×</span>
                  </span>
                  <span className="mt-0.5 flex items-center gap-2">
                    <span className="h-3 min-w-1 rounded-sm" style={{ width: `${(d.nilai / maks) * 78}%`, background: warna }} />
                    <span className="shrink-0 text-xs tabular-nums text-slate-700">{uangPenuh(d.nilai, satuan)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-2 text-xs text-slate-500">Tidak termasuk transfer antar rekening.</p>
    </div>
  )
}

// Unduh rekap jasa giro sesuai filter dan bulan yang tampil
function EksporGiro({ dataId, filter, onDataHilang }) {
  const [sibuk, setSibuk] = useState(false)
  const [galat, setGalat] = useState('')
  const unduh = async () => {
    setSibuk(true)
    setGalat('')
    try {
      await unduhDetail('cash_flow', dataId, filter, { jenis: 'rekap_giro' })
    } catch (e) {
      if (e.status === 404) onDataHilang?.()
      else setGalat(e.message)
    } finally {
      setSibuk(false)
    }
  }
  return (
    <span className="inline-flex items-center gap-2">
      {galat && <span role="alert" className="text-xs text-red-700">Export gagal: {galat}</span>}
      <button type="button" onClick={unduh} disabled={sibuk} aria-busy={sibuk}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-40">
        <IkonUnduh className="h-3.5 w-3.5" />
        {sibuk ? 'Menyiapkan...' : 'Export Excel'}
      </button>
    </span>
  )
}

// Rekap jasa giro per perusahaan. Klik rekening untuk memfilternya.
function JasaGiro({ giro, asli, satuan, terpilih, onPilih }) {
  if (giro.perusahaan.length === 0) return <p className="py-8 text-center text-sm text-slate-500">Tidak ada data</p>
  const angkaSel = 'py-1.5 pl-4 text-right tabular-nums whitespace-nowrap'
  const campur = (v) => (v == null ? '–' : angka.format(v))   // total mata uang asli: USD dan IDR tercampur, jadi tanpa simbol
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-xs">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="pb-1 font-medium">Perusahaan / rekening</th>
            <th className="pb-1 pl-4 text-right font-medium">Giro</th>
            <th className="pb-1 pl-4 text-right font-medium">AVG balance</th>
            <th className="pb-1 pl-4 text-right font-medium" title="Giro ÷ AVG balance × 12">% Giro per tahun</th>
          </tr>
        </thead>
        {giro.perusahaan.map((b) => (
          <tbody key={b.nama}>
            <tr className="border-t border-slate-300 font-semibold text-slate-900">
              <td className="py-1.5">{b.nama}</td>
              <td className={angkaSel}>{asli ? campur(b.nilai_asli) : uangPenuh(b.nilai, satuan)}</td>
              <td className={angkaSel}>{asli ? campur(b.rata_asli) : uangPenuh(b.rata_saldo, satuan)}</td>
              <td className={angkaSel}>{persenGiro(asli ? b.imbal_asli : b.imbal)}</td>
            </tr>
            {b.rekening.map((r) => {
              const pilih = terpilih.includes(r.akun)
              return (
                <tr key={r.akun} onClick={(e) => onPilih(r.akun, e)} aria-selected={pilih}
                  className={'cursor-pointer border-t border-slate-100 hover:bg-slate-50 ' + (pilih ? 'bg-sky-50 font-medium text-sky-900' : 'text-slate-700')}>
                  <td className="py-1.5 pl-3">{r.akun}</td>
                  <td className={angkaSel}>{asli ? uangPenuh(r.nilai_asli, r.mata_uang) : uangPenuh(r.nilai, satuan)}</td>
                  <td className={angkaSel}>{asli ? uangPenuh(r.rata_asli, r.mata_uang) : uangPenuh(r.rata_saldo, satuan)}</td>
                  <td className={angkaSel}>{persenGiro(r.imbal)}</td>
                </tr>
              )
            })}
          </tbody>
        ))}
        <tfoot>
          <tr className="border-t-2 border-slate-400 font-semibold text-slate-900">
            <td className="py-1.5">Grand total</td>
            <td className={angkaSel}>{asli ? campur(giro.total_asli) : uangPenuh(giro.total, satuan)}</td>
            <td className={angkaSel}>{asli ? campur(giro.rata_asli) : uangPenuh(giro.rata_saldo, satuan)}</td>
            <td className={angkaSel}>{persenGiro(asli ? giro.imbal_asli : giro.imbal)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

const NAMA_BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
const namaBulan = (b) => `${NAMA_BULAN[Number(b.slice(5, 7)) - 1]} ${b.slice(0, 4)}`
const akhirBulan = (b) => `${b}-${String(new Date(Date.UTC(Number(b.slice(0, 4)), Number(b.slice(5, 7)), 0)).getUTCDate()).padStart(2, '0')}`

const OPSI_BELAKANG = [3, 6, 12]

// Rekening valas di tabel: mata uang aslinya, atau dikonversi ke rupiah. Grafik dan kartu selalu rupiah.
function PilihMataUang({ asli, onUbah }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <PilihRentang label="Mata uang tabel" nilai={asli ? 'asli' : 'idr'} onUbah={(v) => onUbah({ tampilan: v === 'asli' ? ['asli'] : null })}
        opsi={[{ nilai: 'idr', label: 'Convert ke IDR', judul: 'Rekening valas di tabel dikonversi ke rupiah' }, { nilai: 'asli', label: 'Mata uang asli', judul: 'Rekening valas di tabel tampil dalam mata uangnya' }]} />
      {asli && <span className="text-xs text-slate-500">Grafik dan kartu tetap IDR. Total jasa giro menjumlahkan angka yang tampil.</span>}
    </div>
  )
}

// Bulan laporan, di atas kartu. Bulan terbaru = rentang bawaan server (awal bulan sampai hari ini); bulan lain = satu bulan penuh.
function PilihBulan({ bulan, filter, onUbah }) {
  const nilai = !filter.dari ? bulan[0] : bulan.find((b) => filter.dari === `${b}-01` && filter.sampai === akhirBulan(b)) ?? ''
  const pilih = (b) => onUbah(b === bulan[0] ? { dari: null, sampai: null } : { dari: `${b}-01`, sampai: akhirBulan(b) })
  const i = bulan.indexOf(nilai)   // bulan terbaru lebih dulu
  const lama = i >= 0 ? bulan[i + 1] : undefined
  const baru = i > 0 ? bulan[i - 1] : undefined
  const tombol = 'grid h-8 w-8 place-items-center text-slate-600 hover:bg-slate-100 disabled:text-slate-300 disabled:hover:bg-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500'
  return (
    <div className="inline-flex items-stretch divide-x divide-slate-200 rounded-md border border-slate-300 bg-white">
      <button type="button" className={tombol + ' rounded-l-md'} disabled={!lama} onClick={() => pilih(lama)} aria-label="Bulan sebelumnya" title={lama && namaBulan(lama)}>
        <IkonPanahKanan className="h-4 w-4 rotate-180" />
      </button>
      <select value={nilai} onChange={(e) => pilih(e.target.value)} aria-label="Bulan laporan"
        className="h-8 border-0 bg-transparent px-2 text-sm font-medium text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500">
        {nilai === '' && <option value="">Pilih bulan</option>}
        {bulan.map((b) => <option key={b} value={b}>{namaBulan(b)}</option>)}
      </select>
      <button type="button" className={tombol + ' rounded-r-md'} disabled={!baru} onClick={() => pilih(baru)} aria-label="Bulan berikutnya" title={baru && namaBulan(baru)}>
        <IkonPanahKanan className="h-4 w-4" />
      </button>
    </div>
  )
}

export default function DashboardKasBank({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('cash_flow', dataId, FILTER_AWAL, onDataHilang)

  const pilih = useMemo(() => {
    const dari = (jenis) => (nilai, e) => setFilter((f) => ({ ...f, [jenis]: ubahPilihan(f[jenis] ?? [], nilai, tambahDariEvent(e)) }))
    return { mitra: dari('mitra'), rekening: dari('rekening'), dokumen: dari('dokumen') }
  }, [setFilter])

  const daftarFilter = data?.filter ?? KOSONG
  const tampil = (kunci, nilai) => (kunci === 'tanggal' ? tglLengkap(nilai) : nilai)
  const aktif = chipDaftar(daftarFilter, terpilih, tampil)
  const [belakang, setBelakang] = useState(OPSI_BELAKANG[0])
  const asli = terpilih('tampilan').includes('asli')
  const kpi = data?.kpi
  const satuan = data?.satuan ?? 'IDR'
  // Rentang tampilan lebih dari sebulan: grafik deret waktu bisa per bulan (bawaan) atau per hari; sebulan atau kurang: per hari saja
  const bisaBulan = data?.deret.periode === 'bulan'
  const [pilihan, setPilihan] = useState('bulan')
  const periode = bisaBulan ? pilihan : 'hari'
  const pilihPeriode = bisaBulan ? <PilihPeriode nilai={periode} onUbah={setPilihan} /> : null

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Cash Flow" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Laporan tidak bisa dimuat: {galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat mutasi bank...</p>}

        {data && (
          <div className="flex flex-wrap items-center gap-3">
            <PilihBulan bulan={data.bulan} filter={filter} onUbah={ubah} />
            <PilihMataUang asli={asli} onUbah={ubah} />
          </div>
        )}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            {(data.valas.length > 0 || data.tanpa_kurs.length > 0) && (
              <p className="text-xs text-slate-500">
                Dalam rupiah.
                {data.valas.length > 0 && ` Valas dikonversi: ${kursRingkas(data.valas)}.`}
                {data.tanpa_kurs.length > 0 && (
                  <span className="text-amber-700"> Tanpa kurs, tidak dihitung: {data.tanpa_kurs.join(', ')}.</span>
                )}
              </p>
            )}
            <GridKartu kolom={4}>
              <Kartu judul="Ending balance" nilai={uangPenuh(kpi.saldo_akhir, satuan)} info="Jumlah saldo rekening terpilih"
                catatan={`per ${tglLengkap(kpi.tanggal_saldo)} · opening ${uangPenuh(kpi.saldo_awal, satuan)}`} />
              <Kartu judul="Total debit" nilai={uangPenuh(kpi.masuk, satuan)} info="Penerimaan, termasuk transfer masuk antar rekening"
                catatan={`${angka.format(kpi.jumlah_masuk)} transaksi · transfer ${uangPenuh(kpi.transfer_masuk, satuan)}`} />
              <Kartu judul="Total credit" nilai={uangPenuh(kpi.keluar, satuan)} info="Pengeluaran, termasuk transfer keluar antar rekening"
                catatan={`${angka.format(kpi.jumlah_keluar)} transaksi · transfer ${uangPenuh(kpi.transfer_keluar, satuan)}`} />
              <Kartu judul="Jasa giro" nilai={uangPenuh(data.giro.total, satuan)} info="Giro ÷ AVG balance × 12"
                catatan={data.giro.imbal != null ? `${persenGiro(data.giro.imbal)} per tahun` : null} />
            </GridKartu>

            <KisiGrafik>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Running balance" perbesar petunjuk={`Ending balance, debit, dan credit, ${belakang} bulan terakhir.`}
                  aksi={<PilihRentang label="Panjang running balance" nilai={belakang} onUbah={setBelakang}
                    opsi={OPSI_BELAKANG.map((n) => ({ nilai: n, label: `${n} bln`, judul: `${n} bulan terakhir` }))} />}>
                  <SaldoBerjalan bulanan={data.running.slice(-belakang)} satuan={satuan} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Credit to date" perbesar aksi={pilihPeriode}
                  petunjuk={`Kumulatif sejak ${tglLengkap(kpi.awal_data)}. Tidak terpengaruh filter tanggal.`}>
                  <KreditToDate harian={data.deret.hari} bulanan={data.deret.bulan} periode={periode} satuan={satuan} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-12">
                <KartuGrafik judul="Jasa giro per perusahaan" petunjuk="Klik rekening untuk filter."
                  aksi={<><span className="text-xs tabular-nums text-slate-500">{rentangTgl(data.periode.mulai, data.periode.akhir)}</span><EksporGiro dataId={dataId} filter={filter} onDataHilang={onDataHilang} /></>}>
                  <JasaGiro giro={data.giro} asli={asli} satuan={satuan} terpilih={terpilih('rekening')} onPilih={pilih.rekening} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Jenis dokumen" petunjuk="Klik jenis untuk filter.">
                  <JenisDokumen dokumen={data.dokumen} satuan={satuan} terpilih={terpilih('dokumen')} onPilih={pilih.dokumen} />
                </KartuGrafik>
              </Petak>
              <Petak padat="lg:col-span-6">
                <KartuGrafik judul="Lawan transaksi terbesar" petunjuk="Klik nama untuk filter.">
                  <LawanTransaksi mitra={data.mitra} satuan={satuan} terpilih={terpilih('mitra')} onPilih={pilih.mitra} />
                </KartuGrafik>
              </Petak>
            </KisiGrafik>

            <TabelDetail laporanId="cash_flow" dataId={dataId} filter={filter} jumlah={{ harian: kpi.hari, bank: kpi.hari, mutasi: kpi.baris_mutasi, giro: kpi.jumlah_giro }}
              tab={TAB} onDataHilang={onDataHilang} />
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
