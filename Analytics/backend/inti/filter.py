"""Bantuan filter pilihan banyak dan tanggal yang dipakai semua laporan."""
import pandas as pd


class FilterTidakValid(ValueError):
    """Pesannya aman ditampilkan ke pengguna."""


def daftar(nilai):
    """None, satu teks, atau daftar -> daftar teks tidak kosong."""
    if nilai is None:
        return []
    if isinstance(nilai, str):
        nilai = [nilai]
    return [str(v).strip() for v in nilai if v is not None and str(v).strip() != ""]


def kanonik(nilai, pilihan, nama):
    """Nilai resmi dari `pilihan` (huruf besar-kecil bebas), tanpa duplikat, urut seperti `pilihan`."""
    hasil = []
    for v in daftar(nilai):
        kecil = v.lower()
        cocok = next((p for p in pilihan if p.lower() == kecil), None)
        if cocok is None:
            contoh = ", ".join(list(pilihan)[:8])
            raise FilterTidakValid(f"{nama} '{v}' tidak dikenal. Pilihan: {contoh}")
        if cocok not in hasil:
            hasil.append(cocok)
    return [p for p in pilihan if p in hasil]


def saring(df, filt, dimensi, lewati=None):
    """dimensi: {nama_filter: kolom}. Filter di `lewati` diabaikan, supaya grafik sumber filter tetap menampilkan semua pilihannya."""
    lewati = {lewati} if isinstance(lewati, str) else set(lewati or ())
    mask = pd.Series(True, index=df.index)
    for nama, kolom in dimensi.items():
        if filt.get(nama) and nama not in lewati:
            mask &= df[kolom].isin(filt[nama])
    return df[mask]


def tgl(t):
    return t.strftime("%Y-%m-%d")
