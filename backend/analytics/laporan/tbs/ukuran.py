"""Laporan Penerimaan TBS: KPI, deret harian, dan forecast netto.

Forecast untuk H = TBS_HARI_FORECAST hari setelah hari aktual terakhir:
  forecast(t) = Rata-rata Harian x H x Proporsi Tahun Lalu(t)
- Rata-rata Harian  : rata-rata netto per hari selama TBS_HARI_SKALA hari terakhir (bawaan 14 = 2 minggu), hanya dari hari yang ada
                      penerimaannya. Hari tanpa penerimaan (mis. libur) tidak dihitung. Dikali H = kapasitas minggu depan.
- Proporsi Tahun Lalu(t): netto tanggal t - 364 hari (hari dalam seminggu sama) dibagi total netto blok H hari tahun lalu itu. Jumlah
                      proporsi = 1. Hari yang tahun lalu kosong diisi dulu dari hari yang sama di minggu-minggu sekitarnya (_isi_hari_kosong):
                      forecast memperkirakan penerimaan kalau hari itu tetap ada yang masuk.
Kalau tidak ada hari kosong, hasilnya sama dengan cara Excel lama (total 14 hari / 2 x proporsi).
Kalau blok tahun lalu tidak ada di data (atau seluruhnya nol) forecast kosong.
Interval kepercayaan: lihat _interval (kesalahan metode yang sama pada minggu-minggu sebelumnya)."""
from datetime import date

import numpy as np
import pandas as pd

from inti import konfigurasi

SEHARI = pd.Timedelta(days=1)
GESER_TAHUN = pd.Timedelta(days=364)   # 52 minggu: hari dalam seminggu tetap sama


def kpi(d):
    netto, nilai = float(d["netto"].sum()), float(d["nilai"].sum())
    rata_harian = d.groupby("tgl")["netto"].mean()          # Rata-rata per truk: rata-rata dari rata-rata netto per baris tiap hari (AVERAGEX)
    return {
        "netto": round(netto, 2),
        "nilai": round(nilai, 2),
        "harga": round(nilai / netto, 2) if netto else None,       # rata-rata tertimbang: total nilai / total kg
        "supplier": int(d.loc[d["netto"] > 0, "supplier"].nunique()),
        "per_truk": round(float(rata_harian.mean()), 2) if len(rata_harian) else None,
        "baris": int(len(d)),                                       # jumlah baris tab Per pembelian
        "supplier_baris": int(d["supplier"].nunique()),            # jumlah baris tab Per supplier
    }


def harian(d, mulai, akhir):
    """Netto dan nilai per hari kalender dari mulai sampai akhir; hari tanpa pembelian bernilai nol."""
    hari = pd.date_range(pd.Timestamp(mulai), pd.Timestamp(akhir), freq="D")
    g = d.groupby("tgl")[["netto", "nilai"]].sum()
    return g.reindex(hari, fill_value=0.0)


def akhir_lengkap(d):
    """Hari aktual terakhir (MAX PURCHASE DATE pada seluruh data). Hari ini belum selesai, jadi tidak dipakai."""
    terakhir = d["tgl"].max()
    if pd.isna(terakhir):
        return None
    return min(terakhir, pd.Timestamp(date.today()) - SEHARI)


def _forecast_dari(s, akhir, n_hari):
    """Forecast n_hari setelah `akhir` dari deret harian s (index tanggal tanpa celah). None kalau data tidak cukup."""
    k = konfigurasi.TBS_HARI_SKALA
    s = s[:akhir]
    if len(s) < k:
        return None
    dasar = s.iloc[-k:]
    masuk = dasar[dasar > 0]                      # hari tanpa penerimaan tidak dihitung
    if masuk.empty:
        return None
    rata = float(masuk.mean())
    mulai = akhir + SEHARI
    blok_mulai = mulai - GESER_TAHUN
    blok = s[blok_mulai:blok_mulai + (n_hari - 1) * SEHARI]
    if len(blok) < n_hari or blok.index[0] != blok_mulai or blok.sum() <= 0:
        return None
    lalu = _isi_hari_kosong(s, blok)
    proporsi = lalu / lalu.sum()
    tanggal = pd.date_range(mulai, periods=n_hari, freq="D")
    return {"tanggal": tanggal, "nilai": rata * n_hari * proporsi, "proporsi": proporsi, "rata": rata, "hari_masuk": int(len(masuk)),
            "blok": (blok_mulai, blok_mulai + (n_hari - 1) * SEHARI)}


def _isi_hari_kosong(s, blok):
    """Netto blok tahun lalu, dengan hari yang kosong (nol) diganti: forecast memperkirakan penerimaan kalau hari itu tetap ada yang masuk,
    jadi libur tahun lalu (mis. tanggal merah) tidak boleh membuat proporsinya nol. Pengganti, berurutan sampai ketemu yang ada isinya:
    rata-rata hari yang sama 1 minggu sebelum dan sesudahnya (tahun lalu), lalu 2 minggu sebelum dan sesudahnya, lalu rata-rata hari lain
    di blok yang ada penerimaannya."""
    lalu = blok.to_numpy(dtype=float).copy()
    for i, t in enumerate(blok.index):
        if lalu[i] > 0:
            continue
        for geser in (7, 14):
            tetangga = [s.get(t + arah * geser * SEHARI, 0.0) for arah in (-1, 1)]
            tetangga = [v for v in tetangga if v > 0]
            if tetangga:
                lalu[i] = float(np.mean(tetangga))
                break
    kosong = lalu <= 0
    if kosong.any():
        lalu[kosong] = lalu[~kosong].mean()
    return lalu


def forecast(d, akhir=None):
    """Forecast netto dan nilai TBS_HARI_FORECAST hari ke depan, dengan uji ketepatan. d: semua riwayat yang dimuat (kini dan lalu), sudah
    disaring filter laporan. akhir: hari aktual terakhir dari seluruh data (Excel: MAX dengan ALL(DATA)); bawaan dari d."""
    akhir = akhir if akhir is not None else akhir_lengkap(d)
    if akhir is None or d.empty:
        return None
    n = konfigurasi.TBS_HARI_FORECAST
    deret = harian(d, d["tgl"].min(), akhir)
    f = _forecast_dari(deret["netto"], akhir, n)
    if f is None:
        return None
    k = konfigurasi.TBS_HARI_SKALA
    dasar_harga = deret.iloc[-k:]
    harga = float(dasar_harga["nilai"].sum() / dasar_harga["netto"].sum()) if dasar_harga["netto"].sum() else 0.0

    iv = _interval(deret["netto"], akhir, n)
    hari = []
    for t, v, p in zip(f["tanggal"], f["nilai"], f["proporsi"]):
        h = {"hari": t.strftime("%Y-%m-%d"), "netto": round(float(v), 2), "nilai": round(float(v) * harga, 2), "proporsi": round(float(p), 4)}
        if iv:
            h["bawah"], h["atas"] = round(float(v) * iv["harian"][0], 2), round(float(v) * iv["harian"][1], 2)
        hari.append(h)
    total = float(f["nilai"].sum())
    return {
        "akhir_aktual": akhir.strftime("%Y-%m-%d"),
        "hari": hari,
        "dasar": {"rata_harian": round(f["rata"], 2), "hari_dasar": k, "hari_masuk": f["hari_masuk"], "harga": round(harga, 2),
                  "blok_mulai": f["blok"][0].strftime("%Y-%m-%d"), "blok_akhir": f["blok"][1].strftime("%Y-%m-%d")},
        "uji": _uji_minggu_lalu(deret["netto"], akhir, n),
        # interval kepercayaan dari kesalahan forecast yang sama di minggu-minggu sebelumnya (None kalau ujinya kurang dari TBS_UJI_MIN kali)
        "interval": None if not iv else {"tingkat": konfigurasi.TBS_INTERVAL, "uji": iv["uji"],
                                         "total_bawah": round(total * iv["mingguan"][0], 2), "total_atas": round(total * iv["mingguan"][1], 2)},
    }


def _uji_minggu_lalu(s, akhir, n):
    """Forecast yang dibuat n hari lalu (seolah-olah data berhenti di akhir - n hari) dibandingkan dengan aktual n hari terakhir yang sudah
    terjadi. None kalau forecast itu tidak bisa dibuat atau aktualnya nol."""
    batas = akhir - n * SEHARI
    lama = _forecast_dari(s, batas, n)
    if lama is None:
        return None
    aktual = s[batas + SEHARI:akhir].to_numpy()
    if len(aktual) < n or aktual.sum() <= 0:
        return None
    return {"mulai": (batas + SEHARI).strftime("%Y-%m-%d"), "akhir": akhir.strftime("%Y-%m-%d"),
            "forecast": round(float(lama["nilai"].sum()), 2), "aktual": round(float(aktual.sum()), 2),
            "selisih": round(float(lama["nilai"].sum() / aktual.sum() - 1), 4),                         # + = forecast terlalu tinggi
            "meleset_harian": round(float(np.abs(lama["nilai"] - aktual).sum() / aktual.sum()), 4)}   # rata-rata meleset per hari, ditimbang volume


def _interval(s, akhir, n):
    """Interval kepercayaan empiris. Forecast yang sama dijalankan seolah-olah dari TBS_UJI_MINGGU minggu sebelumnya (titik awal mundur 7 hari
    tiap kali), lalu dibandingkan dengan aktualnya: rasio aktual / forecast per hari dan per total n hari. Batas interval = kuantil rasio itu
    (tingkat TBS_INTERVAL, mis. 0,8 = kuantil 10% dan 90%), dikalikan ke forecast. Hari yang diramal 0 tidak ikut dihitung."""
    harian, mingguan = [], []
    for j in range(1, konfigurasi.TBS_UJI_MINGGU + 1):
        batas = akhir - 7 * j * SEHARI
        lama = _forecast_dari(s, batas, n)
        if lama is None:
            continue
        aktual = s[batas + SEHARI:batas + n * SEHARI].to_numpy()
        if len(aktual) < n:
            continue
        ada = lama["nilai"] > 0
        harian += list(aktual[ada] / lama["nilai"][ada])
        if lama["nilai"].sum() > 0:
            mingguan.append(aktual.sum() / lama["nilai"].sum())
    if len(mingguan) < konfigurasi.TBS_UJI_MIN:
        return None
    a = (1 - konfigurasi.TBS_INTERVAL) / 2
    kuantil = lambda x: (float(np.quantile(x, a)), float(np.quantile(x, 1 - a)))
    return {"harian": kuantil(harian), "mingguan": kuantil(mingguan), "uji": len(mingguan)}
