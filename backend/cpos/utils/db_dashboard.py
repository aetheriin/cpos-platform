"""Dashboard: katalog widget, arus penimbangan, ringkasan security. Data harga di utils/harga.py."""
from utils.db_utils import get_connection, _rows_to_dicts

# Widget yang sudah dibuat di kode (templates/dashboard/widget/<nama>.html + dashboard.js + API datanya); harus sama dengan
# tabel Widget. Widget di tabel yang belum ada di sini diabaikan saat tampil.
WIDGET = {
    "harga": "Harga CPO, kernel, OER & biaya olah",
    "riwayat": "Riwayat harga",
    "arus": "Arus penimbangan & status jembatan timbang hari ini",
    "security": "Truk masuk & di dalam area, tamu, blacklist terdeteksi hari ini",
}
WIDGET_HARGA = {"harga", "riwayat"}       # widget yang memakai tombol Isi Harga (aksi Ubah menu dashboard)


def ringkas_security(id_area):
    """Dashboard Security: truk masuk hari ini & yang masih di dalam (logbook), tamu di dalam, blacklist terdeteksi hari ini."""
    from datetime import date
    from utils.area_filter import sql_area
    from utils.db_pos import logbook
    from utils.db_aktivitas import di_dalam
    lb = logbook(id_area, date.today())
    f_tamu, p_tamu = sql_area("CompAreaID", id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        tamu = sum(1 for d in di_dalam(id_area) if d["kategori"] == "TAMU")
        cursor.execute(f"SELECT COUNT(*) FROM BlacklistDetection WHERE DetectDate >= CAST(GETDATE() AS DATE){f_tamu}", *p_tamu)
        blacklist = cursor.fetchone()[0]
    finally:
        conn.close()
    return {"masuk": lb["masuk_hari_ini"], "di_dalam": len(lb["dalam"]), "keluar": len(lb["keluar"]), "tamu": tamu,
            "blacklist": blacklist, "dalam": lb["dalam"]}


def arus_hari_ini(id_area=None):
    """Ringkasan penimbangan hari ini (id_area None = semua area): angka, distribusi per produk,
    jumlah truk masuk / selesai per jam, dan posisi truk yang masih di dalam per tahap."""
    from utils.db_utils import _filter_area
    filter_area, param_area = _filter_area(id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        dasar = f"""
            FROM WeightBridge t
            JOIN Product p ON p.ProductID = t.ProductID
            LEFT JOIN WeighingSummary tb ON tb.TicketNumber = t.TicketNumber
            OUTER APPLY (SELECT MAX(pn.WeighDate) AS keluar FROM Weighing pn WHERE pn.TicketNumber = t.TicketNumber) w
            WHERE t.TicketDate >= CAST(GETDATE() AS DATE) AND t.StatusCode <> 'VOID'{filter_area}"""
        cursor.execute(f"""SELECT COUNT(*) AS masuk,
                                  SUM(CASE WHEN t.StatusCode = 'SELESAI' THEN 1 ELSE 0 END) AS selesai,
                                  SUM(CASE WHEN p.Category = 'TBS' AND t.StatusCode = 'SELESAI'
                                           THEN COALESCE(tb.Netto, t.SplitWeight) ELSE 0 END) AS tbs_kg,
                                  AVG(CASE WHEN t.StatusCode = 'SELESAI' AND w.keluar IS NOT NULL
                                           THEN CAST(DATEDIFF(MINUTE, t.TicketDate, w.keluar) AS FLOAT) END) AS siklus_menit
                           {dasar}""", *param_area)
        ringkas = _rows_to_dicts(cursor)[0]
        cursor.execute(f"""SELECT p.ProductName AS produk, SUM(COALESCE(tb.Netto, t.SplitWeight)) AS netto
                           {dasar} AND COALESCE(tb.Netto, t.SplitWeight) IS NOT NULL
                           GROUP BY p.ProductName ORDER BY netto DESC""", *param_area)
        distribusi = _rows_to_dicts(cursor)

        # Per jam: masuk = jam tiket dibuat; selesai = jam timbang terakhir tiket yang sudah SELESAI
        per_jam = [{"jam": j, "masuk": 0, "selesai": 0} for j in range(24)]
        cursor.execute(f"SELECT DATEPART(HOUR, t.TicketDate) AS jam, COUNT(*) AS n {dasar} GROUP BY DATEPART(HOUR, t.TicketDate)",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["masuk"] = n
        cursor.execute(f"""SELECT DATEPART(HOUR, w.keluar) AS jam, COUNT(*) AS n {dasar}
                           AND t.StatusCode = 'SELESAI' AND w.keluar IS NOT NULL GROUP BY DATEPART(HOUR, w.keluar)""",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["selesai"] = n

        # Posisi truk yang masih di dalam (semua tiket aktif, tidak hanya yang dibuat hari ini).
        # Setelah timbang 1: TBS ke Sortasi, produk lain ke Laboratorium.
        cursor.execute(f"""SELECT
                SUM(CASE WHEN t.StatusCode = 'SECURITY_REGISTER' AND ISNULL(a.FlowCode, '') <> 'POS_SAJA' THEN 1 ELSE 0 END) AS timbang_1,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_1' AND p.Category = 'TBS' THEN 1 ELSE 0 END) AS sortasi,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_1' AND p.Category <> 'TBS' THEN 1 ELSE 0 END) AS lab,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_2' THEN 1 ELSE 0 END) AS timbang_2,
                COUNT(*) AS di_dalam
            FROM WeightBridge t JOIN Product p ON p.ProductID = t.ProductID
            LEFT JOIN Flow a ON a.FlowID = t.FlowID
            WHERE t.StatusCode NOT IN ('SELESAI', 'REJECTED', 'VOID'){filter_area}""", *param_area)
        posisi = {k: int(v or 0) for k, v in _rows_to_dicts(cursor)[0].items()}
        ringkas["di_dalam"] = posisi.pop("di_dalam")
        # Tiket alur dinamis: dihitung ulang dari tahap yang ditunggu (status ringkasnya tidak cukup, mis. Lab sebelum timbang)
        cursor.execute(f"""SELECT t.TicketNumber AS no_tiket, t.StatusCode AS status, p.Category AS kategori
                           FROM WeightBridge t JOIN Product p ON p.ProductID = t.ProductID
                           WHERE t.StatusCode NOT IN ('SELESAI', 'REJECTED', 'VOID')
                             AND EXISTS (SELECT 1 FROM WeightBridgeStage g WHERE g.TicketNumber = t.TicketNumber){filter_area}""",
                       *param_area)
        dinamis = _rows_to_dicts(cursor)
        terlama = {}                                # menit truk yang paling lama menunggu per posisi (alur dinamis)
        if dinamis:
            from utils.alur import tahap_banyak, tahap_menunggu, durasi_tahap
            tahap = tahap_banyak([r["no_tiket"] for r in dinamis])
            kunci_lama = {"SECURITY_REGISTER": "timbang_1", "TIMBANG_2": "timbang_2",
                          "TIMBANG_1": None}
            for r in dinamis:                       # keluarkan hitungan cara lama, masukkan hitungan per tahap
                k = kunci_lama.get(r["status"], "-")
                if k is None:
                    k = "sortasi" if r["kategori"] == "TBS" else "lab"
                if k in posisi and posisi[k] > 0:
                    posisi[k] -= 1
                milik = tahap.get(r["no_tiket"], [])
                lama = {d["kode"]: d["menit"] for d in durasi_tahap(milik, milik[0]["sekarang"])} if milik else {}
                for kode in tahap_menunggu(milik):
                    kunci = {"TIMBANG_1": "timbang_1", "TIMBANG_2": "timbang_2", "SORTASI": "sortasi", "LAB": "lab",
                             "SECURITY_KELUAR": "keluar"}[kode]
                    posisi[kunci] = posisi.get(kunci, 0) + 1
                    if lama.get(kode) is not None:
                        terlama[kunci] = max(terlama.get(kunci, 0), lama[kode])
        posisi["terlama"] = terlama

        # Rata-rata lama tiap tahap yang selesai hari ini (alur dinamis): dari tuntasnya kelompok sebelumnya
        # sampai tahap itu selesai. Security (pembuatan tiket) tidak dihitung.
        cursor.execute(f"""SELECT g.StageCode AS kode, COUNT(*) AS jumlah,
                                  AVG(CAST(DATEDIFF(SECOND, m.mulai, g.FinishDate) AS FLOAT)) / 60 AS rata_menit
                           FROM WeightBridgeStage g JOIN WeightBridge t ON t.TicketNumber = g.TicketNumber
                           CROSS APPLY (SELECT MAX(h.FinishDate) AS mulai FROM WeightBridgeStage h
                                        WHERE h.TicketNumber = g.TicketNumber AND h.GroupNo < g.GroupNo) m
                           WHERE g.Status = 'SELESAI' AND g.StageCode <> 'SECURITY' AND m.mulai IS NOT NULL
                             AND g.FinishDate >= CAST(GETDATE() AS DATE){filter_area}
                           GROUP BY g.StageCode""", *param_area)
        durasi = {r["kode"]: {"jumlah": r["jumlah"], "rata_menit": round(r["rata_menit"] or 0, 1)} for r in _rows_to_dicts(cursor)}
        return ringkas, distribusi, per_jam, posisi, durasi
    finally:
        conn.close()
