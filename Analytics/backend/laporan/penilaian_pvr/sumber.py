"""Laporan Penilaian PVR: skor pembuat PVR menurut kategori (Check Number) dan bobotnya, sama dengan Excel Penilaian PVR.

Data PVR diambil langsung lewat OPENQUERY ke database tiap perusahaan (server dan database dari tabel company), bobot dari tabel Bobot_PVR.
Aturan hitung: kategori Angkutan (termasuk Angkutan Penjualan) dinilai per baris item, kategori lain cukup sekali per PVR.
"""
from datetime import date, timedelta

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

from ..pi_pvr.sumber import _nama

SUMBER = konfigurasi.SUMBER_LAPORAN
TABEL_BOBOT = konfigurasi.PVR_TABEL_BOBOT
ANGKUTAN = "Angkutan"
_SEBUTAN_ANGKUTAN = {"angkutan", "angkutan penjualan"}   # disatukan jadi satu kategori
KOSONG = "(kosong)"

# Query dari pengguna; {db}, {mulai}, dan {akhir} diisi per perusahaan. Check Number kosong diisi Check Number yang paling sering dipakai supplier itu.
_QUERY = """
    SELECT
        CAST(v.VoucherDate AS date)          AS VoucherDate,
        v.VoucherNo,
        COALESCE(
            NULLIF(i.OBNumber, ''''),
            CASE
                WHEN i.ItemType IN (''PI'', ''PO'', ''PR'')  THEN p.PurchaseNumber
                WHEN i.ItemType IN (''PN'', ''PD'', ''PUK'') THEN n.Number
                WHEN i.ItemType IN (''TV'', ''BT'', ''BTP'') THEN t.TicketNo
            END,
            i.Remarks
        )                                    AS ItemRef,
        COALESCE(ck.CheckNo, h.CheckNo)      AS CheckNumber,
        CASE
            WHEN ck.CheckNo IS NOT NULL THEN ''Asli''
            WHEN h.CheckNo  IS NOT NULL THEN ''Histori Supplier''
            ELSE ''Kosong''
        END                                  AS CheckNoSource,
        i.AmountPaid                         AS ItemAmountPaid,
        v.CreatedBy,
        COALESCE(s.SupplierName, NULLIF(v.AssociateName, '''')) AS SupplierName,
        i.ItemType                           AS RefType
    FROM {db}.dbo.FI_APRequest v
    JOIN {db}.dbo.FI_APRequestItems i
        ON i.VoucherID = v.VoucherID
    CROSS APPLY (SELECT NULLIF(LTRIM(RTRIM(v.CheckNo)), '''') AS CheckNo) ck
    LEFT JOIN {db}.dbo.AP_Purchases p
        ON p.PurchaseID = i.ItemID
       AND i.ItemType IN (''PI'', ''PO'', ''PR'')   -- PR = Purchase Return
    LEFT JOIN {db}.dbo.FI_ARAPNotes n
        ON n.ARAPNoteID = i.ItemID
       AND i.ItemType IN (''PN'', ''PD'', ''PUK'')
    LEFT JOIN {db}.dbo.PALM_Tickets t
        ON t.TicketID = i.ItemID
       AND i.ItemType IN (''TV'', ''BT'', ''BTP'')
    LEFT JOIN {db}.dbo.AP_Suppliers s
        ON s.SupplierID = v.AssociateID
    LEFT JOIN (
        SELECT AssociateID, CheckNo
        FROM (
            SELECT
                AssociateID,
                LTRIM(RTRIM(CheckNo)) AS CheckNo,
                ROW_NUMBER() OVER (
                    PARTITION BY AssociateID
                    ORDER BY COUNT(*) DESC, MAX(VoucherDate) DESC
                ) AS rn
            FROM {db}.dbo.FI_APRequest
            WHERE NULLIF(LTRIM(RTRIM(CheckNo)), '''') IS NOT NULL
              AND ISNULL(Void, 0) = 0
            GROUP BY AssociateID, LTRIM(RTRIM(CheckNo))
        ) x
        WHERE rn = 1
    ) h
        ON h.AssociateID = v.AssociateID
       AND ck.CheckNo IS NULL
    WHERE v.VoucherDate >= ''{mulai}'' AND v.VoucherDate < ''{akhir}''
      AND ISNULL(v.Void, 0) = 0
"""


def perintah(lokasi, mulai, akhir, query=_QUERY):
    """lokasi: (nama, server, database). mulai dan akhir: date, akhir ikut dihitung."""
    comp, server, db = lokasi
    isi = query.format(db=_nama(db, "CompDataBase", comp), mulai=mulai.isoformat(), akhir=(akhir + timedelta(days=1)).isoformat())
    return f"SELECT * FROM OPENQUERY([{_nama(server, 'CompAddr', comp)}], '{isi}')"


def ambil_data(mulai, akhir, lokasi=None, kendali=None, query=_QUERY):
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    peta = {l[0]: l for l in lokasi}
    return per_perusahaan(list(peta), get_connection, lambda comp: perintah(peta[comp], mulai, akhir, query), lambda comp: (), kendali,
                          boleh_kosong=True, tandai=True)


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
    raw = ambil_data(date.fromisoformat(mulai), date.fromisoformat(akhir), kendali=kendali)
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
    d = d[d["tanggal"].notna() & (d["pvr_number"] != "")]
    d["bobot"] = cek.loc[d.index].map(lambda c: peta.get(c.casefold(), (None, 0.0))[1]).astype(float)
    d["item_pvr"] = d.groupby(["comp", "pvr_number"])["pvr_number"].transform("size")
    angkutan = d["kategori"] == ANGKUTAN
    d = pd.concat([d[angkutan], d[~angkutan].drop_duplicates(["comp", "pvr_number"])]).sort_values(["tanggal", "pvr_number"], kind="stable")
    return d.reset_index(drop=True)
