// Aturan warna grafik Analytics. Semua warna minimal kontras 3:1 di latar putih.
// - Biru #0369a1: seri utama, peringkat, nilai yang dibaca. Biru muda #7dd3fc: titik awal atau tahun lalu.
// - Oranye #d97706: seri kedua (uang keluar, PR, forecast). Oranye tua #ea580c hanya di PO Amount.
// - Hijau/merah hanya untuk naik/turun atau baik/buruk. Teal #0d9488/#0f766e untuk kelompok ketiga (PO, tara berat).
// - Abu-abu (slate): garis bantu, rata-rata, target, "lainnya". PALET (lib/data.js) untuk banyak seri: biru, teal, slate, satu amber.
export const WARNA = { awal: '#7dd3fc', akhir: '#0369a1', pr: '#d97706', po: '#0d9488' }

export const GARIS_PR_PO = [
  { kunci: 'new_pr', nama: 'New PR', warna: WARNA.pr },
  { kunci: 'new_po', nama: 'New PO', warna: WARNA.po },
]
export const GARIS_PI_GT = [
  { kunci: 'new_pi', nama: 'Barang di-PI', warna: WARNA.pr },
  { kunci: 'new_gt', nama: 'Barang di-GT', warna: WARNA.po },
]
export const GARIS_PO_PI = [
  { kunci: 'new_po', nama: 'New PO', warna: WARNA.pr },
  { kunci: 'new_pi', nama: 'New PI', warna: WARNA.po },
]
