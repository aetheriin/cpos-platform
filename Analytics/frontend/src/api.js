
export class GalatApi extends Error {
  constructor(pesan, status) {
    super(pesan)
    this.status = status
  }
}

// Didaftarkan App: jawaban 401 di tengah pemakaian kembali ke halaman masuk dengan pesan dari server.
let saatSesiHabis = null
export const aturSesiHabis = (fn) => {
  saatSesiHabis = fn
}

// Aplikasi berada di bawah base (mis. /analytics/), jadi /api/... dipanggil sebagai /analytics/api/...
const DASAR = import.meta.env.BASE_URL.replace(/\/$/, '')
export const alamatApi = (url) => (url.startsWith('/') ? DASAR + url : url)

async function ambilRespons(url, opsi = {}) {
  const { tanpa401, ...opsiFetch } = opsi // tanpa401: panggilan login/cek sesi, 401-nya bukan "sesi berakhir"
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

export const masuk = (username, sandi) =>
  ambilJson('/api/auth/masuk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, sandi }),
    tanpa401: true,
  })

export const keluar = () => ambilJson('/api/auth/keluar', { method: 'POST', tanpa401: true })

export const gantiSandi = (sandiLama, sandiBaru) =>
  ambilJson('/api/auth/ganti-sandi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sandi_lama: sandiLama, sandi_baru: sandiBaru }),
  })

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

export const daftarPengguna = () => ambilJson('/api/admin/pengguna')

export const opsiPengguna = () => ambilJson('/api/admin/opsi')

export const tambahPengguna = (data) =>
  ambilJson('/api/admin/pengguna', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

export const ubahPengguna = (id, data) =>
  ambilJson(`/api/admin/pengguna/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

export const hapusPengguna = (id) => ambilJson(`/api/admin/pengguna/${encodeURIComponent(id)}`, { method: 'DELETE' })

export const daftarStruktur = () => ambilJson('/api/admin/struktur')

const kirimJson = (url, data) => ambilJson(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
export const tambahDivisi = (data) => kirimJson('/api/admin/divisi', data)
export const tambahRole = (data) => kirimJson('/api/admin/role', data)

export const daftarIzin = () => ambilJson('/api/admin/izin')

export const aturIzin = ({ role, laporan, akses }) =>
  ambilJson('/api/admin/izin', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role, laporan, akses }),
  })

// Isian opsi yang kosong tidak dikirim
export function ambilAktivitas(opsi, sinyal) {
  const p = new URLSearchParams(Object.entries(opsi).filter(([, v]) => v !== '' && v != null).map(([k, v]) => [k, String(v)]))
  return ambilJson(`/api/admin/aktivitas?${p}`, { signal: sinyal })
}

export const daftarSesi = (sinyal) => ambilJson('/api/admin/sesi', { signal: sinyal })
export const cabutSesi = (id) => ambilJson(`/api/admin/sesi/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const ambilPengaturanSesi = () => ambilJson('/api/admin/pengaturan/sesi')
export const simpanPengaturanSesi = (idleMenit) =>
  ambilJson('/api/admin/pengaturan/sesi', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idle_menit: idleMenit }) })

// Lihat lib/idle.js
export const tandaAktif = () => ambilJson('/api/auth/aktif', { method: 'POST' })

export const statusServer = () => ambilJson('/api/status', { tanpa401: true })
