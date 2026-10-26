"""Laporan Purchase Invoice: tiga tabel, PI yang belum punya PVR maupun PV, PI yang dibayar PV tanpa PVR, dan PI yang sudah PVR."""
from inti.filter import kanonik, saring, tgl
from inti.laporan import rentang_tampil
from inti.tabel import periksa, susun

from .sumber import BELUM, PV_TANPA_PVR, URUTAN_STATUS

DIM = {"perusahaan": "comp", "status": "status"}
JENIS_DETAIL = {"belum": "Belum PVR & PV", "pv_tanpa_pvr": "PV tanpa PVR", "sudah": "Sudah PVR"}

_KOLOM_AWAL = [("comp", "Perusahaan", "teks"), ("status", "Status", "teks"), ("po_number", "No. PO", "teks"), ("supplier_code", "Kode Supplier", "teks"),
               ("supplier_name", "Nama Supplier", "teks"), ("pi_number", "No. PI", "teks")]
_KOLOM_PI = [("pi_date", "Tanggal PI", "tanggal"), ("itemcode", "Kode Barang", "teks"), ("itemname", "Nama Barang", "teks"),
             ("line_total", "Line Total", "angka"), ("qty", "Qty PI", "angka"), ("pi_by", "PI Dibuat Oleh", "teks")]
_KOLOM_PV = [("pv_number", "No. PV", "teks"), ("pv_date", "Tanggal PV", "tanggal"), ("pv_by", "PV Dibuat Oleh", "teks")]
KOLOM = {
    "belum": _KOLOM_AWAL + [("umur", "Aging PI (hari)", "angka")] + _KOLOM_PI,
    "pv_tanpa_pvr": _KOLOM_AWAL + _KOLOM_PI + _KOLOM_PV,
    "sudah": _KOLOM_AWAL + _KOLOM_PI + [("pvr_number", "No. PVR", "teks"), ("pvr_date", "Tanggal PVR", "tanggal"), ("pvr_by", "PVR Dibuat Oleh", "teks"),
                                        ("lama_pvr", "PI ke PVR (hari)", "angka")] + _KOLOM_PV,
}
KOLOM_CARI = ["comp", "po_number", "supplier_code", "supplier_name", "pi_number", "itemcode", "itemname", "pi_by", "pvr_number", "pv_number"]


def _saring(df, ds, filt):
    dari, sampai = rentang_tampil(ds)
    if "status" not in df.columns:
        raise RuntimeError("Data Purchase Invoice yang tersimpan masih versi lama (tanpa PV). Klik Muat ulang data.")
    pilihan = {"perusahaan": sorted(df["comp"].unique()), "status": URUTAN_STATUS}
    filt = {"perusahaan": kanonik((filt or {}).get("perusahaan"), pilihan["perusahaan"], "Perusahaan"),
            "status": kanonik((filt or {}).get("status"), pilihan["status"], "Status")}
    d = df[(df["pi_date"] >= dari) & (df["pi_date"] <= sampai)]
    return saring(d, filt, DIM), dari, sampai, pilihan


AMBANG_LAMA = 30   # hari; PI belum PVR dan belum PV yang lebih lama dari ini disorot di kartu


def kpi(d):
    """Ringkasan untuk kartu. Dokumen = nomor PI unik per perusahaan; nilai = jumlah Line Total (sudah dikali kurs)."""
    belum, pv_saja, sudah = d[d["status"] == BELUM], d[d["status"] == PV_TANPA_PVR], d[d["sudah_pvr"]]
    dok = lambda t: int(t[["comp", "pi_number"]].drop_duplicates().shape[0])
    umur = belum.groupby(["comp", "pi_number"])["umur"].max()
    lama = sudah.groupby(["comp", "pi_number"])["lama_pvr"].max().dropna()
    return {
        "belum": dok(belum), "nilai_belum": float(belum["line_total"].sum()),
        "belum_lama": int((umur > AMBANG_LAMA).sum()), "umur_maks": int(umur.max()) if len(umur) else None,
        "pv_tanpa_pvr": dok(pv_saja), "nilai_pv_tanpa_pvr": float(pv_saja["line_total"].sum()),
        "sudah": dok(sudah), "nilai_sudah": float(sudah["line_total"].sum()),
        "lama_pvr": {"median": float(lama.median()), "rata": float(lama.mean())} if len(lama) else {"median": None, "rata": None},
        "ambang": AMBANG_LAMA,
    }


def bangun(df, ds, filt=None):
    d, dari, sampai, pilihan = _saring(df, ds, filt)
    sudah = int(d["sudah_pvr"].sum())
    return {
        "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "kpi": kpi(d),
        "jumlah": {"belum": int((d["status"] == BELUM).sum()), "pv_tanpa_pvr": int((d["status"] == PV_TANPA_PVR).sum()), "sudah": sudah},
        "pilihan": pilihan,
    }


def detail(df, jenis, ds, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'belum': PI tanpa PVR dan tanpa PV, yang paling lama di atas. 'pv_tanpa_pvr': PI yang dibayar PV tanpa PVR, PV terbaru di atas.
    'sudah': PI yang sudah disebut PVR, yang terbaru di atas."""
    periksa(jenis, JENIS_DETAIL, urut, KOLOM[jenis] if jenis in KOLOM else [], arah)
    d, dari, sampai, _ = _saring(df, ds, filt)
    t = {"belum": d[d["status"] == BELUM], "pv_tanpa_pvr": d[d["status"] == PV_TANPA_PVR], "sudah": d[d["sudah_pvr"]]}[jenis].reset_index(drop=True)
    urut_awal, arah_awal = {"belum": ("pi_date", "asc"), "pv_tanpa_pvr": ("pv_date", "desc"), "sudah": ("pvr_date", "desc")}[jenis]
    hasil = susun(t, KOLOM[jenis], KOLOM_CARI, cari, urut, arah, urut_awal, arah_awal, halaman, ukuran, pembanding="pi_number")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(dari), "akhir": tgl(sampai)}, **hasil}
