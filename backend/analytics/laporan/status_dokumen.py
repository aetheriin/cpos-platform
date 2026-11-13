"""Kerangka laporan "status tindak lanjut dokumen" (model laporan Purchase Invoice): satu baris per baris dokumen, kartu ringkasan, dan
tabel per status. Dipakai laporan Purchase Request (PR -> PO) dan Purchase Orders (PO -> PI).

Tiap laporan cukup menyebut kolom tanggal dokumen, urutan status, tab tabel (status yang masuk, urutan bawaan, kolom), dan fungsi kartu."""
from dataclasses import dataclass
from datetime import date

import pandas as pd

from inti.filter import kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun
from inti.nama import pisah
from inti.umur import URUTAN_KELOMPOK_UMUR, kelompok_umur

# Filter yang ada di semua laporan ini: {nama: (kolom, judul)}. Laporan menambah filternya sendiri lewat `dim`.
DIM_DASAR = {"perusahaan": ("comp", "Perusahaan"), "status": ("status", "Status"), "aging": ("aging", "Aging")}
AMBANG_LAMA = 30   # hari; dokumen yang belum ditindaklanjuti lebih lama dari ini disorot di kartu


@dataclass
class Tab:
    judul: str
    status: tuple       # status yang masuk tab ini
    urut: str           # kolom urutan bawaan
    arah: str
    kolom: list         # [(kunci, judul, tipe)]


def gabung(nilai):
    """Teks unik dipisah koma, urut kemunculan; yang kosong dibuang."""
    return ", ".join(dict.fromkeys(v for v in nilai if v and v != "(kosong)"))


def hari_sejak(tanggal):
    return (pd.Timestamp(date.today()) - tanggal).dt.days


def dokumen(t, nomor):
    """Jumlah dokumen unik per perusahaan."""
    return int(t[["comp", nomor]].drop_duplicates().shape[0])


def lama(t, kolom):
    """{median, rata} hari, atau None bila belum ada."""
    s = t[kolom].dropna()
    return {"median": float(s.median()), "rata": float(s.mean())} if len(s) else {"median": None, "rata": None}


class LaporanStatus:
    """dim: filter tambahan {nama: (kolom, judul)}, mis. kategori atau supplier. Aging = kelompok umur dokumen (kolom `umur`).
    banyak: nama filter yang selnya bisa berisi beberapa nama dipisah koma (mis. buyer); pilihannya per nama."""

    def __init__(self, nama, kol_tanggal, urutan_status, tab, kolom_cari, kpi, pembanding, dim=None, banyak=()):
        self.nama, self.kol_tanggal, self.urutan_status = nama, kol_tanggal, urutan_status
        self.tab, self.kolom_cari, self.kpi, self.pembanding = tab, kolom_cari, kpi, pembanding
        self.dim, self.banyak = {**DIM_DASAR, **(dim or {})}, set(banyak)

    @property
    def filter_didukung(self):
        return tuple(self.dim)

    @property
    def label_filter(self):
        return {k: judul for k, (_, judul) in self.dim.items()}

    def _pilihan(self, df, nama, kolom):
        if nama == "status":
            return self.urutan_status
        if nama == "aging":
            return [u for u in URUTAN_KELOMPOK_UMUR if u in set(df["aging"])]
        nilai = df[kolom].dropna().astype(str)
        if nama in self.banyak:
            nilai = (n for v in nilai for n in pisah(v))
        return sorted({v for v in nilai if v.strip() and v != "(kosong)"}, key=str.casefold)

    def _saring(self, df, ds, filt):
        dari, sampai = rentang_tampil(ds)
        df = df.assign(aging=[kelompok_umur(u) for u in df["umur"]])
        pilihan = {k: self._pilihan(df, k, kolom) for k, (kolom, _) in self.dim.items()}
        filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul) for k, (_, judul) in self.dim.items()}
        d = df[(df[self.kol_tanggal] >= dari) & (df[self.kol_tanggal] <= sampai)]
        for k in self.banyak:
            if filt[k]:
                d = d[d[self.dim[k][0]].map(lambda v, pilih=set(filt[k]): not pilih.isdisjoint(pisah(v)))]
        biasa = {k: kolom for k, (kolom, _) in self.dim.items() if k not in self.banyak}
        return saring(d, filt, biasa), dari, sampai, pilihan

    def bangun(self, df, ds, filt=None):
        d, dari, sampai, pilihan = self._saring(df, ds, filt)
        return {
            "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
            "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
            "kpi": dict(self.kpi(d), ambang=AMBANG_LAMA),
            "jumlah": {j: int(d["status"].isin(t.status).sum()) for j, t in self.tab.items()},
            "pilihan": pilihan,
        }

    def detail(self, df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
        judul = {j: t.judul for j, t in self.tab.items()}
        periksa(jenis, judul, urut, self.tab[jenis].kolom if jenis in self.tab else [], arah)
        t = self.tab[jenis]
        d, dari, sampai, _ = self._saring(df, ds, filt)
        hasil = susun(d[d["status"].isin(t.status)].reset_index(drop=True), t.kolom, self.kolom_cari, cari, urut, arah, t.urut, t.arah,
                      halaman, ukuran, pembanding=self.pembanding)
        return {"jenis": jenis, "judul": t.judul, "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
