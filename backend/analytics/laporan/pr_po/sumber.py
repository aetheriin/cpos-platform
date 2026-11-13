"""Laporan PR/PO: ambil data dari stored procedure dan bersihkan (kolom turunan, PO ganda, kategori, buyer)."""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from inti import kategori, konfigurasi
from inti.banding import jendela_sebelumnya
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan
from inti.umur import kategori_umur

from .. import harga_po

SP_NAME = konfigurasi.SP_PR_PO
SUMBER = konfigurasi.SUMBER_LAPORAN
SEMUA_STATUS = konfigurasi.SP_STATUS


def ambil_data(tgl_mulai, tgl_akhir, perusahaan=None, kendali=None):
    """tgl_mulai dan tgl_akhir: 'YYYYMMDD', tanggal PR dibuat."""
    if perusahaan is None:
        perusahaan = daftar_perusahaan(SUMBER)
    return per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?, ?, ?, ?",
                          lambda comp: (comp, SUMBER, tgl_mulai, tgl_akhir, SEMUA_STATUS), kendali)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Periode sebelumnya ikut diambil untuk pembanding KPI, ditandai kolom `lalu`."""
    mulai_lalu, _ = jendela_sebelumnya(mulai, akhir)
    # harga PO (tabel detail) diambil bersamaan dengan SP
    with ThreadPoolExecutor(max_workers=2) as pool:
        t_harga = pool.submit(harga_po.ambil, harga_po.mulai_po(mulai_lalu), kendali)
        raw = ambil_data(mulai_lalu.strftime("%Y%m%d"), akhir.replace("-", ""), kendali=kendali)
        harga = t_harga.result()
    if kendali:
        kendali.periksa()
    df = harga_po.tempel_pr(bersihkan(raw), harga)
    df["lalu"] = df["pr_date"] < pd.Timestamp(mulai)
    return df, dict(df.attrs.get("catatan", {}), baris_sp=int((~df["lalu"]).sum()))


def _tanggal(seri):
    teks = seri.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(teks, format="%Y%m%d", errors="coerce")


def _awalan(nomor):
    """Awalan nomor dokumen, mis. 'SJN' dari 'SJN/PO/HO/2609/1208'. Awalan PO selalu sama dengan perusahaan PR-nya."""
    return str(nomor).strip().split("/")[0].strip().upper()


def _banyak_po(teks):
    """Lebih dari satu nomor PO yang berbeda di sel PONUMBER."""
    return len({t.strip() for t in str(teks).split(",") if t.strip()}) > 1


def _bagian(mentah, i, n):
    """Ambil bagian ke-i dari sel yang berisi daftar PO dipisah koma.
    Nama supplier boleh mengandung koma ("CO., LTD"), jadi sel hanya dipecah kalau
    jumlah bagiannya sama dengan jumlah PO. Kalau tidak sama, isinya dipakai utuh."""
    mentah = mentah.strip()
    if n <= 1:
        return mentah
    bagian = [b.strip() for b in mentah.split(",")]
    return bagian[i] if len(bagian) == n else mentah


def bersihkan(raw):
    """Susun kolom turunan dan pecah PO ganda jadi satu baris per PO. Semua buyer dipertahankan."""
    d = pd.DataFrame({
        "comp": raw["COMPID"].astype(str),
        "line": raw["COMPID"].astype(str) + raw["PRDETAILID"].astype(str),
        "pr_date": _tanggal(raw["CREATEDDATE"]),
        "po_tgl": raw["POCREATEDATE"].fillna("").astype(str),
        "po_buyer": raw["POBY"].fillna("").astype(str),
        "category": raw["CATEGORY"],
        "partial": raw["PONUMBER"].fillna("").map(_banyak_po).map({True: "Y", False: "N"}),
        "qtyout": pd.to_numeric(raw["QTYOUT"], errors="coerce").fillna(0),
        "aging": raw["AGING"].fillna("").astype(str).str.strip(),
        "prnumber": raw["PRNUMBER"].fillna("").astype(str).str.strip(),
        "approve_by": raw["APPROVEBY"].fillna("").astype(str).str.strip(),
        "approve_date": _tanggal(raw["APPROVEDATE"].fillna("")),
        "itemcode": raw["ITEMCODE"].fillna("").astype(str).str.strip(),
        "itemname": raw["ITEMNAME"].fillna("").astype(str).str.strip(),
        "uom": raw["UOMNAME"].fillna("").astype(str).str.strip(),
        "itemtype": raw["ITEMTYPE"].fillna("").astype(str).str.strip(),
        "qtyreq": pd.to_numeric(raw["QTYREQ"], errors="coerce"),
        "qtyorder": pd.to_numeric(raw["QTYORDER"], errors="coerce"),
        "po_nomor": raw["PONUMBER"].fillna("").astype(str),
        "sup_kode": raw["SUPPLIERCODE"].fillna("").astype(str),
        "sup_nama": raw["SUPPLIERNAME"].fillna("").astype(str),
    })

    d["umur"] = d["aging"].map(kategori_umur)

    kat, catatan = kategori.petakan_seri(d["comp"], d["category"])
    d["category"] = kat.fillna("(kosong)").astype(str)

    lengkap = raw["ISCOMPLETE"].fillna(False).astype(bool)
    void = raw["ISVOID"].fillna(False).astype(bool)
    close = raw["ISCLOSE"].fillna(False).astype(bool)
    open_ = raw["ISOPEN"].fillna(False).astype(bool)
    d["status"] = "Tidak diketahui"
    # urutan penting: Completed menang atas Void/Closed
    d.loc[open_, "status"] = "Open"
    d.loc[close, "status"] = "Closed"
    d.loc[void, "status"] = "Void"
    d.loc[lengkap, "status"] = "Completed"

    # Pecah PO ganda ("20260925,20260923" dan "Elsa,Elsa") jadi satu baris per PO.
    # Nomor PO, kode supplier, dan nama supplier ikut dipecah sesuai urutan yang sama.
    # Pengaman: PO yang awalannya bukan perusahaan PR-nya (salah tautan dari SP) diabaikan.
    hasil, salah, contoh = [], 0, []
    for r in d.itertuples(index=False):
        tgl = [t.strip() for t in r.po_tgl.split(",") if t.strip()] or [""]
        buyer = [b.strip() for b in r.po_buyer.split(",")]
        nomor = [t.strip() for t in r.po_nomor.split(",") if t.strip()]
        n = len(tgl)
        milik = r.comp.upper()
        sah = []
        for i in range(n):
            if len(nomor) == n:
                lain = _awalan(nomor[i]) != milik
            else:  # tidak bisa disejajarkan: dianggap salah hanya kalau semua nomor milik perusahaan lain
                lain = bool(nomor) and all(_awalan(x) != milik for x in nomor)
            if lain:
                salah += 1
                if len(contoh) < 5:
                    contoh.append(f"{r.prnumber} -> {nomor[i] if len(nomor) == n else nomor[0]}")
            else:
                sah.append(i)
        if sah:
            unik = {nomor[i] for i in sah} if len(nomor) == n else set(nomor)
            partial = "Y" if len(unik) > 1 else "N"
            for i in sah:
                b = buyer[i] if i < len(buyer) else buyer[0]
                hasil.append((
                    r.comp, r.line, r.pr_date, tgl[i], r.status, r.category, b, r.qtyout, r.aging, partial,
                    r.prnumber, r.approve_by, r.approve_date, r.itemcode, r.itemname, r.uom, r.itemtype,
                    r.qtyreq, r.qtyorder,
                    _bagian(r.po_nomor, i, n), _bagian(r.sup_kode, i, n), _bagian(r.sup_nama, i, n), r.umur,
                ))
        else:  # semua PO-nya salah tautan: perlakukan seperti PR yang belum punya PO
            hasil.append((
                r.comp, r.line, r.pr_date, "", r.status, r.category, "", r.qtyout, r.aging, "N",
                r.prnumber, r.approve_by, r.approve_date, r.itemcode, r.itemname, r.uom, r.itemtype,
                r.qtyreq, r.qtyorder, "", "", "", r.umur,
            ))
    out = pd.DataFrame(
        hasil,
        columns=[
            "comp", "line", "pr_date", "po_date", "status", "category", "buyer", "qtyout", "aging", "partial",
            "prnumber", "approve_by", "approve_date", "itemcode", "itemname", "uom", "itemtype",
            "qtyreq", "qtyorder", "po_number", "supplier_code", "supplier_name", "umur",
        ],
    )

    out["po_date"] = _tanggal(out["po_date"])
    out["buyer"] = out["buyer"].str.strip().str.split().str.join(" ").str.title().replace("", "(kosong)")
    # PO yang sama (nomor dan tanggal sama) pada satu baris PR hanya satu baris. Yang tersisa adalah split yang sebenarnya: PO berbeda.
    out = out.drop_duplicates(["line", "po_number", "po_date"]).reset_index(drop=True)
    catatan = dict(catatan, po_beda_perusahaan=salah, po_beda_perusahaan_contoh=contoh)
    if salah:
        catatan["peringatan"] = [
            f"{salah} nomor PO milik perusahaan lain yang tertaut pada PR diabaikan (contoh: {'; '.join(contoh[:3])})."
        ]
    out.attrs["catatan"] = catatan
    return out
