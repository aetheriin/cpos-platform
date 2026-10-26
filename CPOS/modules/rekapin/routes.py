"""Halaman & API RekapIn. Hak: menu RK_* di Admin › Hak Akses (Lihat untuk halaman; Tambah / Ubah / Hapus /
Setujui / Tolak / Selesai untuk aksi). Cakupan perusahaan & area mengikuti user CPOS yang login."""
from datetime import date, timedelta
from calendar import monthrange

import pyodbc
from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from modules.rekapin import rekapin_bp, db
from modules.rekapin import erp, laporan_tbs
from routes.dashboard import BATAS, _company_harga
from utils.db_dashboard import KOLOM, simpan_harga
from utils.hak_akses import izin, boleh, halaman as lihat_halaman, remah_menu

AKSI_STATUS = {"Approved": "setujui", "Rejected": "tolak", "Done": "selesai"}


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
    company = _company_harga(current_user.id)
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
@rekapin_bp.route("/request")
@login_required
@lihat_halaman("RK_REQUEST")
def halaman_request():
    hak = {a: boleh("RK_REQUEST", a) for a in ("tambah", "ubah", "hapus", "setujui", "tolak", "selesai")}
    return _halaman("request", "RK_REQUEST", hak=hak, kategori=db.daftar_kategori(aktif_saja=True))


def _hanya_milik_sendiri():
    """Operator tanpa hak menindaklanjuti hanya melihat request miliknya."""
    if db.adalah_operator(current_user.id) and not boleh("RK_REQUEST", "setujui", "tolak", "selesai"):
        return current_user.id
    return None


@rekapin_bp.route("/api/request")
@login_required
@izin("RK_REQUEST", "lihat")
def api_request():
    status = request.args.get("status") or None
    milik = _hanya_milik_sendiri()
    return jsonify({"data": db.daftar_request(current_user.id, status if status in db.STATUS else None, milik),
                    "ringkas": db.ringkas_request(current_user.id, milik)})


@rekapin_bp.route("/api/operator")
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_operator():
    return jsonify(db.daftar_operator(current_user.id))


@rekapin_bp.route("/api/tiket")
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_tiket():
    id_operator = _angka_id(request.args.get("operator"))
    if id_operator not in {o["id_user"] for o in db.daftar_operator(current_user.id)}:
        return jsonify({"error": "Pilih operator dulu"}), 400
    return jsonify(db.tiket_operator(id_operator, (request.args.get("q") or "")[:50]))


@rekapin_bp.route("/api/request/simpan", methods=["POST"])
@login_required
@izin("RK_REQUEST", "tambah", "ubah")
def api_request_simpan():
    f = request.form
    id_request = _angka_id(f.get("id"))
    if not boleh("RK_REQUEST", "ubah" if id_request else "tambah"):
        return jsonify({"error": "Anda tidak punya hak untuk aksi ini"}), 403
    if id_request and not db.request_dalam_cakupan(id_request, current_user.id):
        return jsonify({"error": "Request tidak ditemukan"}), 404
    id_operator, id_kategori = _angka_id(f.get("operator")), _angka_id(f.get("kategori"))
    tiket = (f.get("tiket") or "").strip()[:50]
    catatan = (f.get("catatan") or "").strip()[:500]
    if id_operator not in {o["id_user"] for o in db.daftar_operator(current_user.id)}:
        return jsonify({"error": "Pilih operator"}), 400
    if id_kategori not in {k["id"] for k in db.daftar_kategori(aktif_saja=True)}:
        return jsonify({"error": "Pilih kesalahan"}), 400
    if not tiket:
        return jsonify({"error": "Pilih nomor tiket"}), 400
    # Info tiket diambil ulang dari CPOS (bukan dari browser) supaya isinya sesuai data timbang
    info = next((t for t in db.tiket_operator(id_operator, tiket) if t["TicketNo"] == tiket), None)
    if info is None and not id_request:
        return jsonify({"error": "Tiket tidak ditemukan di 7 hari terakhir perusahaan operator"}), 400
    if info is None:
        info = (db.get_request(id_request) or {}).get("info_tiket") or {}
    return _jalankan(lambda: db.simpan_request(id_request, id_operator, id_kategori, tiket, info, catatan, current_user.id),
                     "Request berhasil diperbarui" if id_request else "Request berhasil dikirim")


@rekapin_bp.route("/api/request/<int:id_request>/hapus", methods=["POST"])
@login_required
@izin("RK_REQUEST", "hapus")
def api_request_hapus(id_request):
    if not db.request_dalam_cakupan(id_request, current_user.id):
        return jsonify({"error": "Request tidak ditemukan"}), 404
    return _jalankan(lambda: db.hapus_request(id_request), "Request berhasil dihapus")


@rekapin_bp.route("/api/request/<int:id_request>/status", methods=["POST"])
@login_required
@izin("RK_REQUEST", "setujui", "tolak", "selesai")
def api_request_status(id_request):
    status = request.form.get("status")
    if status not in AKSI_STATUS or not boleh("RK_REQUEST", AKSI_STATUS[status]):
        return jsonify({"error": "Anda tidak punya hak untuk aksi ini"}), 403
    if not db.request_dalam_cakupan(id_request, current_user.id):
        return jsonify({"error": "Request tidak ditemukan"}), 404
    if not db.ubah_status(id_request, status, (request.form.get("catatan") or "").strip(), current_user.id):
        return jsonify({"error": "Status request sudah berubah. Muat ulang daftar."}), 409
    return jsonify({"message": {"Approved": "Request disetujui", "Rejected": "Request ditolak", "Done": "Request selesai"}[status]})


@rekapin_bp.route("/api/request/setujui-terpilih", methods=["POST"])
@login_required
@izin("RK_REQUEST", "setujui")
def api_request_setujui_terpilih():
    ids = {int(x) for x in (request.form.get("ids") or "").split(",") if x.strip().isdigit()}
    n = sum(1 for i in ids if db.request_dalam_cakupan(i, current_user.id) and db.ubah_status(i, "Approved", "", current_user.id))
    if not n:
        return jsonify({"error": "Tidak ada request terpilih yang masih menunggu"}), 400
    return jsonify({"message": f"{n} request disetujui"})


# ===== Harga CPO & Kernel (dbo.DailyPrice) =====
@rekapin_bp.route("/harga")
@login_required
@lihat_halaman("RK_HARGA")
def halaman_harga():
    return _halaman("harga", "RK_HARGA", company=_company_harga(current_user.id),
                    hak={a: boleh("RK_HARGA", a) for a in ("tambah", "ubah", "hapus")})


@rekapin_bp.route("/api/harga")
@login_required
@izin("RK_HARGA", "lihat")
def api_harga():
    kode = [c["id_company"] for c in _company_harga(current_user.id)]
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
    if kode not in {c["id_company"] for c in _company_harga(current_user.id)}:
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
    company = _company_harga(current_user.id)
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
