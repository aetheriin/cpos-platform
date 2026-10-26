export const WARNA = { awal: '#7dd3fc', akhir: '#0369a1', pr: '#f59e0b', po: '#10b981' }

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
