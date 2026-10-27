"""Halaman & API RekapIn. Hak: menu RK_* di Admin › Hak Akses (Lihat untuk halaman; Tambah / Ubah / Hapus /
Setujui / Tolak / Selesai untuk aksi). Cakupan perusahaan & area mengikuti user CPOS yang login."""
from datetime import date, timedelta
from calendar import monthrange

import pyodbc
from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from modules.rekapin import rekapin_bp, db
from modules.rekapin import erp, laporan_tbs
from utils import persetujuan
from routes.dashboard import BATAS
from utils.area import company_user
from utils.db_organisasi import daftar_area, daftar_company
from utils.db_dashboard import KOLOM, simpan_harga
from utils.hak_akses import izin, boleh, halaman as lihat_halaman, remah_menu

def _company_rekap(user_id):
    """Perusahaan untuk RekapIn (harga, laporan TBS): semua perusahaan aktif di Admin › Organisasi dalam cakupan user,
    kecuali perusahaan yang areanya hanya kantor pusat (HO). Kodenya = CompName di Main.dbo.Company (ERP)."""
    pt = company_user(user_id)
    area = {}
    for a in daftar_area():
        if a["is_active"]:
            area.setdefault(a["id_company"], []).append(a)
    hanya_pusat = {c for c, isi in area.items() if all(a["is_pusat"] for a in isi)}
    return [{"id_company": c["id_company"], "nama": c["nama"]} for c in daftar_company()
            if c["is_active"] and c["id_company"] not in hanya_pusat and (pt is None or c["id_company"] in pt)]


def _halaman(template, kode, **isi):
    return render_template(f"rekapin/{template}.html", halaman="rekapin", kode_aktif=kode, remah=remah_menu(kode), **isi)


def _jalankan(fn, pesan):
    try:
        fn()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": pesan})


def _angka_id(teks):
    teks = (teks or "").strip()
    return int(teks) if teks.isdigit() else None


# ===== Dashboard =====
@rekapin_bp.route("/dashboard")
@login_required
@lihat_halaman("RK_DASHBOARD")
def dashboard():
    company = _company_rekap(current_user.id)
    kode = [c["id_company"] for c in company]
    harga = db.daftar_harga(kode, batas=200)
    terbaru = {}
    for h in harga:
        terbaru.setdefault(h["id_company"], h)
    tren = db.tren_harga(kode)
    hari = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
    seri = {c: {"cpo": [tren.get(c, {}).get(t, (None, None))[0] for t in hari],
                "kernel": [tren.get(c, {}).get(t, (None, None))[1] for t in hari]} for c in tren}
    ringkas = db.ringkas_request(current_user.id)
    return _halaman("dashboard", "RK_DASHBOARD", company=company, harga=harga[:6], jumlah_harga=len(harga),
                    terbaru=[(c, terbaru[c["id_company"]]) for c in company if c["id_company"] in terbaru],
                    hari=hari, seri=seri, ringkas=ringkas,
                    menunggu=db.daftar_request(current_user.id, "Pending")[:5],
                    jumlah_operator=len(db.daftar_operator(current_user.id)),
                    jumlah_kategori=len(db.daftar_kategori(aktif_saja=True)))


# ===== Request Operator =====
# Persetujuan memakai Admin › Alur Persetujuan, jenis "Request Operator" + aksi:
#   Tambah = request baru disetujui / ditolak (tanpa alur: satu tahap oleh pemegang hak Setujui menu ini),
#   Ubah / Koreksi dan Hapus = perubahan request (tanpa alur: langsung, cukup hak Ubah / Hapus).
for _aksi, _kode, _nama in (("TAMBAH", "REKAP_TAMBAH", "Request operator baru"), ("UBAH", "REKAP_UBAH", "Koreksi request operator"),
                            ("HAPUS", "REKAP_HAPUS", "Hapus request operator")):
    persetujuan.daftarkan_jenis("REKAP_REQUEST", "Request Operator", _aksi, _kode, _nama, "RK_REQUEST", "/rekapin/request?tab=persetujuan")


@persetujuan.pelaksana("REKAP_TAMBAH", saat_ditolak=lambda d: db.ubah_status(d["id_request"], "Rejected", None, None))
def _setujui_request(data, id_pengaju, id_penyetuju):
    db.ubah_status(data["id_request"], "Approved", None, id_penyetuju)


@persetujuan.pelaksana("REKAP_UBAH")
def _ubah_request(data, id_pengaju, id_penyetuju):
    db.simpan_request(data["id_request"], data["id_operator"], data["id_kategori"], data["tiket"], data["info_tiket"],
                      data["catatan"], id_pengaju)


@persetujuan.pelaksana("REKAP_HAPUS")
def _hapus_request(data, id_pengaju, id_penyetuju):
    db.hapus_request(data["id_request"])


@rekapin_bp.route("/request")
@login_required
@lihat_halaman("RK_REQUEST")
def halaman_request():
    hak = {a: boleh("RK_REQUEST", a) for a in ("tambah", "ubah", "hapus", "selesai")}
    return _halaman("request", "RK_REQUEST", hak=hak, kategori=db.daftar_kategori(aktif_saja=True),
                    company=_company_rekap(current_user.id))


def _bisa_setujui():
    """{id pengajuan request yang bisa saya setujui sekarang}"""
    return {p["id_pengajuan"] for p in persetujuan.daftar(current_user, "menunggu", menu="RK_REQUEST")}


@rekapin_bp.route("/api/request")
@login_required
@izin("RK_REQUEST", "lihat")
def api_request():
    status = request.args.get("status") or None
    berjalan, bisa = db.pengajuan_berjalan(), _bisa_setujui()
    # Tanpa hak menindaklanjuti: hanya request tentang dia / yang dia buat / yang menunggu persetujuannya
    milik = None if boleh("RK_REQUEST", "setujui", "selesai") else current_user.id
    juga = [i for i, daftar in berjalan.items() if any(p["id_pengajuan"] in bisa for p in daftar)]
    semua = db.daftar_request(current_user.id, None, milik, juga)
    ringkas = dict.fromkeys(db.STATUS, 0)
    for r in semua:
        ringkas[r["status"]] += 1
    rows = [r for r in semua if not status or r["status"] == status]
    for r in rows:
        r["pengajuan"] = [{"id": p["id_pengajuan"], "jenis": p["jenis"], "nama": persetujuan.JENIS.get(p["jenis"], p["jenis"]),
                           "langkah": p["langkah"], "total": p["total"], "menunggu": p["menunggu"],
                           "bisa": p["id_pengajuan"] in bisa} for p in berjalan.get(r["id"], [])]
    return jsonify({"data": rows, "ringkas": ringkas})


@rekapin_bp.route("/api/operator")
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_operator():
    return jsonify(db.daftar_operator(current_user.id))


def _cari_tiket(id_company, q):
    """Ascend (dbo.sp_GetTiketH7ByCompany di database ERP) bila koneksi ERP diisi; selain itu tiket CPOS sendiri."""
    return db.tiket_ascend(id_company, q) if erp.terhubung() else db.tiket_cpos(id_company, q)


@rekapin_bp.route("/api/tiket")
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_tiket():
    id_company = (request.args.get("company") or "").strip().upper()
    if id_company not in {c["id_company"] for c in _company_rekap(current_user.id)}:
        return jsonify({"error": "Pilih perusahaan dulu"}), 400
    try:
        return jsonify(_cari_tiket(id_company, (request.args.get("q") or "")[:50]))
    except pyodbc.Error:
        current_app.logger.exception("Cari tiket Ascend gagal")
        return jsonify({"error": "Tiket Ascend gagal dimuat. Periksa koneksi ERP (REKAPIN_ERP_*) dan dbo.sp_GetTiketH7ByCompany."}), 502


def _isi_request():
    """Baca & periksa isian form request. Kembalikan dict data (dipakai langsung atau disimpan di pengajuan)."""
    f = request.form
    id_operator, id_kategori = _angka_id(f.get("operator")), _angka_id(f.get("kategori"))
    id_company = (f.get("company") or "").strip().upper()
    tiket = (f.get("tiket") or "").strip()[:50]
    if id_operator not in {o["id_user"] for o in db.daftar_operator(current_user.id)}:
        raise ValueError("Pilih operator")
    if id_kategori not in {k["id"] for k in db.daftar_kategori(aktif_saja=True)}:
        raise ValueError("Pilih kesalahan")
    if not tiket:
        raise ValueError("Pilih nomor tiket")
    info = None
    if id_company in {c["id_company"] for c in _company_rekap(current_user.id)}:
        # Info tiket diambil ulang dari sumbernya (bukan dari browser) supaya isinya sesuai data timbang
        info = next((t for t in _cari_tiket(id_company, tiket) if t["TicketNo"] == tiket), None)
    return {"id_operator": id_operator, "id_kategori": id_kategori, "tiket": tiket, "info_tiket": info,
            "catatan": (f.get("catatan") or "").strip()[:500]}


@rekapin_bp.route("/api/request/simpan", methods=["POST"])
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_request_simpan():
    id_request = _angka_id(request.form.get("id"))
    if not boleh("RK_REQUEST", "ubah" if id_request else "tambah"):
        return jsonify({"error": "Anda tidak punya hak untuk aksi ini"}), 403
    if id_request and not db.request_dalam_cakupan(id_request, current_user.id):
        return jsonify({"error": "Request tidak ditemukan"}), 404
    try:
        d = _isi_request()
        lama = db.get_request(id_request) if id_request else None
        if d["info_tiket"] is None:
            if not lama:
                raise ValueError("Tiket tidak ditemukan di 7 hari terakhir perusahaan itu")
            d["info_tiket"] = lama["info_tiket"]
        judul = f"Request tiket {d['tiket']}"
        if lama is None:
            id_baru = db.simpan_request(None, d["id_operator"], d["id_kategori"], d["tiket"], d["info_tiket"], d["catatan"], current_user.id)
            status, siapa = persetujuan.ajukan("REKAP_TAMBAH", f"RQ{id_baru}", judul, d["catatan"], {"id_request": id_baru},
                                               current_user.id)
            return jsonify({"message": "Request tersimpan dan langsung disetujui" if status == "DISETUJUI"
                            else f"Request terkirim, menunggu persetujuan {siapa}" if siapa else "Request terkirim"})
        if lama["status"] in ("Rejected", "Done"):
            raise ValueError("Request yang sudah ditolak atau selesai tidak dapat diubah")
        if persetujuan.tahap_alur("REKAP_UBAH"):
            status, siapa = persetujuan.ajukan("REKAP_UBAH", f"RQ{id_request}-U", f"Koreksi {judul}", d["catatan"],
                                               {"id_request": id_request, **d}, current_user.id)
            return jsonify({"message": "Koreksi request langsung berlaku" if status == "DISETUJUI"
                            else f"Koreksi diajukan, menunggu persetujuan {siapa}"})
        db.simpan_request(id_request, d["id_operator"], d["id_kategori"], d["tiket"], d["info_tiket"], d["catatan"], current_user.id)
        return jsonify({"message": "Request berhasil diperbarui"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@rekapin_bp.route("/api/request/<int:id_request>/hapus", methods=["POST"])
@login_required
@izin("RK_REQUEST", "hapus")
def api_request_hapus(id_request):
    r = db.get_request(id_request) if db.request_dalam_cakupan(id_request, current_user.id) else None
    if r is None:
        return jsonify({"error": "Request tidak ditemukan"}), 404
    try:
        if persetujuan.tahap_alur("REKAP_HAPUS"):
            status, siapa = persetujuan.ajukan("REKAP_HAPUS", f"RQ{id_request}-H", f"Hapus request tiket {r['tiket']}",
                                               (request.form.get("alasan") or "").strip()[:500], {"id_request": id_request},
                                               current_user.id)
            return jsonify({"message": "Request dihapus" if status == "DISETUJUI" else f"Penghapusan diajukan, menunggu persetujuan {siapa}"})
        db.hapus_request(id_request)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Request berhasil dihapus"})


@rekapin_bp.route("/api/request/<int:id_request>/selesai", methods=["POST"])
@login_required
@izin("RK_REQUEST", "selesai")
def api_request_selesai(id_request):
    if not db.request_dalam_cakupan(id_request, current_user.id):
        return jsonify({"error": "Request tidak ditemukan"}), 404
    if not db.ubah_status(id_request, "Done", None, current_user.id):
        return jsonify({"error": "Hanya request yang sudah disetujui yang bisa ditandai selesai"}), 409
    return jsonify({"message": "Request selesai"})


def _pengajuan_request(id_request, id_pengajuan):
    if not any(p["id_pengajuan"] == id_pengajuan for p in db.pengajuan_berjalan().get(id_request, [])):
        raise ValueError("Pengajuan ini sudah diproses. Muat ulang daftar.")


@rekapin_bp.route("/api/request/<int:id_request>/pengajuan/<int:id_pengajuan>/<any(setujui, tolak):aksi>", methods=["POST"])
@login_required
def api_request_putuskan(id_request, id_pengajuan, aksi):
    """Setujui / tolak satu tahap persetujuan request (hak diperiksa mesin persetujuan: peran tahap berjalan)."""
    catatan = (request.form.get("catatan") or "").strip()[:255] or None
    try:
        _pengajuan_request(id_request, id_pengajuan)
        pesan = (persetujuan.setujui if aksi == "setujui" else persetujuan.tolak)(id_pengajuan, current_user, catatan)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.catat_aksi(id_request, catatan)
    return jsonify({"message": pesan})


@rekapin_bp.route("/api/request/setujui-terpilih", methods=["POST"])
@login_required
def api_request_setujui_terpilih():
    ids = {int(x) for x in (request.form.get("ids") or "").split(",") if x.strip().isdigit()}
    berjalan, bisa, n = db.pengajuan_berjalan(), _bisa_setujui(), 0
    for i in ids:
        for p in berjalan.get(i, []):
            if p["id_pengajuan"] in bisa:
                try:
                    persetujuan.setujui(p["id_pengajuan"], current_user)
                    n += 1
                except ValueError:
                    pass
    if not n:
        return jsonify({"error": "Tidak ada request terpilih yang menunggu persetujuan Anda"}), 400
    return jsonify({"message": f"{n} persetujuan diproses"})


# ===== Harga CPO & Kernel (dbo.DailyPrice) =====
@rekapin_bp.route("/harga")
@login_required
@lihat_halaman("RK_HARGA")
def halaman_harga():
    return _halaman("harga", "RK_HARGA", company=_company_rekap(current_user.id),
                    hak={a: boleh("RK_HARGA", a) for a in ("tambah", "ubah", "hapus")})


@rekapin_bp.route("/api/harga")
@login_required
@izin("RK_HARGA", "lihat")
def api_harga():
    kode = [c["id_company"] for c in _company_rekap(current_user.id)]
    tanggal = request.args.get("tanggal") or ""
    try:
        tanggal = date.fromisoformat(tanggal) if tanggal else ""
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    rows = db.daftar_harga(kode, (request.args.get("company") or "").upper(), tanggal)
    for r in rows:
        r["tanggal"] = r["tanggal"].isoformat()
        for k in ("harga_cpo", "harga_kernel", "oer_cpo", "biaya_olah", "qty_rsi"):
            r[k] = float(r[k]) if r[k] is not None else None
        r["diubah"] = r["diubah"].strftime("%Y-%m-%d %H:%M") if r["diubah"] else ""
    return jsonify(rows)


def _company_boleh(kode):
    if kode not in {c["id_company"] for c in _company_rekap(current_user.id)}:
        raise ValueError("Perusahaan tidak valid")
    return kode


@rekapin_bp.route("/api/harga/simpan", methods=["POST"])
@login_required
@izin("RK_HARGA", "tambah", "ubah")
def api_harga_simpan():
    f = request.form
    try:
        id_company = _company_boleh((f.get("company") or "").strip().upper())
        tanggal = date.fromisoformat(f.get("tanggal", ""))
    except ValueError:
        return jsonify({"error": "Pilih perusahaan dan tanggal"}), 400
    try:
        teks_rsi = (f.get("qty_rsi") or "").strip().replace(",", ".")
        qty_rsi = float(teks_rsi) if teks_rsi else None
        if qty_rsi is not None and not 0 <= qty_rsi <= 1_000_000_000:
            raise ValueError
        nilai = []
        for k in KOLOM:
            v = float((f.get(k) or "").replace(",", "."))
            if not BATAS[k][0] <= v <= BATAS[k][1]:
                raise ValueError
            nilai.append(v)
    except ValueError:
        return jsonify({"error": "Semua nilai wajib diisi angka yang wajar (OER 0 - 100 %)"}), 400
    if tanggal > date.today():
        return jsonify({"error": "Tanggal tidak boleh setelah hari ini"}), 400
    ada = db.harga_ada(id_company, tanggal)
    if not boleh("RK_HARGA", "ubah" if ada else "tambah"):
        return jsonify({"error": f"Harga {id_company} {tanggal:%d-%m-%Y} sudah ada; Anda tidak punya hak mengubahnya" if ada
                        else "Anda tidak punya hak menambah harga"}), 403
    simpan_harga(id_company, tanggal, nilai, qty_rsi, current_user.id)
    return jsonify({"message": f"Harga {id_company} {tanggal:%d-%m-%Y} berhasil disimpan"})


@rekapin_bp.route("/api/harga/hapus", methods=["POST"])
@login_required
@izin("RK_HARGA", "hapus")
def api_harga_hapus():
    try:
        id_company = _company_boleh((request.form.get("company") or "").strip().upper())
        tanggal = date.fromisoformat(request.form.get("tanggal", ""))
    except ValueError:
        return jsonify({"error": "Data harga tidak valid"}), 400
    return _jalankan(lambda: db.hapus_harga(id_company, tanggal), f"Harga {id_company} {tanggal:%d-%m-%Y} dihapus")


# ===== Kategori Request =====
@rekapin_bp.route("/kategori")
@login_required
@lihat_halaman("RK_FITUR")
def halaman_kategori():
    return _halaman("kategori", "RK_FITUR", hak={a: boleh("RK_FITUR", a) for a in ("tambah", "ubah", "hapus")})


@rekapin_bp.route("/api/kategori")
@login_required
@izin("RK_FITUR", "lihat")
def api_kategori():
    return jsonify([{**k, "dibuat": k["dibuat"].strftime("%Y-%m-%d") if k["dibuat"] else ""} for k in db.daftar_kategori()])


@rekapin_bp.route("/api/kategori/simpan", methods=["POST"])
@login_required
@izin("RK_FITUR", "tambah", "ubah")
def api_kategori_simpan():
    id_kategori = _angka_id(request.form.get("id"))
    nama = " ".join((request.form.get("nama") or "").split())[:100]
    if not boleh("RK_FITUR", "ubah" if id_kategori else "tambah"):
        return jsonify({"error": "Anda tidak punya hak untuk aksi ini"}), 403
    if not nama:
        return jsonify({"error": "Nama kategori wajib diisi"}), 400
    return _jalankan(lambda: db.simpan_kategori(id_kategori, nama, current_user.id), f"Kategori {nama} disimpan")


@rekapin_bp.route("/api/kategori/<int:id_kategori>/hapus", methods=["POST"])
@login_required
@izin("RK_FITUR", "hapus")
def api_kategori_hapus(id_kategori):
    try:
        cara = db.hapus_kategori(id_kategori)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Kategori dihapus" if cara == "hapus" else "Kategori sudah dipakai request, jadi hanya dinonaktifkan"})


@rekapin_bp.route("/api/kategori/<int:id_kategori>/aktif", methods=["POST"])
@login_required
@izin("RK_FITUR", "ubah")
def api_kategori_aktif(id_kategori):
    aktif = request.form.get("aktif") == "1"
    return _jalankan(lambda: db.set_aktif_kategori(id_kategori, aktif), "Kategori diaktifkan" if aktif else "Kategori dinonaktifkan")


# ===== Laporan Pembelian TBS (prosedur ERP, modules/rekapin/erp.py) =====
@rekapin_bp.route("/tbs/<any(daily, weekly, monthly):jenis>")
@login_required
@lihat_halaman(lambda r: laporan_tbs.LAPORAN[r.view_args["jenis"]]["menu"])
def laporan(jenis):
    lap = laporan_tbs.LAPORAN[jenis]
    company = _company_rekap(current_user.id)
    kode = [c["id_company"] for c in company]
    pilih = (request.args.get("company") or "").strip().upper() or (kode[0] if kode else "")
    hari_ini = date.today()
    if lap["periode"] == "daily":
        awal = akhir = request.args.get("date") or hari_ini.isoformat()
    elif jenis == "weekly":
        awal = request.args.get("start_date") or (hari_ini - timedelta(weeks=4)).isoformat()
        akhir = request.args.get("end_date") or hari_ini.isoformat()
    else:
        awal = request.args.get("start_date") or hari_ini.replace(day=1).isoformat()
        akhir = request.args.get("end_date") or hari_ini.replace(day=monthrange(hari_ini.year, hari_ini.month)[1]).isoformat()
    tabel, galat = [], ""
    try:
        t_awal, t_akhir = date.fromisoformat(awal), date.fromisoformat(akhir)
    except ValueError:
        galat = "Tanggal laporan tidak valid."
    if not galat and pilih not in kode:
        galat = "Perusahaan tidak valid." if pilih else "Belum ada perusahaan yang dapat dipilih untuk laporan ini."
    elif not galat and t_awal > t_akhir:
        galat = "Tanggal awal tidak boleh melewati tanggal akhir."
    if not galat:
        param = (pilih, awal) if lap["periode"] == "daily" else (pilih, awal, akhir)
        try:
            tabel = laporan_tbs.susun_tabel(jenis, erp.jalankan_prosedur(lap["prosedur"], *param))
        except pyodbc.Error:
            current_app.logger.exception("Laporan TBS %s gagal", jenis)
            galat = "Laporan gagal dimuat. Periksa koneksi database ERP (REKAPIN_ERP_CONNECTION_STRING) dan prosedur " + lap["prosedur"] + "."
    return _halaman("tbs", lap["menu"], jenis=jenis, lap=lap, company=company, pilih=pilih, awal=awal, akhir=akhir,
                    tabel=tabel, galat=galat, nilai=laporan_tbs.tbs_report_value, tgl=laporan_tbs.web_date_format)
