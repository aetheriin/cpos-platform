"""Panggilan SP Kas & Bank (KAS_BANK_SP; SQL di backend/analytics/database/kas_bank_sp.sql).

SP menjalankan aturan ledger bank ERP (USP_FI_BankAccounts_QueryHistory) sekali per perusahaan untuk semua rekening, bukan per rekening.
Saldo awal yang berat dipisah: saldo_awal() (@Bagian SALDO) per 1 Januari, lalu ambil_perusahaan() (@Bagian MUTASI) hanya sejak tanggal itu."""
import pandas as pd

from inti import konfigurasi


def _sp(cur, comp, bagian, mulai, akhir, kode=(), akun=()):
    """Hasil SP sebagai DataFrame. mulai dan akhir: tanggal, akhir ikut dihitung."""
    cur.execute(f"EXEC {konfigurasi.KAS_BANK_SP} ?, ?, ?, ?, ?, ?", comp, bagian, pd.Timestamp(mulai).date(), pd.Timestamp(akhir).date(),
                "|".join(kode), "|".join(akun))
    while cur.description is None:
        if not cur.nextset():
            return pd.DataFrame()
    return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description])


def ambil_giro(cur, comp, mulai, akhir, akun_giro, kode_rekening):
    """Jasa giro satu perusahaan, mulai sampai akhir, dengan aturan SP_GET_GIROTRANSACTION."""
    d = _sp(cur, comp, "GIRO", mulai, akhir, kode_rekening, akun_giro)
    if d.empty:
        return d
    d["VOUCHERDATE"] = pd.to_datetime(d["VOUCHERDATE"])
    return d.assign(COMPID=comp, PERIODE=d["VOUCHERDATE"].dt.strftime("%Y%m"))


def ambil_kurs_voucher(cur, comp, mulai, akhir):
    """[(tanggal, kode mata uang, kurs, jumlah voucher)] dari voucher rekening valas, mulai sampai akhir. Kurs yang sama dengan master
    CO_ExchangeRate dibuang di SP: itu kurs bawaan lama yang tidak diganti saat voucher dibuat."""
    return list(_sp(cur, comp, "KURS", mulai, akhir).itertuples(index=False, name=None))


def saldo_awal(cur, comp, tanggal, kode_rekening):
    """{kode rekening: saldo sebelum `tanggal`} seperti baris Beginning Balance ledger ERP. Lambat: membaca seluruh riwayat."""
    d = _sp(cur, comp, "SALDO", tanggal, tanggal, kode_rekening)
    return {str(k).strip(): float(v) for k, v in zip(d.get("BankAccountCode", []), d.get("Amount", []))}


def ambil_perusahaan(cur, comp, mulai, akhir, kode_rekening, awal):
    """Mutasi semua rekening `kode_rekening` satu perusahaan dari mulai sampai akhir, dengan kolom seperti SP_GET_BANKDAILYDETAILS
    (baris saldo awal: IsOB = 1, DocumentNo = 'Beginning Balance', tanggal = mulai). `awal` = {kode: saldo sebelum mulai} dari saldo_awal()."""
    trans = _sp(cur, comp, "MUTASI", mulai, akhir, kode_rekening)
    if trans.empty:
        trans = pd.DataFrame(columns=["BankAccountCode", "BankName", "DocumentDate", "DocumentDateTime", "DocumentNo", "DocumentTypeID",
                                      "AssociateType", "AssociateName", "Amount", "Remarks", "VoucherCreateBy", "PriorityIndex"])
    trans["BankAccountCode"] = trans["BankAccountCode"].astype(str).str.strip()
    nama = dict(zip(trans["BankAccountCode"], trans["BankName"]))
    ob = pd.DataFrame([(k, nama.get(k, k), v) for k, v in awal.items() if k in kode_rekening and v],
                      columns=["BankAccountCode", "BankName", "Amount"])
    ob = ob.assign(DocumentDate=pd.Timestamp(mulai), DocumentDateTime=pd.Timestamp(mulai), DocumentNo="Beginning Balance", DocumentTypeID=None,
                   AssociateType=None, AssociateName=None, Remarks="", VoucherCreateBy=None, PriorityIndex=0)
    d = pd.concat([ob.assign(IsOB=True), trans.assign(IsOB=False)], ignore_index=True)
    d = d[d["BankAccountCode"].isin(kode_rekening)]
    d["COMPANYID"] = comp
    return d.drop(columns=["PriorityIndex"]).reset_index(drop=True)
