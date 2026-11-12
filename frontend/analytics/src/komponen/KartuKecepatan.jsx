import { Kartu } from './Kartu'
import { angka } from '../lib/data'

const desimal = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const hariBulat = (x) => (x == null ? '–' : `${angka.format(Math.round(x))} hari`)
const persen = (x) => (x == null ? '–' : `${desimal.format(x * 100)}%`)

// Dua kartu untuk GridKartu, tentang PR/PO yang dibuat pada periode. Aturan lengkapnya di README.
export default function KartuKecepatan({ kecepatan, satuan }) {
  const k = kecepatan
  const s = k.selesai_periode
  return (
    <>
      <Kartu
        judul="Kecepatan Penyelesaian"
        nilai={hariBulat(k.rata_rata)}
        info={`rata-rata lama ${satuan} yang dibuat dalam periode sampai selesai`}
      />
      <Kartu
        judul="Completion Rate per Period"
        nilai={persen(s.persen)}
        catatan={`${angka.format(s.jumlah)} dari ${angka.format(s.dari)} ${satuan}`}
        info={`${satuan} yang dibuat dalam periode dan sudah selesai; tanpa Void, Closed, dan tanggal janggal`}
      />
    </>
  )
}
