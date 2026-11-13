import { angka } from '../../lib/data'
import LaporanStatus, { hari } from '../../komponen/LaporanStatus'

const kartu = (k) => [
  { judul: 'Belum PO', nilai: `${angka.format(k.belum)} PR`, catatan: `${angka.format(k.baris_belum)} baris barang` },
  { judul: `Belum PO > ${k.ambang} hari`, nilai: angka.format(k.belum_lama), catatan: 'dokumen PR' },
  { judul: 'Belum PO paling lama', nilai: k.umur_maks == null ? 'tidak ada' : `${angka.format(k.umur_maks)} hari` },
  { judul: 'PO sebagian', nilai: `${angka.format(k.sebagian)} PR`, catatan: `${angka.format(k.baris_sebagian)} baris barang`,
    info: 'Sebagian qty PR sudah dibuatkan PO, sisanya belum' },
  { judul: 'Sudah PO', nilai: `${angka.format(k.sudah)} PR`, catatan: `${angka.format(k.baris_sudah)} baris barang` },
  { judul: 'PR sampai PO', nilai: hari(k.lama.median), catatan: k.lama.rata == null ? '' : `rata-rata ${hari(k.lama.rata)}`,
    info: 'nilai tengah hari dari PR dibuat sampai PO pertama' },
]

const TABEL = [
  { judul: 'PR belum selesai', tab: [
    { kunci: 'belum', nama: 'Belum PO', ket: () => 'PR yang belum dibuatkan PO. Yang paling lama di atas.' },
    { kunci: 'sebagian', nama: 'PO sebagian', ket: () => 'PR yang baru sebagian qty-nya dibuatkan PO.' },
  ] },
  { judul: 'PR selesai', tab: [
    { kunci: 'sudah', nama: 'Sudah PO', ket: () => 'PR yang sudah dibuatkan PO, yang terbaru di atas.' },
    { kunci: 'ditutup', nama: 'Ditutup tanpa PO', ket: () => 'PR yang ditutup atau selesai tanpa PO.' },
  ] },
]

const FILTER = [{ kunci: 'kategori', nama: 'Kategori' }, { kunci: 'buyer', nama: 'Buyer' }]

export default function LaporanPurchaseRequest(props) {
  return <LaporanStatus {...props} laporanId="purchase_request" judul="Purchase Request" teksTanggal="Tanggal PR" kartu={kartu} tabel={TABEL} filterTambahan={FILTER} />
}
