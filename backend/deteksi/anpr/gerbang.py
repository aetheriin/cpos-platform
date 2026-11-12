"""Kejadian gerbang: bacaan plat yang sama dari kamera-kamera satu gerbang dalam satu jendela waktu digabung jadi satu kejadian.
Arah (MASUK / KELUAR) = hadap kamera yang membaca paling awal, setelah ada kamera dengan hadap berbeda yang ikut membaca;
selama itu belum terjadi arahnya BELUM_PASTI. Sisi plat per bacaan: DEPAN bila hadap kamera = arah kendaraan, BELAKANG bila sebaliknya."""
from anpr.penstabil import PenstabilPlat, jarak_edit

# Diisi server_web tiap 30 detik dari database (Admin › Perangkat › Kamera Deteksi Plat, Admin › Pengaturan Site)
STATE = {"info": {}, "jendela": 60.0}          # info: {nama kamera: {'gate', 'facing', 'area'}}


def pasangkan(cur, id_deteksi, waktu, kamera, plat, conf, id_vehicle):
    """Gabungkan bacaan baru ke kejadian gerbang, di transaksi yang sama dengan INSERT riwayat.
    Return (id_kejadian, arah), atau None bila kamera tidak punya gerbang."""
    info = STATE["info"].get(kamera)
    if not info:
        return None
    gate, area = info["gate"], info["area"]
    cur.execute("""SELECT KejadianID, PlatNomor, ConfMax FROM dbo.KejadianPlat
                   WHERE Gate = ? AND CompAreaID = ? AND WaktuMulai >= DATEADD(second, ?, ?) ORDER BY WaktuMulai DESC""",
                gate, area, -int(STATE["jendela"]), waktu)
    cocok = next(((k, p, c) for k, p, c in cur.fetchall() if jarak_edit(p, plat) <= PenstabilPlat.MAKS_BEDA_MIRIP), None)

    if not cocok:                                    # kejadian baru
        cur.execute("""SET NOCOUNT ON;
                       INSERT INTO dbo.KejadianPlat (Gate, CompAreaID, PlatNomor, IDVehicle, Arah, WaktuMulai, WaktuAkhir, JumlahKamera, ConfMax)
                       VALUES (?, ?, ?, ?, 'BELUM_PASTI', ?, ?, 1, ?);
                       SELECT CAST(SCOPE_IDENTITY() AS BIGINT);""", gate, area, plat, id_vehicle, waktu, waktu, conf)
        kid = cur.fetchone()[0]
        cur.execute("UPDATE dbo.RiwayatDeteksi SET KejadianID = ? WHERE DeteksiID = ?", kid, id_deteksi)
        print(f"[GERBANG] {gate}: kejadian baru #{kid} dari {kamera} (arah belum pasti)")
        return kid, "BELUM_PASTI"

    kid, plat_terbaik, conf_max = cocok
    cur.execute("UPDATE dbo.RiwayatDeteksi SET KejadianID = ? WHERE DeteksiID = ?", kid, id_deteksi)
    # hadap kamera yang membaca di kejadian ini, beserta waktu baca paling awalnya
    cur.execute("""SELECT c.Facing, MIN(r.Waktu) FROM dbo.RiwayatDeteksi r JOIN dbo.CameraDeteksi c ON c.CamDetName = r.Kamera
                   WHERE r.KejadianID = ? GROUP BY c.Facing""", kid)
    hadap = {f: t for f, t in cur.fetchall()}
    arah = "BELUM_PASTI"
    if len(hadap) == 2 and len(set(hadap.values())) == 2:          # kedua hadap ikut membaca, dan waktunya tidak persis sama
        arah = min(hadap, key=hadap.get)
    if arah != "BELUM_PASTI":
        cur.execute("""UPDATE r SET Sisi = CASE WHEN c.Facing = ? THEN 'DEPAN' ELSE 'BELAKANG' END
                       FROM dbo.RiwayatDeteksi r JOIN dbo.CameraDeteksi c ON c.CamDetName = r.Kamera WHERE r.KejadianID = ?""", arah, kid)
    terbaik = plat if (conf or 0) > (conf_max or 0) else plat_terbaik
    cur.execute("""UPDATE dbo.KejadianPlat
                   SET Arah = ?, WaktuAkhir = ?, PlatNomor = ?, ConfMax = ?,
                       JumlahKamera = (SELECT COUNT(DISTINCT Kamera) FROM dbo.RiwayatDeteksi WHERE KejadianID = ?),
                       IDVehicle = (SELECT TOP 1 IDVehicle FROM dbo.DetailVehicle WHERE NoVehicle = ?)
                   WHERE KejadianID = ?""", arah, waktu, terbaik, max(conf or 0, conf_max or 0), kid, terbaik, kid)
    print(f"[GERBANG] {gate}: kejadian #{kid} + {kamera} -> arah {arah}")
    return kid, arah