from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

INSPEKSI = ("SORTASI", "LAB")
NAMA_TAHAP = {"SECURITY": "Security", "TIMBANG_1": "timbang masuk", "SORTASI": "sortasi", "LAB": "hasil lab (Diterima)",
              "TIMBANG_2": "timbang keluar", "SECURITY_KELUAR": "Security keluar"}


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


@cache_ttl(60)
def peta_alur():
    """{id_alur: {"kode", "nama", "keterangan", "tahap": [kode_tahap urut], "kelompok": [[kode_tahap paralel], ...]}}"""
    peta = {a["id_alur"]: {**a, "tahap": [], "kelompok": []}
            for a in _query("SELECT FlowID AS id_alur, FlowCode AS kode, FlowName AS nama, Description AS keterangan, Active AS is_active FROM Flow")}
    grup_terakhir = {}
    for r in _query("SELECT FlowID AS id_alur, StageCode AS kode_tahap, GroupNo AS grup FROM FlowStep ORDER BY FlowID, StepNo"):
        a = peta.get(r["id_alur"])
        if a is None:
            continue
        a["tahap"].append(r["kode_tahap"])
        if grup_terakhir.get(r["id_alur"]) == r["grup"]:
            a["kelompok"][-1].append(r["kode_tahap"])
        else:
            a["kelompok"].append([r["kode_tahap"]])
        grup_terakhir[r["id_alur"]] = r["grup"]
    return peta


# ===== Alur dinamis: aturan Area + Produk, kelompok paralel, tahap milik tiket =====
TAHAP_PERTAMA = "SECURITY"           # selalu tahap pertama (membuat tiket)
TAHAP_TERAKHIR = "SECURITY_KELUAR"   # opsional, bila ada harus terakhir
TAHAP_BEBAS = ("TIMBANG_1", "SORTASI", "LAB", "TIMBANG_2", "SECURITY_KELUAR")


def validasi_kelompok(kelompok):
    """kelompok = [[kode_tahap, ...], ...] berurutan (isi satu kelompok = paralel). ValueError bila tidak sah."""
    if not kelompok or kelompok[0] != [TAHAP_PERTAMA]:
        raise ValueError("Tahap pertama harus Security (sendiri, tidak paralel)")
    rata = [t for k in kelompok for t in k]
    if any(not k for k in kelompok):
        raise ValueError("Ada kelompok tahap yang kosong")
    if len(rata) != len(set(rata)):
        raise ValueError("Satu tahap hanya boleh muncul sekali dalam alur")
    asing = [t for t in rata[1:] if t not in TAHAP_BEBAS]
    if asing:
        raise ValueError(f"Tahap tidak dikenal: {', '.join(asing)}")
    posisi = {t: i for i, k in enumerate(kelompok) for t in k}
    if "TIMBANG_2" in posisi:
        if "TIMBANG_1" not in posisi:
            raise ValueError("Timbang 2 membutuhkan Timbang 1")
        if posisi["TIMBANG_2"] <= posisi["TIMBANG_1"]:
            raise ValueError("Timbang 2 harus setelah Timbang 1 (tidak boleh sebelum atau bersamaan)")
    if TAHAP_TERAKHIR in posisi and (posisi[TAHAP_TERAKHIR] != len(kelompok) - 1 or len(kelompok[-1]) != 1):
        raise ValueError("Security Keluar harus tahap terakhir (sendiri, tidak paralel)")
    return kelompok


def pilih_aturan(aturan, id_area, id_produk):
    """aturan = [{id_comp_area, id_produk (None = semua produk), id_alur, is_active}]. Yang paling spesifik:
    Area + Produk, lalu Area + semua produk. None bila area itu tidak punya aturan (pakai alur bawaan produk)."""
    aktif = [a for a in aturan if a["is_active"] and a["id_comp_area"] == id_area]
    tepat = next((a for a in aktif if a["id_produk"] == id_produk), None)
    return tepat or next((a for a in aktif if a["id_produk"] is None), None)


@cache_ttl(60)
def daftar_aturan():
    return _query("""SELECT r.FlowRuleID AS id_aturan, r.CompAreaID AS id_comp_area, r.ProductID AS id_produk, r.FlowID AS id_alur,
                            r.Active AS is_active, a.CompID + ' · ' + a.AreaName AS area, p.ProductName AS produk, f.FlowName AS alur
                     FROM FlowRule r JOIN CompanyArea a ON a.CompAreaID = r.CompAreaID
                     LEFT JOIN Product p ON p.ProductID = r.ProductID JOIN Flow f ON f.FlowID = r.FlowID
                     ORDER BY a.CompID, a.AreaName, CASE WHEN r.ProductID IS NULL THEN 1 ELSE 0 END, p.ProductName""")


def alur_untuk(id_area, id_produk, id_alur_produk):
    """Alur tiket baru: aturan Area + Produk (Admin › Alur Tiket), selain itu alur bawaan produk."""
    a = pilih_aturan(daftar_aturan(), id_area, id_produk)
    return a["id_alur"] if a else id_alur_produk


def tahap_menunggu(tahap_tiket):
    """tahap_tiket = [{kode_tahap, grup, status}]. Tahap yang sedang ditunggu: semua tahap MENUNGGU di kelompok
    terendah yang belum tuntas (kelompok paralel bisa lebih dari satu). [] = semua tahap selesai."""
    sisa = [t for t in tahap_tiket if t["status"] == "MENUNGGU"]
    if not sisa:
        return []
    grup = min(t["grup"] for t in sisa)
    return [t["kode_tahap"] for t in sorted(sisa, key=lambda t: t.get("urutan", 0)) if t["grup"] == grup]


def buat_tahap_tiket(cursor, no_tiket, id_alur, id_user):
    """Salin tahap alur ke tiket (dipanggil di transaksi pembuatan tiket). Security langsung selesai."""
    urutan = 0
    for grup, isi in enumerate(peta_alur().get(id_alur, {}).get("kelompok", []), 1):
        for kode in isi:
            urutan += 1
            selesai = kode == TAHAP_PERTAMA
            cursor.execute("""INSERT INTO WeightBridgeStage (TicketNumber, StageCode, StepNo, GroupNo, Status, FinishDate, FinishBy)
                              VALUES (?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN GETDATE() END, ?)""",
                           no_tiket, kode, urutan, grup, "SELESAI" if selesai else "MENUNGGU", 1 if selesai else 0,
                           id_user if selesai else None)


def tahap_tiket(cursor, no_tiket):
    cursor.execute("""SELECT StageCode AS kode_tahap, StepNo AS urutan, GroupNo AS grup, Status AS status, FinishDate AS selesai,
                             FinishBy AS oleh FROM WeightBridgeStage WHERE TicketNumber = ? ORDER BY StepNo""", no_tiket)
    return _rows_to_dicts(cursor)


def selesaikan_tahap(cursor, no_tiket, kode_tahap, id_user):
    """Tandai tahap tiket selesai. Hanya tahap yang sedang ditunggu (kelompok berjalan) yang boleh.
    Kembalikan daftar tahap yang ditunggu berikutnya ([] = tiket tuntas)."""
    tahap = tahap_tiket(cursor, no_tiket)
    if not tahap:
        raise ValueError("Tiket ini belum memakai alur dinamis")
    if kode_tahap not in tahap_menunggu(tahap):
        raise ValueError(f"Tahap {NAMA_TAHAP.get(kode_tahap, kode_tahap)} belum bisa dikerjakan: menunggu "
                         + " / ".join(NAMA_TAHAP.get(t, t) for t in tahap_menunggu(tahap)))
    cursor.execute("""UPDATE WeightBridgeStage SET Status = 'SELESAI', FinishDate = GETDATE(), FinishBy = ?
                      WHERE TicketNumber = ? AND StageCode = ? AND Status = 'MENUNGGU'""", id_user, no_tiket, kode_tahap)
    for t in tahap:
        if t["kode_tahap"] == kode_tahap:
            t["status"] = "SELESAI"
    return tahap_menunggu(tahap)


# Warna status tiket (tabel status_tiket, migrasi 033), diatur di Admin › Organisasi
WARNA_STATUS = ("abu", "biru", "hijau", "oranye", "merah", "ungu", "kuning", "toska")


@cache_ttl(60)
def daftar_status():
    try:
        return _query("SELECT StatusCode AS kode, StatusName AS nama, StatusColor AS warna FROM Status ORDER BY SortOrder, StatusCode")
    except Exception:       # noqa: BLE001 - sebelum migrasi 033 memakai label bawaan di common.js
        return []


def simpan_status(kode, nama, warna):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Status SET StatusName = ?, StatusColor = ? WHERE StatusCode = ?", nama, warna, kode)
        if cursor.rowcount == 0:
            raise ValueError("Status tidak ditemukan.")
        conn.commit()
    finally:
        conn.close()
    daftar_status.hapus()


def hapus_cache():
    peta_alur.hapus()
    daftar_aturan.hapus()


def tahap_alur(id_alur):
    return list(peta_alur().get(id_alur, {}).get("tahap", []))


def punya_tahap(id_alur, kode_tahap):
    return kode_tahap in tahap_alur(id_alur)


def tahap_berikut(id_alur, kode_selesai):
    tahap = tahap_alur(id_alur)
    if kode_selesai not in tahap:
        return None
    i = tahap.index(kode_selesai)
    return tahap[i + 1] if i + 1 < len(tahap) else None


def status_setelah(id_alur, kode_selesai):
    """Status tiket setelah tahap ini selesai (lihat docstring modul)."""
    berikut = tahap_berikut(id_alur, kode_selesai)
    if berikut is None:
        return "SELESAI"
    if berikut in INSPEKSI:
        return "TIMBANG_1"
    if berikut == "TIMBANG_2":
        return "TIMBANG_2"
    return "SECURITY_REGISTER"


def menunggu(id_alur, status_alur):
    """Teks tahap yang sedang ditunggu tiket (untuk pesan 'belum bisa timbang kedua')."""
    if status_alur == "TIMBANG_1":
        sisa = [t for t in tahap_alur(id_alur) if t in INSPEKSI]
        return " / ".join(NAMA_TAHAP[t] for t in sisa) or "inspeksi"
    return NAMA_TAHAP.get({"SECURITY_REGISTER": "TIMBANG_1", "TIMBANG_2": "TIMBANG_2"}.get(status_alur, ""), status_alur)


def alur_tiket(jenis_transaksi, id_alur_produk):
    """Alur tahap transaksi baru: Penimbangan saja = TIMBANG_SAJA, selain itu alur produk (Admin › Produk)."""
    return id_alur_kode("TIMBANG_SAJA") if jenis_transaksi == "PENIMBANGAN_SAJA" else id_alur_produk


def daftar_alur():
    """Alur aktif untuk pilihan (Admin › Produk)."""
    return [{"id_alur": i, "kode": a["kode"], "nama": a["nama"], "tahap": a["tahap"]}
            for i, a in sorted(peta_alur().items()) if a["is_active"]]


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan")
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def id_alur_kode(kode):
    return next((i for i, a in peta_alur().items() if a["kode"] == kode), None)


def status_dari_tahap(tahap):
    """Status ringkas tiket (kolom WeightBridge.StatusCode, dipakai tampilan & laporan) dari tahap yang ditunggu:
    Registrasi Security = menunggu timbang 1, Inspeksi = sortasi / lab sebelum timbang, Timbang 1 = sortasi / lab setelah
    timbang 1, Timbang 2 = menunggu timbang 2, Menunggu Keluar = tinggal Security Keluar, Selesai = semua tahap tuntas."""
    menunggu = tahap_menunggu(tahap)
    if not menunggu:
        return "SELESAI"
    if "TIMBANG_2" in menunggu:
        return "TIMBANG_2"
    if "TIMBANG_1" in menunggu:
        return "SECURITY_REGISTER"
    if menunggu == [TAHAP_TERAKHIR]:
        return "MENUNGGU_KELUAR"
    timbang1 = next((t for t in tahap if t["kode_tahap"] == "TIMBANG_1"), None)
    return "TIMBANG_1" if timbang1 and timbang1["status"] == "SELESAI" else "INSPEKSI_PROSES"


def tahap_banyak(daftar_tiket):
    """{no_tiket: [tahap]} untuk tiket alur dinamis (tiket lama tanpa tahap tidak ada di hasil)."""
    daftar_tiket = list(dict.fromkeys(daftar_tiket))
    hasil = {}
    for i in range(0, len(daftar_tiket), 500):
        bagian = daftar_tiket[i:i + 500]
        for r in _query(f"""SELECT TicketNumber AS no_tiket, StageCode AS kode_tahap, StepNo AS urutan, GroupNo AS grup, Status AS status
                            FROM WeightBridgeStage WHERE TicketNumber IN ({', '.join('?' * len(bagian))}) ORDER BY TicketNumber, StepNo""",
                        *bagian):
            hasil.setdefault(r.pop("no_tiket"), []).append(r)
    return hasil


def cek_tahap(no_tiket, kode_tahap, boleh_ulang=False):
    """(dinamis, pesan galat). dinamis False = tiket lama tanpa tahap (pemanggil memakai aturan lama).
    boleh_ulang: tahap yang sudah selesai boleh diisi ulang (koreksi sortasi / lab) selama tiket belum tuntas."""
    tahap = tahap_banyak([no_tiket]).get(no_tiket)
    if not tahap:
        return False, None
    nama = NAMA_TAHAP.get(kode_tahap, kode_tahap)
    milik = next((t for t in tahap if t["kode_tahap"] == kode_tahap), None)
    if milik is None:
        return True, f"Tahap {nama} tidak ada di alur tiket ini (Admin › Alur Tiket)"
    menunggu = tahap_menunggu(tahap)
    if kode_tahap in menunggu or (boleh_ulang and milik["status"] == "SELESAI" and menunggu):
        return True, None
    if milik["status"] == "SELESAI":
        return True, f"Tahap {nama} tiket ini sudah selesai"
    return True, "Belum bisa: tiket masih menunggu " + " / ".join(NAMA_TAHAP.get(t, t) for t in menunggu)


def lanjut(cursor, no_tiket, kode_tahap, id_user):
    """Tahap tiket alur dinamis selesai -> status ringkas baru. Tahap yang sudah selesai (diisi ulang) tidak berubah.
    None = tiket lama tanpa tahap (pemanggil memakai aturan lama)."""
    tahap = tahap_tiket(cursor, no_tiket)
    if not tahap:
        return None
    milik = next((t for t in tahap if t["kode_tahap"] == kode_tahap), None)
    if milik is not None and milik["status"] != "SELESAI":
        selesaikan_tahap(cursor, no_tiket, kode_tahap, id_user)
        milik["status"] = "SELESAI"
    return status_dari_tahap(tahap)
