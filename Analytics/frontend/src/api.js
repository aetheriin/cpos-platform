
export class GalatApi extends Error {
  constructor(pesan, status) {
    super(pesan)
    this.status = status
  }
}

// Didaftarkan App: jawaban 401 di tengah pemakaian (sesi CPOS berakhir) menampilkan pesan dari server.
let saatSesiHabis = null
export const aturSesiHabis = (fn) => {
  saatSesiHabis = fn
}

// Aplikasi berada di bawah base (mis. /analytics/), jadi /api/... dipanggil sebagai /analytics/api/...
const DASAR = import.meta.env.BASE_URL.replace(/\/$/, '')
export const alamatApi = (url) => (url.startsWith('/') ? DASAR + url : url)

async function ambilRespons(url, opsi = {}) {
  const { tanpa401, ...opsiFetch } = opsi // tanpa401: panggilan cek sesi, 401-nya bukan "sesi berakhir"
  const res = await fetch(alamatApi(url), { credentials: 'same-origin', cache: 'no-store', ...opsiFetch })
  if (!res.ok) {
    let pesan = `Terjadi kesalahan (${res.status})`
    let dariServer // pesan yang benar-benar ditulis server; kosong kalau jawabannya tidak membawa pesan (mis. dari proxy)
    try {
      const isi = await res.json()
      if (typeof isi.detail === 'string') pesan = dariServer = isi.detail
    } catch {
      // abaikan, pakai pesan bawaan
    }
    if (res.status === 401 && !tanpa401 && saatSesiHabis) saatSesiHabis(dariServer)
    throw new GalatApi(pesan, res.status)
  }
  return res
}

async function ambilJson(url, opsi) {
  return (await ambilRespons(url, opsi)).json()
}

export const sayaSendiri = () => ambilJson('/api/auth/saya', { tanpa401: true })

export const daftarLaporan = () => ambilJson('/api/laporan')

// segarkan: jalankan SQL lagi walau periode ini sudah dimuat
export const mulaiMuat = (laporanId, mulai, akhir, segarkan = false) =>
  ambilJson(`/api/laporan/${encodeURIComponent(laporanId)}/muat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(segarkan ? { mulai, akhir, segarkan: true } : { mulai, akhir }),
  })

export const statusPekerjaan = (pekerjaanId) => ambilJson(`/api/pekerjaan/${encodeURIComponent(pekerjaanId)}`)

export const batalkanPekerjaan = (pekerjaanId) =>
  ambilJson(`/api/pekerjaan/${encodeURIComponent(pekerjaanId)}/batal`, { method: 'POST' })

// Semua isian berupa daftar dikirim sebagai parameter yang diulang: perusahaan=SUN&perusahaan=YBS
function paramFilter(dataId, filter) {
  const p = new URLSearchParams()
  p.set('data_id', dataId)
  if (filter.jumlahMinggu != null) p.set('jumlah_minggu', String(filter.jumlahMinggu)) // laporan tanpa minggu tidak mengirimnya
  if (filter.minggu != null) p.set('minggu', String(filter.minggu))
  if (filter.dari && filter.sampai) {
    p.set('dari', filter.dari) // rentang tampilan di dalam data yang dimuat (laporan mingguan); menggantikan jumlah_minggu
    p.set('sampai', filter.sampai)
  }
  for (const [nama, nilai] of Object.entries(filter)) {
    if (Array.isArray(nilai)) nilai.forEach((v) => p.append(nama, v))
  }
  return p
}

export const ambilDashboard = (laporanId, dataId, filter, sinyal) =>
  ambilJson(`/api/laporan/${encodeURIComponent(laporanId)}/dashboard?${paramFilter(dataId, filter)}`, { signal: sinyal })

export function ambilDetail(laporanId, dataId, filter, opsi, sinyal) {
  const p = paramFilter(dataId, filter)
  p.set('jenis', opsi.jenis)
  if (opsi.cari) p.set('cari', opsi.cari)
  if (opsi.urut) {
    p.set('urut', opsi.urut)
    p.set('arah', opsi.arah)
  }
  p.set('halaman', String(opsi.halaman))
  p.set('ukuran', String(opsi.ukuran))
  return ambilJson(`/api/laporan/${encodeURIComponent(laporanId)}/detail?${p}`, { signal: sinyal })
}

export function namaBerkas(header, cadangan = 'laporan.xlsx') {
  const m = /filename="?([^";]+)"?/i.exec(header ?? '')
  // eslint-disable-next-line no-control-regex
  const bersih = (m?.[1] ?? '').replace(/[\\/:*?"<>|\u0000-\u001f]+/g, '_').replace(/^[._]+/, '').trim()
  return bersih || cadangan
}

export function simpanBerkas(blob, nama) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nama
  a.rel = 'noopener'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export async function unduhDetail(laporanId, dataId, filter, opsi) {
  const p = paramFilter(dataId, filter)
  p.set('jenis', opsi.jenis)
  if (opsi.cari) p.set('cari', opsi.cari)
  if (opsi.urut) {
    p.set('urut', opsi.urut)
    p.set('arah', opsi.arah)
  }
  const res = await ambilRespons(`/api/laporan/${encodeURIComponent(laporanId)}/detail/export?${p}`)
  const nama = namaBerkas(res.headers?.get?.('Content-Disposition'))
  simpanBerkas(await res.blob(), nama)
  return nama
}

export const statusServer = () => ambilJson('/api/status', { tanpa401: true })
