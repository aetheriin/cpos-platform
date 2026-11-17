"""Menu Kontrak & DO (role HO) + pencarian DO untuk Form Security."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from utils.hak_akses import lihat, MENU_KONTRAK, halaman as lihat_halaman
from utils import db_ascend

kontrak_bp = Blueprint("kontrak", __name__)

def _tgl(d):
    return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else d

def _angka(v):
    return float(v) if v is not None else None

def _json_do(d):
    return {**d, "tanggal_do": _tgl(d["tanggal_do"]), "berlaku_sampai": _tgl(d["berlaku_sampai"]),
            "tanggal_kontrak": _tgl(d["tanggal_kontrak"]), "created_at": _tgl(d["created_at"]),
            "qty_kg": _angka(d["qty_kg"]), "harga_per_kg": _angka(d["harga_per_kg"]), "realisasi_kg": _angka(d.get("realisasi_kg")),
            "angkutan": [{**a, "qty_kg": _angka(a["qty_kg"]), "ongkos_per_kg": _angka(a.get("ongkos_per_kg"))} for a in d["angkutan"]],
            "ppn": bool(d.get("ppn")), "harga_termasuk_ppn": bool(d.get("harga_termasuk_ppn"))}

def _json_kontrak(k):
    """Ubah tanggal dari hasil query Ascend agar siap dikirim sebagai JSON."""
    return {
        nama: _tgl(nilai) if hasattr(nilai, "strftime") else nilai
        for nama, nilai in k.items()
    }

@kontrak_bp.route("/kontrak")
@login_required
@lihat_halaman("KONTRAK_DO")
def kontrak_halaman():
    supplier_ascend = db_ascend.daftar_supplier_master_ascend()

    return render_template(
        "kontrak/kontrak.html",
        halaman="kontrak",
        boleh_ubah=False,

        # Pilihan Associate dari Ascend
        associate_produk_list=db_ascend.daftar_associate("Produk"),
        associate_tbs_list=db_ascend.daftar_associate("TBSLuar"),

        # Pilihan produk dari Ascend
        produk_ascend_list=db_ascend.daftar_produk_master_ascend(),
        produk_tbs_luar_list=db_ascend.daftar_produk_tbs_luar_ascend(),

        # Mill dan pengangkut Ascend
        mill_list=db_ascend.daftar_mill(),
        pengangkut_ascend_list=[
            s for s in supplier_ascend
            if s["is_transport"] or s["is_expedition"]
        ],

        # Nilai awal pajak dari data Ascend
        ppn_default_produk=0,
        ppn_default_tbs=11,
        pilihan_ppn=(0, 11),
        pilihan_pph23=(0, 2),
    )

@kontrak_bp.route("/api/kontrak/do")
@login_required
@lihat(*MENU_KONTRAK)
def do_daftar():
    return jsonify([
        _json_do(d)
        for d in db_ascend.daftar_kontrak_do_ascend(
            request.args.get("cari", "")
        )
    ])

@kontrak_bp.route("/api/kontrak/kontrak")
@login_required
@lihat(*MENU_KONTRAK)
def kontrak_daftar():
    return jsonify([
        _json_kontrak(k)
        for k in db_ascend.daftar_kontrak_ascend(
            request.args.get("cari", "")
        )
    ])
