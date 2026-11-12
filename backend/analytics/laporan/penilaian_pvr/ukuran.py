"""Laporan PVR KPI dan PV KPI: rumus skor dan isi grafik. Skor = jumlah bobot dari baris yang dinilai (lihat sumber.bersihkan)."""
from .sumber import ANGKUTAN, KOSONG


def _r(x):
    return round(float(x), 2)


def kpi(d):
    return {
        "skor": _r(d["bobot"].sum()),
        "pvr": int(d[["comp", "pvr_number"]].drop_duplicates().shape[0]),
        "dinilai": len(d),
        "angkutan": int((d["kategori"] == ANGKUTAN).sum()),
        "pembuat": int(d["pembuat"].nunique()),
        "tanpa_kategori": int(d.loc[d["kategori"] == KOSONG, "pvr_number"].nunique()),
    }


def rekap(d):
    """Skor per bulan (baris) x pembuat (kolom), seperti pivot REKAP di Excel. Pembuat urut dari skor tertinggi."""
    if d.empty:
        return {"bulan": [], "pembuat": [], "nilai": [], "total_bulan": [], "total_pembuat": []}
    t = d.assign(bulan=d["tanggal"].dt.strftime("%Y-%m")).pivot_table(index="bulan", columns="pembuat", values="bobot", aggfunc="sum", fill_value=0)
    t = t[t.sum().sort_values(ascending=False).index].sort_index()
    return {
        "bulan": list(t.index), "pembuat": list(t.columns),
        "nilai": [[_r(v) for v in baris] for baris in t.values],
        "total_bulan": [_r(v) for v in t.sum(axis=1)], "total_pembuat": [_r(v) for v in t.sum()],
    }


def per_kategori(d):
    """Bobot, jumlah yang dinilai, dan skor tiap kategori."""
    hasil = [{"nama": kat, "bobot": _r(sub["bobot"].max()), "dinilai": len(sub), "pvr": int(sub["pvr_number"].nunique()), "skor": _r(sub["bobot"].sum())}
             for kat, sub in d.groupby("kategori")]
    return sorted(hasil, key=lambda r: (-r["skor"], -r["bobot"], r["nama"]))
