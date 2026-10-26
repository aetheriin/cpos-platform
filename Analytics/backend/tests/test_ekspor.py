import ahli  # noqa: F401
import io
import re
import zipfile
from types import SimpleNamespace

import pandas as pd
from openpyxl import load_workbook

import api
from inti import ekspor
from inti.filter import FilterTidakValid

KOLOM = [{"kunci": "pr", "judul": "No PR", "tipe": "teks"}, {"kunci": "tgl", "judul": "Tanggal PR", "tipe": "tanggal"},
         {"kunci": "qty", "judul": "Qty", "tipe": "angka"}, {"kunci": "hrg", "judul": "Harga", "tipe": "angka"},
         {"kunci": "item", "judul": "Item", "tipe": "teks"}]


def buka(data):
    return load_workbook(io.BytesIO(data))


def nilai_baris(ws, n):
    return [c.value for c in ws[n]]


def test_lembar_data_judul_tanggal_angka_dan_penyaring():
    baris = [{"pr": "PR-001", "tgl": "2026-10-01", "qty": 5, "hrg": 1234.5, "item": "pipa"},
             {"pr": "PR-002", "tgl": None, "qty": None, "hrg": 7, "item": None}]
    wb = buka(ekspor.buat_xlsx("New PO", KOLOM, baris, [("Laporan", "PR & PO")]))
    assert wb.sheetnames == ["New PO", "Info"]
    ws = wb["New PO"]
    assert nilai_baris(ws, 1) == ["No PR", "Tanggal PR", "Qty", "Harga", "Item"] and ws["A1"].font.bold
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref == "A1:E3"                       # judul tetap terlihat saat digulir, bisa disaring
    r2 = nilai_baris(ws, 2)
    assert r2[0] == "PR-001" and r2[1].year == 2026 and r2[1].month == 10 and r2[1].day == 1 and r2[2] == 5 and r2[3] == 1234.5 and r2[4] == "pipa"
    assert ws["B2"].data_type == "d" and ws["B2"].number_format == "dd/mm/yyyy" and ws["D2"].number_format == "#,##0.00"   # tanggal dan angka sungguhan
    assert nilai_baris(ws, 3) == ["PR-002", None, None, 7, None]                           # sel kosong tetap kosong
    assert ws.column_dimensions["E"].width >= 8 and ws.column_dimensions["A"].width >= 8


def test_isi_database_tidak_pernah_menjadi_rumus_atau_merusak_berkas():
    jahat = ['=HYPERLINK("http://jahat","klik")', "=1+1", "=cmd|' /C calc'!A0", "+cmd", "-5", "@SUM(A1)", "pipa\x07 baja\x00", "x" * 40000]
    baris = [{"pr": v, "tgl": "bukan tanggal", "qty": 1, "hrg": 1, "item": v} for v in jahat]
    data = ekspor.buat_xlsx("Data", KOLOM, baris, [("Catatan", '=SUM(1,2)')])
    ws = buka(data)["Data"]
    for n, asli in enumerate(jahat, start=2):
        sel = ws.cell(row=n, column=1)
        harapan = re.sub("[\x00-\x08\x0b\x0c\x0e-\x1f]", "", asli)[:32767]           # batas Excel: 32.767 karakter per sel
        assert sel.data_type == "s" and sel.value == harapan, asli[:20]                    # selalu teks, karakter ilegal dibuang
    assert ws["B2"].value == "bukan tanggal"                                               # tanggal yang tidak sah ditampilkan apa adanya
    z = zipfile.ZipFile(io.BytesIO(data))
    assert not any("<f>" in z.read(n).decode("utf8", "ignore") for n in z.namelist() if n.startswith("xl/worksheets/"))   # tidak ada rumus sama sekali
    assert buka(data)["Info"]["B1"].data_type == "s"                                       # lembar Info juga aman


def test_lembar_info_melewati_nilai_kosong_dan_berkas_tanpa_baris_tetap_sah():
    wb = buka(ekspor.buat_xlsx("Kosong", KOLOM, [], [("Laporan", "PR & PO"), ("Dilewati", None), ("Baris diekspor", 0), ("Catatan", "ok")]))
    info = [(a.value, b.value) for a, b in wb["Info"].iter_rows()]
    assert info == [("Laporan", "PR & PO"), ("Baris diekspor", 0), ("Catatan", "ok")]
    assert nilai_baris(wb["Kosong"], 1)[0] == "No PR" and wb["Kosong"].max_row == 1


def test_nama_lembar_dan_nama_berkas_aman():
    assert ekspor.nama_sheet("New PO: [PO]/x\\y*?") == "New PO   PO  x y" and len(ekspor.nama_sheet("a" * 80)) == 31
    assert ekspor.nama_sheet("") == "Data" and ekspor.nama_sheet(None) == "Data" and ekspor.nama_sheet("'") == "Data"
    assert ekspor.nama_berkas("pr_po", "outstanding", "2026-09-11", "2026-10-15") == "pr_po_outstanding_2026-09-11_2026-10-15.xlsx"
    assert ekspor.nama_berkas('a"b\r\nc/../d', None, "") == "a_b_c_.._d.xlsx" or ".." not in ekspor.nama_berkas("../../x")
    assert "/" not in ekspor.nama_berkas("../../etc/passwd") and '"' not in ekspor.nama_berkas('x"y') and ekspor.nama_berkas("") == "laporan.xlsx"
    buka(ekspor.buat_xlsx("New PO: [x]", KOLOM, [], []))                                   # nama lembar ilegal tidak merusak berkas


# ---------- endpoint ----------
def laporan_palsu(tangkap, hasil, dukung=("perusahaan", "kategori", "buyer", "umur")):
    def detail(ds, jenis, n, mg, f, cari, urut, arah, hal, uk):
        tangkap.append(dict(jenis=jenis, n=n, mg=mg, f=f, cari=cari, urut=urut, arah=arah, hal=hal, uk=uk))
        if jenis == "salah":
            raise FilterTidakValid("jenis harus salah satu dari: outstanding, po")
        return hasil
    return SimpleNamespace(id="pr_po", nama="PR & PO Outstanding", filter_didukung=dukung, detail=detail)


HASIL = {"jenis": "po", "judul": "New PO", "periode": {"mulai": "2026-09-14", "akhir": "2026-10-18"}, "kolom": KOLOM, "total_semua": 3, "total": 2,
         "halaman": 1, "ukuran": 100000, "jumlah_halaman": 1, "urut": "tgl", "arah": "desc", "cari": "pipa",
         "baris": [{"pr": "PR-1", "tgl": "2026-10-01", "qty": 2, "hrg": 10, "item": "pipa"}, {"pr": "PR-2", "tgl": "2026-10-02", "qty": 3, "hrg": 20, "item": "pipa besi"}]}


def siapkan(hasil=HASIL, **kw):
    """Gudang dengan satu data atas nama admin, dan laporan palsu yang mencatat panggilan detail."""
    from test_auth import ADMIN, pengguna, segar
    segar()
    tangkap = []
    asli = api.LAPORAN
    api.LAPORAN = {"pr_po": laporan_palsu(tangkap, hasil, **kw)}
    user = pengguna(ADMIN)
    p = api.gudang.mulai_muat("pr_po", "2026-01-01", "2026-10-15", lambda m, a, k: (pd.DataFrame({"x": [1]}), {}), api._pemilik(user))
    for _ in range(300):
        if p.status != "berjalan":
            break
        import time
        time.sleep(0.01)
    return user, p.data_id, tangkap, asli


def panggil(user, data_id, **ubah):
    d = dict(laporan_id="pr_po", data_id=data_id, jenis="po", jumlah_minggu=5, minggu=None, perusahaan=None, kategori=None, buyer=None,
             pembuat=None, umur=None, cari=None, urut=None, arah=None, user=user)
    d.update(ubah)
    return api.ekspor_detail(**ahli.dengan_permintaan(d))


def test_endpoint_ekspor_semua_baris_dengan_filter_dan_urutan_yang_sama():
    user, data_id, tangkap, asli = siapkan()
    try:
        r = panggil(user, data_id, perusahaan=["YBS", "SUN"], buyer=["Elsa"], cari="pipa", urut="tgl", arah="desc", jumlah_minggu=8, minggu=2)
    finally:
        api.LAPORAN = asli
    assert tangkap[0]["hal"] == 1 and tangkap[0]["uk"] == ekspor.MAKS_BARIS                 # semua baris, bukan satu halaman
    assert tangkap[0]["f"] == {"perusahaan": ["SUN", "YBS"], "buyer": ["Elsa"]} and tangkap[0]["cari"] == "pipa" and tangkap[0]["urut"] == "tgl"
    assert tangkap[0]["n"] == 8 and tangkap[0]["mg"] == 2 and tangkap[0]["arah"] == "desc"
    assert r.media_type == ekspor.XLSX and r.headers["Content-Disposition"] == 'attachment; filename="pr_po_po_2026-01-01_2026-10-15.xlsx"'
    assert r.headers["Cache-Control"] == "no-store"
    wb = buka(r.body)
    assert wb.sheetnames == ["New PO", "Info"] and wb["New PO"].max_row == 3 and wb["New PO"]["A3"].value == "PR-2"
    info = {a.value: b.value for a, b in wb["Info"].iter_rows()}
    assert info["Laporan"] == "PR & PO Outstanding" and info["Tabel"] == "New PO" and info["Data tanggal"] == "01/01/2026 s/d 15/10/2026"
    assert info["Jendela tabel"] == "14/09/2026 s/d 18/10/2026" and info["Periode grafik"] == "8 minggu"
    assert info["Perusahaan"] == "SUN, YBS" and info["Buyer"] == "Elsa" and "Filter" not in info and info["Pencarian"] == "pipa"
    assert info["Urutan"] == "Tanggal PR (turun)" and info["Baris diekspor"] == 2 and info["Baris sebelum pencarian"] == 3
    assert info["Diekspor oleh"] == "Admin Satu (admin1)" and "Catatan" not in info and re.match(r"\d\d/\d\d/\d{4} \d\d:\d\d", info["Diekspor pada"])


def test_endpoint_ekspor_tanpa_filter_dan_tanpa_pencarian_dan_catatan_pembatasan():
    hasil = {**HASIL, "cari": "", "total": 250000, "total_semua": 250000}
    user, data_id, tangkap, asli = siapkan(hasil)
    try:
        r = panggil(user, data_id)
    finally:
        api.LAPORAN = asli
    info = {a.value: b.value for a, b in buka(r.body)["Info"].iter_rows()}
    assert info["Filter"] == "Tidak ada (semua data)" and "Pencarian" not in info and "Baris sebelum pencarian" not in info
    assert "Dibatasi 100,000 baris dari 250,000 baris" in info["Catatan"] and info["Baris diekspor"] == 2


def test_endpoint_ekspor_menolak_yang_tidak_sah():
    from test_auth import OPERATOR, kode, pengguna
    user, data_id, tangkap, asli = siapkan()
    try:
        assert kode(panggil, user, data_id, jenis="salah")[0] == 422                       # jenis tabel tidak dikenal
        assert kode(panggil, user, data_id, laporan_id="tidak_ada")[0] == 404
        assert kode(panggil, user, "id-ngawur")[0] == 404                                  # data tidak ada
        assert kode(panggil, user, data_id, pembuat=["x"])[0] == 422                       # filter yang tidak berlaku untuk laporan ini
        assert kode(panggil, {**user, "laporan": ["po_pi"]}, data_id)[0] == 403            # role tanpa akses laporan ini
        lain = pengguna(OPERATOR)
        assert kode(panggil, lain, data_id)[0] == 404                                      # data milik sesi lain tidak bisa diekspor
    finally:
        api.LAPORAN = asli


def test_ekspor_dengan_data_nyata_sama_dengan_tabel_di_layar():
    ahli.butuh_data()
    from test_auth import ADMIN, pengguna, segar
    segar()
    user = pengguna(ADMIN)
    for lid, fabrik, jenis_list in (("pr_po", ahli.df_pr_po, ("outstanding", "po")), ("po_pi", ahli.df_po_pi, ("outstanding", "pi"))):
        df = fabrik()
        p = api.gudang.mulai_muat(lid, "2025-10-01", "2026-10-15", lambda m, a, k, df=df: (df, {}), api._pemilik(user))
        for _ in range(300):
            if p.status != "berjalan":
                break
            import time
            time.sleep(0.01)
        lap = api.LAPORAN[lid]
        for jenis in jenis_list:
            r = panggil(user, p.data_id, laporan_id=lid, jenis=jenis)
            layar = lap.detail(api.gudang.ambil(p.data_id), jenis, 5, None, {}, None, None, None, 1, 100000)
            ws = buka(r.body).worksheets[0]
            assert ws.max_row == layar["total"] + 1 and layar["total"] > 0, (lid, jenis)                  # jumlah baris sama dengan di layar
            assert [c.value for c in ws[1]] == [k["judul"] for k in layar["kolom"]]                       # judul kolom sama
            pertama = [c.value for c in ws[2]]
            for k, v in zip(layar["kolom"], pertama):                                                     # urutan dan isi baris pertama sama
                asli = layar["baris"][0][k["kunci"]]
                assert (v is None and asli is None) or (k["tipe"] == "tanggal" and v.strftime("%Y-%m-%d") == asli) or v == asli, (lid, jenis, k["kunci"], v, asli)


def test_respons_detail_membawa_batas_baris_ekspor_agar_tampilan_tidak_menyalin_angkanya():
    user, data_id, tangkap, asli = siapkan()
    try:
        r = api.detail(**ahli.dengan_permintaan(dict(laporan_id="pr_po", data_id=data_id, jenis="po", jumlah_minggu=5, minggu=None, cari=None,
                                                    urut=None, arah=None, halaman=1, ukuran=50, user=user)))
    finally:
        api.LAPORAN = asli
    assert r["maks_ekspor"] == ekspor.MAKS_BARIS == 100_000
    assert r["total"] == 2 and r["baris"] == HASIL["baris"] and r["dataset"]["mulai"] == "2026-01-01"     # isi lain tidak berubah


# ---------- openpyxl belum terpasang: server tetap menyala, hanya ekspor yang gagal ----------
class TanpaOpenpyxl:
    """Pura-pura openpyxl tidak terpasang (import openpyxl gagal) selama blok with."""

    def __enter__(self):
        import sys
        self.asli = sys.modules.get("openpyxl", "tidak-ada")
        sys.modules["openpyxl"] = None
        return self

    def __exit__(self, *a):
        import sys
        if self.asli == "tidak-ada":
            sys.modules.pop("openpyxl", None)
        else:
            sys.modules["openpyxl"] = self.asli


def test_modul_ekspor_diimpor_tanpa_openpyxl_jadi_server_tetap_bisa_menyala():
    import subprocess
    import sys
    from pathlib import Path
    backend = Path(__file__).resolve().parent.parent
    kode = "import sys; sys.modules['openpyxl'] = None; sys.path.insert(0, '.'); import inti.ekspor as e; print(e.tersedia())"
    hasil = subprocess.run([sys.executable, "-c", kode], cwd=backend, capture_output=True, text=True)
    assert hasil.returncode == 0, hasil.stderr                      # impor tidak gagal walau openpyxl tidak ada
    assert hasil.stdout.strip() == "False"
    assert subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import inti.ekspor as e; print(e.tersedia())"],
                          cwd=backend, capture_output=True, text=True).stdout.strip() == "True"


def test_ekspor_tanpa_openpyxl_memberi_pesan_jelas_dan_tidak_bekerja_percuma():
    from test_pengguna import salah
    assert ekspor.tersedia() is True
    user, data_id, tangkap, asli = siapkan()
    try:
        with TanpaOpenpyxl():
            assert ekspor.tersedia() is False
            pesan = salah(lambda: ekspor.buat_xlsx("Data", KOLOM, [], []), ekspor.PustakaHilang)
            k, detail = None, None
            try:
                panggil(user, data_id)
            except Exception as e:
                k, detail = getattr(e, "status_code", None), getattr(e, "detail", "")
        assert "openpyxl" in pesan and "pip install -r requirements.txt" in pesan
        assert k == 503 and detail == ekspor.PESAN_PUSTAKA_HILANG
        assert tangkap == []                                         # tabel tidak disusun sama sekali
        assert panggil(user, data_id).media_type == ekspor.XLSX      # setelah terpasang lagi berfungsi normal
    finally:
        api.LAPORAN = asli


def test_peringatan_saat_server_menyala_kalau_openpyxl_belum_terpasang():
    import logging
    pesan = []

    class Tangkap(logging.Handler):
        def emit(self, rec):
            pesan.append(rec.getMessage())
    h = Tangkap()
    api.log.addHandler(h)
    try:
        api.periksa_ekspor_awal()
        assert pesan == []                                           # terpasang: diam
        with TanpaOpenpyxl():
            api.periksa_ekspor_awal()
    finally:
        api.log.removeHandler(h)
    assert len(pesan) == 1 and "openpyxl" in pesan[0] and "pip install -r requirements.txt" in pesan[0]
