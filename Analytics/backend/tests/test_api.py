import ahli
import json
import threading
import time
import types
from datetime import date

import api
import laporan
from laporan.po_pi import sumber as sumber_pi
from laporan.pr_po import sumber as sumber_pr
from inti.gudang import Gudang
from laporan.pr_po import ukuran as ukuran_pr
from laporan.po_pi import ukuran as ukuran_pi
from inti.banding import jendela_sebelumnya
from pandas import Timestamp as T

try:
    from fastapi import HTTPException
except ImportError:  # tidak terjadi: stub.pasang() menyediakan
    HTTPException = Exception

HARI = date(2026, 10, 12)
# Pengguna yang melihat semua laporan (data yang dikirim server ke tiap endpoint setelah login)
SEMUA = {"id": 1, "username": "admin1", "nama": "Admin", "role": "System Administrator", "divisi": "IT", "company": "YBS", "admin": True, "laporan": ["pr_po", "po_pi"], "ekspor": ["pr_po", "po_pi"]}
ASLI = (sumber_pr.ambil_data, sumber_pi.ambil_data)


def terisolasi(fn):
    """Kembalikan pengambil data asli setelah uji selesai, supaya uji lain tidak ikut terpengaruh."""
    def bungkus():
        try:
            return fn()
        finally:
            sumber_pr.ambil_data, sumber_pi.ambil_data = ASLI
    bungkus.__name__ = fn.__name__
    return bungkus


def baru():
    """Gudang bersih dan pengganti SP yang menghitung panggilan."""
    api.gudang = Gudang()
    panggil = {"pr": [], "pi": []}
    sumber_pr.ambil_data = lambda mulai, akhir, perusahaan=None, kendali=None: (panggil["pr"].append((mulai, akhir)), ahli.raw_pr_po())[1]
    sumber_pi.ambil_data = lambda mulai, akhir, perusahaan=None, kendali=None: (panggil["pi"].append((mulai, akhir)), ahli.raw_po_pi())[1]
    return panggil


def tunggu(pid, detik=15):
    t = time.time()
    while time.time() - t < detik:
        s = api.status_pekerjaan(pid, user=SEMUA)
        if s["status"] != "berjalan":
            return s
        time.sleep(0.02)
    return s


def muat(lid, mulai=date(2025, 10, 1), akhir=HARI):
    return api.muat_laporan(lid, api.PermintaanMuat(mulai=mulai, akhir=akhir), user=SEMUA)


def dash(lid, did, **kw):
    a = dict(jumlah_minggu=5, minggu=None, perusahaan=None, kategori=None, buyer=None, pembuat=None, umur=None)
    a.update(kw)
    return api.dashboard(lid, **ahli.dengan_permintaan({**a, "data_id": did, "user": SEMUA}))


def det(lid, did, jenis, **kw):
    a = dict(jumlah_minggu=5, minggu=None, perusahaan=None, kategori=None, buyer=None, pembuat=None, umur=None,
             cari=None, urut=None, arah=None, halaman=1, ukuran=50)
    a.update(kw)
    return api.detail(lid, **ahli.dengan_permintaan({**a, "data_id": did, "jenis": jenis, "user": SEMUA}))


def kena(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return ahli.kode(e)
    return None


@terisolasi
def test_daftar_laporan_tanpa_sql():
    panggil = baru()
    dl = api.daftar_laporan(user=SEMUA)
    assert [l["id"] for l in dl] == ["pr_po", "po_pi"] and dl[0]["mulai_bawaan"] == "2025-10-01"
    assert not panggil["pr"] and not panggil["pi"]          # menyalakan server dan melihat daftar tidak menjalankan SQL


@terisolasi
def test_muat_cache_dan_pindah_laporan_tanpa_sql_lagi():
    ahli.butuh_data()
    panggil = baru()
    s1 = tunggu(muat("pr_po")["id"])
    mulai_lalu = jendela_sebelumnya("2025-10-01", "2026-10-12")[0].strftime("%Y%m%d")   # periode sebelumnya ikut diambil untuk perbandingan
    assert s1["status"] == "selesai" and panggil["pr"] == [(mulai_lalu, "20261012")]
    s2 = tunggu(muat("po_pi")["id"])
    assert s2["status"] == "selesai" and len(panggil["pi"]) == 1
    r1, r2 = dash("pr_po", s1["data_id"]), dash("po_pi", s2["data_id"])
    # tanpa filter tanggal: seluruh periode yang dimuat; minggu terakhir (Jumat 09/10) dipotong di tanggal akhir data 12/10
    s_, e_ = T("2026-10-09"), T("2026-10-12")
    kini_pr = ahli.df_pr_po()[ahli.df_pr_po()["pr_date"] >= T("2025-10-01")]
    kini_pi = ahli.df_po_pi()[ahli.df_po_pi()["cd"] >= T("2025-10-01")]
    assert r1["mingguan"][-1]["label"] == "09/10 - 12/10" and r1["mingguan"][-1]["new_pr"] == ukuran_pr.new_pr(kini_pr, s_, e_)
    assert r2["kpi"]["outstanding_akhir"] == ukuran_pi.outstanding_akhir(kini_pi, e_) and r2["dataset"]["akhir"] == "2026-10-12"
    f = dash("pr_po", s1["data_id"], dari=date(2026, 9, 1), sampai=date(2026, 10, 1))                   # filter tanggal, tanpa SQL baru
    assert (f["periode"]["mulai"], f["periode"]["akhir"]) == ("2026-09-01", "2026-10-01")
    assert (f["banding"]["mulai"], f["banding"]["akhir"]) == ("2026-08-01", "2026-08-31")                # jumlah hari sama, tepat sebelumnya
    n = (len(panggil["pr"]), len(panggil["pi"]))
    dash("pr_po", s1["data_id"]); dash("po_pi", s2["data_id"], perusahaan=["SUN"]); det("pr_po", s1["data_id"], "po"); det("po_pi", s2["data_id"], "pi")
    assert (len(panggil["pr"]), len(panggil["pi"])) == n     # berpindah laporan dan filter: tidak ada SQL baru
    p3 = muat("pr_po")                                      # rentang sama: langsung selesai
    assert p3["status"] == "selesai" and p3["data_id"] == s1["data_id"] and len(panggil["pr"]) == n[0]
    tunggu(muat("pr_po", mulai=date(2026, 1, 1))["id"])      # rentang beda: SQL lagi, data lama tetap ada
    assert len(panggil["pr"]) == n[0] + 1 and api.gudang.ambil(s1["data_id"]) is not None


@terisolasi
def test_batalkan_pemuatan():
    baru()
    mulai = threading.Event()

    def lambat(mulai_, akhir, perusahaan=None, kendali=None):
        kendali.daftarkan(types.SimpleNamespace(cancel=lambda: mulai.set()))
        for _ in range(500):
            kendali.periksa()
            time.sleep(0.01)
        return ahli.raw_pr_po()

    sumber_pr.ambil_data = lambat
    p = muat("pr_po", mulai=date(2024, 1, 1), akhir=date(2024, 6, 1))
    time.sleep(0.1)
    assert api.batalkan_pekerjaan(p["id"], user=SEMUA)["status"] == "dibatalkan"
    time.sleep(0.1)
    assert api.status_pekerjaan(p["id"], user=SEMUA)["status"] == "dibatalkan" and mulai.is_set()
    assert api.gudang.cari_dataset("pr_po", "2024-01-01", "2024-06-01") is None


@terisolasi
def test_validasi_masukan():
    ahli.butuh_data()
    baru()
    P = api.PermintaanMuat
    assert kena(api.muat_laporan, "pr_po", P(mulai=date(2026, 2, 1), akhir=date(2026, 1, 1)), user=SEMUA) == 422
    assert kena(api.muat_laporan, "pr_po", P(mulai=date(2020, 1, 1), akhir=date(2026, 1, 1)), user=SEMUA) == 422
    assert kena(api.muat_laporan, "xx", P(mulai=date(2026, 1, 1), akhir=date(2026, 2, 1)), user=SEMUA) == 404
    assert kena(api.status_pekerjaan, "zzz", user=SEMUA) == 404 and kena(api.batalkan_pekerjaan, "zzz", user=SEMUA) == 404
    a = tunggu(muat("pr_po")["id"])["data_id"]
    b = tunggu(muat("po_pi")["id"])["data_id"]
    assert kena(dash, "pr_po", "tidakada") == 404 and kena(dash, "po_pi", a) == 404       # id salah atau milik laporan lain
    assert kena(dash, "po_pi", b, buyer=["Elsa"]) == 422 and kena(dash, "pr_po", a, umur=["x"]) == 422
    assert kena(dash, "po_pi", b, pembuat=["zzz"]) == 422 and kena(det, "pr_po", a, "xyz") == 422


@terisolasi
def test_tabel_detail_sama_dengan_kartu_lewat_api():
    ahli.butuh_data()
    baru()
    a = tunggu(muat("pr_po")["id"])["data_id"]
    b = tunggu(muat("po_pi")["id"])["data_id"]
    kp, kq = dash("pr_po", a)["kpi"], dash("po_pi", b)["kpi"]
    assert det("pr_po", a, "outstanding")["total_semua"] == kp["outstanding_akhir"]
    assert det("pr_po", a, "po")["total_semua"] == kp["new_po"]
    assert det("po_pi", b, "outstanding")["total_semua"] == kq["outstanding_akhir"]
    assert det("po_pi", b, "pi")["total_semua"] == kq["new_pi"]
    assert len(json.dumps(dash("po_pi", b))) > 2000


@terisolasi
def test_peringatan_data_dikirim_ke_tampilan():
    """PO salah tautan diabaikan dan pemakai diberi tahu lewat catatan pekerjaan."""
    baru()
    raw = ahli.raw_pr_po().copy()
    sub = raw[(raw["COMPID"] == "SJN") & (raw["POCREATEDATE"].isna()) & raw["ISOPEN"].astype(str).str.lower().isin(["true", "1"])]
    raw.loc[sub.index[0], ["PONUMBER", "POCREATEDATE", "POBY"]] = ["RCM/PO/HO/2610/0107", "20261001", "Mita"]
    sumber_pr.ambil_data = lambda mulai, akhir, perusahaan=None, kendali=None: raw
    s = tunggu(muat("pr_po")["id"])
    assert s["status"] == "selesai" and s["catatan"]["po_beda_perusahaan"] == 1 and "RCM/PO/HO/2610/0107" in s["catatan"]["peringatan"][0]
    bersih = tunggu(muat("po_pi")["id"])
    assert not bersih["catatan"].get("peringatan")           # data bersih: tanpa peringatan


@terisolasi
def test_filter_umur_laporan_pr_po_lewat_api():
    ahli.butuh_data()
    baru()
    a = tunggu(muat("pr_po")["id"])["data_id"]
    total = dash("pr_po", a)["kpi"]["outstanding_akhir"]
    u = dash("pr_po", a, umur=["Perlu Tindakan(>30 Hari)"])
    assert u["filter"]["umur"] == ["Perlu Tindakan(>30 Hari)"] and 0 < u["kpi"]["outstanding_akhir"] < total
    assert "Telat(16-30 Hari)" in u["pilihan"]["umur"]
    assert det("pr_po", a, "outstanding", umur=["Perlu Tindakan(>30 Hari)"])["total_semua"] == u["kpi"]["outstanding_akhir"]
    assert kena(dash, "pr_po", a, umur=["x"]) == 422                       # nilai tidak dikenal ditolak
    b = tunggu(muat("po_pi")["id"])["data_id"]
    assert kena(dash, "po_pi", b, buyer=["Elsa"]) == 422                   # filter yang tidak berlaku di laporan lain tetap ditolak
