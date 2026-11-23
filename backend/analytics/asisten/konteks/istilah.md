# Buku konteks: istilah
<!-- Dibaca Asisten untuk pertanyaan "apa itu ...". Satu istilah per judul "## ". Baris "Sebutan:" berisi kata lain untuk istilah yang sama.
     Ubah isinya di sini; berlaku setelah backend Analytics dijalankan ulang. -->

## PR
Sebutan: purchase request, permintaan pembelian
Purchase Request: permintaan barang dari bagian yang membutuhkan. PR yang sudah disetujui dilanjutkan Purchasing menjadi PO. Di laporan, tiap baris barang PR punya status: Belum PO, PO sebagian, Sudah PO, atau Ditutup tanpa PO.

## PO
Sebutan: purchase order, pesanan pembelian
Purchase Order: pesanan resmi ke supplier, dibuat dari PR. Satu PO bisa memuat barang dari beberapa PR. Setelah barang diterima dan ditagih, PO dilanjutkan menjadi PI.

## PI
Sebutan: purchase invoice, faktur pembelian
Purchase Invoice: tagihan supplier yang dicatat dari PO. PI inilah yang menjadi hutang sampai dibayar dengan PV.

## PO sebagian
Sebutan: pi sebagian, diterima sebagian
Barang di satu baris PO diterima dan ditagih bertahap, jadi satu baris PO bisa punya banyak PI. Di laporan PR, "PO sebagian" berarti baru sebagian qty PR yang dibuatkan PO.

## PVR
Sebutan: payment voucher request
Payment Voucher Request: pengajuan pembayaran hutang. PVR perlu disetujui (approve), lalu dibayar dengan PV. Hutang yang sudah masuk PVR tetap dihitung hutang sampai PV-nya dibuat.

## PV
Sebutan: payment voucher
Payment Voucher: bukti pembayaran hutang. PV yang tanggalnya di masa depan dihitung "PV tanggal ke depan": sudah dijadwalkan, tapi belum jatuh tempo.

## RV
Sebutan: receipt voucher
Receipt Voucher: bukti penerimaan pembayaran piutang dari customer.

## Hutang
Sebutan: utang, outstanding hutang, ap
Sisa tagihan supplier yang belum lunas, dihitung dari semua sumber tagihan (PI, nota, tiket TBS, ongkos angkut, dan lainnya), dalam rupiah. Dokumen valas dikalikan kurs dokumen; kalau tidak ada, kurs cadangan.

## Piutang
Sebutan: ar, outstanding piutang
Sisa tagihan ke customer yang belum diterima, dalam rupiah.

## Status hutang
Sebutan: belum pvr, pvr pending, pvr sebagian
Belum PVR: belum diajukan sama sekali. PVR sebagian: baru sebagian yang diajukan. PVR pending: sudah diajukan, menunggu PV. PV tanggal ke depan: sudah ada PV tapi tanggalnya belum tiba.

## Aging
Sebutan: umur dokumen, umur
Umur dokumen dalam hari sejak tanggal dokumen. Kelompoknya: Tepat Waktu (0 sampai 8 hari), Perlu Perhatian (9 sampai 15), Telat (16 sampai 30), Perlu Tindakan (lebih dari 30).

## Void
Dokumen yang dibatalkan di ERP. Tidak ikut dihitung di laporan mana pun.

## GT
Sebutan: goods transfer, transfer gudang
Pemindahan barang antar gudang. Barang yang dibeli lewat HO untuk gudang lain perlu di-GT ke gudang peminta; laporan PI & GT memantau yang belum.

## Buyer
Orang Purchasing yang membuat PO dari PR. Di laporan Purchase Request, satu baris PR bisa punya beberapa buyer kalau dipecah ke beberapa PO.

## TBS
Sebutan: tandan buah segar, ffb
Tandan Buah Segar kelapa sawit yang dibeli dan ditimbang di timbangan pabrik.

## Tara
Berat kendaraan kosong. Netto = bruto (kendaraan berisi) dikurangi tara.

## Kurs
Nilai tukar untuk dokumen valas. Urutannya: kurs di dokumen ERP, lalu kurs tahunan, lalu kurs dari internet. Dokumen tanpa kurs ditandai di laporan.

## Aging PR
Sebutan: umur pr, aging purchase request, aging pr belum po
Hari dari tanggal PR sampai hari ini, dihitung per baris barang. Di kartu dan daftar, satu PR memakai umur barangnya yang paling tua. Kelompoknya sama dengan dokumen lain: Tepat Waktu (0 sampai 8 hari), Perlu Perhatian (9 sampai 15), Telat (16 sampai 30), Perlu Tindakan (lebih dari 30). Lama PR sampai jadi PO itu ukuran lain: tanggal PO pertama dikurangi tanggal PR.

## Aging PO
Sebutan: umur po, aging purchase order, aging po belum pi
Hari dari tanggal PO dibuat sampai hari ini, per baris PO. Lama PO sampai jadi PI dihitung terpisah: tanggal PI pertama dikurangi tanggal PO dibuat.

## Aging hutang
Sebutan: umur hutang, aging piutang, umur piutang, aging outstanding
Hari dari tanggal dokumen tagihan (PI, nota, tiket) sampai hari ini, hanya untuk dokumen yang masih punya sisa.

## Netto
Sebutan: berat bersih, cara hitung netto
Berat muatan sebenarnya: bruto (kendaraan berisi) dikurangi tara (kendaraan kosong).

## Bruto
Sebutan: berat kotor
Berat kendaraan bersama muatannya saat ditimbang masuk atau keluar.

## Business group
Sebutan: grup supplier, bg
Pengelompokan supplier TBS yang dipakai laporan Pembelian TBS Mingguan untuk melihat tonase per grup.

## Forecast
Sebutan: perkiraan, prediksi
Perkiraan penerimaan TBS 7 hari ke depan di laporan Forecast Penerimaan TBS, dihitung dari penerimaan hari-hari sebelumnya.

## Jasa giro
Sebutan: bunga giro
Bunga yang diberikan bank atas saldo rekening giro, terlihat di laporan Bank Statement.

## Running balance
Sebutan: saldo berjalan
Saldo rekening setelah tiap mutasi, dihitung berurutan dari saldo awal di laporan Bank Statement.

## Lead time
Sebutan: lama proses
Lama dari satu tahap ke tahap berikutnya, misalnya PR ke PO, PO ke PI, atau PI ke GT, dalam hari.

## PO Spend
Sebutan: spend analysis, belanja po
Nilai belanja PO dalam rupiah, dipakai laporan PO Spend Analysis untuk melihat nilai per kategori, bulan, dan supplier.
