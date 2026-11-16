import { memo } from 'react'
import Peringkat from './Peringkat'
import { angka } from '../lib/data'

const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const NBSP = String.fromCharCode(160) // angka dan satuannya tidak terpisah ke baris lain

// Peringkat berat (produk, pengangkut, pembeli) dalam ton. lainnya: { jumlah, netto } untuk nama di luar peringkat.
function BatangTonase({ data, terpilih, onPilih, warna = '#0369a1', persen = false, lainnya = null, satuanLain = 'lainnya', kosong }) {
  const baris = data.map((d) => ({
    nama: d.nama,
    nilai: d.netto,
    teks: `${satu.format(d.netto / 1000)}${NBSP}ton`,
    judul: `${d.nama}: ${satu.format(d.netto / 1000)} ton dalam ${angka.format(d.rit)} pengiriman` + (persen ? `, ${satu.format(d.persen * 100)}% dari total berat` : ''),
  }))
  const catatan = lainnya ? `+${angka.format(lainnya.jumlah)} ${satuanLain} lain, ${satu.format(lainnya.netto / 1000)} ton` : null
  return <Peringkat data={baris} terpilih={terpilih} onPilih={onPilih} warna={warna} kosong={kosong} catatan={catatan} />
}

export default memo(BatangTonase)
