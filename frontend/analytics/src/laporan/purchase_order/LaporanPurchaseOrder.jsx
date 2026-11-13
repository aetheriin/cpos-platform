import { angka } from '../../lib/data'
import LaporanStatus, { hari, rupiah, rupiahPenuh } from '../../komponen/LaporanStatus'

const kartu = (k) => {
  const valas = k.valas ? ` PO valas (${angka.format(k.valas)} dokumen) tidak ikut dijumlahkan.` : ''
  return [
    { judul: 'Belum PI', nilai: rupiah(k.nilai_belum), catatan: `${angka.format(k.belum)} dokumen PO`, info: `total Line Total, ${rupiahPenuh.format(k.nilai_belum)}.${valas}` },
    { judul: `Belum PI > ${k.ambang} hari`, nilai: angka.format(k.belum_lama), catatan: 'dokumen PO' },
    { judul: 'Belum PI paling lama', nilai: k.umur_maks == null ? 'tidak ada' : `${angka.format(k.umur_maks)} hari` },
    { judul: 'PI sebagian', nilai: rupiah(k.nilai_sebagian), catatan: `${angka.format(k.sebagian)} dokumen PO`,
      info: `Sudah ada PI, tapi barangnya belum diterima semua. Total ${rupiahPenuh.format(k.nilai_sebagian)}` },
    { judul: 'Sudah PI', nilai: rupiah(k.nilai_sudah), catatan: `${angka.format(k.sudah)} dokumen PO`, info: `total Line Total, ${rupiahPenuh.format(k.nilai_sudah)}` },
    { judul: 'PO sampai PI', nilai: hari(k.lama.median), catatan: k.lama.rata == null ? '' : `rata-rata ${hari(k.lama.rata)}`,
      info: 'nilai tengah hari dari PO dibuat sampai PI pertama' },
  ]
}

const TABEL = [
  { judul: 'PO belum selesai', tab: [
    { kunci: 'belum', nama: 'Belum PI', ket: () => 'PO yang belum dibuatkan PI. Yang paling lama di atas.' },
    { kunci: 'sebagian', nama: 'PI sebagian', ket: () => 'PO yang sudah ada PI, tapi barangnya belum diterima semua.' },
  ] },
  { judul: 'PO selesai', tab: [
    { kunci: 'sudah', nama: 'Sudah PI', ket: () => 'PO yang sudah dibuatkan PI, yang terbaru di atas.' },
    { kunci: 'ditutup', nama: 'Ditutup tanpa PI', ket: () => 'PO yang ditutup atau selesai tanpa PI.' },
  ] },
]

const FILTER = [{ kunci: 'kategori', nama: 'Kategori' }, { kunci: 'supplier', nama: 'Supplier' }, { kunci: 'pembuat', nama: 'Dibuat oleh' }]

export default function LaporanPurchaseOrder(props) {
  return <LaporanStatus {...props} laporanId="purchase_order" judul="Purchase Orders" teksTanggal="Tanggal PO dibuat" kartu={kartu} tabel={TABEL} filterTambahan={FILTER} />
}
