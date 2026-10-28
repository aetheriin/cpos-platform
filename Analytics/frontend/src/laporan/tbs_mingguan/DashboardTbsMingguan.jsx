import { useEffect, useMemo, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { angka, bandingKpi, tambahDariEvent, ubahPilihan } from '../../lib/data'
import { chipDaftar, chipRentang, useDashboard } from '../../lib/filter'
import FilterTanggal from '../../komponen/FilterTanggal'
import FilterMulti from '../../komponen/FilterMulti'
import { GridKartu, Kartu, KartuGrafik } from '../../komponen/Kartu'
import KepalaLaporan from '../../komponen/KepalaLaporan'
import PanelFilter from '../../komponen/PanelFilter'
import TabelDetail from '../../komponen/TabelDetail'

// Atensi dihitung di backend (laporan/tbs_mingguan/ukuran.py): minggu lengkap terakhir dibanding rata-rata ± batas SD minggu lengkap sebelumnya.
// Tampilan awal hanya YBS; perusahaan lain lewat panel filter.
const FILTER_AWAL = { perusahaan: ['YBS'] }
const KOSONG = []
const PER_HALAMAN = 12
const BIRU = '#2563eb'
const HIJAU = '#16a34a'
const MERAH = '#dc2626'
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const URUT = [
  { kunci: 'atensi', nama: 'Atensi', banding: (a, b) => (b.status ? 1 : 0) - (a.status ? 1 : 0) || Math.abs(b.persen ?? 0) - Math.abs(a.persen ?? 0) },
  { kunci: 'tonase', nama: 'Tonase terbesar', banding: (a, b) => b.tonase - a.tonase },
  { kunci: 'perubahan', nama: 'Perubahan terbesar', banding: (a, b) => Math.abs(b.persen ?? 0) - Math.abs(a.persen ?? 0) },
  { kunci: 'nama', nama: 'Nama A sampai Z', banding: (a, b) => a.nama.localeCompare(b.nama) },
]

const TAB = [
  {
    kunci: 'atensi',
    nama: 'Per jenis kebun dan grup',
    ket: () => 'Tonase dalam kg per minggu lengkap. Std Dev dan Mean dari minggu sebelum minggu dinilai; tiap baris punya atensinya sendiri.',
  },
]

const satu = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const tglPendek = (iso) => `${Number(iso.slice(8, 10))} ${BULAN[Number(iso.slice(5, 7)) - 1]}`
const rentangPendek = (m) => (m.awal.slice(5, 7) === m.akhir.slice(5, 7) ? `${Number(m.awal.slice(8, 10))}–${tglPendek(m.akhir)}` : `${tglPendek(m.awal)} – ${tglPendek(m.akhir)}`)
const tonTeks = (kg) => `${angka.format(Math.round(kg / 1000))} ton`
const tonKecil = (kg) => `${satu.format(kg / 1000)} ton`
const persenTeks = (x) => `${x > 0 ? '+' : ''}${satu.format(x)}%`

// Lebar elemen dalam piksel, supaya SVG digambar tanpa diregangkan (titik tetap bulat, teks tidak gepeng).
function useLebar() {
  const [lebar, setLebar] = useState(0)
  const [el, setEl] = useState(null)
  useEffect(() => {
    if (!el) return undefined
    const amati = new ResizeObserver(([e]) => setLebar(Math.round(e.contentRect.width)))
    amati.observe(el)
    return () => amati.disconnect()
  }, [el])
  return [setEl, lebar]
}

function Ringkasan({ r, minggu, jumlahRiwayat }) {
  const dinilai = minggu.at(-1)
  const lalu = minggu.at(-2)
  const banding = lalu ? { mulai: lalu.awal, akhir: lalu.akhir, kpi: { nilai: r.lalu } } : null
  return (
    <GridKartu kolom={5}>
      <Kartu
        judul={`Tonase ${rentangPendek(dinilai)}`}
        nilai={tonTeks(r.nilai)}
        catatan="dari minggu lalu"
        info="netto TBS minggu dinilai, Senin sampai Minggu"
        banding={bandingKpi(r.nilai, banding, (k) => k.nilai, { naikBaik: true })}
      />
      <Kartu judul="Rata-rata per Minggu" nilai={tonTeks(r.rata)} catatan={`${jumlahRiwayat} minggu sebelumnya`} info="rata-rata tonase minggu lengkap sebelum minggu dinilai" />
      <Kartu judul="Pencapaian Target" nilai={`${Math.round((r.nilai / r.target) * 100)}%`} catatan={`target ${angka.format(r.target / 1000)} ton per minggu`} />
      <Kartu judul="Atensi Naik" nilai={angka.format(r.naik)} catatan="grup di atas kisaran normal" />
      <Kartu judul="Atensi Turun" nilai={angka.format(r.turun)} catatan={r.berhenti ? `${r.berhenti} grup berhenti kirim` : 'grup di bawah kisaran normal'} />
    </GridKartu>
  )
}

function TrenTotal({ minggu, rata, target, jumlahRiwayat }) {
  const data = minggu.map((m) => ({ ...m, ton: m.netto / 1000, rentang: rentangPendek(m) }))
  return (
    <KartuGrafik
      judul="Tonase per Minggu" perbesar
      petunjuk={`Total ton tiap minggu lengkap (Senin sampai Minggu). Garis putus-putus: rata-rata ${jumlahRiwayat} minggu sebelum minggu dinilai. Garis abu-abu: target ${angka.format(target / 1000)} ton.`}
    >
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="rentang" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 10, fill: '#475569' }} interval="preserveStartEnd" minTickGap={4} />
            <YAxis tickFormatter={(v) => angka.format(v)} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} width={52} domain={[0, 'auto']} />
            <Tooltip
              formatter={(v) => [`${angka.format(Math.round(v))} ton`, 'Tonase']}
              labelFormatter={(_, p) => (p?.[0] ? `${tglPendek(p[0].payload.awal)} sampai ${tglPendek(p[0].payload.akhir)}` : '')}
            />
            <ReferenceLine y={target / 1000} stroke="#94a3b8" strokeWidth={1.5} />
            {rata != null && <ReferenceLine y={rata / 1000} stroke="#64748b" strokeDasharray="6 4" />}
            <Area type="linear" dataKey="ton" stroke={BIRU} strokeWidth={2} fill={BIRU} fillOpacity={0.08} dot={{ r: 3.5, fill: BIRU, strokeWidth: 0 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </KartuGrafik>
  )
}

// Garis kecil per grup: pita rata-rata ± batas SD, rata-rata putus-putus, kolom abu-abu untuk minggu dinilai, titik akhir hijau/merah.
function Sparkline({ g, minggu, batas, sorot, onSorot }) {
  const [ref, lebar] = useLebar()
  const tinggi = 84
  const pad = { x: 4, atas: 6, bawah: 18 }
  const n = g.seri.length
  const pita = g.rata != null && g.sd != null ? [Math.max(0, g.rata - batas * g.sd), g.rata + batas * g.sd] : null
  const maks = Math.max(...g.seri, pita?.[1] ?? 0, 1)
  const langkah = (lebar - 2 * pad.x) / Math.max(1, n - 1)
  const x = (i) => pad.x + i * langkah
  const y = (v) => tinggi - pad.bawah - (v / maks) * (tinggi - pad.atas - pad.bawah)
  const warna = g.status === 'NAIK' ? HIJAU : g.status === 'TURUN' ? MERAH : BIRU
  return (
    <div ref={ref} style={{ height: tinggi }}>
      {lebar > 0 && (
        <svg
          width={lebar}
          height={tinggi}
          className="block"
          onPointerLeave={() => onSorot(null)}
          onPointerMove={(e) => onSorot(Math.min(n - 1, Math.max(0, Math.round((e.clientX - e.currentTarget.getBoundingClientRect().left - pad.x) / langkah))))}
        >
          <rect x={x(n - 1) - langkah / 2} width={langkah / 2 + pad.x} y={pad.atas} height={tinggi - pad.atas - pad.bawah} className="fill-slate-100" />
          {pita && <rect x={pad.x} width={lebar - 2 * pad.x} y={y(pita[1])} height={Math.max(1, y(pita[0]) - y(pita[1]))} className="fill-slate-200/70" />}
          {g.rata != null && <line x1={pad.x} x2={lebar - pad.x} y1={y(g.rata)} y2={y(g.rata)} stroke="#94a3b8" strokeDasharray="4 3" />}
          {sorot != null && <line x1={x(sorot)} x2={x(sorot)} y1={pad.atas} y2={tinggi - pad.bawah} stroke="#94a3b8" />}
          <polyline points={g.seri.map((v, i) => `${x(i)},${y(v)}`).join(' ')} fill="none" stroke={BIRU} strokeWidth="1.6" strokeLinejoin="round" />
          <circle cx={x(n - 1)} cy={y(g.seri[n - 1])} r="3.5" fill={warna} />
          <text x={pad.x} y={tinggi - 4} fontSize="11" className="fill-slate-400">
            {tglPendek(minggu[0].awal)}
          </text>
          <text x={lebar - pad.x} y={tinggi - 4} fontSize="11" textAnchor="end" className="fill-slate-400">
            {tglPendek(minggu[n - 1].awal)}
          </text>
        </svg>
      )}
    </div>
  )
}

function KartuGrup({ g, minggu, batas, sorot, onSorot, pilih, onPilih }) {
  const i = sorot ?? g.seri.length - 1
  return (
    <button
      type="button"
      aria-pressed={pilih}
      onClick={onPilih}
      className={'min-w-0 rounded-xl border bg-white p-3 text-left hover:border-slate-400 ' + (pilih ? 'border-sky-500 ring-1 ring-sky-500' : 'border-slate-200')}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium" title={g.nama}>
            {g.nama}
          </p>
          <p className="truncate text-sm text-slate-500">
            {g.tipe}
            {g.comp ? ` · ${g.comp}` : ''}
          </p>
        </div>
        {g.status && (
          <span className={'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ' + (g.status === 'NAIK' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700')}>
            {g.status === 'NAIK' ? '▲ naik' : '▼ turun'}
          </span>
        )}
      </div>
      <Sparkline g={g} minggu={minggu} batas={batas} sorot={sorot} onSorot={onSorot} />
      <div className="flex items-baseline justify-between gap-2 text-sm tabular-nums">
        <span className="truncate">
          {sorot != null && `${rentangPendek(minggu[i])}: `}
          {tonKecil(g.seri[i])}
        </span>
        {sorot == null && g.persen != null && (
          <span className={g.status === 'NAIK' ? 'text-emerald-700' : g.status === 'TURUN' ? 'text-red-700' : 'text-slate-500'}>{persenTeks(g.persen)}</span>
        )}
      </div>
      {g.rata != null && (
        <p className="text-xs text-slate-500 tabular-nums">
          Rata-rata {satu.format(g.rata / 1000)} · normal {satu.format(Math.max(0, g.rata - batas * g.sd) / 1000)}–{tonKecil(g.rata + batas * g.sd)}
        </p>
      )}
    </button>
  )
}

function DaftarGrup({ data, terpilih, onPilih }) {
  const [tab, setTab] = useState('atensi')
  const [cari, setCari] = useState('')
  const [urut, setUrut] = useState('atensi')
  const [halaman, setHalaman] = useState(1)
  const [sorot, setSorot] = useState(null)
  const jumlahAtensi = data.grup.filter((g) => g.status).length
  const daftar = useMemo(() => {
    const teks = cari.trim().toLowerCase()
    return data.grup
      .filter((g) => (tab === 'semua' || g.status) && (!teks || g.nama.toLowerCase().includes(teks)))
      .sort(URUT.find((u) => u.kunci === urut).banding)
  }, [data.grup, tab, cari, urut])
  const jumlahHalaman = Math.max(1, Math.ceil(daftar.length / PER_HALAMAN))
  const hal = Math.min(halaman, jumlahHalaman)
  const ganti = (f) => (v) => {
    f(v)
    setHalaman(1)
  }

  return (
    <KartuGrafik
      judul="Atensi per Grup"
      petunjuk={`Pita abu-abu: kisaran normal (rata-rata ± ${satu.format(data.batas_sd)} simpangan baku). Garis putus-putus: rata-rata. Titik hijau: naik, merah: turun. Arahkan kursor ke grafik untuk melihat minggu yang sama di semua grup; klik kartu untuk memfilter semua grafik, kartu, dan tabel ke grup itu.`}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="tablist" className="inline-flex rounded-lg border border-slate-300 p-0.5">
          {[
            ['atensi', `Perlu atensi ${jumlahAtensi}`],
            ['semua', `Semua ${data.grup.length}`],
          ].map(([k, nama]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              onClick={() => ganti(setTab)(k)}
              className={'rounded-md px-3 py-1 text-sm ' + (tab === k ? 'bg-sky-600 text-white' : 'text-slate-700 hover:bg-slate-100')}
            >
              {nama}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={cari}
          onChange={(e) => ganti(setCari)(e.target.value)}
          placeholder="Cari grup"
          aria-label="Cari grup"
          className="w-44 rounded-md border border-slate-300 px-2 py-1 text-sm"
        />
        <select value={urut} onChange={(e) => ganti(setUrut)(e.target.value)} aria-label="Urutkan" className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm">
          {URUT.map((u) => (
            <option key={u.kunci} value={u.kunci}>
              {u.nama}
            </option>
          ))}
        </select>
      </div>

      {daftar.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          {cari ? `Tidak ada grup yang cocok dengan "${cari}".` : tab === 'atensi' ? 'Tidak ada grup di luar kisaran normal minggu ini. Lihat tab Semua untuk seluruh grup.' : 'Tidak ada pembelian di periode ini.'}
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {daftar.slice((hal - 1) * PER_HALAMAN, hal * PER_HALAMAN).map((g) => (
            <KartuGrup
              key={`${g.comp ?? ''}|${g.nama}`}
              g={g}
              minggu={data.minggu}
              batas={data.batas_sd}
              sorot={sorot}
              onSorot={setSorot}
              pilih={terpilih.includes(g.nama)}
              onPilih={(e) => onPilih(g.nama, e)}
            />
          ))}
        </div>
      )}

      {jumlahHalaman > 1 && (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs text-slate-600">
            <button type="button" disabled={hal <= 1} onClick={() => setHalaman(hal - 1)} className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40">
              Sebelumnya
            </button>
            <span className="tabular-nums">
              Halaman {hal} dari {jumlahHalaman}
            </span>
            <button type="button" disabled={hal >= jumlahHalaman} onClick={() => setHalaman(hal + 1)} className="rounded-md border border-slate-300 px-2 py-1 disabled:opacity-40">
              Berikutnya
            </button>
        </div>
      )}
    </KartuGrafik>
  )
}

export default function DashboardTbsMingguan({ dataId, onDataHilang }) {
  const { data, galat, memuat, filter, setFilter, ubah, terpilih, lepas, reset, panel, setPanel, togglePanel } = useDashboard('tbs_mingguan', dataId, FILTER_AWAL, onDataHilang)

  const daftarFilter = (data?.filter ?? KOSONG).filter((f) => f.panel)
  const aktif = [...chipRentang(filter), ...chipDaftar(daftarFilter, terpilih)]
  const pilihGrup = (nama, e) => setFilter((f) => ({ ...f, grup: ubahPilihan(f.grup ?? [], nama, tambahDariEvent(e)) }))
  const dinilai = data?.minggu.at(-1)

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <KepalaLaporan judul="Pembelian TBS Mingguan" data={data} aktif={aktif} onLepas={lepas} onReset={reset} panelTerbuka={panel} onTogglePanel={togglePanel} />

        {galat && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Laporan tidak bisa dimuat: {galat.message}</div>}
        {!data && !galat && <p className="text-sm text-slate-500">Memuat pembelian TBS mingguan...</p>}

        {data && (
          <div className={memuat ? 'space-y-4 opacity-60 transition-opacity' : 'space-y-4 transition-opacity'}>
            <p className="-mt-3 text-sm text-slate-500">
              {data.minggu.length} minggu lengkap · {data.perusahaan.length > 1 ? `perusahaan ${data.perusahaan.join(', ')}` : data.perusahaan[0]}
              {data.dinilai && ` · atensi dinilai di minggu ${rentangPendek(dinilai)}`}
            </p>
            {!data.dinilai ? (
              <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                Atensi butuh minimal {data.min_minggu} minggu lengkap (Senin sampai Minggu). Periode ini baru punya {data.minggu.length}. Pakai Ganti periode dengan tanggal mulai
                lebih awal.
              </p>
            ) : (
              <>
                <Ringkasan r={data.ringkasan} minggu={data.minggu} jumlahRiwayat={data.jumlah_riwayat} />
                <TrenTotal minggu={data.minggu} rata={data.ringkasan.rata} target={data.ringkasan.target} jumlahRiwayat={data.jumlah_riwayat} />
                <DaftarGrup data={data} terpilih={terpilih('grup')} onPilih={pilihGrup} />
                <TabelDetail
                  laporanId="tbs_mingguan"
                  dataId={dataId}
                  filter={filter}
                  jumlah={{ atensi: data.tabel_baris }}
                  tab={TAB}
                  onDataHilang={onDataHilang}
                  onPilihBaris={(b, e) => pilihGrup(b.grup, e)}
                  barisTerpilih={(b) => terpilih('grup').includes(b.grup)}
                />
              </>
            )}
          </div>
        )}
      </div>
      <PanelFilter terbuka={panel} onTutup={() => setPanel(false)} jumlahAktif={aktif.length} onReset={reset}>
        {data && (
          <FilterTanggal
            dari={filter.dari}
            sampai={filter.sampai}
            efektif={data.rentang}
            satuan="minggu"
            bawaan={data.rentang.bawaan}
            dataset={data.dataset}
            mingguSenin
            onUbah={ubah}
          />
        )}
        {daftarFilter.map(({ kunci, nama }) => (
          <FilterMulti key={kunci} sebaris label={nama} opsi={data.pilihan[kunci] ?? KOSONG} terpilih={terpilih(kunci)} onUbah={(v) => ubah({ [kunci]: v })} />
        ))}
      </PanelFilter>
    </div>
  )
}
