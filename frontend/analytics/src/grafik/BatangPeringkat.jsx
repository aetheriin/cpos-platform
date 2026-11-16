import { memo } from 'react'
import Peringkat from './Peringkat'
import { hargaKg, kgRingkas } from './tbs'
import { Kosong } from '../komponen/Keadaan'

// Peringkat netto (tipe, business group, supplier) dengan harga rata-rata di kanan nama. Bentuknya dari Peringkat, sama dengan laporan lain.
function BatangPeringkat({ data, terpilih, onPilih, warna = '#0369a1', keterangan }) {
  const baris = data.map((d) => ({ nama: d.nama, nilai: d.netto, teks: kgRingkas(d.netto), kanan: hargaKg(d.harga),
    judul: `${d.nama}: ${kgRingkas(d.netto)}, harga rata-rata ${hargaKg(d.harga)}` }))
  return <Peringkat data={baris} terpilih={terpilih} onPilih={onPilih} warna={warna} catatan={keterangan}
    kosong={<Kosong teks="Tidak ada pembelian pada periode dan filter ini" />} />
}

export default memo(BatangPeringkat)
