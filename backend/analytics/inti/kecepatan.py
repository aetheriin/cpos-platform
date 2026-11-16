"""Kecepatan penyelesaian PR atau PO yang DIBUAT pada sebuah periode.

Masukan g (dari penyelesaian() tiap laporan): awal (tanggal dibuat, sama dengan Aging), selesai (PO/PI terakhir, kosong kalau belum),
lama (hari awal sampai selesai). rata_rata = rata-rata lama yang sudah selesai; selesai_periode = persen yang selesai di periode itu juga."""
import pandas as pd


def sekarang():
    return pd.Timestamp.today().normalize()


def ringkas(g, mulai, akhir):
    """Ringkasan untuk yang dibuat pada [mulai, akhir].

    Lama negatif (tanggal selesai lebih awal dari tanggal awal) adalah data janggal: dikeluarkan dari semua hitungan di sini dan
    jumlahnya dilaporkan di `dikecualikan` (tidak ditampilkan di layar). Void dan Closed tidak ada di g, jadi tidak ikut."""
    w = g[(g["awal"] >= mulai) & (g["awal"] <= akhir)]
    selesai = w[w["selesai"].notna()]
    janggal = selesai[selesai["lama"] < 0]
    sah = selesai[selesai["lama"] >= 0]
    dibuat = len(w) - len(janggal)                          # yang dibuat pada periode: masih Open + yang bisa diukur
    dalam = int((sah["selesai"] <= akhir).sum())            # sudah selesai pada atau sebelum akhir periode
    return {
        "rata_rata": round(float(sah["lama"].mean()), 1) if len(sah) else None,
        "diukur": int(len(sah)),
        "selesai_periode": {"jumlah": dalam, "dari": int(dibuat), "persen": (dalam / dibuat) if dibuat else None},
        "dikecualikan": int(len(janggal)),
    }
