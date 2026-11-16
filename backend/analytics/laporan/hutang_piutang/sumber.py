"""Laporan Outstanding: hutang dan piutang belum lunas dari semua sumber yang dipakai ERP untuk PV/RV (SH_ARAPCalculations).

Data dari SP OUTSTANDING_SP (backend/database/outstanding_sp.sql), per perusahaan bersamaan; perusahaan tanpa server/database dilewati.
Di sini: potongan hutang (IsPositive = 0) bernilai negatif; PVR pending dan PV bertanggal setelah hari muat dihitung belum dibayar;
kurs memakai kurs dokumen ERP, kalau tidak ada urutan kurs laporan Cash Flow."""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

from . import pengadaan
from ..kas_bank import sumber as kas
from ..pi_pvr.sumber import _nama

SUMBER = konfigurasi.SUMBER_LAPORAN
log = logging.getLogger("dashboard")

# Status hutang, urut dari yang paling perlu ditindaklanjuti
BELUM_PVR, PV_SEBAGIAN, PVR_SEBAGIAN, PVR_PENDING, PV_DEPAN_SEBAGIAN, PV_DEPAN = (
    "Belum PVR", "PV sebagian, sisa belum PVR", "PVR sebagian", "PVR pending", "PV tanggal ke depan sebagian", "PV tanggal ke depan")
URUTAN_STATUS = [BELUM_PVR, PV_SEBAGIAN, PVR_SEBAGIAN, PVR_PENDING, PV_DEPAN_SEBAGIAN, PV_DEPAN]
BELUM_RV, RV_SEBAGIAN = "Belum RV", "RV sebagian"


def perusahaan():
    """{CompID: (server tertaut, database ERP)} perusahaan aktif bertipe SUMBER yang punya server dan database (HO dilewati)."""
    return {kode: (_nama(server, "CompAddr", kode), _nama(db, "CompDataBase", kode)) for kode, server, db in lokasi_perusahaan(SUMBER)}


def _ada_sp(buka=get_connection):
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute("SELECT OBJECT_ID(?, 'P')", konfigurasi.OUTSTANDING_SP)
        return cur.fetchone()[0] is not None
    finally:
        conn.close()


def ambil_data(kendali=None, peta=None):
    """Satu DataFrame untuk semua perusahaan, kolom __comp = CompID."""
    peta = peta if peta is not None else perusahaan()
    if not peta:
        raise RuntimeError(f"Tabel company tidak punya perusahaan aktif bertipe '{SUMBER}' yang punya server dan database.")
    if not _ada_sp():   # OBJECT_ID kosong juga kalau login aplikasi belum diberi izin EXECUTE pada SP itu
        raise RuntimeError(f"Stored procedure {konfigurasi.OUTSTANDING_SP} belum ada di database Main atau login aplikasi belum diberi izin EXECUTE. "
                           "Jalankan backend/database/outstanding_sp.sql lalu GRANT EXECUTE.")
    d = per_perusahaan(list(peta), get_connection, f"EXEC {konfigurasi.OUTSTANDING_SP} ?", lambda c: (c,), kendali, boleh_kosong=True, tandai=True)
    return d.drop(columns=["CompID"], errors="ignore")


def _teks(seri):
    return seri.fillna("").astype(str).str.strip()


def _angka(seri):
    return pd.to_numeric(seri, errors="coerce").fillna(0.0).astype(float)


def _status_hutang(sisa, pvr, pv_depan, sudah_pv):
    if pv_depan >= sisa - 0.5:
        return PV_DEPAN
    if pv_depan > 0:
        return PV_DEPAN_SEBAGIAN
    if pvr >= sisa - 0.5:
        return PVR_PENDING
    if pvr > 0:
        return PVR_SEBAGIAN
    if sudah_pv > 0:
        return PV_SEBAGIAN
    return BELUM_PVR


# Nama sumber dari ERP (SH_ARAPCalculations.DisplayTitle) diganti nama yang biasa dipakai pengguna. Yang tidak ada di sini tetap apa adanya.
NAMA_SUMBER = {
    "AP Purchase": "Purchase Invoice", "AP Purchase Return": "Retur Pembelian",
    "IT2/Purchase": "Purchase Invoice (Pajak Impor)", "X1/Purchase": "Purchase Invoice (Biaya Tambahan)",
    "X2/Purchase": "Purchase Invoice (Biaya Tambahan)", "Shp/Purchase": "Purchase Invoice (Ongkos Kirim)",
    "FFB Purchase": "Pembelian TBS", "FFB Purchase (PPn)": "Pembelian TBS (PPN)", "FFB By.Bongkar": "Biaya Bongkar TBS",
    "FFB Fee": "Fee TBS", "FFB Fee-2": "Fee TBS", "FFB Fee-3": "Fee TBS", "FFB Fee-4": "Fee TBS",
    "FFB Pot. Lain": "Potongan Lain TBS", "FFB SPSI": "SPSI TBS", "FFB Shipping Cost": "Ongkos Angkut TBS",
    "Penjualan TBS (Transport)": "Ongkos Angkut Penjualan TBS", "Transport": "Ongkos Angkut",
    "Sales Shipping Cost": "Ongkos Kirim Penjualan", "OA Pembelian (Non-Kontrak)": "Ongkos Angkut Pembelian",
    "Pending Cash V2": "Pending Cash", "Card Charges": "Biaya Kartu", "Customer Rebate (AP)": "Rebate Customer",
    "Customer Rebate (AR)": "Rebate Customer", "Warr. Card (AP)": "Kartu Garansi", "Warr. Card (AR)": "Kartu Garansi",
    "Salary Loan": "Pinjaman Karyawan", "Void AP Check": "Cek Batal", "Void AR Check": "Cek Batal",
    "Sales": "Penjualan", "AR Sales": "Penjualan", "AR Sales Return": "Retur Penjualan", "AP FA Sales": "Penjualan Aset",
    "Asset Rental": "Sewa Aset", "Shipping Contract": "Kontrak Angkut", "PPh Deduction (ARDN)": "Potongan PPh",
}


def bersihkan(raw, kurs_cadangan=None):
    """Satu baris per dokumen. Nilai, sisa, dan kolom PVR diberi tanda (potongan negatif), lalu dikali kurs ke rupiah.
    kurs_cadangan: fungsi(DataFrame comp, mata_uang, tgl) -> (Series kurs, [sumber]) untuk dokumen valas tanpa kurs dokumen."""
    if raw.empty:
        return pd.DataFrame()
    arah = _angka(raw["Arah"])
    d = pd.DataFrame({
        "comp": _teks(raw["__comp"]),
        "jenis": raw["IsAR"].map(lambda v: "piutang" if bool(v) else "hutang"),
        "kode": _teks(raw["Kode"]),
        "sumber": _teks(raw["Sumber"]),
        "no_dok": _teks(raw["NoDok"]),
        "tgl": pd.to_datetime(raw["Tgl"], errors="coerce").dt.normalize(),
        "mitra": _teks(raw["Mitra"]),
        "mata_uang": _teks(raw["Mata"]).replace("", "IDR").str.upper(),
        "kurs_dok": pd.to_numeric(raw["KursDok"], errors="coerce"),
        "nilai": arah * _angka(raw["Nilai"]),
        "sudah_bayar": arah * _angka(raw["SudahPV"]),
        "sisa": arah * _angka(raw["Sisa"]),
        "dalam_pvr": arah * _angka(raw["DalamPVR"]),
        "pv_depan": arah * _angka(raw["PVBelumJatuhTempo"]),
        "no_pv_depan": _teks(raw["NoPVBelumJatuhTempo"]),
        "tgl_pv_depan": pd.to_datetime(raw["TglPVBelumJatuhTempo"], errors="coerce").dt.normalize(),
        "no_bayar": _teks(raw["NoPV"]),
        "no_pvr": _teks(raw["NoPVR"]),
        "tgl_pvr": pd.to_datetime(raw["TglPVR"], errors="coerce").dt.normalize(),
        "approve_pvr": _teks(raw["ApprovePVR"]),
        "tagihan_pvr": pd.to_numeric(raw["TagihanPVR"], errors="coerce"),
        "potongan_pvr": pd.to_numeric(raw["PotonganPVR"], errors="coerce"),
        "no_do": _teks(raw["NoDO"]),
        "no_kontrak": _teks(raw["NoKontrak"]),
        "no_tc": _teks(raw["NoTC"]),
        "keterangan": _teks(raw["Keterangan"]),
    })
    d["sumber"] = d["sumber"].replace(NAMA_SUMBER)
    d["nilai_pvr"] = d["tagihan_pvr"] - d["potongan_pvr"]
    d["belum_diajukan"] = d["sisa"] - d["dalam_pvr"] - d["pv_depan"]
    hutang = d["jenis"] == "hutang"
    d["status"] = [
        _status_hutang(abs(s), abs(p), abs(v), abs(b)) if h else (RV_SEBAGIAN if abs(b) > 0 else BELUM_RV)
        for h, s, p, v, b in zip(hutang, d["sisa"], d["dalam_pvr"], d["pv_depan"], d["sudah_bayar"])
    ]
    d["umur"] = (pd.Timestamp(date.today()) - d["tgl"]).dt.days

    # Kurs: IDR = 1, lalu kurs dokumen, lalu kurs cadangan (aturan laporan Cash Flow)
    d["kurs"] = 1.0
    d["sumber_kurs"] = "IDR"
    valas = d["mata_uang"] != "IDR"
    dok = valas & (d["kurs_dok"] > 1)
    d.loc[dok, "kurs"] = d.loc[dok, "kurs_dok"]
    d.loc[dok, "sumber_kurs"] = "Dokumen ERP"
    sisa_valas = valas & ~dok
    if sisa_valas.any():
        if kurs_cadangan is not None:
            k, s = kurs_cadangan(d.loc[sisa_valas, ["comp", "mata_uang", "tgl"]])
            d.loc[sisa_valas, "kurs"] = k.values
            d.loc[sisa_valas, "sumber_kurs"] = [x or "Tidak ada kurs" for x in s]
        else:
            d.loc[sisa_valas, "kurs"] = float("nan")
            d.loc[sisa_valas, "sumber_kurs"] = "Tidak ada kurs"
    d["tanpa_kurs"] = d["kurs"].isna()
    kali = d["kurs"].fillna(0.0)
    for k in ("nilai", "sudah_bayar", "sisa", "dalam_pvr", "pv_depan", "belum_diajukan"):
        d[f"{k}_rp"] = d[k] * kali
    for k in ("tagihan_pvr", "potongan_pvr", "nilai_pvr"):
        d[k] = d[k] * kali
    return d.reset_index(drop=True)


def _kurs_tahunan(lokasi, buka=get_connection):
    """{(CompID, kode mata uang, tahun): kurs} dari exc_rate. lokasi: [(server, database)]; kode CURRENCYID dibaca dari
    CO_Currency perusahaan pertama."""
    server, db = lokasi[0]
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute(kas._KURS.format(tabel=konfigurasi.TABEL_KAS_KURS, server=server, db=db))
        return {(str(c).strip(), str(u).strip().upper(), int(y)): float(k) for c, u, y, k in cur.fetchall() if k}
    finally:
        conn.close()


def kurs_cadangan(t):
    """(Series kurs, [sumber]) untuk dokumen valas tanpa kurs dokumen; t: DataFrame comp (CompID), mata_uang, tgl.
    Urutan sama dengan laporan Cash Flow: kurs voucher ERP, kurs input CPOS, kurs tahunan exc_rate, kurs internet.
    Sumber yang gagal dibaca dilewati; dokumen yang tetap tanpa kurs ditandai."""
    def aman(f, *a):
        try:
            return f(*a)
        except Exception as e:   # laporan tetap tampil
            log.warning("Kurs cadangan Outstanding: %s", e)
            return {}
    mulai, akhir = t["tgl"].min().date().isoformat(), t["tgl"].max().date().isoformat()
    peta = aman(perusahaan)
    erp = aman(kas.ambil_kurs_erp, mulai, akhir)                                   # kunci: CompID
    masukan = aman(kas.ambil_kurs_input)                                             # kunci: CompID
    tahunan = aman(_kurs_tahunan, list(peta.values())) if peta else {}               # kunci: CompID
    internet = {u: kas.kurs_internet(u, mulai, akhir) for u in sorted(set(t["mata_uang"])) if u != "IDR"}
    k, s = [], []
    for c, u, tg in zip(t["comp"], t["mata_uang"], t["tgl"]):
        pilihan = [
            ("ERP", kas._kurs_erp(erp, c, u, tg) if pd.notna(tg) else None),
            ("CPOS", kas._kurs_berlaku(masukan, c, u, tg) if pd.notna(tg) else None),
            ("EXC_RATE", tahunan.get((c, u, tg.year)) if pd.notna(tg) else None),
            ("internet", internet.get(u, pd.Series(dtype=float)).get(tg) if pd.notna(tg) else None),
        ]
        sumber, nilai = next(((n, v) for n, v in pilihan if v is not None and pd.notna(v)), ("", float("nan")))
        k.append(nilai); s.append(sumber)
    return pd.Series(k, dtype=float), s


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Hutang/piutang: selalu semua riwayat (periode hanya membatasi tampilan). PR dan PO outstanding: yang dibuat
    dalam periode. Keduanya diambil bersamaan; baris PR/PO dibedakan lewat kolom jenis ('pr', 'po')."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        tugas_arap = pool.submit(ambil_data, kendali)
        tugas_pp = pool.submit(pengadaan.muat, mulai, akhir, kendali)
        raw, pp = tugas_arap.result(), tugas_pp.result()
    if kendali:
        kendali.periksa()
    d = pd.concat([bersihkan(raw, kurs_cadangan), pp], ignore_index=True)
    return d, {"baris_sp": len(d)}


def ambil_rincian(comp, kode, no_dok, buka=get_connection):
    """Baris SP RINCIAN_SP untuk satu dokumen (info, item PI, PVR/PV/RV). None kalau SP belum dibuat di database Main."""
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute("SELECT OBJECT_ID(?, 'P')", konfigurasi.RINCIAN_SP)
        if cur.fetchone()[0] is None:
            return None
        cur.execute(f"EXEC {konfigurasi.RINCIAN_SP} ?, ?, ?", comp, kode, no_dok)
        while cur.description is None:
            if not cur.nextset():
                return pd.DataFrame(columns=["Bagian", "Urut", "No", "Tgl", "Nama", "Qty", "Harga", "Nilai", "Status", "Ket"])
        return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description])
    finally:
        conn.close()
