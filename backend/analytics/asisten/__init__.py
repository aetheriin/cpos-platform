"""Asisten: tanya jawab data laporan dengan kalimat biasa, tanpa AI dan tanpa data keluar kantor.

pembaca.py mengubah kalimat jadi permintaan, pengolah.py menghitungnya dari data laporan yang sudah dimuat. Pertanyaan dan penilaian 👍/👎
dicatat di folder lokal server (ASISTEN_FOLDER, bawaan %LOCALAPPDATA%\\cpos-platform\\asisten) untuk perbaikan kamus."""
import json
import os
import random
import threading
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from . import kamus, pengolah
from .pembaca import NAMA_BULAN, baca, lengkapi, normal
from .pengolah import Memuat, TanpaAkses

FOLDER = Path(os.environ.get("ASISTEN_FOLDER") or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "cpos-platform" / "asisten")
_kunci = threading.Lock()
_istilah = None


def _catat(nama, isi):
    try:
        FOLDER.mkdir(parents=True, exist_ok=True)
        with _kunci, open(FOLDER / nama, "a", encoding="utf-8") as f:
            f.write(json.dumps(isi, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass   # catatan gagal tidak boleh menggagalkan jawaban


def _belajar():
    """{kalimat normal: pertanyaan contoh} dari klik "Maksud Anda" sebelumnya."""
    hasil = {}
    try:
        with open(FOLDER / "belajar.jsonl", encoding="utf-8") as f:
            for baris in f:
                d = json.loads(baris)
                hasil[d["asal"]] = d["ke"]
    except (OSError, ValueError, KeyError):
        pass
    return hasil


def istilah():
    global _istilah
    if _istilah is None:
        _istilah = pengolah.muat_istilah()
    return _istilah


def ingat(asal, ke, pengguna):
    """Pengguna memilih saran "Maksud Anda" untuk kalimat yang tidak dikenali: lain kali kalimat itu langsung diarahkan ke sana."""
    asal_n = normal(asal)
    if asal_n and ke in kamus.CONTOH:
        _catat("belajar.jsonl", {"waktu": datetime.now(), "pengguna": pengguna, "asal": asal_n, "ke": ke})


def nilai(id_jawaban, suka, pengguna, komentar=None):
    _catat("nilai.jsonl", {"waktu": datetime.now(), "pengguna": pengguna, "id": id_jawaban, "suka": bool(suka), "komentar": (komentar or "")[:500]})


def _arahkan(teks):
    """Kalimat yang dulu tidak dikenali dan sudah dipetakan pengguna ke pertanyaan contoh."""
    t = normal(teks)
    belajar = _belajar()
    if t in belajar:
        return belajar[t]
    for asal, ke in belajar.items():
        if SequenceMatcher(None, t, asal).ratio() >= 0.9:
            return ke
    return None


def tanya(teks, lalu, ambil, perusahaan, pengguna, nama=None, menu=None, nama_menu=None):
    """ambil(sumber) -> (DataFrame, info); bisa melempar Memuat / TanpaAkses. lalu: permintaan sebelumnya (dari layar)."""
    teks = (teks or "").strip()[:300]
    id_jawaban = uuid.uuid4().hex[:12]
    arah = _arahkan(teks)
    # Konteks percakapan hanya diteruskan di menu yang sama: pindah menu = mulai dari ukuran menu yang baru
    if isinstance(lalu, dict) and lalu.get("menu") != menu:
        lalu = None
    p = baca(arah or teks, perusahaan, menu=menu)
    p = lengkapi(p, lalu if isinstance(lalu, dict) else None)
    hasil = _jawab(p, ambil, perusahaan, teks, nama, menu, nama_menu)
    hasil["id"] = id_jawaban
    if arah:
        hasil.setdefault("catatan", []).insert(0, f"Dibaca sebagai: \"{arah}\".")
    if hasil.get("jenis") == "memuat":   # pertanyaan yang sama diulang layar sampai data siap: dicatat sekali saja nanti
        return hasil
    _catat("riwayat.jsonl", {"waktu": datetime.now(), "pengguna": pengguna, "id": id_jawaban, "teks": teks, "menu": menu, "maksud": hasil.get("jenis"),
                             "dipahami": hasil.get("jenis") != "tidak_paham", "permintaan": hasil.get("permintaan")})
    return hasil


def _jawab(p, ambil, perusahaan, teks, nama=None, menu=None, nama_menu=None):
    m = p["maksud"]
    info_menu = kamus.MENU.get(menu or "", {})
    saran_menu = info_menu.get("saran") or kamus.CONTOH[:4]
    if m == "menu":
        if not info_menu:
            return {"jenis": "obrolan", "teks": "Buka salah satu laporan dulu, nanti saya jelaskan isinya.", "saran": kamus.CONTOH[:4]}
        bisa = ("Angkanya bisa ditanyakan ke saya." if info_menu.get("sumber") else
                "Angka di menu ini belum bisa ditanyakan ke saya, tapi istilahnya bisa.")
        return {"jenis": "obrolan", "teks": f"{nama_menu or 'Menu ini'}: {info_menu['isi']} {bisa}", "saran": saran_menu}
    # Pertanyaan tanpa ukuran di menu yang punya data ("per supplier", "yang belum"): pakai ukuran utama menu itu
    dari_menu = None
    if m in ("angka", "daftar") and not p.get("ukuran") and not p.get("status") and info_menu.get("ukuran"):
        p["ukuran"] = dari_menu = info_menu["ukuran"]
    if m == "obrolan":
        o = kamus.OBROLAN[p["obrolan"]]
        h = datetime.now()
        jam = h.hour
        salam = "Selamat pagi" if jam < 11 else "Selamat siang" if jam < 15 else "Selamat sore" if jam < 18 else "Selamat malam"
        hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][h.weekday()]
        jawab = random.choice(o["jawab"]) if isinstance(o["jawab"], list) else o["jawab"]
        pola = jawab if nama else jawab.replace(", {nama}", "")
        teks = pola.format(nama=nama, salam=salam, asisten=kamus.NAMA_ASISTEN, jam=h.strftime("%H.%M"),
                                 tanggal=f"{hari}, {h.day} {NAMA_BULAN[h.month - 1]} {h.year}")
        return {"jenis": "obrolan", "teks": teks, **({"saran": saran_menu} if o.get("saran") else {})}
    if m == "bantuan":
        return {"jenis": "teks", "teks": "Saya bisa menjawab angka dari laporan Outstanding, Purchase Request, dan Purchase Order: total, per perusahaan, "
                                         "per supplier, per bulan, daftar dokumen, membandingkan periode, mencari satu nomor dokumen, dan arti istilah. "
                                         "Pertanyaan lanjutan seperti \"kalau YBS?\" atau \"per supplier\" melanjutkan pertanyaan sebelumnya.",
                "saran": saran_menu}
    if m == "istilah":
        judul = pengolah._cari_istilah(p["istilah"], istilah())
        if judul is None:
            return {"jenis": "tidak_paham", "teks": f"Istilah \"{p['istilah']}\" belum ada di catatan saya. Yang sudah ada misalnya:",
                    "saran": [f"Apa itu {k}?" for k in list(istilah())[:4]]}
        if judul.startswith("ukuran:"):
            u = kamus.UKURAN[judul[7:]]
            return {"jenis": "teks", "teks": f"{u['label']}: {u['arti']}", "sumber_teks": "Kamus data Asisten", "saran": [u["label"], f"{u['label']} per perusahaan"]}
        return {"jenis": "teks", "teks": f"{judul}: {istilah()[judul]['teks']}", "sumber_teks": "Buku konteks istilah"}
    try:
        if m == "dokumen":
            return {"jenis": "dokumen", **pengolah.jawab_dokumen(p["nomor"], ambil)}
        hasil = pengolah.jawab_angka(p, ambil, perusahaan)
    except Memuat as e:
        return {"jenis": "memuat", "teks": "Sedang mengambil data laporan dari server. Tunggu sebentar…", "sumber": e.sumber}
    except TanpaAkses as e:
        nama = pengolah.NAMA_LAPORAN[kamus.SUMBER[e.sumber]["laporan"]]
        return {"jenis": "teks", "teks": f"Akun Anda tidak punya akses ke laporan {nama}, jadi pertanyaan ini tidak bisa saya jawab."}
    if hasil is None:
        return {"jenis": "tidak_paham", "teks": "Waduh, yang ini belum bisa saya tangkap. Saya baru paham angka hutang, piutang, PR, PO, dan PI. Mungkin maksudnya salah satu ini:", "saran": pengolah.tebak(teks, menu=menu), "asal": teks}
    if dari_menu:
        hasil.setdefault("catatan", []).append(f"Dihitung dengan ukuran utama menu ini: {kamus.UKURAN[dari_menu]['label']}.")
    jenis = "daftar" if p.get("maksud") == "daftar" else "grafik" if hasil.get("grafik") else "angka" if hasil.get("angka") else "teks"
    return {"jenis": jenis, **hasil}
