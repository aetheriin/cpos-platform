"""Rumus Pembelian TBS Mingguan.

Atensi hanya untuk minggu lengkap terakhir, per business group, atas tonase. MEAN dan SD dari minggu-minggu lengkap sebelumnya
(grup yang tidak kirim dihitung 0 kg). NAIK kalau selisih > batas x SD, TURUN kalau < -batas x SD.
Kurang dari TBS_MINGGUAN_MIN_MINGGU minggu lengkap: tanpa atensi. Minggu belum lengkap ditampilkan tapi tidak dihitung."""
import pandas as pd

from inti import konfigurasi

BATAS = konfigurasi.TBS_MINGGUAN_BATAS_SD
MIN_MINGGU = konfigurasi.TBS_MINGGUAN_MIN_MINGGU


def daftar_minggu(d):
    """[{minggu, awal, akhir, lengkap}] dari yang paling lama."""
    m = d.groupby("minggu").agg(awal=("awal", "min"), akhir=("akhir", "max")).sort_index()
    return [{"minggu": k, "awal": r["awal"], "akhir": r["akhir"], "lengkap": (r["akhir"] - r["awal"]).days == 6} for k, r in m.iterrows()]


def minggu_dinilai(minggu):
    """(kunci minggu dinilai, [kunci minggu riwayat]) atau (None, []) kalau minggu lengkap kurang dari MIN_MINGGU."""
    lengkap = [m["minggu"] for m in minggu if m["lengkap"]]
    if len(lengkap) < MIN_MINGGU:
        return None, []
    return lengkap[-1], lengkap[:-1]


def atensi(tabel, dinilai, riwayat):
    """Per grup: rata, sd, nilai minggu dinilai, selisih, status ('NAIK', 'TURUN', atau None)."""
    if dinilai is None or tabel.empty:
        return pd.DataFrame(columns=["rata", "sd", "nilai", "selisih", "status"])
    h = tabel[riwayat]
    hasil = pd.DataFrame({"rata": h.mean(axis=1), "sd": h.std(axis=1, ddof=1), "nilai": tabel[dinilai]})
    hasil["selisih"] = hasil["nilai"] - hasil["rata"]
    batas = BATAS * hasil["sd"]
    hasil["status"] = None
    hasil.loc[hasil["selisih"] > batas, "status"] = "NAIK"
    hasil.loc[hasil["selisih"] < -batas, "status"] = "TURUN"
    return hasil
