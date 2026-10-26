import ahli  # noqa: F401
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from inti.aktivitas import LogAktivitas, ringkas_pengguna


class Jam:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def baru(jam, simpan_hari=30):
    return LogAktivitas(tempfile.mkdtemp(prefix="uji_aktivitas_"), simpan_hari, jam=jam)


def test_catat_dan_baca_terbaru_lebih_dulu_lintas_hari():
    jam = Jam(datetime(2026, 10, 18, 9, 0))
    la = baru(jam)
    la.catat("masuk", "budi", "Budi", "Operator", ip="10.0.0.1")
    jam.t = datetime(2026, 10, 19, 8, 0)
    la.catat("muat", "budi", "Budi", "Operator", "pr_po", "01/10/2026 s/d 18/10/2026, dari SQL Server")
    jam.t = datetime(2026, 10, 19, 8, 5)
    la.catat("ekspor", "budi", "Budi", "Operator", "pr_po", "Tab Sudah PO; 120 baris")
    hasil = la.baca(date(2026, 10, 18), date(2026, 10, 19))
    assert [b["jenis"] for b in hasil] == ["ekspor", "muat", "masuk"]
    assert hasil[2]["ip"] == "10.0.0.1" and hasil[0]["laporan"] == "pr_po"
    assert [b["jenis"] for b in la.baca(date(2026, 10, 19), date(2026, 10, 19))] == ["ekspor", "muat"]


def test_jenis_tidak_dikenal_ditolak_dan_baris_rusak_dilewati():
    jam = Jam(datetime(2026, 10, 19, 8, 0))
    la = baru(jam)
    try:
        la.catat("lihat", "budi")
        assert False, "jenis tidak dikenal harus ditolak"
    except ValueError:
        pass
    la.catat("masuk", "budi")
    with open(Path(la.folder) / "aktivitas-2026-10-19.jsonl", "a", encoding="utf-8") as f:
        f.write("{rusak\n")
    assert len(la.baca(date(2026, 10, 19), date(2026, 10, 19))) == 1


def test_file_lebih_tua_dari_masa_simpan_dihapus():
    jam = Jam(datetime(2026, 10, 1, 8, 0))
    la = baru(jam, simpan_hari=7)
    la.catat("masuk", "budi")
    jam.t = datetime(2026, 10, 19, 8, 0)
    la.catat("masuk", "sari")
    sisa = sorted(p.name for p in Path(la.folder).glob("*.jsonl"))
    assert sisa == ["aktivitas-2026-10-19.jsonl"]


def test_gagal_menulis_tidak_melempar_galat():
    berkas = Path(tempfile.mkdtemp()) / "bukan-folder"
    berkas.write_text("x")
    LogAktivitas(berkas, 30, jam=Jam(datetime(2026, 10, 19))).catat("masuk", "budi")   # folder tidak bisa dibuat: hanya dicatat ke log server


def test_ringkasan_per_pengguna():
    t = lambda m: (datetime(2026, 10, 19, 8, 0) + timedelta(minutes=m)).isoformat()
    baris = [
        {"waktu": t(9), "jenis": "keluar", "username": "budi", "nama": "", "role": "", "laporan": None},
        {"waktu": t(8), "jenis": "ekspor", "username": "budi", "nama": "Budi", "role": "Operator", "laporan": "pr_po"},
        {"waktu": t(7), "jenis": "muat", "username": "budi", "nama": "Budi", "role": "Operator", "laporan": "po_pi"},
        {"waktu": t(6), "jenis": "muat", "username": "budi", "nama": "Budi", "role": "Operator", "laporan": "pr_po"},
        {"waktu": t(5), "jenis": "gagal_masuk", "username": "tamu", "nama": "", "role": "", "laporan": None},
        {"waktu": t(1), "jenis": "masuk", "username": "sari", "nama": "Sari", "role": "PPIC", "laporan": None},
    ]
    r = ringkas_pengguna(baris)
    assert [x["username"] for x in r] == ["budi", "sari"]
    assert r[0] == {"username": "budi", "nama": "Budi", "role": "Operator", "terakhir": t(9), "masuk": 0, "muat": 2, "ekspor": 1, "laporan": ["po_pi", "pr_po"]}


def test_endpoint_admin_filter_halaman_dan_ringkasan():
    import api

    jam = Jam(datetime.now().replace(microsecond=0))
    asli, api.log_aktivitas = api.log_aktivitas, baru(jam)
    try:
        for i in range(3):
            api.log_aktivitas.catat("muat", "budi", "Budi", "Operator", "pr_po", f"muat {i}")
        api.log_aktivitas.catat("ekspor", "budi", "Budi", "Operator", "pr_po", "Tab Sudah PO; 5 baris")
        api.log_aktivitas.catat("masuk", "sari", "Sari", "PPIC")
        api.log_aktivitas.catat("gagal_masuk", "tamu")
        semua = dict(mulai=None, akhir=None, pengguna=None, jenis=None, laporan=None, halaman=1, ukuran=10, user={"username": "admin"})
        r = api.daftar_aktivitas(**semua)
        assert r["total"] == 6 and r["jumlah_gagal_masuk"] == 1 and r["mulai"] == (date.today() - timedelta(days=6)).isoformat()
        assert {b["jenis_nama"] for b in r["baris"]} >= {"Membuka laporan", "Export Excel", "Gagal masuk"}
        assert [p["username"] for p in r["per_pengguna"]] == ["sari", "budi"] or [p["username"] for p in r["per_pengguna"]] == ["budi", "sari"]
        r = api.daftar_aktivitas(**{**semua, "pengguna": "BUDI", "jenis": "muat", "ukuran": 2, "halaman": 2})
        assert r["total"] == 3 and r["jumlah_halaman"] == 2 and len(r["baris"]) == 1 and r["baris"][0]["laporan_nama"] == "PR & PO Outstanding"
        assert [p["username"] for p in r["per_pengguna"]] == ["budi"]            # ringkasan ikut filter jenis, tidak ikut filter pengguna
        r = api.daftar_aktivitas(**{**semua, "jenis": "masuk", "pengguna": "budi"})
        assert r["total"] == 0 and [p["username"] for p in r["per_pengguna"]] == ["sari"]
        for salah in (dict(jenis="lihat"), dict(mulai=date(2026, 10, 19), akhir=date(2026, 10, 1)), dict(mulai=date(2020, 1, 1))):
            try:
                api.daftar_aktivitas(**{**semua, **salah})
                assert False, salah
            except api.HTTPException as e:
                assert ahli.kode(e) == 422
    finally:
        api.log_aktivitas = asli


def test_format_baris_json():
    jam = Jam(datetime(2026, 10, 19, 8, 0, 30))
    la = baru(jam)
    la.catat("izin", "admin", "Admin", "System Administrator", "pr_po", "Role Operator: diberi akses")
    isi = json.loads((Path(la.folder) / "aktivitas-2026-10-19.jsonl").read_text(encoding="utf-8"))
    assert isi == {"waktu": "2026-10-19T08:00:30", "jenis": "izin", "username": "admin", "nama": "Admin", "role": "System Administrator",
                   "laporan": "pr_po", "keterangan": "Role Operator: diberi akses", "ip": None}
