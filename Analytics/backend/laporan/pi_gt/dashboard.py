"""Laporan PI & GT: data dashboard dan tabel detail, per bulan dengan pola seperti PO & PI.

Outstanding dan New PI dihitung dari baris PI yang perlu GT (lihat sumber.perlu_gt) dan hanya ikut filter perusahaan dan importance. Filter yang hanya dimiliki GT
(pembuat, gudang asal dan tujuan) dipakai untuk angka GT saja, supaya outstanding tidak berubah saat tampilan awal menyaring
pembuat Logistik.
"""
from inti import konfigurasi
from inti.filter import FilterTidakValid, kanonik, saring, tgl
import pandas as pd
from inti.tabel import periksa, susun

from . import ukuran as U

# (kunci filter, judul, kolom)
FILTER = [
    ("perusahaan", "Perusahaan", "comp"),
    ("pembuat", "Pembuat GT", "gt_by"),
    ("dari_gudang", "Gudang asal", "dari_gudang"),
    ("ke_gudang", "Gudang tujuan", "ke_gudang"),
    ("importance", "Importance", "importance"),
]
DIM = {k: kolom for k, _, kolom in FILTER}
KHUSUS_GT = ("pembuat", "dari_gudang", "ke_gudang")
URUTAN_IMPORTANCE = ["Critical", "Urgent", "Important", "Normal", "Low"]

KOLOM_DETAIL = [
    ("comp", "Perusahaan", "teks"), ("status", "Status", "teks"),
    ("pi_number", "No. PI", "teks"), ("pi_date", "Tgl PI", "tanggal"), ("umur", "Aging (hari)", "angka"), ("pi_by", "PI Dibuat Oleh", "teks"),
    ("peminta", "Gudang Peminta", "teks"),
    ("gt_number", "No. GT", "teks"), ("gt_date", "Tgl GT", "tanggal"), ("gt_by", "GT Dibuat Oleh", "teks"),
    ("dari_gudang", "Dari Gudang", "teks"), ("ke_gudang", "Ke Gudang", "teks"),
    ("terima_date", "Tgl Diterima", "tanggal"), ("diterima_oleh", "Diterima Oleh", "teks"),
    ("lead_logistik", "Logistics Lead Time (hari)", "angka"), ("lead_pengadaan", "Procurement Lead Time (hari)", "angka"),
    ("itemcode", "Kode Barang", "teks"), ("itemname", "Nama Barang", "teks"), ("uom", "UOM", "teks"),
    ("qty_pi", "Qty PI", "angka"), ("qty_gt", "Qty GT", "angka"), ("importance", "Importance", "teks"),
    ("pr_number", "No. PR", "teks"), ("po_number", "No. PO", "teks"),
]
KOLOM_CARI = ["comp", "pi_number", "gt_number", "gt_by", "pi_by", "pr_number", "po_number", "itemcode", "itemname", "dari_gudang", "ke_gudang"]
JENIS_DETAIL = {"outstanding": "Outstanding akhir", "gt": "GT", "belum_diterima": "GT belum diterima"}


def _urut(nilai, acuan):
    ada = set(nilai)
    return [v for v in acuan if v in ada] + sorted(ada - set(acuan), key=str.casefold)


def _pilihan(df):
    gt = df[df["gt_number"] != ""]
    # Orang Logistik selalu ada di pilihan, supaya tampilan awal tetap sah walau salah satunya tidak membuat GT di periode ini
    pembuat = set(gt["gt_by"]) | {n.title() for n in konfigurasi.PIGT_LOGISTIK}
    return {
        "perusahaan": sorted(df["comp"].unique()),
        "pembuat": sorted(pembuat, key=str.casefold),
        "dari_gudang": sorted(gt["dari_gudang"].unique(), key=str.casefold),
        "ke_gudang": sorted(gt["ke_gudang"].unique(), key=str.casefold),
        "importance": _urut(df["importance"].unique(), URUTAN_IMPORTANCE),
    }


def bulan_rentang(dari, sampai):
    """[(mulai, akhir)] bulan kalender yang menyentuh rentang, dipotong ke rentang itu, dari yang paling lama."""
    dari, sampai = pd.Timestamp(dari).normalize(), pd.Timestamp(sampai).normalize()
    hasil, s = [], dari.replace(day=1)
    while s <= sampai:
        akhir = s + pd.offsets.MonthEnd(0)
        hasil.append((max(s, dari), min(akhir, sampai)))
        s = akhir + pd.Timedelta(days=1)
    return hasil


def _siapkan(df, dari, sampai, bulan, filt):
    """(baris PI yang perlu GT, baris GT, filter rapi, pilihan, daftar bulan, awal jendela, akhir jendela).
    bulan: indeks bulan terpilih (parameter API-nya tetap bernama `minggu`, sama dengan laporan mingguan)."""
    daftar = bulan_rentang(dari, sampai)
    if bulan is not None and not (0 <= bulan < len(daftar)):
        raise FilterTidakValid(f"bulan harus antara 0 dan {len(daftar) - 1} (0 = bulan paling lama)")
    ws, we = daftar[bulan] if bulan is not None else (daftar[0][0], daftar[-1][1])
    pilihan = _pilihan(df)
    filt = {k: kanonik((filt or {}).get(k), pilihan[k], judul) for k, judul, _ in FILTER}
    pi = saring(df[(df["pi_number"] != "") & df["perlu_gt"]], filt, DIM, lewati=KHUSUS_GT)
    gt = saring(df[df["gt_number"] != ""], filt, DIM)
    return pi, gt, filt, pilihan, daftar, ws, we


def bangun(df, dari, sampai, bulan=None, filt=None):
    pi, gt, filt, pilihan, daftar, ws, we = _siapkan(df, dari, sampai, bulan, filt)
    dalam = U.gt_dalam(gt, ws, we)
    out = pi[U.mask_outstanding(pi, we)]
    # Grafik GT per pembuat tidak disaring pembuatnya sendiri, supaya nama lain tetap terlihat setelah satu nama dipilih
    gt_semua_pembuat = saring(df[df["gt_number"] != ""], filt, DIM, lewati="pembuat")
    urut_pembuat = U.gt_dalam(gt_semua_pembuat, daftar[0][0], daftar[-1][1])["gt_by"].value_counts().index
    tampil_pembuat = [n for n in urut_pembuat if n in filt["pembuat"]] if filt["pembuat"] else list(urut_pembuat)
    urut_comp = U.gt_dalam(gt, daftar[0][0], daftar[-1][1])["comp"].value_counts().index
    return {
        "filter": {"minggu": bulan, **filt},
        "periode": {"mulai": tgl(ws), "akhir": tgl(we), "jumlah_bulan": len(daftar)},
        "rentang": {"dari": tgl(dari), "sampai": tgl(sampai), "satuan": "hari", "bawaan": None},
        "ambang": U.AMBANG,
        "kpi": U.kpi(pi, gt, ws, we),
        "temuan": U.temuan(dalam, out, gt[U.mask_belum_diterima(gt, we)], we),
        "bulanan": U.per_periode(pi, gt, daftar, tgl),
        "outstanding_perusahaan": U.outstanding_per(pi, "comp", ws, we),
        "gt_per_perusahaan": U.gt_per(gt, "comp", list(urut_comp), daftar),
        "gt_per_pembuat": U.gt_per(gt_semua_pembuat, "gt_by", tampil_pembuat, daftar),
        "durasi_rute": U.durasi_per(dalam, ["dari_gudang", "ke_gudang"], "lead_logistik"),
        "durasi_perusahaan": U.durasi_per(dalam, "comp", "lead_pengadaan"),
        "jumlah": {"outstanding": len(out), "gt": len(dalam), "belum_diterima": int(U.mask_belum_diterima(gt, we).sum())},
        "pilihan": {**pilihan, "pembuat_semua": pilihan["pembuat"]},
    }


def detail(df, jenis, dari, sampai, bulan=None, filt=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """'outstanding': PI yang belum di-GT pada akhir periode, yang paling lama di atas. 'gt': barang di GT dalam periode.
    'belum_diterima': GT yang belum diterima pada akhir periode."""
    periksa(jenis, JENIS_DETAIL, urut, KOLOM_DETAIL, arah)
    pi, gt, _, _, _, ws, we = _siapkan(df, dari, sampai, bulan, filt)
    if jenis == "outstanding":
        t, urut_awal, arah_awal = pi[U.mask_outstanding(pi, we)], "umur", "desc"
    elif jenis == "gt":
        t, urut_awal, arah_awal = U.gt_dalam(gt, ws, we), "gt_date", "desc"
    else:
        t, urut_awal, arah_awal = gt[U.mask_belum_diterima(gt, we)], "gt_date", "asc"
    t = t.assign(umur=(we - t["pi_date"]).dt.days.where(t["pi_date"].notna())).reset_index(drop=True)
    hasil = susun(t, KOLOM_DETAIL, KOLOM_CARI, cari, urut, arah, urut_awal, arah_awal, halaman, ukuran, pembanding="gt_number")
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": tgl(ws), "akhir": tgl(we)}, **hasil}
