# Rencana Penghapusan Master Supplier/Product Lokal CPOS

Status: audit awal pada branch `feature/ascend-master-data-only`. Dokumen ini bukan izin untuk menjalankan DROP di database produksi.

## Prinsip

- Ascend menjadi sumber master customer, supplier/pengangkutan, dan produk.
- CPOS tidak membuat/mengedit master supplier atau produk lokal dan tidak fallback ke master lokal.
- Histori tiket/transaksi lama dipertahankan; label historis harus disimpan sebagai snapshot atau dipetakan ke ID eksternal.
- Tidak menghapus tabel sebelum seluruh FK, query, API, UI, laporan, dan data historis selesai dipindahkan.
- Semua perubahan hanya di branch fitur. Tidak merge ke main.

## Dependensi yang ditemukan (audit awal)

### Kontrak / Delivery Order
- `backend/cpos/utils/db_kontrak.py`: SELECT kontrak join Supplier/Product; DOTransport join Supplier; daftar mitra membaca SupplierTypeDetails; fungsi `id_pengangkutan_dari_nama` membuat Supplier lokal dan SupplierTypeDetails.
- `backend/cpos/routes/kontrak.py`: form memakai ID integer lokal `id_customer`, `id_produk`, `id_pengangkutan`; daftar produk lokal `get_semua_produk()`; validasi blacklist memakai supplier lokal.
- Tabel Contract/DOTransport perlu dirancang ulang untuk menyimpan ID Ascend + nama/kode snapshot, bukan FK Supplier/Product lokal.

### Blacklist
- `backend/cpos/utils/db_blacklist.py`: query riwayat dan transaksi personel join Supplier/Product; target SUPPLIER menggunakan Supplier lokal; customer/pengangkutan blacklist mengandalkan SupplierID lokal.
- `backend/cpos/routes/blacklist.py`: form dan validasi memakai ID mitra CPOS lokal (`mitra_aktif`, `info_supplier`).
- Perlu identitas eksternal Ascend (dan snapshot nama) serta migrasi data blacklist lama yang aman; tidak boleh menghapus catatan blacklist aktif.

### Timbangan / histori / laporan
- `backend/cpos/utils/db_utils.py`: fungsi master lokal `get_semua_supplier` dan `get_semua_produk`; beberapa query tiket/kontrak/vehicle-contract masih join Supplier/Product.
- Query historis harus menampilkan snapshot yang tersedia atau lookup Ascend yang terkontrol; jangan menghilangkan tiket lama jika master lokal dihapus.

### Skema
- `backend/cpos/database/schema.sql` masih mendefinisikan Supplier/Product dan relasi transaksi.
- Migrasi penghapusan final wajib memeriksa FK, indeks, view, stored procedure, trigger, dan seluruh kolom yang mengacu pada ID lokal. Tidak aman melakukan DROP hanya berdasarkan pencarian nama tabel di Python.

## Urutan implementasi wajib

1. **Inventaris penuh**: semua referensi Supplier/Product/TypeDetails/Company/Group di backend, frontend, SQL schema, migrasi, stored procedure, analytics, export, dan laporan.
2. **Kontrak data eksternal**: sepakati format ID Ascend (string/UUID), sumber endpoint, serta snapshot nama/kode untuk histori.
3. **Migrasi aditif**: tambahkan kolom Ascend ID dan snapshot; backfill hanya jika pemetaan dapat diverifikasi. Baris tidak terpetakan ditandai dan dilaporkan, bukan ditebak.
4. **Refactor Kontrak/DO**: master pilihan dari Ascend; pengangkutan pihak ketiga tidak membuat Supplier lokal. Simpan referensi eksternal/snapshot.
5. **Refactor Blacklist**: target supplier/customer/transport berbasis Ascend; histori blacklist lama tetap tersedia dan status aktif tidak hilang.
6. **Refactor transaksi dan laporan**: tiket, kontrak, vehicle contract, dashboard, export, analytics, dan pencarian histori bebas join ke master lokal.
7. **Hapus API/UI/cache lokal**: hilangkan endpoint, fungsi, form, dan cache Supplier/Product lokal serta SupplierTypeDetails.
8. **Audit SQL dan uji**: static search, compile/syntax, tes integrasi pada DB salinan; validasi row counts, FK, histori, dan alur tiket.
9. **Migrasi DROP final**: hanya setelah seluruh tahap di atas lulus; backup dan rollback script wajib. Jalankan oleh pemilik DB setelah uji.

## Status
Audit awal menunjukkan ketergantungan masih aktif pada Kontrak/DO dan Blacklist. Karena itu, tabel Supplier/Product belum aman di-DROP pada tahap ini.
