# Rencana Penghapusan Master Supplier/Product Lokal CPOS

Update 14 November 2026: skrip audit SQL 027 tersedia; migrasi persiapan Contract/DO 028 dibuat (belum dijalankan). 028 melepas FK lokal Contract/DOTransport dan membuat ID lokal Contract nullable; jalankan hanya setelah verifikasi backup dan urutan deploy kode.

Status: audit awal pada branch `feature/ascend-master-data-only`. Dokumen ini bukan izin untuk menjalankan DROP di database produksi.

## Prinsip

- Ascend menjadi sumber master customer, supplier/pengangkutan, dan produk.
- CPOS tidak membuat/mengedit master supplier atau produk lokal dan tidak fallback ke master lokal.
- Histori tiket/transaksi lama dipertahankan; label historis harus disimpan sebagai snapshot atau dipetakan ke ID eksternal.
- Tidak menghapus tabel sebelum seluruh FK, query, API, UI, laporan, dan data historis selesai dipindahkan.
- Semua perubahan hanya di branch fitur. Tidak merge ke main.

Update 14 November 2026: migration 029 menambah kode snapshot customer/produk/pengangkutan pada Contract/DOTransport (belum dijalankan). Ini additive dan tidak mengisi ID Ascend otomatis.\n\n## Dependensi yang ditemukan (audit awal)

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
- Skema Supplier lokal masih direferensikan oleh `VehicleContract`, `Contract`, `DOTransport`, `Invoice`, `WeightBridge`, dan `Blacklist`.
- Skema Product lokal masih direferensikan oleh `ProductPrice`, `VehicleContract`, `Contract`, `WeightBridge`, dan `FlowRule`. Kolom Product juga menyimpan standar FFA/Moisture/Dirt dan FlowID; aturan standar Lab serta pemetaan alur harus dipisahkan sebelum tabel Product bisa dihapus.

### Skema
- `backend/cpos/database/schema.sql` masih mempertahankan tabel transaksi yang ber-FK ke Supplier/Product. Definisi `SupplierCompany` dan `SupplierTypeDetails` dihapus dari schema, tetapi kode Kontrak/DO saat ini masih memanggil `SupplierTypeDetails`; dependensi runtime tersebut wajib direfaktor sebelum instalasi baru/cleanup dianggap selesai.
- `backend/cpos/config.py` menggunakan `DB_NAME` dengan default `Main`; karena itu migrasi bisnis harus menargetkan `Main`, bukan otomatis `CPOS`. Schema awal masih memakai nama database `CPOS`, sehingga jalur instalasi database harus diaudit terpisah.
- Migrasi DROP final wajib memeriksa FK, indeks, view, stored procedure, trigger, dan seluruh kolom yang mengacu pada ID lokal. Tidak aman melakukan DROP hanya berdasarkan pencarian nama tabel di Python.

## Urutan implementasi wajib

1. **Inventaris penuh**: semua referensi Supplier/Product/TypeDetails/Company/Group di backend, frontend, SQL schema, migrasi, stored procedure, analytics, export, dan laporan.
2. **Kontrak data eksternal**: sepakati format ID Ascend (string/UUID), sumber endpoint, serta snapshot nama/kode untuk histori.
3. **Migrasi aditif**: migrasi `026_ascend_master_reference_snapshots.sql` sudah ditambahkan. Migrasi ini membuat kolom ID Ascend opsional dan snapshot nama historis pada Contract, DOTransport, VehicleContract, Invoice, WeightBridge, Blacklist, ProductPrice, dan FlowRule. Backfill hanya menyalin nama lama dari tabel lokal; tidak mengarang/mencocokkan ID Ascend. Migrasi ini belum dijalankan atau diuji pada database pengguna.
4. **Refactor Kontrak/DO**: master pilihan dari Ascend; pengangkutan pihak ketiga tidak membuat Supplier lokal. Simpan referensi eksternal/snapshot.
5. **Refactor Blacklist**: target supplier/customer/transport berbasis Ascend; histori blacklist lama tetap tersedia dan status aktif tidak hilang.
6. **Refactor transaksi dan laporan**: tiket, kontrak, vehicle contract, dashboard, export, analytics, dan pencarian histori bebas join ke master lokal.
7. **Hapus API/UI/cache lokal**: hilangkan endpoint, fungsi, form, dan cache Supplier/Product lokal serta SupplierTypeDetails.
8. **Audit SQL dan uji**: static search, compile/syntax, tes integrasi pada DB salinan; validasi row counts, FK, histori, dan alur tiket.
9. **Migrasi DROP final**: hanya setelah seluruh tahap di atas lulus; backup dan rollback script wajib. Jalankan oleh pemilik DB setelah uji.

## Update 14 November 2026
- Ditambahkan skrip audit read-only `backend/cpos/database/audit/027_audit_dependensi_master_lokal.sql` untuk memetakan FK, kolom kandidat ID, modul SQL yang menyebut Supplier/Product, dan jumlah baris tabel legacy (hanya tabel yang ada). Skrip tidak mengubah database.
- Skrip audit dibuat defensif terhadap tabel legacy yang sudah tidak ada.
- Commit audit SQL: `74fb8fe`; perbaikan guard tabel: `6cf236d`.

## Status saat ini
- Commit dokumentasi audit: `fc9f4bb`.
- Definisi SupplierCompany/SupplierTypeDetails di schema dirapikan: `b390288`.
- Migrasi snapshot aditif 026 ditambahkan: `d5bab00`.
- Migrasi penghapusan SupplierTypeDetails yang terlalu dini telah dihapus dari branch karena `db_kontrak.py` masih memanggil tabel itu. Jangan jalankan migration DROP Supplier/Product sampai refactor Kontrak/DO, Blacklist, tiket, laporan, dan Lab selesai.
- Belum ada perubahan database pengguna, belum menjalankan migration, dan belum ada tes integrasi pada SQL Server.

Audit awal menunjukkan ketergantungan masih aktif pada Kontrak/DO, Blacklist, tiket, FlowRule, ProductPrice, dan standar mutu Lab. Karena itu, tabel Supplier/Product belum aman di-DROP pada tahap ini.


## Implementasi Kontrak/DO — 14 November 2026

- Form Kontrak/DO kini mengambil Customer dan daftar Pengangkutan dari fungsi master Ascend; Produk diambil dari DO outstanding Ascend (nama produk, karena sumber saat ini belum menyediakan ProductID master yang stabil di fungsi tersebut).
- Pilihan pihak ketiga pada form menggunakan select ID pengangkutan Ascend; tidak lagi meminta nama bebas untuk membuat Supplier lokal.
- Backend penyimpanan Kontrak/DO menyimpan `AscendCustomerID`, `CustomerNameSnapshot`, dan `ProductNameSnapshot`; kolom SupplierID/ProductID lokal diisi NULL untuk transaksi baru. DOTransport menyimpan `AscendTransportID` dan `TransportNameSnapshot`; TransportID lokal diisi NULL.
- Query daftar DO menggunakan LEFT JOIN dan COALESCE snapshot/local agar data lama tetap terbaca.
- Validasi penyimpanan DO mengecek blacklist berdasarkan identitas Ascend melalui fungsi baru `supplier_ascend_diblacklist`. Ini hanya memeriksa blacklist yang sudah mempunyai kolom AscendID; pengajuan blacklist supplier baru masih perlu migrasi UI/API tersendiri.
- Form dan API memerlukan migration 026, 028, dan 029 sebelum deploy. Belum diuji terhadap SQL Server/Ascend runtime; jangan deploy ke server aktif sebelum test DB salinan.
- Belum selesai: edit DO lama dengan pengangkut lokal yang belum punya AscendID perlu penanganan UI snapshot; modul blacklist supplier masih menerima target Supplier lokal; transaksi WeightBridge, VehicleContract, Invoice, ProductPrice, FlowRule, Lab/standar mutu, dan laporan masih perlu refactor sebelum master lokal dihapus.


## Schema & migration groundwork — 14 November 2026 (lanjutan)

- `backend/cpos/database/schema.sql` diperbarui untuk schema fresh: kolom referensi Supplier/Product pada Contract, DOTransport, VehicleContract, Invoice, WeightBridge, ProductPrice, FlowRule menjadi nullable legacy; kolom Ascend ID dan snapshot tersedia. Blacklist mendukung entitas supplier/customer/transport Ascend tanpa SupplierID lokal. Constraint DOTransport mengizinkan pihak ketiga dengan AscendTransportID.
- Migration 026 tetap additive untuk snapshot (tidak melepas FK transaksi). Ditambahkan CustomerCodeSnapshot, Product/Transport code snapshots, AscendProductCode, dan constraint Blacklist Target yang menerima ID Ascend.
- Migration 030 dibuat untuk pelepasan FK Supplier/Product serta nullable legacy ID pada VehicleContract, Invoice, WeightBridge, ProductPrice/FlowRule. **JANGAN jalankan 030 sebelum seluruh code modul terkait menggunakan Ascend ID/snapshot**; saat ini belum siap deployment.
- Migration 028/029 khusus Contract/DO. 026/028/029/030 belum dijalankan pada database.
- Risiko yang masih harus dibereskan: schema fresh vs migration existing harus diuji di database clone; schema.sql tidak otomatis mengubah DB existing; constraint unik DOTransport perlu review saat TransportID NULL; implementasi blacklist CRUD harus mengisi Ascend ID/snapshot; WeightBridge dan Invoice/VehicleContract/ProductPrice/FlowRule belum sepenuhnya refactor.
