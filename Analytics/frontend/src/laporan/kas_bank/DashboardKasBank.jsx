import { useMemo, useState } from 'react'
import { angka, tambahDariEvent, tglLengkap, ubahPilihan } from '../../lib/data'
import { chipDaftar, useDashboard } from '../../lib/filter'
import FilterMulti from '../../komponen/FilterMulti'
import PilihRentang from '../../komponen/PilihRentang'
import { GridKartu, Kartu, KartuGrafik, KisiGrafik, Petak } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'
import { uangPenuh, WARNA_KELUAR, WARNA_MASUK } from '../../grafik/kas'
import { JenisDokumen, KreditToDate, PilihPeriode, SaldoBerjalan } from '../../grafik/KasTren'

const FILTER_AWAL = {}
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

// Rekap jasa giro per bank, mengikuti sheet BANK GIRO. Klik rekening untuk memfilternya.
function JasaGiro({ giro, satuan, terpilih, onPilih }) {
  if (giro.bank.length === 0) return <p className="py-8 text-center text-sm text-slate-500">Tidak ada data</p>
  const angkaSel = 'py-1.5 pl-4 text-right tabular-nums whitespace-nowrap'
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-xs">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="pb-1 font-medium">Bank / rekening</th>
            <th className="pb-1 pl-4 text-right font-medium">Giro</th>
            <th className="pb-1 pl-4 text-right font-medium">AVG balance</th>
            <th className="pb-1 pl-4 text-right font-medium" title="Giro ÷ AVG balance × 12">% Giro per tahun</th>
          </tr>
        </thead>
        {giro.bank.map((b) => (
          <tbody key={b.bank}>
            <tr className="border-t border-slate-300 font-semibold text-slate-900">
              <td className="py-1.5">{b.bank}</td>
              <td className={angkaSel}>{uangPenuh(b.nilai, satuan)}</td>
              <td className={angkaSel}>{uangPenuh(b.rata_saldo, satuan)}</td>
              <td className={angkaSel}>{persenGiro(b.imbal)}</td>
            </tr>
            {b.rekening.map((r) => {
              const pilih = terpilih.includes(r.akun)
              return (
                <tr key={r.akun} onClick={(e) => onPilih(r.akun, e)} aria-selected={pilih}
                  className={'cursor-pointer border-t border-slate-100 hover:bg-slate-50 ' + (pilih ? 'bg-sky-50 font-medium text-sky-900' : 'text-slate-700')}>
                  <td className="py-1.5 pl-3">{r.akun}</td>
                  <td className={angkaSel}>{uangPenuh(r.nilai, satuan)}</td>
                  <td className={angkaSel}>{uangPenuh(r.rata_saldo, satuan)}</td>
                  <td className={angkaSel}>{persenGiro(r.imbal)}</td>
                </tr>
              )
            })}
          </tbody>
        ))}
        <tfoot>
          <tr className="border-t-2 border-slate-400 font-semibold text-slate-900">
            <td className="py-1.5">Grand total</td>
            <td className={angkaSel}>{uangPenuh(giro.total, satuan)}</td>
            <td className={angkaSel}>{uangPenuh(giro.rata_saldo, satuan)}</td>
            <td className={angkaSel}>{persenGiro(giro.imbal)}</td>
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

// Panel filter: bulan laporan (bulan terbaru = rentang bawaan server, awal bulan sampai hari ini; bulan lain = satu bulan penuh)
// dan berapa bulan ke belakang yang tampil di Running balance
function PilihBulan({ bulan, filter, belakang, onBelakang, onUbah }) {
  const nilai = !filter.dari ? bulan[0] : bulan.find((b) => filter.dari === `${b}-01` && filter.sampai === akhirBulan(b)) ?? ''
  return (
    <div className="space-y-3 border-b border-slate-200 pb-3">
      <label className="block space-y-1 text-sm text-slate-600">
        <span>Bulan</span>
        <select value={nilai} onChange={(e) => onUbah(e.target.value === bulan[0] ? { dari: null, sampai: null } : { dari: `${e.target.value}-01`, sampai: akhirBulan(e.target.value) })}
          className="block w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
          {nilai === '' && <option value="">Pilih bulan</option>}
          {bulan.map((b) => <option key={b} value={b}>{namaBulan(b)}</option>)}
        </select>
      </label>
      <div className="space-y-1 text-sm text-slate-600">
        <div>Running balance</div>
        <PilihRentang label="Bulan ke belakang" nilai={belakang} onUbah={onBelakang}
          opsi={OPSI_BELAKANG.map((n) => ({ nilai: n, label: `${n} bln`, judul: `${n} bulan terakhir` }))} />
      </div>
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
  const aktif = [...(filter.dari ? [['rentang', null, `Bulan ${namaBulan(filter.dari.slice(0, 7))}`]] : []), ...chipDaftar(daftarFilter, terpilih, tampil)]
  const [belakang, setBelakang] = useState(OPSI_BELAKANG[0])
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
                <KartuGrafik judul="Running balance" perbesar petunjuk={`Ending balance, debit, dan credit, ${belakang} bulan terakhir.`}>
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
                <KartuGrafik judul="Jasa giro per bank" petunjuk="Klik rekening untuk filter.">
                  <JasaGiro giro={data.giro} satuan={satuan} terpilih={terpilih('rekening')} onPilih={pilih.rekening} />
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

            <TabelDetail laporanId="cash_flow" dataId={dataId} filter={filter} jumlah={{ harian: kpi.hari, bank: kpi.hari, mutasi: kpi.mutasi, giro: kpi.jumlah_giro }}
              tab={TAB} onDataHilang={onDataHilang} />
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && <PilihBulan bulan={data.bulan} filter={filter} belakang={belakang} onBelakang={setBelakang} onUbah={ubah} />}
        {daftarFilter
          .filter((f) => f.panel)
          .map(({ kunci, nama }) => (
            <FilterMulti key={kunci} sebaris label={nama} opsi={data?.pilihan[kunci] ?? KOSONG} terpilih={terpilih(kunci)} onUbah={(v) => ubah({ [kunci]: v })} />
          ))}
      </PanelFilter>
    </div>
  )
}
