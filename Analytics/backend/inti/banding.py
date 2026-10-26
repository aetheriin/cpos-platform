"""Periode pembanding untuk kartu KPI: jendela sepanjang rentang yang tampil (jumlah hari sama), tepat sebelum rentang itu.

Pemuat laporan ikut mengambil periode sepanjang periode yang dimuat tepat sebelumnya (baris bertanda kolom `lalu`), jadi rentang tampilan mana
pun di dalam periode yang dimuat selalu punya pembanding, termasuk rentang yang dimulai di tanggal awal data."""
import pandas as pd

from . import konfigurasi

SEHARI = pd.Timedelta(days=1)
_cache = {}   # id(df) -> (df, kini, lalu)


def jendela_sebelumnya(mulai, akhir):
    """(mulai, akhir) jendela sebelumnya untuk jendela [mulai, akhir] (keduanya inklusif), sama panjang."""
    mulai, akhir = pd.Timestamp(mulai), pd.Timestamp(akhir)
    lebar = akhir - mulai + SEHARI
    return mulai - lebar, mulai - SEHARI


def lengkap(mulai_lalu, mulai_data):
    """True kalau jendela sebelumnya seluruhnya ada di periode yang dimuat (bukan di baris `lalu`)."""
    return mulai_data is not None and pd.Timestamp(mulai_lalu) >= pd.Timestamp(mulai_data)


def bagi(df):
    """(kini, lalu). lalu None untuk data lama yang dimuat tanpa periode sebelumnya. Dicache per DataFrame."""
    simpan = _cache.get(id(df))
    if simpan and simpan[0] is df:
        return simpan[1], simpan[2]
    if "lalu" in df.columns:
        kini, lalu = df[~df["lalu"]].reset_index(drop=True), df[df["lalu"]].reset_index(drop=True)
    else:
        kini, lalu = df, None
    if len(_cache) >= konfigurasi.MAKS_DATASET:
        _cache.clear()
    _cache[id(df)] = (df, kini, lalu)
    return kini, lalu


def kpi_sebelumnya(hitung, kini, semua, ada_lalu, ps, pe, mulai_data, stok=()):
    """KPI jendela sebelumnya [ps, pe] untuk laporan yang ukurannya dihitung dari tanggal dokumen (PR/PO, PO/PI).

    Kalau jendela itu di dalam periode yang dimuat: dihitung dari `kini`, sama persis dengan cara menghitung rentang yang tampil.
    Kalau (sebagian) sebelum periode yang dimuat: dihitung dari `semua` (kini + lalu). Ukuran posisi (`stok`, mis. outstanding) dikosongkan di
    kasus ini, karena dokumen yang dibuat sebelum periode sebelumnya tidak pernah dimuat sehingga posisinya tidak sebanding.
    None kalau data periode sebelumnya tidak ada (data lama)."""
    if lengkap(ps, mulai_data):
        return hitung(kini, ps, pe)
    if not ada_lalu:
        return None
    k = hitung(semua, ps, pe)
    for s in stok:
        k[s] = None
    return k
