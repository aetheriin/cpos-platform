"""Laporan PV KPI: skor kasir pembuat PV menurut kategori (Check Number) dan bobotnya, sama dengan Excel Penilaian PV.

Aturan hitung dan pembersihan sama dengan PVR KPI (laporan.penilaian_pvr.sumber); yang beda hanya query (tabel FI_ARAP, IsAR = 0)
dan tabel bobot (Bobot_PV). Satu baris per item PV, ditambah item lain-lain dan potongan PPh.
"""
from datetime import date

from inti import konfigurasi

from ..penilaian_pvr.sumber import ambil_bobot, ambil_data, bersihkan

# Query dari pengguna; {db}, {mulai}, dan {akhir} diisi per perusahaan.
_QUERY = """
    SELECT
        CAST(v.VoucherDate AS date)           AS VoucherDate,
        v.VoucherNo,
        d.ItemRef,
        v.CreatedBy,
        NULLIF(LTRIM(RTRIM(v.CheckNo)), '''') AS CheckNumber,
        d.Amount                              AS ItemAmountPaid,
        COALESCE(s.SupplierName,
                 NULLIF(v.AssociateName, ''''),
                 NULLIF(v.AnonymName, ''''))   AS SupplierName,
        d.Source
    FROM {db}.dbo.FI_ARAP v
    JOIN (
        SELECT
            i.VoucherID,
            COALESCE(
                CASE
                    WHEN i.ItemType IN (''PI'', ''PO'')          THEN p.PurchaseNumber
                    WHEN i.ItemType IN (''PN'', ''PD'', ''PUK'') THEN n.Number
                    WHEN i.ItemType IN (''TV'', ''BT'', ''BTP'') THEN t.TicketNo
                END,
                NULLIF(LTRIM(RTRIM(i.Remarks)), '''')
            )            AS ItemRef,
            i.AmountPaid AS Amount,
            i.ItemType   AS Source
        FROM {db}.dbo.FI_ARAPItems i
        LEFT JOIN {db}.dbo.AP_Purchases p
            ON p.PurchaseID = i.ItemID
           AND i.ItemType IN (''PI'', ''PO'')
        LEFT JOIN {db}.dbo.FI_ARAPNotes n
            ON n.ARAPNoteID = i.ItemID
           AND i.ItemType IN (''PN'', ''PD'', ''PUK'')
        LEFT JOIN {db}.dbo.PALM_Tickets t
            ON t.TicketID = i.ItemID
           AND i.ItemType IN (''TV'', ''BT'', ''BTP'')

        UNION ALL

        SELECT
            e.VoucherID,
            LTRIM(RTRIM(e.Description)),
            e.Amount,
            ''Others''
        FROM {db}.dbo.FI_ARAPExtraItems e

        UNION ALL

        SELECT
            x.VoucherID,
            ''Pot. PPh '' + ISNULL(pt.PPHTypeDescription, ''''),
            -ABS(x.DeductedPPh),
            ''PPh''
        FROM {db}.dbo.FI_ARAP x
        LEFT JOIN {db}.dbo.FI_PPhTypes pt
            ON pt.PPHTypeID = x.PPhTypeID
        WHERE ISNULL(x.DeductedPPh, 0) <> 0
    ) d
        ON d.VoucherID = v.VoucherID
    LEFT JOIN {db}.dbo.AP_Suppliers s
        ON s.SupplierID = v.AssociateID
    WHERE v.IsAR = 0
      AND ISNULL(v.Void, 0) = 0
      AND v.VoucherDate >= ''{mulai}'' AND v.VoucherDate < ''{akhir}''
"""


def isi_dari_histori(raw):
    """PV tanpa Check Number diberi Check Number yang paling sering dipakai supplier yang sama di perusahaan itu, seperti sheet
    MasterSupplier di Excel (dan histori supplier di query PVR). Hanya PV pada periode yang dimuat yang dipakai sebagai acuan."""
    raw = raw.copy()
    cek = raw["CheckNumber"].fillna("").astype(str).str.strip()
    ada = raw.assign(cek=cek, supplier=raw["SupplierName"].fillna("").astype(str).str.strip())
    ada = ada[(ada["cek"] != "") & (ada["supplier"] != "")].drop_duplicates(["__comp", "VoucherNo"])
    paling = ada.groupby(["__comp", "supplier"])["cek"].agg(lambda s: s.value_counts().index[0])
    kunci = list(zip(raw["__comp"], raw["SupplierName"].fillna("").astype(str).str.strip()))
    dari_histori = [paling.get(k, "") for k in kunci]
    kosong = cek == ""
    raw["CheckNoSource"] = "Asli"
    raw.loc[kosong, "CheckNumber"] = [v for v, k in zip(dari_histori, kosong) if k]
    raw.loc[kosong, "CheckNoSource"] = ["Histori Supplier" if v else "Kosong" for v, k in zip(dari_histori, kosong) if k]
    return raw


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang."""
    raw = ambil_data(date.fromisoformat(mulai), date.fromisoformat(akhir), kendali=kendali, query=_QUERY)
    bobot = ambil_bobot(konfigurasi.PV_TABEL_BOBOT)
    if kendali:
        kendali.periksa()
    d = bersihkan(isi_dari_histori(raw) if not raw.empty else raw, bobot)
    return d, {"baris_dinilai": len(d)}
