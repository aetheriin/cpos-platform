"""Halaman & API Netto Sumber. Hak menu FM_NETTO_SUMBER di Admin › Hak Akses: Lihat (halaman), Tambah (isi tiket yang belum
diisi), Ubah (ubah atau batalkan isian), Setujui (ubah isian bulan yang sudah ditutup). Perusahaan mengikuti cakupan data menu ini."""
import logging
import math
from datetime import date, datetime, timedelta

import pyodbc
from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from modules.netto_sumber import db, netto_sumber_bp as bp
from utils import pengaturan
from utils.area import company_user
from utils.hak_akses import boleh, halaman as lihat_halaman, izin, remah_menu

log = logging.getLogger(__name__)
KODE = "FM_NETTO_SUMBER"
MAKS_HARI = 62          # rentang terpanjang sekali tampil (SP membaca server Tiket per perusahaan)
MAKS_NETTO = 200000     # kg, batas wajar satu truk
NAMA_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November",
              "Desember")


def _perusahaan():
    """Perusahaan ERP dalam cakupan data menu ini: [{kode, nama}]."""
    pt = company_user(current_user.id, KODE)
    return [p for p in db.perusahaan_tiket() if pt is None or p["kode"] in pt]


def _tutup(tgl):
    """Mulai tanggal ini isian tiket bertanggal tgl terkunci: tanggal tutup di bulan berikutnya."""
    tahun, bulan = (tgl.year + 1, 1) if tgl.month == 12 else (tgl.year, tgl.month + 1)
    return date(tahun, bulan, pengaturan.nilai("NETTO_SUMBER_TUTUP_TANGGAL"))


def _mulai_bawaan(hari_ini):
    """Awal bulan tertua yang belum ditutup: bulan lalu masih terbuka sampai tanggal tutup bulan ini."""
    awal = hari_ini.replace(day=1)
    if hari_ini < _tutup(awal - timedelta(days=1)):
        return (awal - timedelta(days=1)).replace(day=1)
    return awal


def _tgl(teks):
    try:
        return date.fromisoformat(str(teks or "").strip()[:10])
    except ValueError:
        return None


def _iso(v):
    return v.isoformat(timespec="minutes") if isinstance(v, datetime) else v.isoformat() if isinstance(v, date) else v


def _isian_json(r):
    if r is None or r["netto_sumber"] is None:
        return None
    return {"id": r["id"], "netto_sumber": float(r["netto_sumber"]), "referensi": r["referensi"] or "",
            "catatan": r["catatan"] or "", "oleh": r["oleh"] or "", "pada": _iso(r["pada"])}


def _status(t, isian, rusak):
    if isian:
        return "diisi"
    if (t["split"] and (t["comp"], t["induk"]) in rusak) or t["sumber_tiket"] < 0:
        return "perlu_dicek"
    return "perlu_diisi" if t["sumber_tiket"] == 0 else "dari_tiket"


@bp.route("")
@login_required
@lihat_halaman(KODE)
def halaman_netto_sumber():
    hari_ini = date.today()
    hak = {a: boleh(KODE, a) for a in ("tambah", "ubah", "setujui")}
    return render_template("netto_sumber/index.html", halaman="netto_sumber", kode_aktif=KODE, remah=remah_menu(KODE),
                           hak=hak, perusahaan=_perusahaan(), mulai=_mulai_bawaan(hari_ini).isoformat(),
                           akhir=hari_ini.isoformat(), maks_hari=MAKS_HARI, produk=db.PRODUK,
                           batas=pengaturan.nilai("NETTO_SUMBER_BATAS_PERSEN"))


@bp.route("/api/tiket")
@login_required
@izin(KODE, "lihat")
def api_tiket():
    mulai, akhir = _tgl(request.args.get("mulai")), _tgl(request.args.get("akhir"))
    if not mulai or not akhir:
        return jsonify({"error": "Isi tanggal dari dan sampai"}), 400
    if mulai > akhir:
        return jsonify({"error": "Tanggal dari tidak boleh setelah tanggal sampai"}), 400
    if (akhir - mulai).days + 1 > MAKS_HARI:
        return jsonify({"error": f"Rentang paling panjang {MAKS_HARI} hari"}), 400
    boleh_pt = [p["kode"] for p in _perusahaan()]
    pilih = (request.args.get("perusahaan") or "").strip()
    if pilih and pilih not in boleh_pt:
        return jsonify({"error": "Perusahaan di luar cakupan Anda."}), 403
    kode_pt = [pilih] if pilih else boleh_pt
    if not kode_pt:
        return jsonify({"data": [], "siap": True})
    try:
        daftar, gagal = db.tiket(kode_pt, mulai, akhir)
    except pyodbc.Error:
        log.exception("Gagal membaca tiket penjualan (dbo.TIKET_PENJUALAN)")
        return jsonify({"error": "Tiket belum bisa dibaca dari Tiket. Coba lagi, atau hubungi IT bila masih gagal."}), 502
    for kode, e in gagal.items():
        log.error("dbo.TIKET_PENJUALAN gagal untuk %s: %s", kode, e)
    pesan, siap = None, True
    try:
        isian = db.isian_terakhir(mulai, akhir)
    except db.TabelBelumAda as e:
        log.error("Tabel dbo.NettoSumberIsian belum ada: jalankan database/perubahan/029_netto_sumber.sql di database Main")
        isian, pesan, siap = {}, str(e), False
    hari_ini = date.today()
    rusak = {(t["comp"], t["induk"]) for t in daftar if t["split"] and t["sumber_tiket"] < 0}
    data = []
    for t in sorted(daftar, key=lambda x: (x["tanggal"], x["comp"], x["tiket"]), reverse=True):
        terakhir = isian.get((t["comp"], t["tiket"]))
        isi = _isian_json(terakhir)
        data.append({**{k: t[k] for k in ("comp", "tiket", "split", "induk", "produk", "pembeli", "no_do", "kendaraan",
                                          "netto", "sumber_tiket")},
                     "tanggal": t["tanggal"].isoformat(), "isian": isi, "id_terakhir": terakhir["id"] if terakhir else 0,
                     "status": _status(t, isi, rusak), "terkunci": hari_ini >= _tutup(t["tanggal"])})
    return jsonify({"data": data, "siap": siap, "pesan": pesan,
                    "gagal": sorted(gagal), "dimuat": datetime.now().isoformat(timespec="minutes")})


@bp.route("/api/riwayat")
@login_required
@izin(KODE, "lihat")
def api_riwayat():
    kode, no_tiket = (request.args.get("perusahaan") or "").strip(), (request.args.get("tiket") or "").strip()[:50]
    if kode not in {p["kode"] for p in _perusahaan()}:
        return jsonify({"error": "Perusahaan di luar cakupan Anda."}), 403
    return jsonify([{"id": r["id"], "netto_sumber": None if r["netto_sumber"] is None else float(r["netto_sumber"]),
                     "referensi": r["referensi"] or "", "catatan": r["catatan"] or "", "oleh": r["oleh"] or "",
                     "pada": _iso(r["pada"]), "netto_tiket": float(r["netto_tiket"])}
                    for r in db.riwayat(kode, no_tiket)])


def _netto(teks):
    """Angka kg dari isian: 28340, 28.340, atau 28340,5."""
    s = str(teks or "").strip().replace(" ", "")
    if not s:
        raise ValueError("Isi netto sumber.")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")
    try:
        nilai = float(s)
    except ValueError:
        raise ValueError("Netto sumber harus berupa angka kg.") from None
    if not math.isfinite(nilai) or nilai <= 0:
        raise ValueError("Netto sumber harus lebih dari 0 kg.")
    if nilai > MAKS_NETTO:
        raise ValueError(f"Netto sumber paling besar {MAKS_NETTO:,} kg.".replace(",", "."))
    return round(nilai, 2)


def _rupa(n):
    return f"{n:,.0f}".replace(",", ".")


@bp.route("/api/simpan", methods=["POST"])
@login_required
@izin(KODE, "tambah", "ubah")
def api_simpan():
    f = request.form
    kode, no_tiket, tgl = (f.get("perusahaan") or "").strip(), (f.get("tiket") or "").strip()[:50], _tgl(f.get("tanggal"))
    batalkan = f.get("batalkan") == "1"
    try:
        id_terakhir = int(f.get("id_terakhir") or 0)
    except ValueError:
        id_terakhir = -1
    if kode not in {p["kode"] for p in _perusahaan()}:
        return jsonify({"error": "Perusahaan di luar cakupan Anda."}), 403
    if not no_tiket or tgl is None:
        return jsonify({"error": "Tiket tidak lengkap. Muat ulang halaman lalu coba lagi."}), 400
    lama = next(iter(db.riwayat(kode, no_tiket)), None)
    ada = lama is not None and lama["netto_sumber"] is not None
    aksi = "ubah" if ada or batalkan else "tambah"
    if not boleh(KODE, aksi):
        return jsonify({"error": "Anda tidak punya hak mengubah isian tiket ini" if aksi == "ubah"
                        else "Anda tidak punya hak mengisi netto sumber"}), 403
    if batalkan and not ada:
        return jsonify({"error": "Tiket ini belum punya isian."}), 400
    try:
        t = db.satu_tiket(kode, no_tiket, tgl)
    except pyodbc.Error:
        log.exception("Gagal membaca ulang tiket %s %s", kode, no_tiket)
        return jsonify({"error": "Tiket belum bisa dibaca dari Tiket. Coba lagi sebentar."}), 502
    if t is None:
        return jsonify({"error": "Tiket tidak ditemukan di Tiket pada tanggal itu. Muat ulang daftar tiket."}), 404
    if date.today() >= _tutup(t["tanggal"]) and not boleh(KODE, "setujui"):
        bulan = f"{NAMA_BULAN[t['tanggal'].month - 1]} {t['tanggal'].year}"
        return jsonify({"error": f"Bulan {bulan} sudah ditutup. Minta pemegang hak Setujui di menu Netto Sumber untuk mengubahnya."}), 403
    referensi, catatan = (f.get("referensi") or "").strip()[:50], (f.get("catatan") or "").strip()[:500]
    try:
        if batalkan:
            netto_sumber, referensi = None, ""
        else:
            netto_sumber = _netto(f.get("netto_sumber"))
            batas = pengaturan.nilai("NETTO_SUMBER_BATAS_PERSEN")
            persen = abs(t["netto"] - netto_sumber) / t["netto"] * 100 if t["netto"] else None
            if not catatan and (persen is None or persen > batas):
                angka = f"{batas:g}".replace(".", ",")
                raise ValueError(f"Selisih dengan netto timbangan lebih dari {angka}%. Isi catatan alasannya."
                                 if persen is not None else "Isi catatan alasannya.")
        db.simpan(kode, t, netto_sumber, referensi, catatan, id_terakhir, current_user.id)
    except db.SudahBerubah as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except db.TabelBelumAda as e:
        log.error("Tabel dbo.NettoSumberIsian belum ada: jalankan database/perubahan/029_netto_sumber.sql di database Main")
        return jsonify({"error": str(e)}), 503
    if batalkan:
        return jsonify({"message": f"Isian {no_tiket} dibatalkan. Riwayatnya tetap tersimpan."})
    return jsonify({"message": f"Netto sumber {no_tiket} tersimpan: {_rupa(netto_sumber)} kg"})
