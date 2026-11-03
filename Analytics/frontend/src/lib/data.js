export const angka = new Intl.NumberFormat('id-ID')
export const persen = (x) => `${(x * 100).toFixed(1).replace('.', ',')}%`

// Item terpilih yang tidak masuk teratas tetap ditambahkan, supaya pilihan aktif selalu terlihat.
export function teratas(daftar, batas, terpilih, kunci) {
  const pilih = Array.isArray(terpilih) ? terpilih : terpilih ? [terpilih] : []
  const atas = daftar.slice(0, batas)
  for (const p of pilih) {
    if (!atas.some((d) => d[kunci] === p)) {
      const s = daftar.find((d) => d[kunci] === p)
      if (s) atas.push(s)
    }
  }
  return atas
}

export function potong(teks, maks) {
  return teks.length > maks ? teks.slice(0, maks - 1) + '…' : teks
}

// Warna ditentukan urutan item di daftar pilihan, bukan oleh filter, supaya tidak bergeser.
// Palet seri (perusahaan, pembuat, kategori): keluarga biru, teal, dan slate dengan satu aksen hangat (amber), dibedakan lewat terang-gelap,
// bukan lewat banyak warna yang jauh berbeda. Merah dan hijau disimpan untuk arti (risiko, naik/turun).
// Semua cukup gelap untuk garis tipis di latar putih (kontras minimal sekitar 3:1).
export const PALET = ['#0369a1', '#0d9488', '#d97706', '#64748b', '#0284c7', '#1e3a8a', '#0f766e', '#475569', '#0e7490', '#b45309', '#2563eb', '#334155']
export const warna = (indeks) => PALET[((indeks % PALET.length) + PALET.length) % PALET.length]
export const WARNA_LAINNYA = '#cbd5e1'

export function itemDonat(daftar, batas, terpilih) {
  const atas = teratas(daftar, batas, terpilih, 'kategori')
  const total = daftar.reduce((a, d) => a + d.jumlah, 0)
  const sisa = total - atas.reduce((a, d) => a + d.jumlah, 0)
  const item = atas.map((d, i) => ({ kategori: d.kategori, jumlah: d.jumlah, warna: warna(i), lainnya: false }))
  if (sisa > 0) item.push({ kategori: 'Lainnya', jumlah: sisa, warna: WARNA_LAINNYA, lainnya: true })
  return { item, total }
}

// iso: 'YYYY-MM-DD'
export const tgl = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
export const tglLengkap = (iso) => `${tgl(iso)}/${iso.slice(0, 4)}`

// "18 Sep – 21 Okt 2026"; tahun awal hanya ditulis kalau beda dengan tahun akhir.
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const tglBulan = (iso) => `${Number(iso.slice(8, 10))} ${BULAN[Number(iso.slice(5, 7)) - 1]}`
export const rentangTgl = (mulai, akhir) =>
  `${tglBulan(mulai)}${mulai.slice(0, 4) === akhir.slice(0, 4) ? '' : ` ${mulai.slice(0, 4)}`} – ${tglBulan(akhir)} ${akhir.slice(0, 4)}`

export const labelSingkat = (w) => `${tgl(w.mulai)}-${tgl(w.akhir)}`

export const tahunRentang = (w) => {
  const a = w.mulai.slice(0, 4)
  const b = w.akhir.slice(0, 4)
  return a === b ? a : `${a}/${b}`
}

export const labelLengkap = (w) => `${tglLengkap(w.mulai)} - ${tglLengkap(w.akhir)}`

// Periode yang membawa label sendiri (mis. bulan "Sep" dan "2026" di PI & GT) memakai label itu
export const barisMinggu = (mingguan) =>
  mingguan.map((w) => ({
    ...w,
    singkat: w.singkat ?? labelSingkat(w),
    tahun: w.tahun ?? tahunRentang(w),
    lengkap: labelLengkap(w),
  }))

// Lebih dari jumlah minggu ini, label sumbu diputar miring supaya tidak bertumpuk
export const BATAS_PADAT = 8
export const BATAS_PADAT_KECIL = 5   // grafik setengah lebar

// interval sumbu X Recharts: lebih dari `maks` titik, hanya sebagian label yang ditulis
export const jedaLabel = (jumlah, maks) => (jumlah > maks ? Math.ceil(jumlah / maks) - 1 : 0)

// Deret harian yang melewati pergantian tahun: label perlu tahun supaya 01/01 tidak ambigu
export const lintasTahun = (deret) => deret.length > 0 && deret[0].hari.slice(0, 4) !== deret.at(-1).hari.slice(0, 4)

// Klik biasa: hanya nilai itu (klik lagi mengosongkan). tambah (Ctrl/Cmd/Shift): tambahkan atau buang nilai itu.
export function ubahPilihan(saatIni, nilai, tambah) {
  const ada = saatIni.includes(nilai)
  if (tambah) return ada ? saatIni.filter((v) => v !== nilai) : [...saatIni, nilai]
  return ada && saatIni.length === 1 ? [] : [nilai]
}

export const tambahDariEvent = (e) => Boolean(e && (e.ctrlKey || e.metaKey || e.shiftKey))

export function saringOpsi(opsi, teks) {
  const kecil = teks.trim().toLowerCase()
  return kecil ? opsi.filter((o) => o.toLowerCase().includes(kecil)) : opsi
}

const formatAngka = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 })

export function formatSel(nilai, tipe) {
  if (nilai === null || nilai === undefined || nilai === '') return '–'
  if (tipe === 'tanggal') return tglLengkap(nilai)
  if (tipe === 'waktu') return `${tglLengkap(nilai)} ${nilai.slice(11, 16)}`
  if (typeof nilai === 'number') return formatAngka.format(nilai)
  return String(nilai)
}

export function rentangBaris(halaman, ukuran, total) {
  if (total === 0) return { dari: 0, sampai: 0 }
  return { dari: (halaman - 1) * ukuran + 1, sampai: Math.min(halaman * ukuran, total) }
}

export const selisihHari = (mulai, akhir) => Math.round((new Date(akhir + 'T00:00:00Z') - new Date(mulai + 'T00:00:00Z')) / 86400000)

// Pesan kesalahan, atau null kalau sah. maks (hari) dari server; kosong = tidak diperiksa di sini, server tetap menolak.
export function periksaPeriode(mulai, akhir, maks) {
  if (!mulai || !akhir) return 'Isi tanggal mulai dan tanggal akhir.'
  if (mulai > akhir) return 'Tanggal mulai tidak boleh setelah tanggal akhir.'
  if (maks && selisihHari(mulai, akhir) > maks) return `Rentang terlalu panjang (maksimal ${maks} hari).`
  return null
}

export const jamDari = (iso) => new Date(iso).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })

// Dua desimal untuk angka kecil seperti PO partial: 0,65% tidak boleh jadi 0,7%
const duaDesimal = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const persenKecil = (x) => `${duaDesimal.format(x * 100)}%`

export const hariIni = (tanggal = new Date()) => tanggal.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

// Salam menurut jam: pagi 05.00-10.59, siang 11.00-14.59, sore 15.00-17.59, selain itu malam
export const salam = (tanggal = new Date()) => {
  const jam = tanggal.getHours()
  if (jam >= 5 && jam < 11) return 'Selamat Pagi'
  if (jam >= 11 && jam < 15) return 'Selamat Siang'
  if (jam >= 15 && jam < 18) return 'Selamat Sore'
  return 'Selamat Malam'
}

// Kartu KPI lawan periode sebelumnya. banding: { mulai, akhir, kpi } dari server, atau null.
// jenis 'relatif': persen dari nilai lalu; 'poin': selisih poin untuk nilai yang sudah berupa rasio. naikBaik null = tanpa warna.
const satuDesimal = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
export function bandingKpi(kini, banding, ambil, { jenis = 'relatif', naikBaik = null } = {}) {
  const lalu = banding ? ambil(banding.kpi) : null
  if (lalu == null || kini == null || (jenis === 'relatif' && lalu === 0)) return null
  const beda = jenis === 'poin' ? (kini - lalu) * 100 : ((kini - lalu) / Math.abs(lalu)) * 100
  const arah = Math.abs(beda) < 0.05 ? 0 : Math.sign(beda)
  const nada = arah === 0 || naikBaik === null ? 'netral' : (arah > 0) === naikBaik ? 'baik' : 'buruk'
  const angka = `${satuDesimal.format(Math.abs(beda))}${jenis === 'poin' ? ' poin' : '%'}`
  return {
    teks: arah === 0 ? 'tetap' : `${arah > 0 ? '▲' : '▼'} ${angka}`,
    nada,
    // tahun hanya ditulis kalau melintasi tahun atau bukan tahun ini
    periode:
      banding.mulai.slice(0, 4) === banding.akhir.slice(0, 4) && banding.akhir.slice(0, 4) === String(new Date().getFullYear())
        ? `${tgl(banding.mulai)}–${tgl(banding.akhir)}`
        : `${tglLengkap(banding.mulai)}–${tglLengkap(banding.akhir)}`,
    judul: `Periode sebelumnya ${tglLengkap(banding.mulai)} sampai ${tglLengkap(banding.akhir)}`,
  }
}
