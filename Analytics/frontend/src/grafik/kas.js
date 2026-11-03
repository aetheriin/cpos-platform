// Format uang laporan Kas & Bank. satuan: 'IDR' (Rp) atau 'USD'.
const ringkas = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const penuh = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 })

export function uangRingkas(v, satuan = 'IDR') {
  if (v == null) return '–'
  const a = Math.abs(v)
  const tanda = v < 0 ? '−' : ''
  const [n, akhiran] = a >= 1e12 ? [a / 1e12, ' T'] : a >= 1e9 ? [a / 1e9, ' M'] : a >= 1e6 ? [a / 1e6, ' jt'] : a >= 1e3 ? [a / 1e3, ' rb'] : [a, '']
  return `${tanda}${satuan === 'USD' ? 'USD ' : 'Rp '}${ringkas.format(n)}${akhiran}`
}

export const uangPenuh = (v, satuan = 'IDR') => (v == null ? '–' : `${satuan === 'USD' ? 'USD ' : 'Rp '}${penuh.format(v)}`)

// Sumbu grafik: tanpa awalan mata uang supaya ringkas
export const sumbuUang = (v) => uangRingkas(v).replace('Rp ', '')

export const WARNA_MASUK = '#0369a1'
export const WARNA_KELUAR = '#d97706'
