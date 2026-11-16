// Garis besar tiap laporan untuk ikon ⓘ di judul, dicari dari judul halaman.
export const CARA_FILTER = 'Klik grafik atau baris tabel untuk memfilter, tahan Ctrl untuk memilih lebih dari satu.'

export const TENTANG = {
  'PR & PO Outstanding': 'PR yang belum menjadi PO dan lama prosesnya. Periode dan aging memakai tanggal PR dibuat.',
  'PO & PI Outstanding': 'PO yang belum dibuatkan PI. Periode dan aging memakai tanggal PO dibuat; lama proses dari tanggal PO sampai PI terakhir.',
  'PO Spend Analysis': 'Nilai belanja PO dalam rupiah per kategori, bulan, dan supplier. Kurs kosong atau janggal diganti kurs terdekat.',
  'PI & GT': 'Barang yang sudah di-PI tapi belum diterima gudang tujuan lewat GT, beserta lead time-nya.',
  'PVR KPI': 'Skor pembuat PVR per bulan menurut kategori dan bobotnya, sama dengan Excel Penilaian PVR.',
  'PV KPI': 'Skor kasir pembuat PV hutang per bulan, aturannya sama dengan PVR KPI dengan bobot PV.',
  'Weighbridge Fraud Early Detector': 'Tiket timbang sawit yang janggal, misalnya tara menyimpang dari riwayat kendaraan atau durasi tidak wajar.',
  'Tiket Penjualan': 'Tiket timbang produk keluar per hari, minggu, atau bulan, dengan peringkat produk, pengangkut, dan pembeli.',
  'Pembelian TBS Mingguan': 'Tonase TBS per business group per minggu lengkap (Senin sampai Minggu), dengan tanda naik atau turun yang tidak biasa.',
  'Forecast Penerimaan TBS': 'Penerimaan TBS harian dan perkiraan 7 hari ke depan, per supplier dan kebun.',
  'Bank Statement': 'Saldo berjalan, mutasi harian, dan jasa giro per rekening. Debit uang masuk, kredit uang keluar.',
  'Purchase Request': 'Tiap baris PR dengan status belum, sebagian, atau sudah dibuatkan PO.',
  'Purchase Orders': 'Tiap baris PO dengan status belum, sebagian, atau sudah dibuatkan PI.',
  'Purchase Invoice': 'PI yang belum punya PVR atau PV, yang dibayar PV tanpa PVR, dan yang sudah PVR.',
  Outstanding: 'Hutang dan piutang yang belum lunas. Periode dan aging memakai tanggal dokumen, dihitung sampai hari ini.',
}
