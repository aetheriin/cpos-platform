import ahli  # noqa: F401
import threading
import time

import pandas as pd

from inti.gudang import Gudang


def tunggu(p, detik=3):
    t = time.time()
    while p.status == "berjalan" and time.time() - t < detik:
        time.sleep(0.01)
    return p


def pemuat_ok(panggil):
    def f(m, a, k):
        panggil.append((m, a))
        return pd.DataFrame({"x": [1, 2, 3]}), {"info": "ok"}
    return f


def test_muat_cache_dan_batas_dataset():
    panggil = []
    ok = pemuat_ok(panggil)
    g = Gudang(maks_dataset=2)
    p = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", ok))
    assert p.status == "selesai" and p.data_id and len(panggil) == 1
    assert g.ambil(p.data_id).catatan == {"info": "ok"}
    p2 = g.mulai_muat("a", "2026-01-01", "2026-10-01", ok)          # periode sama: tanpa SQL lagi
    assert p2.status == "selesai" and p2.data_id == p.data_id and len(panggil) == 1
    p3 = tunggu(g.mulai_muat("a", "2026-02-01", "2026-10-01", ok))
    p4 = tunggu(g.mulai_muat("b", "2026-01-01", "2026-10-01", ok))
    assert len(panggil) == 3 and g.ambil(p.data_id) is None          # yang paling lama dibuang
    assert g.ambil(p3.data_id) is not None and g.ambil(p4.data_id) is not None


def test_gagal_tidak_membocorkan_pesan():
    def gagal(m, a, k):
        raise RuntimeError("server mati")
    g = Gudang()
    p = tunggu(g.mulai_muat("a", "2025-01-01", "2025-02-01", gagal))
    assert p.status == "gagal" and p.data_id is None and "SQL Server" in p.pesan and "server mati" not in p.pesan


def test_batal_saat_berjalan():
    mulai = threading.Event()
    dibatalkan = []

    class Kursor:
        def cancel(self):
            dibatalkan.append(1)

    def lambat(m, a, k):
        k.daftarkan(Kursor())
        mulai.set()
        for _ in range(300):
            k.periksa()
            time.sleep(0.01)
        return pd.DataFrame({"x": [1]}), {}

    g = Gudang()
    p = g.mulai_muat("a", "2024-01-01", "2024-12-31", lambat)
    mulai.wait(2)
    assert g.mulai_muat("a", "2024-01-01", "2024-12-31", lambat).id == p.id   # permintaan sama memakai pekerjaan yang sama
    g.batalkan(p.id)
    tunggu(p)
    time.sleep(0.1)
    assert p.status == "dibatalkan" and dibatalkan == [1]
    assert g.cari_dataset("a", "2024-01-01", "2024-12-31") is None
    assert g.batalkan("tidak-ada") is None


def test_batal_tetapi_query_tetap_selesai_hasilnya_dibuang():
    def abai(m, a, k):
        time.sleep(0.15)
        return pd.DataFrame({"x": [1]}), {}

    g = Gudang()
    p = g.mulai_muat("a", "2023-01-01", "2023-12-31", abai)
    g.batalkan(p.id)
    time.sleep(0.4)
    assert p.status == "dibatalkan" and g.cari_dataset("a", "2023-01-01", "2023-12-31") is None
    p2 = tunggu(g.mulai_muat("a", "2023-01-01", "2023-12-31", pemuat_ok([])))   # boleh dimuat lagi
    assert p2.status == "selesai"


# ---------- kepemilikan sesi: data dibuang saat sesi berakhir ----------
def test_data_hanya_bisa_dibaca_pemiliknya():
    panggil = []
    g = Gudang()
    p = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat_ok(panggil), "sesi-A"))
    assert g.ambil(p.data_id, "sesi-A") is not None and g.ambil_pekerjaan(p.id, "sesi-A") is not None
    assert g.ambil(p.data_id, "sesi-B") is None and g.ambil_pekerjaan(p.id, "sesi-B") is None     # sesi lain: dianggap tidak ada


def test_sesi_lain_memuat_ulang_dari_sql_dan_data_bersama_bertahan_untuk_yang_lain():
    panggil = []
    ok = pemuat_ok(panggil)
    g = Gudang()
    pa = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", ok, "sesi-A"))
    ulang = g.mulai_muat("a", "2026-01-01", "2026-10-01", ok, "sesi-A")       # sesi yang sama membuka lagi: tanpa SQL
    assert ulang.status == "selesai" and ulang.data_id == pa.data_id and len(panggil) == 1
    pb = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", ok, "sesi-B"))  # sesi lain, periode sama: tetap dari SQL
    assert pb.status == "selesai" and pb.data_id != pa.data_id and len(panggil) == 2
    assert g.ambil(pa.data_id, "sesi-A").id == pb.data_id                     # sesi A ikut memakai data terbaru
    assert g.lepas("sesi-A") == (0, 0)                                        # masih dimiliki sesi B: data tetap ada
    assert g.ambil(pb.data_id, "sesi-A") is None and g.ambil(pb.data_id, "sesi-B") is not None
    assert g.ambil_pekerjaan(pa.id, "sesi-A") is None                         # pekerjaan sesi A sudah dibuang
    assert g.lepas("sesi-B") == (1, 0)                                        # tidak ada pemilik lagi: data dihapus
    assert g.ambil(pb.data_id) is None and not g.dataset and not g.pekerjaan
    assert g.lepas("sesi-B") == (0, 0) and g.lepas("tidak-ada") == (0, 0)
    pc = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", ok, "sesi-C"))   # harus memuat ulang dari SQL
    assert pc.status == "selesai" and len(panggil) == 3


def test_lepas_menghentikan_pemuatan_yang_tidak_ditunggu_siapa_pun():
    mulai, lanjut, kendali_dipakai = threading.Event(), threading.Event(), []

    def lambat(m, a, k):
        kendali_dipakai.append(k)
        mulai.set()
        lanjut.wait(3)
        return pd.DataFrame({"x": [1]}), {}
    g = Gudang()
    p = g.mulai_muat("a", "2026-01-01", "2026-10-01", lambat, "sesi-A")
    assert mulai.wait(3)
    assert g.lepas("sesi-A") == (0, 1) and kendali_dipakai[0].dibatalkan and not g.pekerjaan
    lanjut.set()                                                              # query "selesai" setelah pemiliknya pergi
    tunggu(p)
    assert p.status == "dibatalkan" and not g.dataset                         # hasilnya tidak disimpan


def test_pemuatan_bersama_jalan_terus_selama_masih_ada_yang_menunggu():
    mulai, lanjut = threading.Event(), threading.Event()

    def lambat(m, a, k):
        mulai.set()
        lanjut.wait(3)
        return pd.DataFrame({"x": [1]}), {}
    g = Gudang()
    pa = g.mulai_muat("a", "2026-01-01", "2026-10-01", lambat, "sesi-A")
    assert mulai.wait(3)
    pb = g.mulai_muat("a", "2026-01-01", "2026-10-01", lambat, "sesi-B")
    assert pb is pa and pa.pemilik == {"sesi-A", "sesi-B"}                    # ikut menunggu pekerjaan yang sama
    salinan = g.batalkan(pa.id, "sesi-A")                                     # A batal, tetapi B masih menunggu
    assert salinan.status == "dibatalkan" and pa.status == "berjalan" and not pa.kendali.dibatalkan
    assert g.ambil_pekerjaan(pa.id, "sesi-A") is None and g.ambil_pekerjaan(pa.id, "sesi-B") is pa
    lanjut.set()
    tunggu(pa)
    assert pa.status == "selesai" and g.ambil(pa.data_id, "sesi-B") is not None and g.ambil(pa.data_id, "sesi-A") is None


def test_batal_oleh_satu_satunya_penunggu_menghentikan_pemuatan_dan_tetap_terbaca():
    mulai, lanjut = threading.Event(), threading.Event()

    def lambat(m, a, k):
        mulai.set()
        lanjut.wait(3)
        return pd.DataFrame({"x": [1]}), {}
    g = Gudang()
    p = g.mulai_muat("a", "2026-01-01", "2026-10-01", lambat, "sesi-A")
    assert mulai.wait(3)
    assert g.batalkan(p.id, "sesi-B") is None                                 # bukan pemilik: tidak bisa membatalkan
    assert g.batalkan(p.id, "sesi-A") is p and p.status == "dibatalkan" and p.kendali.dibatalkan
    assert g.ambil_pekerjaan(p.id, "sesi-A") is p                             # status akhir tetap bisa dibaca peminta
    lanjut.set()
    tunggu(p)
    assert not g.dataset


# ---------- Refresh: SQL dijalankan lagi untuk periode yang sama ----------
def pemuat_berurut(panggil):
    """Pemuat yang hasilnya berubah di tiap panggilan (seperti data di database yang terus diperbarui)."""
    def f(m, a, k):
        panggil.append(1)
        return pd.DataFrame({"x": [len(panggil)] * len(panggil)}), {"info": f"muat ke-{len(panggil)}"}
    return f


def test_segarkan_menjalankan_sql_lagi_dan_menggantikan_data_lama():
    panggil = []
    f = pemuat_berurut(panggil)
    g = Gudang()
    p1 = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A"))
    assert len(panggil) == 1 and len(g.ambil(p1.data_id, "sesi-A").df) == 1
    g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A")                       # tanpa segarkan: tetap memakai data lama
    assert len(panggil) == 1
    p2 = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A", segarkan=True))
    assert p2.status == "selesai" and len(panggil) == 2 and p2.data_id != p1.data_id          # SQL dijalankan lagi, data baru berid baru
    assert len(g.dataset) == 1 and len(g.ambil(p2.data_id, "sesi-A").df) == 2 and g.ambil(p2.data_id, "sesi-A").catatan == {"info": "muat ke-2"}
    assert g.ambil(p1.data_id, "sesi-A") is g.ambil(p2.data_id, "sesi-A")                      # id lama dialihkan ke data baru
    p3 = g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A")                           # muat biasa sesudahnya: data terbaru, tanpa SQL
    assert p3.data_id == p2.data_id and len(panggil) == 2


def test_segarkan_sesi_lain_tetap_terlayani_dan_alias_dirapikan():
    panggil = []
    f = pemuat_berurut(panggil)
    g = Gudang()
    pa = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A"))
    g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-B")                                 # B memakai data yang sama
    pa2 = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A", segarkan=True))   # A menyegarkan
    baru = g.ambil(pa2.data_id, "sesi-A")
    assert g.ambil(pa.data_id, "sesi-B") is baru and baru.pemilik == {"sesi-A", "sesi-B"}     # B tetap memegang id lama tanpa 404
    assert g.ambil(pa.data_id, "sesi-C") is None                                              # sesi lain yang bukan pemilik tetap ditolak
    assert g.lepas("sesi-A") == (0, 0) and g.ambil(pa.data_id, "sesi-B") is baru and g.alias    # B masih memakainya
    assert g.lepas("sesi-B") == (1, 0)
    assert not g.dataset and g.alias == {}                                                      # tidak ada alias yang menggantung


def test_segarkan_berulang_alias_selalu_menunjuk_yang_terbaru():
    panggil = []
    f = pemuat_berurut(panggil)
    g = Gudang()
    ids = [tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A")).data_id]
    for _ in range(3):
        ids.append(tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", f, "sesi-A", segarkan=True)).data_id)
    assert len(set(ids)) == 4 and len(panggil) == 4
    terbaru = g.ambil(ids[-1], "sesi-A")
    assert all(g.ambil(i, "sesi-A") is terbaru for i in ids)                                  # id paling lama pun masih terlayani
    assert set(g.alias) == set(ids[:-1]) and set(g.alias.values()) == {ids[-1]}               # tidak berantai


def test_segarkan_data_lama_tetap_terbaca_selama_menunggu_dan_gagal_tidak_merusak():
    mulai, lanjut, panggil = threading.Event(), threading.Event(), []

    def pemuat(m, a, k):
        panggil.append(1)
        if len(panggil) == 1:
            return pd.DataFrame({"x": [1]}), {}
        mulai.set()
        lanjut.wait(3)
        if len(panggil) == 2:
            raise RuntimeError("SQL Server tidak terjangkau")
        return pd.DataFrame({"x": [1, 2]}), {}
    g = Gudang()
    p1 = tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat, "sesi-A"))
    lama = g.ambil(p1.data_id, "sesi-A")
    p2 = g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat, "sesi-A", segarkan=True)
    assert mulai.wait(3) and p2.status == "berjalan"
    assert g.ambil(p1.data_id, "sesi-A") is lama                                              # selama menunggu, data lama tetap tampil
    p2b = g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat, "sesi-A", segarkan=True)      # klik ganda: ikut pekerjaan yang sama
    assert p2b is p2 and len(panggil) == 2
    lanjut.set()
    tunggu(p2)
    assert p2.status == "gagal" and g.ambil(p1.data_id, "sesi-A") is lama and g.alias == {}   # gagal: data lama utuh, tidak ada alias


def test_segarkan_dibuang_kalau_peminta_keluar_selama_menunggu():
    mulai, lanjut, panggil = threading.Event(), threading.Event(), []

    def pemuat(m, a, k):
        panggil.append(1)
        if len(panggil) == 1:
            return pd.DataFrame({"x": [1]}), {}
        mulai.set()
        lanjut.wait(3)
        return pd.DataFrame({"x": [1, 2]}), {}
    g = Gudang()
    tunggu(g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat, "sesi-A"))
    p2 = g.mulai_muat("a", "2026-01-01", "2026-10-01", pemuat, "sesi-A", segarkan=True)
    assert mulai.wait(3)
    assert g.lepas("sesi-A") == (1, 1)                                                          # data lama hilang, refresh dihentikan
    lanjut.set()
    tunggu(p2)
    assert not g.dataset and g.alias == {} and p2.status == "dibatalkan"                      # hasil refresh tidak disimpan untuk siapa pun
