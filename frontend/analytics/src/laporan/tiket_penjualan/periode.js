// Periode laporan Tiket Penjualan: satu hari, satu minggu (Senin sampai Minggu), atau satu bulan. Semua tanggal teks ISO 'YYYY-MM-DD'
// dan dihitung dalam UTC supaya zona waktu browser tidak menggeser hari.

export const MODE = [
  { kunci: 'hari', nama: 'Harian' },
  { kunci: 'minggu', nama: 'Mingguan' },
  { kunci: 'bulan', nama: 'Bulanan' },
]

const BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
const BULAN_SINGKAT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
const HARI_SINGKAT = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab']

const keDate = (iso) => new Date(`${iso}T00:00:00Z`)
const keIso = (d) => d.toISOString().slice(0, 10)
const bagian = (iso) => [Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))]

export const hariIniIso = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function tambahHari(iso, n) {
  const d = keDate(iso)
  d.setUTCDate(d.getUTCDate() + n)
  return keIso(d)
}

export const senin = (iso) => tambahHari(iso, -((keDate(iso).getUTCDay() + 6) % 7))
export const awalBulan = (iso) => `${iso.slice(0, 7)}-01`
export function akhirBulan(iso) {
  const [t, b] = bagian(iso)
  return keIso(new Date(Date.UTC(t, b + 1, 0)))
}
function tambahBulan(iso, n) {
  const [t, b] = bagian(iso)
  return keIso(new Date(Date.UTC(t, b + n, 1)))
}

const lebih = (a, b) => (a > b ? a : b)
const kurang = (a, b) => (a < b ? a : b)

// Rentang penuh periode yang memuat `acuan`.
export function rentangPenuh(mode, acuan) {
  if (mode === 'hari') return { dari: acuan, sampai: acuan }
  if (mode === 'minggu') return { dari: senin(acuan), sampai: tambahHari(senin(acuan), 6) }
  return { dari: awalBulan(acuan), sampai: akhirBulan(acuan) }
}

// Rentang yang dikirim ke server: rentang penuh dipotong ke data yang dimuat. null kalau periode itu di luar data.
export function rentangData(mode, acuan, batas) {
  const p = rentangPenuh(mode, acuan)
  const dari = lebih(p.dari, batas.mulai)
  const sampai = kurang(p.sampai, batas.akhir)
  return dari > sampai ? null : { dari, sampai, terpotong: dari !== p.dari || sampai !== p.sampai }
}

export function geser(mode, acuan, langkah) {
  if (mode === 'hari') return tambahHari(acuan, langkah)
  if (mode === 'minggu') return tambahHari(senin(acuan), 7 * langkah)
  return tambahBulan(acuan, langkah)
}

// Batas data yang bisa ditampilkan: data yang dimuat, paling lambat hari ini.
export const batasData = (dataset) => ({ mulai: dataset.mulai, akhir: kurang(dataset.akhir, hariIniIso()) })

export function tglPanjang(iso, { hari = false, tahun = true } = {}) {
  const [t, b, h] = bagian(iso)
  return `${hari ? `${HARI[keDate(iso).getUTCDay()]}, ` : ''}${h} ${BULAN[b]}${tahun ? ` ${t}` : ''}`
}

export function tglPendek(iso) {
  const [, b, h] = bagian(iso)
  return `${h} ${BULAN_SINGKAT[b]}`
}

export const namaHari = (iso) => HARI[keDate(iso).getUTCDay()]
export const namaHariSingkat = (iso) => HARI_SINGKAT[keDate(iso).getUTCDay()]

// Judul periode: 'Jumat, 13 November 2026', '9–15 November 2026', '28 September – 4 Oktober 2026', 'November 2026'.
export function judulPeriode(mode, acuan) {
  if (mode === 'hari') return tglPanjang(acuan, { hari: true })
  const { dari, sampai } = rentangPenuh(mode, acuan)
  const [t1, b1, h1] = bagian(dari)
  const [t2, b2, h2] = bagian(sampai)
  if (mode === 'bulan') return `${BULAN[b1]} ${t1}`
  if (t1 !== t2) return `${h1} ${BULAN[b1]} ${t1} – ${h2} ${BULAN[b2]} ${t2}`
  if (b1 !== b2) return `${h1} ${BULAN[b1]} – ${h2} ${BULAN[b2]} ${t2}`
  return `${h1}–${h2} ${BULAN[b2]} ${t2}`
}

// Pilihan di daftar minggu atau bulan, terbaru lebih dulu. Hanya periode yang menyentuh data yang dimuat.
export function daftarPeriode(mode, batas) {
  const hasil = []
  let acuan = mode === 'minggu' ? senin(batas.akhir) : awalBulan(batas.akhir)
  while (rentangPenuh(mode, acuan).sampai >= batas.mulai && hasil.length < 160) {
    hasil.push({ nilai: acuan, label: judulPeriode(mode, acuan) })
    acuan = geser(mode, acuan, -1)
  }
  return hasil
}

// Kunci pilihan daftar untuk tanggal mana pun di dalam periode
export const kunciPeriode = (mode, acuan) => (mode === 'minggu' ? senin(acuan) : mode === 'bulan' ? awalBulan(acuan) : acuan)
