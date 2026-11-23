import { useEffect, useId, useRef, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ingatAsisten, nilaiAsisten, saranAsisten, tanyaAsisten } from '../api'
import Peringkat from '../grafik/Peringkat'
import { ANIMASI, DURASI_ANIMASI } from '../grafik/animasi'
import { angka, rupiah, rupiahPenuh, tglLengkap } from '../lib/data'
import { IkonTutup } from './Ikon'

// Tanya jawab data laporan dengan kalimat biasa. Jawaban dihitung server (backend/analytics/asisten) dari data laporan yang sama,
// tanpa AI. Panel samping, bukan modal: laporan di belakangnya tetap bisa dibaca dan digulir.

const CONTOH = [
  'Hutang per perusahaan',
  '10 supplier dengan hutang terbesar',
  'PR yang belum PO per perusahaan',
  'Nilai PO bulan ini dibanding bulan lalu',
  'Daftar PR belum PO terlama',
  'Apa itu PVR?',
]
const JEDA_MEMUAT = 1500
const MAKS_MEMUAT = 80 // sekitar 2 menit

const desimal = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
function format(nilai, tipe, ringkas = false) {
  if (nilai === null || nilai === undefined || nilai === '') return '–'
  if (tipe === 'rp') return ringkas ? rupiah(nilai) : rupiahPenuh.format(nilai)
  if (tipe === 'hari') return `${desimal.format(nilai)} hari`
  if (tipe === 'tanggal') return tglLengkap(String(nilai))
  if (typeof nilai === 'number') return angka.format(Math.round(nilai * 100) / 100)
  return String(nilai)
}

// Label sumbu grafik garis: singkat supaya tidak terpotong ("45 M", "800 jt")
function sumbu(v, tipe) {
  if (tipe !== 'rp') return angka.format(v)
  const n = Math.abs(v)
  return n >= 1e12 ? `${desimal.format(v / 1e12)} T` : n >= 1e9 ? `${desimal.format(v / 1e9)} M` : n >= 1e6 ? `${desimal.format(v / 1e6)} jt` : angka.format(v)
}

// Lambang AkasaBot: timbangan dua piring. goyang = sedang menimbang (lengan dan piring berayun pelan, berhenti saat jawaban datang;
// mati sama sekali kalau pengguna memilih "kurangi gerak").
function IkonNeraca({ className = 'h-4 w-4', goyang = false }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M12 4v16M8 20h8" />
      <g className={goyang ? 'neraca-goyang' : undefined} style={{ transformOrigin: '12px 5px', transformBox: 'view-box' }}>
        <path d="M4 6h16" />
        <path d="M6 6l-3 6a3 3 0 0 0 6 0zM18 6l-3 6a3 3 0 0 0 6 0z" />
      </g>
      <circle cx="12" cy="4" r="1" fill="currentColor" />
    </svg>
  )
}

// Pesan saat menimbang, bergantian supaya tunggu terasa hidup; isinya tetap jujur tentang apa yang sedang terjadi
const PESAN_TIMBANG = ['Menimbang angka…', 'Menyeimbangkan neraca…', 'Mencocokkan dengan laporan…', 'Memastikan tidak berat sebelah…']
const PESAN_MUAT = ['Mengambil data laporan dari server…', 'Data sedang diangkut ke timbangan…', 'Pertama kali memang agak lama, sampai satu menit…']

function PesanBerganti({ daftar }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % daftar.length), 2200)
    return () => clearInterval(t)
  }, [daftar])
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-slate-600">
      <IkonNeraca className="h-5 w-5 text-sky-700" goyang />
      {daftar[i]}
    </p>
  )
}

function IkonKirim({ className = 'h-4 w-4' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

function Tabel({ tabel }) {
  return (
    <div className="mt-2 max-h-72 overflow-auto rounded-md border border-slate-200">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-slate-50 text-slate-600">
          <tr>
            {tabel.kolom.map((k) => (
              <th key={k.kunci} scope="col" className={'whitespace-nowrap px-2 py-1.5 font-medium ' + (['rp', 'angka', 'hari'].includes(k.tipe) ? 'text-right' : 'text-left')}>
                {k.judul}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tabel.baris.map((b, i) => (
            <tr key={i} className="border-t border-slate-100">
              {tabel.kolom.map((k) => (
                <td key={k.kunci} className={'px-2 py-1 align-top text-slate-700 ' + (['rp', 'angka', 'hari'].includes(k.tipe) ? 'whitespace-nowrap text-right tabular-nums' : 'max-w-48 break-words')}>
                  {format(b[k.kunci], k.tipe)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Grafik({ grafik, tabel }) {
  const tipe = grafik.tipe
  if (!tabel.baris.length) return null
  if (grafik.jenis === 'garis') {
    return (
      <div className="mt-2 h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={tabel.baris} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="kelompok" tickLine={false} axisLine={{ stroke: '#cbd5e1' }} tick={{ fontSize: 11, fill: '#475569' }} minTickGap={8} />
            <YAxis width={48} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#475569' }} tickFormatter={(v) => sumbu(v, tipe)} />
            <Tooltip formatter={(v) => [format(v, tipe), grafik.seri[0].nama]} contentStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="nilai" stroke="#0369a1" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={ANIMASI} animationDuration={DURASI_ANIMASI} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }
  if (grafik.seri.length > 1) return null // perbandingan per kelompok: cukup tabel
  const data = tabel.baris.map((b) => ({ nama: b.kelompok, nilai: b.nilai, teks: format(b.nilai, tipe, true), judul: `${b.kelompok}: ${format(b.nilai, tipe)}` }))
  return (
    <div className="mt-2">
      <Peringkat data={data} />
    </div>
  )
}

function Jawaban({ j, terakhir, onTanya, onBuka, bolehBuka }) {
  const [tabelTerbuka, setTabelTerbuka] = useState(j.jenis === 'daftar' || j.jenis === 'dokumen')
  const [nilai, setNilai] = useState(null)
  const nilaiKe = (suka) => {
    setNilai(suka)
    nilaiAsisten(j.id, suka).catch(() => {})
  }
  const adaTabel = j.tabel && j.tabel.baris?.length > 0
  return (
    <div className="space-y-2">
      {/* Satu angka: angkanya yang paling menonjol, kalimatnya penjelas di bawah */}
      {j.angka && <p className="text-2xl font-semibold tabular-nums text-slate-900">{format(j.angka.nilai, j.angka.satuan === 'rp' ? 'rp' : j.angka.satuan === 'hari' ? 'hari' : 'angka', true)}</p>}
      <p className="text-sm leading-relaxed text-slate-800">{j.teks}</p>
      {/* Pertanyaan ditulis ulang sebagai filter laporan, bentuknya sama dengan filter di halaman laporan, supaya mudah dicocokkan */}
      {j.tafsiran?.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-xs">
          <span className="mr-0.5 text-slate-600">Dibaca sebagai</span>
          {j.tafsiran.map((t) => (
            <span key={t.label + t.nilai} className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-slate-700">
              {t.label === 'Ukuran' ? <b className="font-semibold text-slate-800">{t.nilai}</b> : t.label === 'Per' ? `per ${t.nilai.toLowerCase()}` : <><span className="text-slate-600">{t.label}:</span> {t.nilai}</>}
            </span>
          ))}
        </div>
      )}
      {j.catatan?.map((c) => (
        <p key={c} className="text-xs text-amber-800">{c}</p>
      ))}
      {j.grafik && adaTabel && <Grafik grafik={j.grafik} tabel={j.tabel} />}
      {adaTabel && j.grafik && (
        <button type="button" onClick={() => setTabelTerbuka((t) => !t)} aria-expanded={tabelTerbuka}
          className="text-xs font-medium text-sky-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
          {tabelTerbuka ? 'Sembunyikan tabel' : 'Lihat tabel'}
        </button>
      )}
      {adaTabel && tabelTerbuka && <Tabel tabel={j.tabel} />}
      {j.arti && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-800">Cara menghitung</summary>
          <p className="mt-1">{j.arti}</p>
        </details>
      )}
      {j.sumber_teks && <p className="text-xs text-slate-500">Sumber: {j.sumber_teks}</p>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-xs">
        {j.laporan && bolehBuka(j.laporan.id) && (
          <button type="button" onClick={() => onBuka(j.laporan.id)}
            className="font-medium text-sky-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
            Buka laporan {j.laporan.nama}
          </button>
        )}
        {j.id && !['tidak_paham', 'obrolan'].includes(j.jenis) && (
          <span className="ml-auto flex items-center gap-1.5 text-slate-600">
            {nilai === null ? (
              <>
                Sesuai?
                <button type="button" onClick={() => nilaiKe(true)} className="rounded-md border border-slate-300 px-2 py-0.5 text-slate-700 hover:border-slate-400 hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 pointer-coarse:py-2">Ya</button>
                <button type="button" onClick={() => nilaiKe(false)} className="rounded-md border border-slate-300 px-2 py-0.5 text-slate-700 hover:border-slate-400 hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 pointer-coarse:py-2">Kurang tepat</button>
              </>
            ) : (
              <span role="status">{nilai ? 'Terima kasih.' : 'Terima kasih, akan diperiksa.'}</span>
            )}
          </span>
        )}
      </div>
      {terakhir && j.saran?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {j.saran.map((s) => (
            <button key={s} type="button" onClick={() => onTanya(s, j.jenis === 'tidak_paham' ? j.asal : null)}
              className="rounded-full border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:border-sky-600 hover:text-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 pointer-coarse:py-2">
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// Rekomendasi pertanyaan menu yang sedang dibuka
function SaranMenu({ saran, onTanya }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {saran.saran.map((c) => (
        <button key={c} type="button" onClick={() => onTanya(c)} className="rounded-full border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:border-sky-600 hover:text-sky-800 active:bg-sky-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 pointer-coarse:py-2">
          {c}
        </button>
      ))}
    </div>
  )
}

export default function Asisten({ laporan, menu, onBukaLaporan }) {
  const [buka, setBuka] = useState(false)
  const [pesan, setPesan] = useState([]) // [{ dari: 'saya' | 'asisten', teks | jawaban }]
  const [teks, setTeks] = useState('')
  const [sibuk, setSibuk] = useState(false)
  const lalu = useRef(null)
  const giliran = useRef(0)
  const masukan = useRef(null)
  const tombol = useRef(null)
  const daftar = useRef(null)
  const idJudul = useId()

  const bolehBuka = (id) => laporan?.some((l) => l.id === id)
  const namaMenu = laporan?.find((l) => l.id === menu)?.nama

  // Rekomendasi diambil tiap panel dibuka di menu baru. Pindah menu di tengah percakapan: konteks lama dilepas dan rekomendasi menu
  // baru ditampilkan sebagai penanda di percakapan, supaya jelas jawaban berikutnya mengikuti menu itu.
  const [saran, setSaran] = useState({ menu: undefined, saran: CONTOH, ada_data: true })
  const menuTerakhir = useRef(menu)
  useEffect(() => {
    if (!buka || saran.menu === menu) return undefined
    let batal = false
    saranAsisten(menu)
      .then((d) => {
        if (batal) return
        setSaran({ ...d, menu })
        if (menuTerakhir.current !== menu) {
          menuTerakhir.current = menu
          lalu.current = null
          setPesan((p) => (p.length ? [...p, { dari: 'menu', nama: d.menu, saran: d }] : p))
        }
      })
      .catch(() => {
        if (!batal) setSaran({ menu, saran: CONTOH, ada_data: true })
      })
    return () => {
      batal = true
    }
  }, [buka, menu, saran.menu])

  useEffect(() => {
    if (!buka) return undefined
    masukan.current?.focus()
    const tekan = (e) => {
      if (e.key === 'Escape') tutup()
    }
    document.addEventListener('keydown', tekan)
    return () => document.removeEventListener('keydown', tekan)
  }, [buka])

  useEffect(() => {
    const el = daftar.current
    if (el) el.scrollTop = el.scrollHeight
  }, [pesan, sibuk])

  // Percakapan tetap tersimpan saat panel ditutup; fokus kembali ke tab Tanya AkasaBot setelah tombolnya tampil lagi
  const kembalikanFokus = useRef(false)
  const tutup = () => {
    kembalikanFokus.current = true
    setBuka(false)
  }
  useEffect(() => {
    if (!buka && kembalikanFokus.current) {
      kembalikanFokus.current = false
      tombol.current?.focus()
    }
  }, [buka])
  const baru = () => {
    giliran.current += 1
    lalu.current = null
    setPesan([])
    setSibuk(false)
    masukan.current?.focus()
  }

  const tanya = async (kalimat, asalTidakPaham = null) => {
    const q = kalimat.trim()
    if (!q || sibuk) return
    if (asalTidakPaham) ingatAsisten(asalTidakPaham, q).catch(() => {})
    const ke = ++giliran.current
    setTeks('')
    setSibuk(true)
    setPesan((p) => [...p, { dari: 'saya', teks: q }])
    try {
      let j
      for (let i = 0; ; i++) {
        j = await tanyaAsisten(q, lalu.current, menu)
        if (ke !== giliran.current) return
        if (j.jenis !== 'memuat') break
        if (i >= MAKS_MEMUAT) {
          j = { jenis: 'teks', teks: 'Data laporan belum selesai dimuat. Coba tanyakan lagi sebentar lagi.' }
          break
        }
        setPesan((p) => (p.at(-1)?.memuat ? p : [...p, { dari: 'asisten', memuat: true }]))
        await new Promise((r) => setTimeout(r, JEDA_MEMUAT))
        if (ke !== giliran.current) return
      }
      if (j.permintaan && ['angka', 'daftar'].includes(j.permintaan.maksud)) lalu.current = j.permintaan
      setPesan((p) => [...p.filter((x) => !x.memuat), { dari: 'asisten', jawaban: j }])
    } catch (e) {
      if (ke !== giliran.current) return
      setPesan((p) => [...p.filter((x) => !x.memuat), { dari: 'asisten', jawaban: { jenis: 'galat', teks: e.message || 'Pertanyaan tidak bisa diproses.' } }])
    } finally {
      if (ke === giliran.current) {
        setSibuk(false)
        masukan.current?.focus()
      }
    }
  }

  const terakhir = pesan.findLastIndex((x) => x.jawaban || x.dari === 'menu')

  return (
    <>
      {!buka && (
        // Tab di tepi kanan, di bawah tab Filter: pola laci yang sama dengan Filter, tidak menutupi tabel atau tombol ke atas, dan tetap
        // terjangkau di posisi gulir mana pun. Putih bertepi supaya beda dari tab Filter yang biru penuh.
        <button
          ref={tombol}
          type="button"
          onClick={() => setBuka(true)}
          title="Tanya AkasaBot: terminal tanya angka laporan"
          style={{ top: 'calc(33.333% + 3.25rem)' }}
          className="fixed right-0 z-30 flex flex-col items-center gap-1.5 rounded-l-md border border-r-0 border-sky-700 bg-white px-1.5 py-2.5 text-xs font-semibold text-sky-800 shadow-[-4px_4px_14px_-6px_rgb(15_23_42/0.35)] hover:bg-sky-50 active:bg-sky-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 pointer-coarse:px-2.5"
        >
          <IkonNeraca className="neraca-hover h-4 w-4" />
          <span className="[writing-mode:vertical-rl] rotate-180 tracking-wide">Tanya AkasaBot</span>
        </button>
      )}
      {buka && (
        <aside
          role="complementary"
          aria-labelledby={idJudul}
          className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-slate-200 bg-white shadow-xl sm:w-[28rem]"
        >
          {/* Pita biru tua: satu-satunya bidang berwarna penuh di panel, jadi identitas AkasaBot terbaca tanpa hiasan lain */}
          <header className="neraca-pita flex items-start gap-3 bg-sky-900 px-4 py-3 text-white">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/10">
              <IkonNeraca className="h-6 w-6" goyang={sibuk} />
            </span>
            <div className="min-w-0 flex-1">
              <h2 id={idJudul} className="text-base font-semibold">AkasaBot</h2>
              <p className="truncate text-xs text-sky-100">{namaMenu ? `Terhubung ke menu ${namaMenu}` : 'Terminal tanya angka laporan'}</p>
            </div>
            {pesan.length > 0 && (
              <button type="button" onClick={baru}
                className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-sky-100 hover:bg-white/10 hover:text-white active:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white pointer-coarse:py-2.5">
                Percakapan baru
              </button>
            )}
            <button type="button" onClick={tutup} aria-label="Tutup AkasaBot"
              className="-mr-1 shrink-0 rounded-md p-1.5 text-sky-100 hover:bg-white/10 hover:text-white active:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white pointer-coarse:p-3">
              <IkonTutup className="h-5 w-5" />
            </button>
          </header>

          <div ref={daftar} className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite" aria-busy={sibuk}>
            {pesan.length === 0 && (
              <div className="space-y-3 text-sm text-slate-700">
                <p>Taruh pertanyaan di piring kiri, saya taruh datanya di piring kanan. Ketik dengan kalimat biasa, lalu lanjutkan dengan "per supplier" atau "kalau YBS?" untuk mengubah jawabannya.</p>
                <p className="text-xs font-medium text-slate-600">{namaMenu ? `Coba tanya soal ${namaMenu}:` : 'Coba tanya:'}</p>
                <SaranMenu saran={saran} onTanya={tanya} />
                {!saran.ada_data && (
                  <p className="text-xs text-slate-600">Angka di menu ini belum bisa saya hitung, tapi istilahnya bisa ditanyakan. Untuk angka, buka Outstanding, Purchase Request, Purchase Order, atau Purchase Invoice.</p>
                )}
                <p className="text-xs text-slate-500">Bisa juga menempel nomor dokumen, mis. nomor PR, PO, atau PI, untuk melihat statusnya.</p>
              </div>
            )}
            {pesan.map((m, i) =>
              m.dari === 'saya' ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] rounded-lg bg-sky-700 px-3 py-2 text-sm text-white">{m.teks}</p>
                </div>
              ) : m.memuat ? (
                <PesanBerganti key={i} daftar={PESAN_MUAT} />
              ) : m.dari === 'menu' ? (
                <div key={i} className="space-y-2">
                  <p className="flex items-center gap-2 text-xs text-slate-600">
                    <span className="h-px flex-1 bg-slate-200" aria-hidden="true" />
                    Pindah ke menu {m.nama || 'lain'}
                    <span className="h-px flex-1 bg-slate-200" aria-hidden="true" />
                  </p>
                  {i === terakhir && <SaranMenu saran={m.saran} onTanya={tanya} />}
                </div>
              ) : (
                <div key={i} className={'rounded-lg border px-3 py-2.5 ' + (m.jawaban.jenis === 'galat' ? 'border-red-200 bg-red-50' : 'border-slate-200')}>
                  {m.jawaban.jenis === 'galat' ? (
                    <p className="text-sm text-red-700">{m.jawaban.teks}</p>
                  ) : (
                    <Jawaban j={m.jawaban} terakhir={i === terakhir} onTanya={tanya} bolehBuka={bolehBuka}
                      onBuka={(id) => onBukaLaporan(id)} />
                  )}
                </div>
              ),
            )}
            {sibuk && !pesan.at(-1)?.memuat && <PesanBerganti daftar={PESAN_TIMBANG} />}
          </div>

          <form
            className="flex items-end gap-2 border-t border-slate-200 px-4 py-3"
            onSubmit={(e) => {
              e.preventDefault()
              tanya(teks)
            }}
          >
            <label htmlFor={idJudul + '-teks'} className="sr-only">Pertanyaan</label>
            <input
              id={idJudul + '-teks'}
              ref={masukan}
              value={teks}
              onChange={(e) => setTeks(e.target.value)}
              maxLength={300}
              autoComplete="off"
              placeholder={`Mis. ${(saran.saran[0] || "hutang ORI per supplier").toLowerCase()}`}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
            />
            <button type="submit" disabled={sibuk || !teks.trim()} aria-label="Kirim pertanyaan"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-700 text-white hover:bg-sky-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
              <IkonKirim />
            </button>
          </form>
        </aside>
      )}
    </>
  )
}
