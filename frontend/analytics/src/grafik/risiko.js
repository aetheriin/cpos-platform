// NORMAL abu-abu supaya mata langsung ke WARNING; dua warna WARNING berbeda terang-gelapnya agar tetap terbedakan saat ditumpuk.
export const WARNA_RISIKO = { normal: '#94a3b8', tara: '#f59e0b', durasi: '#b45309' }
export const warnaRisiko = (kunci) => WARNA_RISIKO[kunci] ?? '#94a3b8'

// Arah selisih tara: lebih ringan dari historis (netto tercatat lebih berat) atau lebih berat (netto lebih ringan)
export const WARNA_TARA_RINGAN = '#b91c1c'
export const WARNA_TARA_BERAT = '#0f766e'

export const redup = (terpilih, nilai) => (terpilih.length > 0 && !terpilih.includes(nilai) ? 0.25 : 1)
