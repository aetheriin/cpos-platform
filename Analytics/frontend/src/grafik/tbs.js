const ringkas = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const angka = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const ton = (kg) => `${satu.format(kg / 1000)} ton`
export const kgRingkas = (kg) => `${ringkas.format(kg)} kg`
export const rupiah = (x) => `Rp ${ringkas.format(x)}`
export const rupiahPenuh = (x) => `Rp ${angka.format(x)}`
export const hargaKg = (x) => (x == null ? '–' : `Rp ${angka.format(x)}/kg`)
export const sumbu = (x) => ringkas.format(x)
