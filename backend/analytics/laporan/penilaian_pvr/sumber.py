"""Laporan Penilaian PVR: skor pembuat PVR menurut kategori (Check Number) dan bobotnya, sama dengan Excel Penilaian PVR.

Data mentah dari SP PENILAIAN_PVR_SP (Main.dbo.PENILAIAN_PVR, SQL-nya di backend/database/penilaian_pvr_sp.sql), dipanggil per perusahaan
bersamaan: item PVR pada periode itu, dan riwayat Check Number per supplier. Bobot dari tabel Bobot_PVR. Di sini: nomor dokumen (ItemRef),
nama supplier, Check Number kosong diisi yang paling sering dipakai supplier itu (seri: yang terakhir dipakai), kategori, dan bobot.
Aturan hitung: kategori Angkutan (termasuk Angkutan Penjualan) dinilai per baris item, kategori lain cukup sekali per PVR.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

SUMBER = konfigurasi.SUMBER_LAPORAN
TABEL_BOBOT = konfigurasi.PVR_TABEL_BOBOT
ANGKUTAN = "Angkutan"
_SEBUTAN_ANGKUTAN = {"angkutan", "angkutan penjualan"}   # disatukan jadi satu kategori
KOSONG = "(kosong)"

def ambil_sp(mulai, akhir, bagian, lokasi=None, kendali=None):
    """Satu bagian SP Penilaian PVR ('ITEM' atau 'CEK') untuk semua perusahaan, kolom __comp = CompID."""
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    tgl = (mulai.isoformat(), akhir.isoformat()) if bagian == "ITEM" else (None, None)
    d = per_perusahaan([l[0] for l in lokasi], get_connection, f"EXEC {konfigurasi.PENILAIAN_PVR_SP} ?, ?, ?, ?",
                       lambda comp: (comp, *tgl, bagian), kendali, boleh_kosong=True, tandai=True)
    return d.drop(columns=["CompID"], errors="ignore")


_REF_DOKUMEN = {"PurchaseNumber": ("PI", "PO", "PR"), "NoteNumber": ("PN", "PD", "PUK"), "TicketNo": ("TV", "BT", "BTP")}


def _kosong_jadi_na(seri):
    t = seri.astype("string").str.strip()
    return t.where(t != "")


def cek_supplier(cek):
    """{(perusahaan, AssociateID): Check Number} yang paling sering dipakai supplier itu; seri: yang terakhir dipakai."""
    if cek.empty:
        return {}
    c = cek.assign(Jumlah=pd.to_numeric(cek["Jumlah"], errors="coerce"), Terakhir=pd.to_datetime(cek["Terakhir"], errors="coerce"))
    c = c.sort_values(["Jumlah", "Terakhir"], ascending=False, kind="stable").drop_duplicates(["__comp", "AssociateID"])
    return {(k, int(a)): str(n).strip() for k, a, n in zip(c["__comp"], c["AssociateID"], c["CheckNo"]) if pd.notna(a)}


def rakit(item, cek):
    """Data mentah SP jadi bentuk yang dibaca bersihkan(): ItemRef, CheckNumber + sumbernya, SupplierName, RefType."""
    if item.empty:
        return pd.DataFrame(columns=["__comp", "VoucherDate", "VoucherNo", "ItemRef", "CheckNumber", "CheckNoSource", "ItemAmountPaid",
                                     "CreatedBy", "SupplierName", "RefType", "Urut"])
    jenis = item["ItemType"].fillna("").astype(str).str.strip()
    # ItemRef: OBNumber, lalu nomor dokumen asal menurut jenis item, lalu Remarks
    dok = pd.Series(pd.NA, index=item.index, dtype="string")
    for kolom, jenis_ini in _REF_DOKUMEN.items():
        dok = dok.mask(jenis.isin(jenis_ini), item[kolom].astype("string"))
    ref = _kosong_jadi_na(item["OBNumber"]).fillna(dok).fillna(item["Remarks"].astype("string"))
    # Check Number: yang tertulis di PVR; kalau kosong, yang paling sering dipakai supplier itu
    asli = _kosong_jadi_na(item["CheckNo"])
    peta = cek_supplier(cek)
    histori = pd.Series([peta.get((k, int(a))) if pd.notna(a) else None for k, a in zip(item["__comp"], item["AssociateID"])],
                        index=item.index, dtype="string")
    histori = histori.where(asli.isna())
    sumber = pd.Series("Kosong", index=item.index).mask(histori.notna(), "Histori Supplier").mask(asli.notna(), "Asli")
    return pd.DataFrame({
        "__comp": item["__comp"],
        "VoucherDate": pd.to_datetime(item["VoucherDate"], errors="coerce").dt.normalize(),
        "VoucherNo": item["VoucherNo"],
        "Urut": pd.to_numeric(item["VoucherItemID"], errors="coerce"),
        "ItemRef": ref,
        "CheckNumber": asli.fillna(histori),
        "CheckNoSource": sumber,
        "ItemAmountPaid": item["AmountPaid"],
        "CreatedBy": item["CreatedBy"],
        "SupplierName": item["SupplierName"].astype("string").fillna(_kosong_jadi_na(item["AssociateName"])),
        "RefType": item["ItemType"],
    })


def ambil_bobot(tabel=TABEL_BOBOT):
    """[(kategori, bobot)] dari tabel bobot."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT Kategori, Bobot FROM {tabel}")
        return [(str(k).strip(), float(b)) for k, b in cur.fetchall() if k is not None and b is not None]
    finally:
        conn.close()


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang."""
    m, a = date.fromisoformat(mulai), date.fromisoformat(akhir)
    with ThreadPoolExecutor(max_workers=2) as pool:   # item dan riwayat Check Number diambil bersamaan
        t_item = pool.submit(ambil_sp, m, a, "ITEM", None, kendali)
        t_cek = pool.submit(ambil_sp, m, a, "CEK", None, kendali)
        raw = rakit(t_item.result(), t_cek.result())
    bobot = ambil_bobot()
    if kendali:
        kendali.periksa()
    d = bersihkan(raw, bobot)
    return d, {"baris_dinilai": len(d)}


def _teks(seri):
    return seri.fillna("").astype(str).str.strip()


def peta_kategori(bobot):
    """{huruf kecil: (nama kategori, bobot)}; Angkutan Penjualan dan Angkutan jadi satu kategori Angkutan."""
    peta = {}
    for nama, b in bobot:
        kunci = nama.casefold()
        peta[kunci] = (ANGKUTAN, b) if kunci in _SEBUTAN_ANGKUTAN else (nama, b)
    return peta


def bersihkan(raw, bobot):
    """Satu baris per hal yang dinilai: tiap item untuk Angkutan, satu baris (item pertama) per PVR untuk kategori lain."""
    if raw.empty:
        return pd.DataFrame(columns=["comp", "tanggal", "pvr_number", "item_ref", "kategori", "check_asli", "sumber_kategori", "jumlah",
                                     "pembuat", "supplier", "jenis_ref", "bobot", "item_pvr"])
    peta = peta_kategori(bobot)
    cek = _teks(raw["CheckNumber"])
    # Query PV tidak punya CheckNoSource (tanpa isian dari histori supplier) dan menamai jenis ref "Source"
    asal = _teks(raw["CheckNoSource"]) if "CheckNoSource" in raw.columns else cek.map(lambda c: "Asli" if c else "Kosong")
    jenis_ref = raw["RefType"] if "RefType" in raw.columns else raw["Source"]
    kategori = cek.map(lambda c: peta.get(c.casefold(), (ANGKUTAN if c.casefold() in _SEBUTAN_ANGKUTAN else c.title(), None))[0] if c else KOSONG)
    d = pd.DataFrame({
        "comp": _teks(raw["__comp"]),
        "tanggal": pd.to_datetime(raw["VoucherDate"], errors="coerce").dt.normalize(),
        "pvr_number": _teks(raw["VoucherNo"]),
        "item_ref": _teks(raw["ItemRef"]),
        "kategori": kategori,
        "check_asli": cek,
        "sumber_kategori": asal,
        "jumlah": pd.to_numeric(raw["ItemAmountPaid"], errors="coerce"),
        "pembuat": _teks(raw["CreatedBy"]).str.split().str.join(" ").str.title().replace("", KOSONG),
        "supplier": _teks(raw["SupplierName"]),
        "jenis_ref": _teks(jenis_ref),
    })
    if "Urut" in raw.columns:   # item pertama per PVR = yang diinput paling awal (VoucherItemID), supaya hasilnya tetap tiap kali dimuat
        d = d.loc[pd.to_numeric(raw["Urut"], errors="coerce").sort_values(kind="stable").index]
    d = d[d["tanggal"].notna() & (d["pvr_number"] != "")]
    d["bobot"] = cek.loc[d.index].map(lambda c: peta.get(c.casefold(), (None, 0.0))[1]).astype(float)
    d["item_pvr"] = d.groupby(["comp", "pvr_number"])["pvr_number"].transform("size")
    angkutan = d["kategori"] == ANGKUTAN
    d = pd.concat([d[angkutan], d[~angkutan].drop_duplicates(["comp", "pvr_number"])]).sort_values(["tanggal", "pvr_number"], kind="stable")
    return d.reset_index(drop=True)
