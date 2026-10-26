import PilihRentang from './PilihRentang'
import RentangTanggal from './RentangTanggal'

const tambahHari = (iso, n) => {
  const t = new Date(iso + 'T00:00:00Z')
  t.setUTCDate(t.getUTCDate() + n)
  return t.toISOString().slice(0, 10)
}
// Jumat pada atau sebelum tanggal itu (minggu laporan: Jumat sampai Kamis)
const awalMinggu = (iso) => tambahHari(iso, -((new Date(iso + 'T00:00:00Z').getUTCDay() + 2) % 7))
const hariIniIso = () => {
  const t = new Date()
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
}
const PINTASAN = { minggu: [5, 8, 12], hari: [7, 30, 90] } // cukup satu baris di panel filter; rentang lain lewat isian tanggal

// Mempersempit tampilan di dalam data yang sudah dimuat, tanpa SQL. dari/sampai null = rentang bawaan dari server;
// efektif: rentang yang sedang tampil. satuan: 'minggu' (Jumat-Kamis) atau 'hari'.
export default function FilterTanggal({ dari, sampai, efektif, dataset, satuan, bawaan, onUbah }) {
  const min = dataset.mulai
  const maks = dataset.akhir
  const ujung = maks < hariIniIso() ? maks : hariIniIso() < min ? min : hariIniIso() // data sampai hari ini; tanggal setelahnya belum ada isinya
  const awalPintasan = (n) => (satuan === 'minggu' ? tambahHari(awalMinggu(ujung), -7 * (n - 1)) : tambahHari(ujung, -(n - 1)))
  const pilihan = satuan === 'minggu' ? 'mgg' : 'hari'

  const opsi = [
    ...PINTASAN[satuan]
      .filter((n) => awalPintasan(n) > min)
      .map((n) => ({ nilai: n, label: `${n} ${pilihan}`, judul: `${n} ${satuan} terakhir${n === bawaan ? ' (bawaan)' : ''}` })),
    { nilai: 'semua', label: 'Semua', judul: 'Seluruh periode yang dimuat' },
  ]
  const bebas = Boolean(dari && sampai)
  const cocok = (n) => (n === 'semua' ? dari === min : dari === awalPintasan(n)) && sampai === ujung
  const terpilih = !bebas ? (opsi.some((o) => o.nilai === bawaan) ? bawaan : 'semua') : opsi.find((o) => cocok(o.nilai))?.nilai
  const pilih = (n) =>
    onUbah(n === bawaan ? { dari: null, sampai: null } : n === 'semua' ? { dari: min, sampai: ujung } : { dari: awalPintasan(n), sampai: ujung })

  return (
    <div className="space-y-2 border-b border-slate-200 pb-3">
      <div className="text-sm text-slate-600">Tanggal</div>
      <RentangTanggal dari={bebas ? dari : efektif.dari} sampai={bebas ? sampai : efektif.sampai} min={min} maks={maks} onUbah={(d, s) => onUbah({ dari: d, sampai: s })} />
      <PilihRentang label="Pintasan tanggal" opsi={opsi} nilai={terpilih} onUbah={pilih} />
    </div>
  )
}
