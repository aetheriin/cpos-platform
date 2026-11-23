import os
import uuid

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import UPLOAD_FOLDER
from utils.db_utils import get_connection, query as _query
from utils.hak_akses import boleh, halaman as lihat_halaman, izin

# Alamatnya sama dengan Url menu FM_IT_HELPDESK di dbo.Menu, jadi menu sidebar langsung membuka halaman ini
helpdesk_bp = Blueprint("helpdesk", __name__, url_prefix="/halaman/FM_IT_HELPDESK")

KODE = "FM_IT_HELPDESK"          # kode menu / hak akses IT Helpdesk (sesuai halaman placeholder)
ALLOWED_EXT = {"png", "jpg", "jpeg", "pdf", "xls", "xlsx", "csv"}
MAX_FILE_MB = 10
STATUSES = ["Open", "In Progress", "Done", "Rejected"]


# ---------------------------------------------------------------- user & hak akses
def user_id():
    """ID akun login (dipakai untuk membatasi user biasa hanya melihat tiketnya sendiri)."""
    return str(current_user.id)


def user_name():
    """Nama yang ditampilkan di Teknisi / riwayat / lampiran.
    SESUAIKAN urutan atribut dengan model user CPOS jika perlu."""
    for attr in ("nama_lengkap", "nama", "full_name", "name", "username"):
        v = getattr(current_user, attr, None)
        if v:
            return str(v)
    return str(current_user.id)


def is_it():
    """Tim IT = akun yang punya izin 'ubah' pada menu IT Helpdesk."""
    return boleh(KODE, "ubah")


def upload_dir():
    # Jika folder uploads CPOS dilayani publik, ganti ke folder di luar static lewat config ini
    return current_app.config.get("HELPDESK_UPLOAD_DIR") or os.path.join(UPLOAD_FOLDER, "helpdesk")


# ---------------------------------------------------------------- database
# Memakai koneksi SQL Server bawaan CPOS (utils.db_utils). Tabel helpdesk harus ada di database yang sama.
def query(sql, params=(), one=False):
    rows = list(_query(sql, *params))
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    conn = get_connection()
    try:
        conn.cursor().execute(sql, *params)
        conn.commit()
    finally:
        conn.close()


def get_request_or_404(request_id):
    row = query("SELECT * FROM dbo.HelpdeskRequest WHERE RequestId = ?",
                (request_id,), one=True)
    if not row:
        abort(404)
    if not is_it() and row["CreatedBy"] != user_id():
        abort(403)
    return row


def save_attachments(request_id, files):
    """Simpan file ke disk + catat path-nya di database. Return jumlah file tersimpan."""
    saved = 0
    folder = os.path.join(upload_dir(), str(request_id))
    os.makedirs(folder, exist_ok=True)

    for f in files:
        if not f or not f.filename:
            continue
        original = secure_filename(f.filename)
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in ALLOWED_EXT:
            flash(f"File '{f.filename}' ditolak: ekstensi tidak diizinkan.", "warning")
            continue

        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_MB * 1024 * 1024:
            flash(f"File '{f.filename}' ditolak: maksimal {MAX_FILE_MB} MB.", "warning")
            continue

        stored_name = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(folder, stored_name))
        execute(
            "INSERT INTO dbo.HelpdeskAttachment "
            "(RequestId, FileName, FilePath, ContentType, FileSizeKB, UploadedBy) "
            "VALUES (?,?,?,?,?,?)",
            (request_id, original, os.path.join(str(request_id), stored_name),
             f.mimetype, max(1, size // 1024), user_name()))
        saved += 1
    return saved


# ----------------------------------------------------------------- routes
@helpdesk_bp.route("", strict_slashes=False)
@login_required
@lihat_halaman(KODE)
def index():
    status = request.args.get("status", "")
    site = request.args.get("site", "")
    q = request.args.get("q", "").strip()
    where, params = [], []
    if not is_it():
        where.append("r.CreatedBy = ?")
        params.append(user_id())
    if status in STATUSES:
        where.append("r.Status = ?")
        params.append(status)
    if site:
        where.append("r.SiteCode = ?")
        params.append(site)
    if q:
        where.append("(r.TicketNo LIKE ? OR r.RequestTitle LIKE ? "
                     "OR r.RequesterName LIKE ? OR r.PersonInCharge LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    requests_ = query(
        "SELECT TOP 200 r.RequestId, r.TicketNo, r.SiteCode, r.RequestTitle, "
        "r.RequesterName, r.PersonInCharge, r.Status, r.AssignedTo, r.CreatedAt "
        f"FROM dbo.HelpdeskRequest r {clause} ORDER BY r.CreatedAt DESC", params)

    sites = query("SELECT SiteCode FROM dbo.HelpdeskSite WHERE IsActive = 1 ORDER BY SiteCode")
    # Ringkasan: tim IT melihat semua tiket, user biasa hanya tiketnya sendiri
    if is_it():
        summary = query("SELECT * FROM dbo.vw_HelpdeskSummary", one=True)
    else:
        summary = query(
            "SELECT COUNT(*) AS TotalRequest, "
            "SUM(CASE WHEN Status='Open' THEN 1 ELSE 0 END) AS TotalOpen, "
            "SUM(CASE WHEN Status='In Progress' THEN 1 ELSE 0 END) AS TotalInProgress, "
            "SUM(CASE WHEN Status='Done' THEN 1 ELSE 0 END) AS TotalDone "
            "FROM dbo.HelpdeskRequest WHERE CreatedBy = ?", (user_id(),), one=True)

    return render_template("helpdesk/index.html", halaman="it_helpdesk", kode_aktif=KODE,
                           requests=requests_, summary=summary, status=status, site=site, q=q,
                           sites=sites, statuses=STATUSES, is_it=is_it(),
                           boleh_tambah=boleh(KODE, "tambah"))


@helpdesk_bp.route("/new", methods=["GET", "POST"])
@login_required
@lihat_halaman(KODE)
def new_request():
    if not boleh(KODE, "tambah"):          # halaman HTML: tolak dengan 403, bukan JSON
        abort(403)
    sites = query("SELECT SiteCode, SiteName FROM dbo.HelpdeskSite "
                  "WHERE IsActive = 1 ORDER BY SiteCode")
    base = dict(halaman="it_helpdesk", kode_aktif=KODE, sites=sites)

    if request.method == "POST":
        site_code = request.form.get("site_code", "").strip()
        requester = request.form.get("requester_name", "").strip()
        title = request.form.get("request_title", "").strip()
        chronology = request.form.get("chronology", "").strip()
        pic = request.form.get("person_in_charge", "").strip()

        valid_sites = {x["SiteCode"] for x in sites}
        if not (site_code in valid_sites and requester and title and chronology and pic):
            flash("Site, nama pembuat request, request, kronologi, dan "
                  "penanggung jawab wajib diisi.", "danger")
            return render_template("helpdesk/new.html", form=request.form, **base)

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("EXEC dbo.sp_Helpdesk_Create ?,?,?,?,?,?",
                        site_code, title, chronology, requester, pic, user_id())
            row = cur.fetchone()
            conn.commit()
            request_id, ticket_no = row[0], row[1]
        finally:
            conn.close()

        save_attachments(request_id, request.files.getlist("attachments"))
        flash(f"Request berhasil dibuat dengan nomor tiket {ticket_no}.", "success")
        return redirect(url_for("helpdesk.detail", request_id=request_id))

    return render_template("helpdesk/new.html", form={}, **base)


@helpdesk_bp.route("/<int:request_id>")
@login_required
@lihat_halaman(KODE)
def detail(request_id):
    req = get_request_or_404(request_id)
    attachments = query("SELECT * FROM dbo.HelpdeskAttachment "
                        "WHERE RequestId = ? ORDER BY UploadedAt", (request_id,))
    logs = query("SELECT * FROM dbo.HelpdeskStatusLog "
                 "WHERE RequestId = ? ORDER BY ChangedAt DESC", (request_id,))
    return render_template("helpdesk/detail.html", halaman="it_helpdesk", kode_aktif=KODE,
                           req=req, attachments=attachments, logs=logs,
                           statuses=STATUSES, is_it=is_it())


@helpdesk_bp.route("/<int:request_id>/upload", methods=["POST"])
@login_required
@izin(KODE, "tambah")
def upload(request_id):
    get_request_or_404(request_id)
    n = save_attachments(request_id, request.files.getlist("attachments"))
    if n:
        flash(f"{n} lampiran ditambahkan.", "success")
    return redirect(url_for("helpdesk.detail", request_id=request_id))


@helpdesk_bp.route("/<int:request_id>/status", methods=["POST"])
@login_required
@izin(KODE, "ubah")
def update_status(request_id):
    get_request_or_404(request_id)

    new_status = request.form.get("status")
    note = request.form.get("note", "").strip() or None
    resolution = request.form.get("resolution_note", "").strip() or None

    if new_status not in STATUSES:
        abort(400)
    if new_status == "Done" and not resolution:
        flash("Catatan penyelesaian wajib diisi saat menandai Done.", "danger")
        return redirect(url_for("helpdesk.detail", request_id=request_id))

    execute("EXEC dbo.sp_Helpdesk_UpdateStatus ?,?,?,?,?",
            (request_id, new_status, user_name(), note, resolution))
    flash(f"Status diubah menjadi {new_status}.", "success")
    return redirect(url_for("helpdesk.detail", request_id=request_id))


@helpdesk_bp.route("/file/<int:attachment_id>")
@login_required
@izin(KODE, "lihat")
def download(attachment_id):
    att = query("SELECT * FROM dbo.HelpdeskAttachment WHERE AttachmentId = ?",
                (attachment_id,), one=True)
    if not att:
        abort(404)
    get_request_or_404(att["RequestId"])  # cek hak akses ke tiketnya

    dasar = os.path.realpath(upload_dir())
    path = os.path.realpath(os.path.join(dasar, att["FilePath"]))
    try:
        aman = os.path.commonpath([dasar, path]) == dasar   # cegah path keluar dari folder
    except ValueError:
        aman = False
    if not aman or not os.path.isfile(path):
        abort(404)
    return send_from_directory(os.path.dirname(path), os.path.basename(path),
                               as_attachment=True, download_name=att["FileName"])
