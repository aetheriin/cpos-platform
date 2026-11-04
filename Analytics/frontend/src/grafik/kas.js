// Format uang laporan Cash Flow, selalu angka lengkap. satuan: 'IDR' (Rp) atau 'USD'.
const penuh = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 })
const bulat = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })

export const uangPenuh = (v, satuan = 'IDR') => (v == null ? '–' : `${satuan === 'USD' ? 'USD ' : 'Rp '}${penuh.format(v)}`)

// Sumbu grafik: angka lengkap tanpa awalan mata uang dan tanpa sen
export const sumbuUang = (v) => bulat.format(v)

export const WARNA_MASUK = '#0369a1'
export const WARNA_KELUAR = '#d97706'
