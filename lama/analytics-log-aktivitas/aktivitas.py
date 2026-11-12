"""Log aktivitas untuk halaman admin, satu berkas JSON Lines per hari di AKTIVITAS_FOLDER (tidak butuh tabel baru).

Berkas yang lebih tua dari AKTIVITAS_SIMPAN_HARI dihapus. Gagal menulis log tidak pernah menggagalkan permintaan pengguna."""
import json
import logging
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger("dashboard")

JENIS = {
    "masuk": "Masuk",
    "gagal_masuk": "Gagal masuk",
    "keluar": "Keluar",
    "muat": "Membuka laporan",
    "ekspor": "Export Excel",
    "akun_tambah": "Membuat akun",
    "akun_ubah": "Mengubah akun",
    "akun_hapus": "Menghapus akun",
    "role_tambah": "Membuat role",
    "divisi_tambah": "Membuat divisi",
    "izin": "Mengubah hak akses",
    "sesi_cabut": "Mengeluarkan sesi",
    "pengaturan": "Mengubah pengaturan",
    "ganti_sandi": "Mengganti password sendiri",
}


class LogAktivitas:
    def __init__(self, folder, simpan_hari, jam=datetime.now):
        self.folder, self.simpan_hari, self._jam = Path(folder), simpan_hari, jam
        self._kunci = threading.Lock()
        self._disapu = None

    def _berkas(self, hari):
        return self.folder / f"aktivitas-{hari.isoformat()}.jsonl"

    def catat(self, jenis, username, nama="", role="", laporan=None, keterangan="", ip=None):
        if jenis not in JENIS:
            raise ValueError(f"Jenis aktivitas tidak dikenal: {jenis}")
        waktu = self._jam()
        baris = {"waktu": waktu.isoformat(timespec="seconds"), "jenis": jenis, "username": username or "", "nama": nama or "",
                 "role": role or "", "laporan": laporan, "keterangan": keterangan or "", "ip": ip}
        try:
            with self._kunci:
                self.folder.mkdir(parents=True, exist_ok=True)
                with open(self._berkas(waktu.date()), "a", encoding="utf-8") as f:
                    f.write(json.dumps(baris, ensure_ascii=False) + "\n")
                if self._disapu != waktu.date():
                    self._sapu(waktu.date())
        except OSError as e:
            log.error("Log aktivitas tidak bisa ditulis ke %s: %s", self.folder, e)

    def _sapu(self, hari_ini):
        batas = hari_ini - timedelta(days=self.simpan_hari)
        for p in self.folder.glob("aktivitas-*.jsonl"):
            try:
                if date.fromisoformat(p.stem.removeprefix("aktivitas-")) < batas:
                    p.unlink()
            except (ValueError, OSError):
                continue
        self._disapu = hari_ini

    def baca(self, mulai, akhir):
        """Terbaru lebih dulu. Baris yang rusak dilewati."""
        hasil = []
        hari = akhir
        while hari >= mulai:
            p = self._berkas(hari)
            if p.exists():
                with self._kunci, open(p, encoding="utf-8") as f:
                    for teks in f:
                        try:
                            hasil.append(json.loads(teks))
                        except json.JSONDecodeError:
                            continue
            hari -= timedelta(days=1)
        hasil.sort(key=lambda b: b.get("waktu", ""), reverse=True)
        return hasil


def ringkas_pengguna(baris):
    """Gagal masuk tidak dihitung: username-nya belum tentu ada."""
    per = {}
    for b in baris:
        if b["jenis"] == "gagal_masuk" or not b["username"]:
            continue
        r = per.setdefault(b["username"], {"username": b["username"], "nama": b["nama"], "role": b["role"], "terakhir": b["waktu"],
                                           "masuk": 0, "muat": 0, "ekspor": 0, "laporan": set()})
        if not r["nama"] and b["nama"]:
            r["nama"], r["role"] = b["nama"], b["role"]
        if b["jenis"] in ("masuk", "muat", "ekspor"):
            r[b["jenis"]] += 1
        if b["jenis"] == "muat" and b.get("laporan"):
            r["laporan"].add(b["laporan"])
    return [{**r, "laporan": sorted(r["laporan"])} for r in sorted(per.values(), key=lambda r: r["terakhir"], reverse=True)]
