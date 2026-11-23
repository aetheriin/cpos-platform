"""Kamus data Asisten: apa yang bisa dihitung (ukuran), dipecah per apa (pemecah), dan disaring dengan apa (status).

Semua angka diambil dari data laporan yang sudah ada (Outstanding, Purchase Request, Purchase Order), jadi aturannya sama dengan laporan.
Menambah kata yang dikenali cukup di daftar `sebutan`; huruf besar kecil dan salah ketik ringan tidak masalah."""

# Data laporan yang dipakai. tanggal: kolom tanggal dokumen untuk saringan waktu. posisi: angka berupa sisa saat ini (tanpa periode = semua
# dokumen yang masih terbuka), bukan transaksi dalam periode.
SUMBER = {
    "outstanding": {"laporan": "outstanding", "tanggal": "tgl", "posisi": True},
    "pr": {"laporan": "purchase_request", "tanggal": "pr_date", "posisi": False},
    "po": {"laporan": "purchase_order", "tanggal": "cd", "posisi": False},
    "pi": {"laporan": "pi_pvr", "tanggal": "pi_date", "posisi": False},
}

# hitung: jumlah (kolom), rata (kolom), dokumen (jumlah nomor unik per perusahaan). saring: {kolom: [nilai]} yang selalu berlaku.
UKURAN = {
    "hutang": {
        "label": "Hutang", "sumber": "outstanding", "saring": {"jenis": ["hutang"]}, "hitung": "jumlah", "kolom": "sisa_rp", "satuan": "rp",
        "sebutan": ["hutang", "utang", "ap", "payable", "belum dibayar", "belum kita bayar", "tagihan supplier", "kewajiban", "utang dagang",
                    "hutang dagang", "account payable", "outstanding hutang", "sisa hutang", "hutang supplier"],
        "nomor": "no_dok", "tabel": "hutang",
        "arti": "Sisa tagihan supplier yang belum lunas (sudah dikurangi PV), dalam rupiah. Retur dan potongan mengurangi hutang.",
    },
    "piutang": {
        "label": "Piutang", "sumber": "outstanding", "saring": {"jenis": ["piutang"]}, "hitung": "jumlah", "kolom": "sisa_rp", "satuan": "rp",
        "sebutan": ["piutang", "ar", "receivable", "belum diterima", "tagihan customer", "belum dibayar customer", "piutang dagang",
                    "account receivable", "outstanding piutang", "sisa piutang", "tagihan ke customer"],
        "nomor": "no_dok", "tabel": "piutang",
        "arti": "Sisa tagihan ke customer yang belum diterima (sudah dikurangi RV), dalam rupiah.",
    },
    "hutang_pvr": {
        "label": "Hutang yang sudah diajukan PVR", "sumber": "outstanding", "saring": {"jenis": ["hutang"]}, "hitung": "jumlah",
        "kolom": "dalam_pvr_rp", "satuan": "rp", "nomor": "no_dok", "tabel": "hutang",
        "sebutan": ["sudah diajukan pvr", "sudah pvr", "dalam pvr", "diajukan pvr", "nilai pvr"],
        "arti": "Bagian hutang yang sudah masuk PVR tapi belum dibayar dengan PV.",
    },
    "hutang_belum_diajukan": {
        "label": "Hutang yang belum diajukan PVR", "sumber": "outstanding", "saring": {"jenis": ["hutang"]}, "hitung": "jumlah",
        "kolom": "belum_diajukan_rp", "satuan": "rp", "nomor": "no_dok", "tabel": "hutang",
        "sebutan": ["belum diajukan", "belum diajukan pvr", "belum masuk pvr"],
        "arti": "Bagian hutang yang belum masuk PVR dan belum punya PV tanggal ke depan.",
    },
    "jumlah_pr": {
        "label": "Jumlah PR", "sumber": "pr", "hitung": "dokumen", "kolom": "prnumber", "satuan": "dokumen", "nomor": "prnumber",
        "sebutan": ["pr", "purchase request", "permintaan pembelian", "permintaan barang", "jumlah pr", "berapa pr", "requisition",
                    "permintaan", "pengajuan barang", "banyak pr"],
        "arti": "Jumlah dokumen PR (Void tidak dihitung). Satu PR bisa berisi beberapa barang.",
    },
    "lama_pr_po": {
        "label": "Rata-rata lama PR jadi PO", "sumber": "pr", "hitung": "rata", "kolom": "lama_po", "satuan": "hari", "nomor": "prnumber",
        "saring": {"status": ["PO sebagian", "Sudah PO"]},
        "sebutan": ["lama pr ke po", "lama pr jadi po", "pr ke po", "kecepatan po", "berapa lama pr", "waktu pr ke po"],
        "arti": "Hari dari tanggal PR sampai PO pertama untuk barang itu, dirata-rata per baris barang yang sudah dibuatkan PO.",
    },
    "jumlah_po": {
        "label": "Jumlah PO", "sumber": "po", "hitung": "dokumen", "kolom": "po_number", "satuan": "dokumen", "nomor": "po_number",
        "sebutan": ["po", "purchase order", "pesanan pembelian", "jumlah po", "berapa po", "order pembelian", "banyak po", "pesanan"],
        "arti": "Jumlah dokumen PO (Void tidak dihitung), menurut tanggal PO dibuat.",
    },
    "nilai_po": {
        "label": "Nilai PO", "sumber": "po", "hitung": "jumlah", "kolom": "total_po", "satuan": "rp", "nomor": "po_number",
        "saring": {"rupiah": [True]},
        "sebutan": ["nilai po", "total po", "belanja", "pembelian", "nilai pembelian", "total pembelian", "spending", "pengeluaran pembelian",
                    "spend", "po spend", "rupiah po", "belanja barang", "nominal po"],
        "arti": "Jumlah harga x qty semua baris PO dalam rupiah. PO valas tidak ikut karena kursnya tidak ada di data PO.",
    },
    "lama_po_pi": {
        "label": "Rata-rata lama PO jadi PI", "sumber": "po", "hitung": "rata", "kolom": "lama_pi", "satuan": "hari", "nomor": "po_number",
        "saring": {"status": ["PI sebagian", "Sudah PI"]},
        "sebutan": ["lama po ke pi", "lama po jadi pi", "po ke pi", "waktu po ke pi", "berapa lama po"],
        "arti": "Hari dari PO dibuat sampai PI pertama untuk baris itu, dirata-rata per baris PO yang sudah ditagih.",
    },
    "hutang_pv_depan": {
        "label": "Hutang dengan PV tanggal ke depan", "sumber": "outstanding", "saring": {"jenis": ["hutang"]}, "hitung": "jumlah",
        "kolom": "pv_depan_rp", "satuan": "rp", "nomor": "no_dok", "tabel": "hutang",
        "sebutan": ["pv tanggal ke depan", "pv mundur", "pv belum jatuh tempo", "jadwal bayar", "akan dibayar"],
        "arti": "Bagian hutang yang sudah dibuatkan PV, tapi tanggal PV-nya belum tiba.",
    },
    "dokumen_hutang": {
        "label": "Jumlah dokumen hutang", "sumber": "outstanding", "saring": {"jenis": ["hutang"]}, "hitung": "dokumen", "kolom": "no_dok",
        "satuan": "dokumen", "nomor": "no_dok", "sebutan": ["dokumen hutang", "jumlah dokumen hutang", "berapa dokumen hutang", "tagihan belum lunas"],
        "arti": "Jumlah dokumen tagihan supplier (PI, nota, tiket, dan lainnya) yang masih punya sisa.",
    },
    "item_pr": {
        "label": "Jumlah baris barang PR", "sumber": "pr", "hitung": "baris", "kolom": "itemname", "satuan": "baris barang", "nomor": "prnumber",
        "sebutan": ["item pr", "barang pr", "baris pr", "jumlah item pr", "jumlah barang pr"],
        "arti": "Jumlah baris barang di PR. Satu PR bisa berisi banyak barang.",
    },
    "umur_pr": {
        "label": "Rata-rata aging PR", "sumber": "pr", "hitung": "rata", "kolom": "umur", "satuan": "hari", "nomor": "prnumber",
        "sebutan": ["rata rata aging pr", "rata aging pr", "umur rata rata pr", "rata rata umur pr"],
        "arti": "Rata-rata umur baris PR dalam hari sejak tanggal PR. Biasanya dipakai bersama status Belum PO.",
    },
    "item_po": {
        "label": "Jumlah baris barang PO", "sumber": "po", "hitung": "baris", "kolom": "itemname", "satuan": "baris barang", "nomor": "po_number",
        "sebutan": ["item po", "barang po", "baris po", "jumlah item po", "jumlah barang po"],
        "arti": "Jumlah baris barang di PO.",
    },
    "supplier_po": {
        "label": "Jumlah supplier PO", "sumber": "po", "hitung": "unik", "kolom": "supplier_name", "satuan": "supplier", "nomor": "po_number",
        "sebutan": ["jumlah supplier", "berapa supplier", "banyak supplier", "supplier aktif"],
        "arti": "Jumlah supplier berbeda yang menerima PO pada periode itu.",
    },
    "jumlah_pi": {
        "label": "Jumlah PI", "sumber": "pi", "hitung": "dokumen", "kolom": "pi_number", "satuan": "dokumen", "nomor": "pi_number",
        "sebutan": ["pi", "purchase invoice", "invoice", "faktur pembelian", "jumlah pi", "berapa pi", "tagihan masuk", "banyak pi"],
        "arti": "Jumlah dokumen PI menurut tanggal PI dibuat.",
    },
    "nilai_pi": {
        "label": "Nilai PI", "sumber": "pi", "hitung": "jumlah", "kolom": "line_total", "satuan": "rp", "nomor": "pi_number",
        "sebutan": ["nilai pi", "total pi", "nilai invoice", "nilai faktur", "nominal pi", "rupiah pi"],
        "arti": "Jumlah nilai baris PI dalam rupiah (valas dikalikan kurs di PI).",
    },
    "lama_pi_pvr": {
        "label": "Rata-rata lama PI jadi PVR", "sumber": "pi", "hitung": "rata", "kolom": "lama_pvr", "satuan": "hari", "nomor": "pi_number",
        "sebutan": ["lama pi ke pvr", "lama pi jadi pvr", "pi ke pvr", "berapa lama pi"],
        "arti": "Hari dari PI dibuat sampai PVR pertamanya dibuat di sistem, dirata-rata per baris PI yang sudah punya PVR.",
    },
    "lama_pi_pv": {
        "label": "Rata-rata lama PI sampai PV", "sumber": "pi", "hitung": "rata", "kolom": "lama_pv", "satuan": "hari", "nomor": "pi_number",
        "sebutan": ["lama pi ke pv", "lama pi jadi pv", "pi ke pv", "lama bayar", "berapa lama dibayar", "kecepatan bayar"],
        "arti": "Hari dari PI dibuat sampai tanggal PV pertamanya, dirata-rata per baris PI yang sudah dibayar.",
    },
}

# Pemecah: kolom per sumber. Yang tidak punya kolom di suatu sumber tidak bisa dipakai untuk ukuran dari sumber itu.
PEMECAH = {
    "perusahaan": {"label": "Perusahaan", "sebutan": ["perusahaan", "per pt", "tiap pt", "company"],
                   "kolom": {"outstanding": "comp", "pr": "comp", "po": "comp", "pi": "comp"}},
    "supplier": {"label": "Supplier", "sebutan": ["supplier", "vendor", "pemasok", "suplier", "rekanan", "toko", "penjual"],
                 "kolom": {"outstanding": "mitra", "po": "supplier_name", "pr": "supplier_name", "pi": "supplier_name"}, "hanya": {"outstanding": ["hutang"]}},
    "customer": {"label": "Customer", "sebutan": ["customer", "pelanggan", "pembeli", "costumer"],
                 "kolom": {"outstanding": "mitra"}, "hanya": {"outstanding": ["piutang"]}},
    "kategori": {"label": "Kategori", "sebutan": ["kategori", "category", "jenis barang", "golongan"],
                 "kolom": {"pr": "category", "po": "category"}},
    "buyer": {"label": "Buyer", "sebutan": ["buyer", "pembeli po", "purchasing"], "kolom": {"pr": "buyer"}, "banyak": True},
    "pembuat": {"label": "Dibuat oleh", "sebutan": ["pembuat", "dibuat oleh", "siapa yang buat", "creator", "admin"],
                "kolom": {"po": "creator", "pi": "pi_by"}},
    "penyetuju": {"label": "Disetujui oleh", "sebutan": ["penyetuju", "disetujui", "approver", "approve"], "kolom": {"pr": "approve_by"}},
    "status": {"label": "Status", "sebutan": ["status", "tahap", "progres"], "kolom": {"outstanding": "status", "pr": "status", "po": "status", "pi": "status"}},
    "sumber_dok": {"label": "Sumber", "sebutan": ["sumber", "jenis dokumen", "jenis tagihan"], "kolom": {"outstanding": "sumber"}},
    "aging": {"label": "Aging", "sebutan": ["aging", "umur", "kelompok umur"], "kolom": {"outstanding": "aging", "pr": "aging", "po": "aging", "pi": "aging"}},
    "barang": {"label": "Barang", "sebutan": ["barang", "item", "produk", "material", "nama barang", "sparepart"],
               "kolom": {"pr": "itemname", "po": "itemname", "pi": "itemname"}},
    "bulan": {"label": "Bulan", "sebutan": ["bulan", "bulanan", "per bulan", "tren", "trend"], "waktu": "M"},
    "minggu": {"label": "Minggu", "sebutan": ["minggu", "mingguan", "pekan"], "waktu": "W"},
    "hari": {"label": "Hari", "sebutan": ["harian", "per hari", "tiap hari"], "waktu": "D"},
}

# Kata status: menyaring sumbernya, dan menjadi ukuran bawaan kalau ukuran tidak disebut ("PR yang belum PO" = jumlah PR).
STATUS = [
    {"sebutan": ["belum po", "belum dibuat po", "belum di po", "belum jadi po", "tanpa po"], "sumber": "pr", "nilai": ["Belum PO"], "ukuran": "jumlah_pr"},
    {"sebutan": ["po sebagian"], "sumber": "pr", "nilai": ["PO sebagian"], "ukuran": "jumlah_pr"},
    {"sebutan": ["sudah po", "sudah jadi po", "sudah dibuat po"], "sumber": "pr", "nilai": ["Sudah PO"], "ukuran": "jumlah_pr"},
    {"sebutan": ["belum disetujui", "belum diapprove", "belum approve", "belum di approve", "menunggu persetujuan"], "sumber": "pr",
     "nilai": ["Belum PO", "PO sebagian"], "kosong": "approve_date", "label": "Belum disetujui", "ukuran": "jumlah_pr"},
    {"sebutan": ["ditutup tanpa po"], "sumber": "pr", "nilai": ["Ditutup tanpa PO"], "ukuran": "jumlah_pr"},
    {"sebutan": ["belum pi", "belum ditagih", "belum jadi pi", "belum diterima barangnya", "belum datang"], "sumber": "po", "nilai": ["Belum PI"], "ukuran": "jumlah_po"},
    {"sebutan": ["pi sebagian", "diterima sebagian", "datang sebagian"], "sumber": "po", "nilai": ["PI sebagian"], "ukuran": "jumlah_po"},
    {"sebutan": ["sudah pi", "sudah ditagih", "sudah jadi pi"], "sumber": "po", "nilai": ["Sudah PI"], "ukuran": "jumlah_po"},
    {"sebutan": ["ditutup tanpa pi"], "sumber": "po", "nilai": ["Ditutup tanpa PI"], "ukuran": "jumlah_po"},
    {"sebutan": ["belum pvr", "belum ada pvr"], "sumber": "outstanding", "nilai": ["Belum PVR"], "ukuran": "hutang"},
    {"sebutan": ["pvr pending", "pvr belum approve", "pvr belum disetujui"], "sumber": "outstanding", "nilai": ["PVR pending"], "ukuran": "hutang"},
    {"sebutan": ["pvr sebagian"], "sumber": "outstanding", "nilai": ["PVR sebagian"], "ukuran": "hutang"},
    {"sebutan": ["pv tanggal ke depan", "pv mundur", "belum jatuh tempo"], "sumber": "outstanding",
     "nilai": ["PV tanggal ke depan", "PV tanggal ke depan sebagian"], "ukuran": "hutang"},
    {"sebutan": ["belum pvr", "belum ada pvr", "belum pvr dan pv", "belum diproses"], "sumber": "pi", "nilai": ["Belum PVR & PV"], "ukuran": "jumlah_pi"},
    {"sebutan": ["pv tanpa pvr", "langsung pv", "dibayar tanpa pvr"], "sumber": "pi", "nilai": ["PV tanpa PVR"], "ukuran": "jumlah_pi"},
    {"sebutan": ["pvr belum pv", "sudah pvr belum pv", "belum dibayar pv"], "sumber": "pi", "nilai": ["PVR, belum PV"], "ukuran": "jumlah_pi"},
    {"sebutan": ["sudah pvr dan pv", "pvr dan pv", "lengkap", "sudah dibayar"], "sumber": "pi", "nilai": ["PVR & PV"], "ukuran": "jumlah_pi"},
    {"sebutan": ["perlu tindakan", "lebih dari 30 hari", "lewat 30 hari"], "kolom": "aging", "nilai": ["Perlu Tindakan (>30 hari)"]},
    {"sebutan": ["telat"], "kolom": "aging", "nilai": ["Telat (16–30 hari)"]},
    {"sebutan": ["perlu perhatian"], "kolom": "aging", "nilai": ["Perlu Perhatian (9–15 hari)"]},
    {"sebutan": ["tepat waktu"], "kolom": "aging", "nilai": ["Tepat Waktu (0–8 hari)"]},
]

# Kolom daftar dokumen ("PR mana saja yang belum PO"). urut: kolom (arah) bawaan; "terlama" memakai kolom umur.
DAFTAR = {
    "outstanding": {"hutang": [("comp", "Perusahaan"), ("mitra", "Supplier"), ("no_dok", "No. Dokumen"), ("tgl", "Tanggal"),
                               ("umur", "Aging (hari)"), ("status", "Status"), ("sisa_rp", "Sisa")],
                    "piutang": [("comp", "Perusahaan"), ("mitra", "Customer"), ("no_dok", "No. Dokumen"), ("tgl", "Tanggal"),
                                ("umur", "Aging (hari)"), ("status", "Status"), ("sisa_rp", "Sisa")]},
    "pr": [("comp", "Perusahaan"), ("prnumber", "No. PR"), ("pr_date", "Tanggal dibuat"), ("umur", "Aging (hari)"), ("status", "Status"),
           ("itemname", "Barang"), ("po_number", "No. PO")],
    "po": [("comp", "Perusahaan"), ("po_number", "No. PO"), ("cd", "Tanggal PO"), ("umur", "Aging (hari)"), ("status", "Status"),
           ("supplier_name", "Supplier"), ("total_po", "Nilai"), ("pi_number", "No. PI")],
    "pi": [("comp", "Perusahaan"), ("pi_number", "No. PI"), ("pi_date", "Tanggal PI"), ("umur", "Aging (hari)"), ("status", "Status"),
           ("supplier_name", "Supplier"), ("line_total", "Nilai"), ("pvr_number", "No. PVR")],
}

# Pertanyaan contoh: dipakai sebagai saran awal dan untuk menebak "Maksud Anda" saat kalimat tidak dikenali.
CONTOH = [
    "Hutang per perusahaan",
    "Hutang ORI per supplier",
    "10 supplier dengan hutang terbesar",
    "Hutang yang belum PVR per perusahaan",
    "Daftar hutang terlama",
    "Piutang per customer",
    "PR yang belum PO per perusahaan",
    "Daftar PR belum PO terlama",
    "Jumlah PR per bulan",
    "Lama PR jadi PO per buyer",
    "Nilai PO bulan ini per supplier",
    "Nilai PO per bulan",
    "PO yang belum PI per supplier",
    "Lama PO jadi PI per perusahaan",
    "Apa itu PVR?",
    "PI yang belum PVR per perusahaan",
    "Lama PI jadi PVR per bulan",
    "Gimana cara hitung aging PR?",
]

# Nama yang dipakai Asisten saat ditanya "siapa namamu". Ganti di sini kalau ingin nama lain.
NAMA_ASISTEN = "AkasaBot"

# Obrolan ringan: pola (regex pada kalimat huruf kecil) -> jawaban. {nama} = nama pengguna, {salam} = selamat pagi/siang/sore/malam,
# {asisten} = NAMA_ASISTEN, {jam} dan {tanggal} = saat ini. Dicek sebelum pertanyaan data, hanya untuk kalimat pendek.
OBROLAN = [
    {"pola": r"^(hai|hi|halo|hallo|hello|hey|hei|pagi|siang|sore|malam|selamat (pagi|siang|sore|malam)|assalamu ?alaikum|permisi|p)$",
     "jawab": "{salam}, {nama}. AkasaBot tersambung. Mau tanya angka apa?", "saran": True},
    {"pola": r"(siapa (nama ?(mu|kamu|anda)|kamu|anda|ini)|nama ?(mu|kamu|anda)( siapa)?|kamu siapa|anda siapa|kenalan)",
     "jawab": "Saya {asisten}, terminal kecil yang tersambung ke semua laporan. Tanya saja, jawabannya saya hitung dari "
              "laporan Outstanding, Purchase Request, dan Purchase Order, jadi angkanya sama persis dengan laporannya.", "saran": True},
    {"pola": r"(kamu|anda|ini) (ai|robot|bot|chatgpt|gpt|manusia|orang)|pakai ai|apakah (kamu|anda) (ai|robot|manusia)",
     "jawab": "Saya bot, tapi bukan AI. Saya mengenali kata seperti hutang, supplier, atau bulan ini, lalu menghitung dari "
              "data laporan di server kantor. Datanya tidak ke mana-mana."},
    {"pola": r"(apa kabar|gimana kabar|bagaimana kabar|kabarmu|kabar (kamu|anda))",
     "jawab": "Baik, sinyal ke laporan kuat. Ada yang mau dicek, {nama}?", "saran": True},
    {"pola": r"^((ok|oke|okay|sip) )?(terima ?kasih|makasih|trims|thanks|thank you|tq|thx)( (ya|banyak|bro|kak|pak|bu))*$",
     "jawab": "Sama-sama, {nama}."},
    {"pola": r"^(ok|oke|okay|sip|siap|mantap|baik|baiklah|noted|paham|mengerti)$", "jawab": "Siap. AkasaBot standby."},
    {"pola": r"(pintar|pinter|keren|hebat|mantap|bagus) (sekali|banget|juga)?|(kamu|anda) (pintar|pinter|keren|hebat)",
     "jawab": ["Makasih. Pujiannya saya simpan di catatan, di sebelah laporan hutang.",
               "Bot juga bisa malu, ternyata. Kalau ada jawaban yang meleset, tandai \"kurang tepat\" ya."]},
    {"pola": r"(bodoh|goblok|bego|tolol|payah|ga ?guna|tidak berguna|jelek)",
     "jawab": "Aduh, maaf kalau jawabannya meleset. Coba tulis dengan kata lain, atau tandai \"kurang tepat\" di bawah "
              "jawabannya supaya bisa diperbaiki.", "saran": True},
    {"pola": r"(irminsul|aaru|akasha|akasa|sumeru|pohon pengetahuan)",
     "jawab": "Kalau di Sumeru, pengetahuan disimpan di pohonnya, dan Akasha cuma terminal untuk bertanya. Di sini juga begitu: "
              "pohonnya laporan-laporan di server kantor, saya terminalnya.", "saran": True},
    {"pola": r"(jam berapa|pukul berapa|sekarang jam)", "jawab": "Sekarang pukul {jam}."},
    {"pola": r"(hari apa|tanggal berapa|hari ini tanggal)", "jawab": "Hari ini {tanggal}."},
    {"pola": r"(siapa yang (buat|bikin|membuat)|dibuat (oleh )?siapa|pembuatmu)",
     "jawab": "Saya bot bagian dari Analytics di CPOS. Usul atau keluhan soal saya bisa disampaikan ke tim IT."},
    {"pola": r"^(dah|dadah|bye|sampai jumpa|sampai nanti|see you)$", "jawab": "Dadah, {nama}. AkasaBot tetap tersambung kalau dibutuhkan."},
    # Pertanyaan yang sering muncul di menu PR & PO Outstanding dan PO & PI Outstanding
    {"pola": r"(kenapa|mengapa|kok|alasan).*\bpr\b.*(belum|tidak|gak|ga) (jadi |dibuat(kan)? )?po",
     "jawab": "Alasannya tidak tercatat di data ERP, jadi saya tidak bisa menebaknya. Yang bisa dilihat dari laporan: PR itu sudah disetujui "
              "atau belum, dan sudah berapa lama menunggu. PR yang belum disetujui belum bisa dibuatkan PO oleh Purchasing. "
              "Untuk alasan per PR, tanyakan ke buyer atau peminta barangnya.",
     "saran_khusus": ["Daftar PR belum PO terlama", "PR yang belum PO per perusahaan"]},
    {"pola": r"(kenapa|mengapa|kok|alasan).*\bpo\b.*(belum|tidak|gak|ga) (jadi |dibuat(kan)? )?pi",
     "jawab": "PI dibuat setelah barang diterima dan tagihan supplier dicatat, jadi PO yang belum PI biasanya barangnya belum datang atau "
              "tagihannya belum masuk. Alasan pastinya tidak tercatat di data; cek ke supplier atau gudang penerima untuk PO yang sudah lama.",
     "saran_khusus": ["Daftar PO belum PI terlama", "PO yang belum PI per supplier"]},
    {"pola": r"(cara|bagaimana|gimana|bisa) .*(tutup|menutup|hapus|batal|membatalkan|close)\w* .*\b(pr|po)\b|(tutup|batalkan|hapus) (pr|po)\b",
     "jawab": "PR dan PO ditutup atau dibatalkan di ERP oleh Purchasing. Saya dan laporan ini hanya membaca data, tidak bisa mengubahnya. "
              "Setelah ditutup di ERP, statusnya berubah menjadi \"Ditutup tanpa PO\" atau \"Ditutup tanpa PI\" saat data dimuat ulang."},
    {"pola": r"(beda|perbedaan|bedanya).*(aging|umur).*(lama)|(beda|perbedaan|bedanya).*(lama).*(aging|umur)",
     "jawab": "Aging dipakai untuk dokumen yang masih menunggu: hari dari tanggal dokumen dibuat sampai hari ini. Lama proses dipakai untuk "
              "dokumen yang sudah lanjut: hari dari tanggal dokumen dibuat sampai dokumen berikutnya dibuat, misalnya PR sampai PO pertama. "
              "Jadi PR yang belum jadi PO punya aging tapi belum punya lama proses.",
     "saran_khusus": ["Gimana cara hitung aging PR?", "Gimana cara hitung aging PO?"]},
    {"pola": r"(data|laporan|angka)(nya)? .*(diperbarui|diupdate|update|terbaru|real ?time|kapan)|kapan (data|laporan)(nya)? .*(update|diperbarui)",
     "jawab": "Data diambil dari ERP saat laporan dibuka, lalu dipakai ulang sampai 15 menit supaya tidak memuat ulang terus. "
              "Kalau perlu angka paling baru, tekan Muat ulang data di panel periode."},
    {"pola": r"(cerita|lelucon|lawak|jokes?|lucu|ngelawak|receh|pantun|nyanyi|puisi|hibur)",
     "jawab": ["Kenapa truk sawit ditimbang dua kali? Biar ketahuan mana muatan, mana yang cuma tara.",
               "Pohon pengetahuan boleh terbakar, tapi hutang tetap tercatat. Hutang memang tahan api.",
               "Saya ini terminal pengetahuan. Sayangnya pengetahuan saya cuma soal hutang, PR, dan PO.",
               "Supplier boleh lupa, tapi aging tidak. Tiap hari dia nambah satu."], "saran": True},
]


# Menu (id laporan) -> sumber dan ukuran utamanya, arti kata status umum di menu itu, rekomendasi pertanyaan, dan isi menunya.
# Di menu yang punya sumber, pertanyaan tanpa ukuran ("per supplier", "yang belum") dijawab dengan ukuran utama menu itu.
# Menu tanpa sumber hanya dapat rekomendasi istilah: datanya belum bisa ditanyakan ke AkasaBot.
MENU = {
    "outstanding": {"sumber": "outstanding", "ukuran": "hutang",
                    "umum": {"belum": "belum pvr", "sebagian": "pvr sebagian", "pending": "pvr pending"},
                    "isi": "Hutang dan piutang yang belum lunas. Periode dan aging memakai tanggal dokumen, dihitung sampai hari ini.",
                    "saran": ["Apa yang perlu diperhatikan di menu ini?", "Hutang per perusahaan", "10 supplier dengan hutang terbesar", "Hutang yang belum PVR per perusahaan",
                              "Daftar hutang terlama", "Piutang per customer", "Hutang per sumber"]},
    "purchase_request": {"sumber": "pr", "ukuran": "jumlah_pr",
                         "umum": {"belum": "belum po", "sebagian": "po sebagian", "sudah": "sudah po", "ditutup": "ditutup tanpa po"},
                         "isi": "Tiap baris PR dengan status belum, sebagian, atau sudah dibuatkan PO.",
                         "saran": ["Apa yang perlu diperhatikan di menu ini?", "PR yang belum PO per perusahaan", "Daftar PR belum PO terlama", "Lama PR jadi PO per buyer",
                                   "Jumlah PR per bulan", "PR bulan ini per kategori", "Gimana cara hitung aging PR?"]},
    "pr_po": {"sumber": "pr", "ukuran": "jumlah_pr",
              "umum": {"belum": "belum po", "sebagian": "po sebagian", "sudah": "sudah po"},
              "isi": "PR yang belum menjadi PO dan lama prosesnya. Periode dan aging memakai tanggal PR dibuat.",
              "saran": ["Apa yang perlu diperhatikan di menu ini?", "PR yang belum PO per perusahaan", "Lama PR jadi PO per bulan", "Daftar PR belum PO terlama",
                        "Rata-rata aging PR belum PO per perusahaan", "Gimana cara hitung aging PR?"]},
    "purchase_order": {"sumber": "po", "ukuran": "jumlah_po",
                       "umum": {"belum": "belum pi", "sebagian": "pi sebagian", "sudah": "sudah pi", "ditutup": "ditutup tanpa pi"},
                       "isi": "Tiap baris PO dengan status belum, sebagian, atau sudah dibuatkan PI.",
                       "saran": ["Apa yang perlu diperhatikan di menu ini?", "PO yang belum PI per supplier", "Nilai PO bulan ini per supplier", "Lama PO jadi PI per perusahaan",
                                 "Daftar PO belum PI terlama", "Nilai PO bulan ini dibanding bulan lalu"]},
    "po_pi": {"sumber": "po", "ukuran": "jumlah_po",
              "umum": {"belum": "belum pi", "sebagian": "pi sebagian", "sudah": "sudah pi"},
              "isi": "PO yang belum dibuatkan PI. Periode dan aging memakai tanggal PO dibuat; lama proses dari tanggal PO sampai PI terakhir.",
              "saran": ["Apa yang perlu diperhatikan di menu ini?", "PO yang belum PI per perusahaan", "Lama PO jadi PI per bulan", "Daftar PO belum PI terlama",
                        "PO yang belum PI per supplier", "Gimana cara hitung aging PO?"]},
    "po_amt": {"sumber": "po", "ukuran": "nilai_po", "umum": {},
               "isi": "Nilai belanja PO dalam rupiah per kategori, bulan, dan supplier.",
               "saran": ["Apa yang perlu diperhatikan di menu ini?", "Nilai PO per bulan", "Nilai PO per kategori", "10 supplier dengan nilai PO terbesar",
                         "Nilai PO bulan ini dibanding bulan lalu", "Jumlah supplier PO per perusahaan"]},
    "pi_pvr": {"sumber": "pi", "ukuran": "jumlah_pi",
               "umum": {"belum": "belum pvr", "sudah": "sudah pvr dan pv"},
               "isi": "PI yang belum punya PVR atau PV, yang dibayar PV tanpa PVR, dan yang sudah PVR.",
               "saran": ["Apa yang perlu diperhatikan di menu ini?", "PI yang belum PVR per perusahaan", "Daftar PI belum PVR terlama", "Lama PI jadi PVR per perusahaan",
                         "Nilai PI bulan ini per supplier", "PI yang dibayar tanpa PVR per pembuat"]},
    "pi_gt": {"sumber": "pi", "ukuran": "jumlah_pi", "umum": {},
              "isi": "Barang yang sudah di-PI tapi belum diterima gudang tujuan lewat GT, beserta lead time-nya.",
              "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu GT?", "Jumlah PI per bulan", "Nilai PI per perusahaan"]},
    "penilaian_pvr": {"isi": "Skor pembuat PVR per bulan menurut kategori dan bobotnya, sama dengan Excel Penilaian PVR.",
                      "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu PVR?", "Hutang yang belum PVR per perusahaan", "Lama PI jadi PVR per bulan"]},
    "penilaian_pv": {"isi": "Skor kasir pembuat PV hutang per bulan, aturannya sama dengan PVR KPI dengan bobot PV.",
                     "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu PV?", "Lama PI sampai PV per perusahaan", "Hutang dengan PV tanggal ke depan per perusahaan"]},
    "palm_weighbridge": {"isi": "Tiket timbang sawit yang janggal, misalnya tara menyimpang dari riwayat kendaraan atau durasi tidak wajar.",
                         "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu tara?", "Apa itu TBS?", "Gimana cara hitung netto?"]},
    "tiket_penjualan": {"isi": "Tiket timbang produk keluar per hari, minggu, atau bulan, dengan peringkat produk, pengangkut, dan pembeli.",
                        "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu tara?", "Piutang per customer", "Gimana cara hitung netto?"]},
    "tbs_mingguan": {"isi": "Tonase TBS per business group per minggu lengkap (Senin sampai Minggu), dengan tanda naik atau turun yang tidak biasa.",
                     "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu TBS?", "Apa itu business group?", "Hutang per sumber"]},
    "penerimaan_tbs": {"isi": "Penerimaan TBS harian dan perkiraan 7 hari ke depan, per supplier dan kebun.",
                       "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu TBS?", "Apa itu forecast?", "Gimana cara hitung netto?"]},
    "cash_flow": {"isi": "Saldo berjalan, mutasi harian, dan jasa giro per rekening. In uang masuk, out uang keluar.",
                  "saran": ["Apa yang perlu diperhatikan di menu ini?", "Apa itu jasa giro?", "Apa itu running balance?", "Hutang per perusahaan"]},
}

# Pertanyaan tentang menu yang sedang dibuka
POLA_MENU = r"((menu|laporan|halaman|dashboard) ini (isinya )?(apa|tentang apa|buat apa|untuk apa|isinya apa)|isi (menu|laporan|halaman) ini|ini (menu|laporan) apa|ini apa ya)"

# Minta insight menu yang sedang dibuka
POLA_INSIGHT = (r"\b(insight|insigh|ringkasan|rangkuman|ringkas|kesimpulan|kesimpulannya|temuan|sorotan|highlight|poin penting|"
                r"(perlu|harus|wajib) (diperhatikan|diperhatiin|dicek|dilihat|diwaspadai)|apa yang (menarik|penting|janggal|aneh)|"
                r"(bisa|dapat) diambil|apa (masalahnya|yang bermasalah)|ada masalah|analisa|analisis|gimana kondisinya|kondisi(nya)? (gimana|bagaimana))\b")
INSIGHT_SARAN = "Apa yang perlu diperhatikan di menu ini?"
