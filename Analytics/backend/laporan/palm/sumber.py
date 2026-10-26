"""Laporan Deteksi Kecurangan Timbangan: ambil transaksi timbang (weighbridge sawit) dari stored procedure dan bersihkan."""
import re
from datetime import date

import pandas as pd

from inti import konfigurasi
from inti.banding import jendela_sebelumnya
from inti.db import get_connection
from inti.perusahaan import daftar_perusahaan
from inti.sp import per_perusahaan

from . import ukuran as U

SP_NAME = konfigurasi.SP_PALM
SUMBER = konfigurasi.SUMBER_PALM
FORMAT_TANGGAL = konfigurasi.FORMAT_TANGGAL_PALM

# Kolom hasil SP -> nama di program. Pencocokan tidak peduli huruf besar-kecil, spasi, dan garis bawah ("Ticket Date" sama dengan TicketDate).
# Kolom lain di hasil SP (termasuk RiskIndicator dari SP) diabaikan: indikator risiko dihitung program dari selisih tara dan durasi.
WAJIB = {
    "TicketNo": "ticket_no", "TicketDate": "tgl", "DurationMinutes": "durasi", "VehicleNo": "kendaraan", "ProductName": "produk", "Bruto": "bruto",
    "ActualTara": "tara_aktual", "MaxHistoricalTara": "tara_historis", "TaraDeviation": "tara_selisih", "Deduction": "potongan", "Netto": "netto",
    "Operator": "operator", "NamaSupir": "supir", "SupplierCode": "kode_supplier", "SupplierName": "supplier",
}
OPSIONAL = {"CompID": "comp", "DateTimeIn": "masuk", "DateTimeOut": "keluar", "Splitted": "split", "TicketType": "tipe_tiket"}
NAMA_LAMA = {"MaxHistoricalTara": "AvgHistoricalTara"}   # SP versi lama (tara historis median) masih bisa dibaca
ANGKA = ["durasi", "bruto", "tara_aktual", "tara_historis", "tara_selisih", "potongan", "netto"]
TEKS = ["ticket_no", "kendaraan", "produk", "operator", "supir", "kode_supplier", "supplier", "comp"]
KOSONG = "(kosong)"
SPLIT_YA, SPLIT_TIDAK = "Ya", "Tidak"
# TicketType -> jenis transaksi. Tipe lain tampil apa adanya.
JENIS_TIKET = {"tbsluar": "Pembelian", "produk": "Penjualan"}


def _kunci(nama):
    return re.sub(r"[^a-z0-9]", "", str(nama).lower())


def ambil_data(tgl_mulai, tgl_akhir, perusahaan=None, kendali=None):
    """tgl_mulai dan tgl_akhir sudah berformat PALM_FORMAT_TANGGAL."""
    if perusahaan is None:
        perusahaan = daftar_perusahaan(SUMBER)
    return per_perusahaan(perusahaan, get_connection, f"EXEC {SP_NAME} ?, ?, ?", lambda comp: (comp, tgl_mulai, tgl_akhir), kendali,
                          tandai=True)


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Periode sebelumnya ikut diambil untuk pembanding KPI, ditandai kolom `lalu`."""
    mulai_lalu, _ = jendela_sebelumnya(mulai, akhir)
    raw = ambil_data(mulai_lalu.strftime(FORMAT_TANGGAL), date.fromisoformat(akhir).strftime(FORMAT_TANGGAL), kendali=kendali)
    if kendali:
        kendali.periksa()
    d = bersihkan(raw)
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
        raise RuntimeError(f"Hasil SP {SP_NAME} tidak memuat kolom yang dibutuhkan: {', '.join(hilang)}. Kolom yang ada: {', '.join(map(str, raw.columns))}")
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
