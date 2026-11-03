"""Laporan Deteksi Kecurangan Timbangan: ambil transaksi timbang (weighbridge sawit) langsung dari PALM_Tickets tiap perusahaan dan bersihkan.

Server tertaut dan nama database diambil dari tabel company (CompAddr, CompDataBase), jadi perusahaan baru langsung ikut."""
import re
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.banding import jendela_sebelumnya
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan
from inti.sp import per_perusahaan

from . import ukuran as U

SUMBER = konfigurasi.SUMBER_PALM

# Kolom hasil query -> nama di program. Pencocokan tidak peduli huruf besar-kecil, spasi, dan garis bawah ("Ticket Date" sama dengan TicketDate).
WAJIB = {
    "TicketNo": "ticket_no", "TicketDate": "tgl", "DurationMinutes": "durasi", "VehicleNo": "kendaraan", "ProductName": "produk", "Bruto": "bruto",
    "ActualTara": "tara_aktual", "MaxHistoricalTara": "tara_historis", "TaraDeviation": "tara_selisih", "Deduction": "potongan", "Netto": "netto",
    "Operator": "operator", "NamaSupir": "supir", "SupplierCode": "kode_supplier", "SupplierName": "supplier",
}
OPSIONAL = {"CompID": "comp", "DateTimeIn": "masuk", "DateTimeOut": "keluar", "Splitted": "split", "TicketType": "tipe_tiket",
            "CustomerCode": "kode_customer", "CustomerName": "customer"}
NAMA_LAMA = {"MaxHistoricalTara": "AvgHistoricalTara"}   # SP versi lama (tara historis median) masih bisa dibaca
ANGKA = ["durasi", "bruto", "tara_aktual", "tara_historis", "tara_selisih", "potongan", "netto"]
TEKS = ["ticket_no", "kendaraan", "produk", "operator", "supir", "kode_supplier", "supplier", "kode_customer", "customer", "comp"]
KOSONG = "(kosong)"
SPLIT_YA, SPLIT_TIDAK = "Ya", "Tidak"
# TicketType -> jenis transaksi. Tipe lain tampil apa adanya.
JENIS_TIKET = {"tbsluar": "Pembelian", "produk": "Penjualan"}


def _kunci(nama):
    return re.sub(r"[^a-z0-9]", "", str(nama).lower())


# Data langsung dari PALM_Tickets tiap perusahaan lewat OPENQUERY. SQL hanya menyaring dan mengirim kolom tiket yang dipakai; waktu habis
# untuk mengirim baris lewat server tertaut, bukan menghitung, jadi tara historis dan nama supplier/customer dihitung di Python (_susun):
# satu kali kirim, tanpa membaca tabel tiket dua kali dan tanpa nama yang diulang di tiap baris.
# Aturan sama dengan SP PalmWeighbridge; bedanya supplier hanya untuk Pembelian (TBSLuar) dan customer untuk Penjualan (Produk), karena
# AssociateID menunjuk AP_Suppliers atau AR_Customers menurut jenis tiketnya.
_NAMA_SQL = re.compile(r"^[A-Za-z0-9_]+$")   # nama server dan database disisipkan ke teks SQL, jadi hanya huruf, angka, dan _
HISTORIS_BULAN = 6                 # tara historis: tara tertinggi kendaraan dalam 6 bulan terakhir...
TARA_HISTORIS_KG = (2000, 15000)   # ...dari tiket dengan tara di rentang ini
_TIKET = """
    SELECT TicketID, TicketNo, TicketType, Date, DateTimeIn, DateTimeOut, VehicleNo, ProductName, Bruto, Tara, Deduction, Netto,
           Operator, NamaSupir, Splitted, AssociateID
    FROM {db}.dbo.PALM_Tickets
    WHERE Date >= ''{mulai}'' AND ((Void IS NULL OR Void = 0) OR Splitted = 1) AND (ParentTicketID IS NULL OR ParentTicketID = 0)
      AND DateTimeOut IS NOT NULL AND VehicleNo IS NOT NULL AND RTRIM(LTRIM(VehicleNo)) <> ''''
"""
_SUPPLIER = "SELECT SupplierID AS ID, SupplierCode AS Kode, SupplierName AS Nama FROM {db}.dbo.AP_Suppliers"
_CUSTOMER = "SELECT CustomerID AS ID, CustomerCode AS Kode, CustomerName AS Nama FROM {db}.dbo.AR_Customers"


def _nama(teks, apa, comp):
    if not _NAMA_SQL.match(teks or ""):
        raise RuntimeError(f"{apa} perusahaan {comp} di tabel company tidak valid: '{teks}'. Hanya huruf, angka, dan _.")
    return teks


def perintah(lokasi, query, **isian):
    """lokasi: (nama, server, database)."""
    comp, server, db = lokasi
    return f"SELECT * FROM OPENQUERY([{_nama(server, 'CompAddr', comp)}], '{query.format(db=_nama(db, 'CompDataBase', comp), **isian)}')"


def _kendaraan(s):
    return s.astype("string").str.strip().str.replace(" ", "", regex=False).str.replace("-", "", regex=False).str.upper()


def _susun(tiket, supplier, customer, mulai, hari_ini):
    """Hasil sama dengan SELECT akhir SP PalmWeighbridge (nama kolom juga), ditambah CustomerCode/CustomerName."""
    if tiket.empty:
        return tiket
    t = tiket.assign(Kendaraan=_kendaraan(tiket["VehicleNo"]), Date=pd.to_datetime(tiket["Date"]))
    for k in ("Bruto", "Tara", "Deduction", "Netto"):
        t[k] = pd.to_numeric(t[k], errors="coerce")
    batas = pd.Timestamp(hari_ini) - pd.DateOffset(months=HISTORIS_BULAN)
    h = t[(t["Date"] >= batas) & t["Tara"].between(*TARA_HISTORIS_KG)]
    stats = h.groupby(["__comp", "Kendaraan"])["Tara"].agg(TotalLifetimeTrips="size", MaxHistoricalTara="max").reset_index()

    t = t[(t["Date"] >= pd.Timestamp(mulai)) & (t["Bruto"] > 0) & (t["Tara"] > 0) & (t["Netto"] > 0)]
    t = t.merge(stats[stats["TotalLifetimeTrips"] > 1], on=["__comp", "Kendaraan"], how="inner")
    tipe = t["TicketType"].astype("string").str.strip().str.lower()
    pasang = lambda tabel, awalan: tabel.rename(columns={"ID": "AssociateID", "Kode": f"{awalan}Code", "Nama": f"{awalan}Name"})
    t = t.merge(pasang(supplier, "Supplier"), on=["__comp", "AssociateID"], how="left")
    t = t.merge(pasang(customer, "Customer"), on=["__comp", "AssociateID"], how="left")
    t.loc[tipe.values != "tbsluar", ["SupplierCode", "SupplierName"]] = None
    t.loc[tipe.values != "produk", ["CustomerCode", "CustomerName"]] = None
    t = t[t["SupplierName"].notna() | t["CustomerName"].notna()]

    masuk, keluar = pd.to_datetime(t["DateTimeIn"]), pd.to_datetime(t["DateTimeOut"])
    return pd.DataFrame({
        "__comp": t["__comp"], "TicketID": t["TicketID"], "TicketNo": t["TicketNo"], "TicketType": t["TicketType"], "TicketDate": t["Date"],
        "DateTimeIn": masuk, "DateTimeOut": keluar,
        # DATEDIFF(MINUTE, ...) menghitung batas menit yang dilewati, bukan selisih yang dibulatkan
        "DurationMinutes": (keluar.dt.floor("min") - masuk.dt.floor("min")).dt.total_seconds() // 60,
        "VehicleNo": t["Kendaraan"], "ProductName": t["ProductName"], "Bruto": t["Bruto"], "ActualTara": t["Tara"],
        "MaxHistoricalTara": t["MaxHistoricalTara"], "TaraDeviation": (t["Tara"] - t["MaxHistoricalTara"]).round(2),
        "Deduction": t["Deduction"], "Netto": t["Netto"], "Operator": t["Operator"], "NamaSupir": t["NamaSupir"],
        "Splitted": t["Splitted"].fillna(0).astype(int),
        "SupplierCode": t["SupplierCode"], "SupplierName": t["SupplierName"], "CustomerCode": t["CustomerCode"], "CustomerName": t["CustomerName"],
    }).reset_index(drop=True)


def ambil_data(mulai, lokasi=None, kendali=None, hari_ini=None):
    """Tiket dari tanggal `mulai` (date) sampai data terakhir, semua perusahaan sumber laporan."""
    hari_ini = hari_ini or date.today()
    dari = min(mulai, (pd.Timestamp(hari_ini) - pd.DateOffset(months=HISTORIS_BULAN)).date())   # riwayat tara ikut terambil
    lokasi = lokasi if lokasi is not None else lokasi_perusahaan(SUMBER)
    peta = {l[0]: l for l in lokasi}
    ambil = lambda query, **isian: per_perusahaan(list(peta), get_connection, lambda comp: perintah(peta[comp], query, **isian),
                                                  lambda comp: (), kendali, boleh_kosong=True, tandai=True)
    tiket = ambil(_TIKET, mulai=dari.isoformat())
    if kendali:
        kendali.periksa()
    return _susun(tiket, ambil(_SUPPLIER), ambil(_CUSTOMER), mulai, hari_ini)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Periode sebelumnya ikut diambil untuk pembanding KPI, ditandai kolom `lalu`.
    Query tidak memakai tanggal akhir, jadi baris setelah `akhir` dibuang di sini."""
    mulai_lalu, _ = jendela_sebelumnya(mulai, akhir)
    raw = ambil_data(pd.Timestamp(mulai_lalu).date(), kendali=kendali)
    if kendali:
        kendali.periksa()
    d = bersihkan(raw)
    d = d[d["tgl"].isna() | (d["tgl"] <= pd.Timestamp(akhir))].reset_index(drop=True)
    d["lalu"] = d["tgl"] < pd.Timestamp(mulai)
    return d, {"baris_sp": int((~d["lalu"]).sum())}


def bersihkan(raw):
    """Pilih dan namai ulang kolom, rapikan tipe, lalu hitung indikator risiko. Melempar RuntimeError kalau kolom wajib tidak ada di hasil SP."""
    ada = {_kunci(c): c for c in raw.columns}
    peta = {k: _kunci(k) for k in (*WAJIB, *OPSIONAL)}
    for baru, lama in NAMA_LAMA.items():
        if peta[baru] not in ada and _kunci(lama) in ada:
            peta[baru] = _kunci(lama)
    hilang = [k for k in WAJIB if peta[k] not in ada]
    if hilang:
        raise RuntimeError(f"Hasil query PALM_Tickets tidak memuat kolom yang dibutuhkan: {', '.join(hilang)}. Kolom yang ada: {', '.join(map(str, raw.columns))}")
    d = pd.DataFrame({baru: raw[ada[peta[lama]]] for lama, baru in WAJIB.items()})
    for lama, baru in OPSIONAL.items():
        d[baru] = raw[ada[peta[lama]]] if peta[lama] in ada else None
    # perusahaan: kolom CompID dari SP; kalau kosong, perusahaan yang dipanggil
    if "__comp" in raw.columns:
        d["comp"] = d["comp"].where(d["comp"].notna() & (d["comp"].astype(str).str.strip() != ""), raw["__comp"])

    d["tgl"] = pd.to_datetime(d["tgl"], errors="coerce").dt.normalize()
    d["masuk"] = pd.to_datetime(d["masuk"], errors="coerce")
    d["keluar"] = pd.to_datetime(d["keluar"], errors="coerce")
    for k in ANGKA:
        d[k] = pd.to_numeric(d[k], errors="coerce")
    for k in TEKS:
        t = d[k].astype("string").str.strip()
        d[k] = t.where(t.notna() & (t != ""), KOSONG).astype(str)
    # Splitted dari SP: 1 = tiket hasil split (tiket pecahannya sudah tidak ikut dikirim SP). Kolom kosong atau tidak ada dianggap bukan split.
    split = d["split"].astype("string").str.strip().str.upper().isin(["1", "Y", "YES", "TRUE"])
    d["split"] = split.map({True: SPLIT_YA, False: SPLIT_TIDAK})
    tipe = d["tipe_tiket"].astype("string").str.strip()
    d["jenis"] = [JENIS_TIKET.get(_kunci(t), t) if isinstance(t, str) and t else KOSONG for t in tipe.fillna("")]
    d = d.drop(columns="tipe_tiket")
    d["risiko"] = U.indikator(d["tara_selisih"], d["durasi"])
    d["hari"] = d["tgl"].dt.strftime("%Y-%m-%d").fillna("(kosong)")
    d["jam"] = d["masuk"].dt.strftime("%H").fillna("(kosong)")
    return d.reset_index(drop=True)
