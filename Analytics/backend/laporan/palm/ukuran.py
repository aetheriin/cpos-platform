"""Laporan Deteksi Kecurangan Timbangan: indikator risiko dan KPI."""
import pandas as pd

from inti import konfigurasi

AMBANG_TARA = konfigurasi.PALM_AMBANG_TARA_KG
AMBANG_DURASI = konfigurasi.PALM_AMBANG_DURASI_MENIT


def _teks_angka(x):
    """150 -> '150', 2.5 -> '2,5' (untuk label)."""
    return str(int(x)) if float(x) == int(x) else str(round(float(x), 2)).replace(".", ",")


# Label dibentuk dari ambang di .env, jadi tulisan dan aturannya selalu sama
NORMAL = "NORMAL"
RISIKO_TARA = f"WARNING: Tara >{_teks_angka(AMBANG_TARA)}kg atau <-{_teks_angka(AMBANG_TARA)}kg"
RISIKO_DURASI = f"WARNING: Durasi Timbang >{_teks_angka(AMBANG_DURASI / 60)} Jam"
URUTAN_RISIKO = [NORMAL, RISIKO_TARA, RISIKO_DURASI]
KUNCI_RISIKO = {NORMAL: "normal", RISIKO_TARA: "tara", RISIKO_DURASI: "durasi"}   # kunci di JSON (label panjang tidak dipakai sebagai kunci)


def indikator(tara_selisih, durasi):
    """Indikator risiko tiap transaksi. Selisih tara dinilai lebih dulu: kalau selisih tara melewati ambang (lebih dari +AMBANG atau kurang dari
    -AMBANG) transaksinya WARNING tara walau durasinya juga lama. Selain itu, durasi lebih dari ambang adalah WARNING durasi. Batas tepat
    (mis. tepat 150 kg atau 180 menit) masih NORMAL. Nilai kosong tidak pernah memicu WARNING."""
    tara = pd.to_numeric(tara_selisih, errors="coerce")
    lama = pd.to_numeric(durasi, errors="coerce")
    hasil = pd.Series(NORMAL, index=tara.index, dtype=object)
    hasil[lama > AMBANG_DURASI] = RISIKO_DURASI
    hasil[(tara > AMBANG_TARA) | (tara < -AMBANG_TARA)] = RISIKO_TARA
    return hasil


def kpi(df):
    """Empat kartu ringkasan: jumlah transaksi, yang berisiko (bukan NORMAL), rata-rata selisih tara, dan rata-rata potongan."""
    n = len(df)
    return {
        "transaksi": int(n),
        "berisiko": int((df["risiko"] != NORMAL).sum()),
        "rata_selisih_tara": round(float(df["tara_selisih"].mean()), 2) if n else 0.0,
        "rata_potongan": round(float(df["potongan"].mean()), 2) if n else 0.0,
    }
