"""Laporan PO/PI: ambil data dari SP dan bersihkan. PURCHASEID/NUMBER/DATE yang dipisah koma dipecah jadi satu baris per PI."""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from inti import kategori, konfigurasi
from inti.banding import jendela_sebelumnya
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan
from inti.umur import kategori_umur

from .. import harga_po

SP_NAME = konfigurasi.SP_PO_PI
SUMBER = konfigurasi.SUMBER_LAPORAN
SEMUA_STATUS = int(konfigurasi.SP_STATUS) if konfigurasi.SP_STATUS.isdigit() else konfigurasi.SP_STATUS


def ambil_data(tgl_mulai, tgl_akhir, perusahaan=None, kendali=None):
    """tgl_mulai dan tgl_akhir: 'YYYYMMDD', tanggal PO dibuat."""
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
    df = harga_po.tempel_po(bersihkan(raw), harga)
    df["lalu"] = df["cd"] < pd.Timestamp(mulai)
    return df, dict(df.attrs.get("catatan", {}), baris_sp=int((~df["lalu"]).sum()))


def _tanggal(seri):
    teks = seri.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(teks, format="%Y%m%d", errors="coerce")


def _bool(seri):
    """Bool dari bool, 'True'/'False', atau 1/0. Kosong dianggap False."""
    return seri.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0")).astype(bool)


def _awalan(nomor):
    """Awalan nomor dokumen, mis. 'YBS' dari 'YBS/PI/HO/2511/345'. PI selalu berawalan sama dengan perusahaan PO-nya."""
    return str(nomor).strip().split("/")[0].strip().upper()


def _daftar(teks):
    if teks is None or (not isinstance(teks, str) and pd.isna(teks)):
        return []
    return [t.strip() for t in str(teks).split(",")]


def bersihkan(raw):
    d = pd.DataFrame({
        "comp": raw["COMPID"].astype(str),
        "line": raw["COMPID"].astype(str) + raw["PODETAILID"].astype(str).str.replace(r"\.0$", "", regex=True),
        "po_number": raw["PONUMBER"].fillna("").astype(str).str.strip(),
        "po_date": _tanggal(raw["PODATE"]),
        "cd": _tanggal(raw["CREATEDDATE"]),
        "creator": raw["CREATEDBY"].fillna("").astype(str).str.strip().str.lower().str.capitalize().replace("", "(kosong)"),
        "itemcode": raw["ITEMCODE"].fillna("").astype(str).str.strip(),
        "itemname": raw["ITEMNAME"].fillna("").astype(str).str.strip(),
        "category": raw["CATEGORY"],
        "itemtype": raw["ITEMTYPE"].fillna("").astype(str).str.strip(),
        "uom": raw["UOMNAME"].fillna("").astype(str).str.strip(),
        "qtyordered": pd.to_numeric(raw["QTYORDERED"], errors="coerce"),
        "qtydelivered": pd.to_numeric(raw["QTYDELIVERED"], errors="coerce"),
        "qtyout": pd.to_numeric(raw["QTYOUT"], errors="coerce").fillna(0),
        "supplier_code": raw["SUPPLIERCODE"].fillna("").astype(str).str.strip(),
        "supplier_name": raw["SUPPLIERNAME"].fillna("").astype(str).str.strip(),
        "aging": raw["AGING"].fillna("").astype(str).str.strip(),
        "pi_nomor_mentah": raw["PURCHASENUMBER"],
        "pi_tgl_mentah": raw["PURCHASEDATE"],
    })

    kat, catatan = kategori.petakan_seri(d["comp"], d["category"])
    d["category"] = kat.fillna("(kosong)").astype(str)

    # Status: yang ditulis belakangan menimpa yang sebelumnya, jadi Void paling menentukan, lalu Completed, Closed, Open
    d["status"] = "Tidak diketahui"
    d.loc[_bool(raw["ISOPEN"]), "status"] = "Open"
    d.loc[_bool(raw["ISCLOSE"]) | _bool(raw["POISCLOSE"]), "status"] = "Closed"
    d.loc[_bool(raw["ISCOMPLETE"]), "status"] = "Completed"
    d.loc[_bool(raw["ISVOID"]), "status"] = "Void"
    # Aging dari SP dihitung dari tanggal order; yang benar dari Created Date. Label (COMPLETED, VOID, CLOSED) dibiarkan.
    hari = (pd.Timestamp.today().normalize() - d["cd"]).dt.days
    angka = pd.to_numeric(d["aging"], errors="coerce").notna() & hari.notna()
    d.loc[angka, "aging"] = hari[angka].astype(int).astype(str)
    d["umur"] = d["aging"].map(kategori_umur)

    # PARTIAL: PI lebih dari satu nomor yang berbeda (nomor sama yang tertulis dua kali dihitung satu)
    d["partial"] = d["pi_nomor_mentah"].map(lambda t: "Y" if len({x for x in _daftar(t) if x}) > 1 else "N")

    # Pecah daftar PI menjadi satu baris per PI (daftar yang lebih pendek diisi kosong, seperti List.Zip).
    # Pengaman: PI yang awalannya bukan perusahaan PO-nya (salah tautan dari SP) diabaikan.
    kolom_tetap = [c for c in d.columns if c not in ("pi_nomor_mentah", "pi_tgl_mentah")]
    ip, ic = kolom_tetap.index("partial"), kolom_tetap.index("comp")
    hasil, salah, contoh = [], 0, []
    for baris in d.to_dict("records"):
        nomor = _daftar(baris["pi_nomor_mentah"])
        tgl = _daftar(baris["pi_tgl_mentah"])
        n = max(len(nomor), len(tgl), 1)
        tetap = [baris[k] for k in kolom_tetap]
        milik = str(tetap[ic]).upper()
        sah = []
        for i in range(n):
            nm = nomor[i] if i < len(nomor) else ""
            if nm and _awalan(nm) != milik:
                salah += 1
                if len(contoh) < 5:
                    contoh.append(f"{baris['po_number']} -> {nm}")
            else:
                sah.append(i)
        if sah:
            tetap[ip] = "Y" if len({nomor[i] for i in sah if i < len(nomor) and nomor[i]}) > 1 else "N"
            for i in sah:
                hasil.append(tetap + [nomor[i] if i < len(nomor) else "", tgl[i] if i < len(tgl) else ""])
        else:  # semua PI-nya salah tautan: perlakukan seperti PO yang belum punya PI
            tetap[ip] = "N"
            hasil.append(tetap + ["", ""])
    out = pd.DataFrame(hasil, columns=kolom_tetap + ["pi_number", "pi_tgl"])
    out["pi_date"] = _tanggal(out["pi_tgl"].replace("", None))
    out = out.drop(columns="pi_tgl")

    catatan = dict(catatan, pi_beda_perusahaan=salah, pi_beda_perusahaan_contoh=contoh)
    if salah:
        catatan["peringatan"] = [
            f"{salah} nomor PI milik perusahaan lain yang tertaut pada PO diabaikan (contoh: {'; '.join(contoh[:3])})."
        ]
    out.attrs["catatan"] = catatan
    return out
