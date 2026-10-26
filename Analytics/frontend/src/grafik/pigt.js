// Biru tua = rata-rata, abu-abu gelap = median; dipakai di kedua grafik durasi supaya artinya sama.
export const WARNA_RATA = '#0369a1'
export const WARNA_MEDIAN = '#334155'

const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
// "2026-03" -> "Mar 2026"
export const labelBulan = (ym) => `${BULAN[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}`
