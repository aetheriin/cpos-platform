"""Laporan Cash Flow: mutasi rekening bank harian dan jasa giro, dengan query langsung ke database ERP tiap perusahaan.

Mutasi diambil langsung dari database ERP tiap perusahaan (ledger.py, aturan sama dengan ledger bank ERP yang dipanggil
SP_GET_BANKDAILYDETAILS), satu panggilan per perusahaan, bersamaan. Saldo awal pada 1 Januari tahun periode dihitung terpisah dan disimpan
di KAS_CACHE_FOLDER karena perhitungannya membaca seluruh riwayat (lambat); simpanan yang lebih tua dari KAS_SALDO_AWAL_JAM dihitung ulang
di latar belakang. Giro juga per perusahaan (ledger.ambil_giro, aturan sama dengan SP_GET_GIROTRANSACTION). Daftar rekening, perusahaan, dan akun
giro dari tabel TABEL_KAS_* di database Main.

Saldo dihitung ulang di sini dari baris "Beginning Balance" di awal periode ditambah mutasi berurutan tanggal: kolom AmtBalance dari SP
mengikuti urutan baris SP, yang untuk beberapa rekening tidak berurutan tanggal.
Rekening USD tidak dikonversi oleh SP (ExchangeRate selalu 1), jadi dikonversi di sini. Urutan kurs: kurs voucher ERP (FI_ARAP; hari tanpa voucher
memakai kurs terakhir sampai KAS_KURS_ERP_HARI hari, perusahaan itu dulu lalu perusahaan lain), lalu kurs transaksi yang diinput di CPOS
(TABEL_KAS_KURS_INPUT, Data Master › Kurs Mata Uang: kurs terakhir yang berlaku pada tanggal transaksi, kurs perusahaan itu lebih dulu dari
kurs untuk semua perusahaan), lalu kurs tahunan TABEL_KAS_KURS
(EXC_RATE: COMPID, CURRENCYID, YR, RATE; kode CURRENCYID dibaca dari CO_Currency perusahaan pertama) kalau ada untuk perusahaan dan tahun
itu, selain itu kurs harian dari internet (KAS_KURS_INTERNET, kurs referensi ECB lewat frankfurter.dev; hari libur memakai kurs hari kerja
sebelumnya). Semua nilai jadi rupiah; nilai asli di nilai_asli, kurs dan sumbernya di kurs dan sumber_kurs. Rekening yang tetap tanpa kurs
(mis. internet tidak terjangkau) ditandai tanpa_kurs dan tidak ikut dijumlahkan.
"""
import bisect
import json
import logging
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from inti import konfigurasi
from inti.db import get_connection
from inti.perusahaan import lokasi_perusahaan

from . import ledger

log = logging.getLogger(__name__)
KOSONG = "(kosong)"
JENIS_DOKUMEN = {"BS.AP": "Payment Voucher", "BS.AR": "Receipt Voucher", "BS.Deposit": "Deposit / Kas Kecil"}


def bulan_di(mulai, akhir):
    """['YYYYMM'] dari bulan `mulai` sampai bulan `akhir`."""
    return [p.strftime("%Y%m") for p in pd.period_range(pd.Timestamp(mulai), pd.Timestamp(akhir), freq="M")]


def _jalankan(perintah, parameter, periode, buka, kendali):
    if kendali:
        kendali.periksa()
    conn = buka()
    try:
        cur = conn.cursor()
        if kendali:
            kendali.daftarkan(cur)
        cur.execute(perintah, *parameter)
        while cur.description is None:
            if not cur.nextset():
                return pd.DataFrame()
        return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description]).assign(__periode=periode)
    finally:
        conn.close()


def _rekening(buka):
    """{perusahaan: (server tertaut, database ERP, [kode rekening aktif], {BankAccountID: kode}, [kode akun giro])}."""
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT RTRIM(C.CompName), RTRIM(C.CompAddr), RTRIM(C.CompDataBase), B.BANKACCOUNTCODE, B.BANKACCOUNTID "
                    f"FROM {konfigurasi.TABEL_KAS_PERUSAHAAN} C JOIN {konfigurasi.TABEL_KAS_BANK} B ON B.COMPID = C.CompName AND B.ACTIVE = 1 "
                    "WHERE C.CompType = 'CLOUD' AND C.Status = 1 ORDER BY C.CompName")
        baris = cur.fetchall()
        cur.execute(f"SELECT COMPID, RTRIM(ACCOUNTCODE) FROM {konfigurasi.TABEL_KAS_GIRO} WHERE ACTIVE = 1")
        giro = {}
        for comp, akun in cur.fetchall():
            giro.setdefault(str(comp).strip(), []).append(str(akun))
        hasil = {}
        for comp, server, basis, kode, id_bank in baris:
            if not all(str(n).replace("_", "").isalnum() for n in (server, basis)):
                raise RuntimeError(f"Server/database perusahaan {comp} di tabel company tidak valid: {server}.{basis}")
            isi = hasil.setdefault(str(comp), (str(server), str(basis), [], {}, giro.get(str(comp), [])))
            isi[2].append(str(kode).strip())
            isi[3][int(id_bank)] = str(kode).strip()
        return hasil
    finally:
        conn.close()


_kunci_cache = threading.Lock()
_dihitung = set()   # saldo awal yang sedang dihitung ulang di latar belakang


def _berkas_cache():
    from pathlib import Path
    folder = Path(konfigurasi.KAS_CACHE_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "saldo_awal.json"


def _baca_cache():
    try:
        return json.loads(_berkas_cache().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _hitung_saldo_awal(kunci, comp, server, db, patokan, kode, buka):
    conn = buka()
    try:
        saldo = ledger.saldo_awal(conn.cursor(), server, db, patokan, kode)
    finally:
        conn.close()
    with _kunci_cache:
        isi = _baca_cache()
        isi[kunci] = {"dihitung": pd.Timestamp.now().isoformat(timespec="seconds"), "kode": sorted(kode), "saldo": saldo}
        _berkas_cache().write_text(json.dumps(isi, indent=1), encoding="utf-8")
    log.info("Saldo awal Cash Flow %s per %s dihitung ulang", comp, patokan.date())
    return saldo


def _saldo_awal(comp, server, db, patokan, kode, buka):
    """Saldo awal per rekening pada `patokan`, dari simpanan kalau ada (dihitung ulang di latar belakang kalau sudah tua)."""
    kunci = f"{comp}|{db}|{patokan.date()}"
    simpan = _baca_cache().get(kunci)
    if not simpan or simpan.get("kode") != sorted(kode):
        return _hitung_saldo_awal(kunci, comp, server, db, patokan, kode, buka)
    umur = pd.Timestamp.now() - pd.Timestamp(simpan["dihitung"])
    if umur > pd.Timedelta(hours=konfigurasi.KAS_SALDO_AWAL_JAM) and kunci not in _dihitung:
        def ulang():
            try:
                _hitung_saldo_awal(kunci, comp, server, db, patokan, kode, buka)
            except Exception as e:
                log.warning("Saldo awal Cash Flow %s gagal dihitung ulang: %s", comp, e)
            finally:
                _dihitung.discard(kunci)
        _dihitung.add(kunci)
        threading.Thread(target=ulang, daemon=True).start()
    return simpan["saldo"]


def _mutasi_perusahaan(comp, lokasi, patokan, akhir, buka, kendali):
    server, db, kode = lokasi[:3]
    if kendali:
        kendali.periksa()
    awal = _saldo_awal(comp, server, db, patokan, kode, buka)
    conn = buka()
    try:
        cur = conn.cursor()
        if kendali:
            kendali.daftarkan(cur)
        return ledger.ambil_perusahaan(cur, comp, server, db, patokan, akhir, kode, awal)
    finally:
        conn.close()


def _giro_perusahaan(comp, lokasi, mulai, selesai, buka, kendali):
    server, db, _, id_kode, akun = lokasi
    if not akun or not id_kode:
        return pd.DataFrame()
    if kendali:
        kendali.periksa()
    conn = buka()
    try:
        cur = conn.cursor()
        if kendali:
            kendali.daftarkan(cur)
        return ledger.ambil_giro(cur, comp, server, db, mulai, selesai, akun, id_kode)
    finally:
        conn.close()


def ambil(mulai, akhir, kendali=None, buka=get_connection):
    """(mutasi mentah, giro mentah). Mutasi dari 1 Januari tahun `mulai` (patokan saldo awal) sampai akhir bulan `akhir`."""
    awal = bulan_di(mulai, akhir)[0]
    patokan = pd.Timestamp(year=pd.Timestamp(mulai).year, month=1, day=1)
    sampai = pd.Timestamp(akhir) + pd.offsets.MonthEnd(0)
    rekening = _rekening(buka)
    with ThreadPoolExecutor(max_workers=max(1, min(konfigurasi.KAS_PARALEL, len(rekening) + 1))) as pool:
        giro = [pool.submit(_giro_perusahaan, comp, lok, pd.Timestamp(f"{awal}01"), sampai + pd.Timedelta(days=1), buka, kendali)
                for comp, lok in rekening.items()]
        mutasi = [pool.submit(_mutasi_perusahaan, comp, lok, patokan, sampai, buka, kendali) for comp, lok in rekening.items()]
        mutasi = [m.result() for m in mutasi]
        giro = pd.concat([g for g in (x.result() for x in giro) if len(g)] or [pd.DataFrame()], ignore_index=True)
    mutasi = pd.concat([m for m in mutasi if len(m)] or [pd.DataFrame()], ignore_index=True)
    return mutasi.assign(__periode=awal), giro


_KURS = """
    SELECT e.COMPID, c.Currency, e.YR, e.RATE
    FROM {tabel} e
    JOIN OPENQUERY([{server}], 'SELECT CurrencyID, Currency FROM {db}.dbo.CO_Currency') c ON c.CurrencyID = e.CURRENCYID
"""


def ambil_kurs(buka=get_connection):
    """{(comp, kode mata uang, tahun): kurs ke rupiah}."""
    _, server, db = lokasi_perusahaan()[0]
    if not all(n.replace("_", "").isalnum() for n in (server, db)):
        raise RuntimeError(f"Nama server/database di tabel company tidak valid: {server}.{db}")
    conn = buka()
    try:
        cur = conn.cursor()
        cur.execute(_KURS.format(tabel=konfigurasi.TABEL_KAS_KURS, server=server, db=db))
        return {(str(c).strip(), str(u).strip().upper(), int(y)): float(k) for c, u, y, k in cur.fetchall() if k}
    finally:
        conn.close()


_KURS_INPUT = """
    SELECT x.CompID, c.CurrencyCode, x.RateDate, x.Rate
    FROM {tabel} x JOIN {mata_uang} c ON c.CurrencyID = x.CurrencyID
    WHERE x.IsVoid = 0 AND x.RateType = 'TRANSAKSI'
    ORDER BY x.RateDate
"""


def ambil_kurs_input(buka=get_connection):
    """{(comp atau None = semua perusahaan, kode): ([tanggal berlaku naik], [kurs])} dari kurs input CPOS. Kosong kalau tidak terbaca."""
    conn = None
    try:
        conn = buka()
        cur = conn.cursor()
        cur.execute(_KURS_INPUT.format(tabel=konfigurasi.TABEL_KAS_KURS_INPUT, mata_uang=konfigurasi.TABEL_KAS_MATA_UANG))
        hasil = {}
        for comp, kode, tgl, kurs in cur.fetchall():
            t, k = hasil.setdefault((str(comp).strip() if comp else None, str(kode).strip().upper()), ([], []))
            t.append(pd.Timestamp(tgl))
            k.append(float(kurs))
        return hasil
    except Exception as e:      # laporan tetap jalan dengan kurs tabel tahunan / internet
        log.warning("Kurs input CPOS (%s) tidak terbaca: %s", konfigurasi.TABEL_KAS_KURS_INPUT, e)
        return {}
    finally:
        if conn is not None:
            conn.close()


def ambil_kurs_erp(mulai, akhir, buka=get_connection):
    """{(comp atau None = perusahaan mana pun, kode): ([tanggal naik], [kurs])} dari voucher ERP. Satu tanggal: kurs yang paling banyak dipakai.
    Kosong kalau tidak terbaca, laporan tetap jalan dengan kurs berikutnya."""
    dari = pd.Timestamp(mulai) - pd.Timedelta(days=konfigurasi.KAS_KURS_ERP_HARI)
    sampai = pd.Timestamp(akhir) + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)
    baris = []
    try:
        for comp, lokasi in _rekening(buka).items():
            conn = buka()
            try:
                baris += [(comp, pd.Timestamp(t), str(u).strip().upper(), float(k), int(n))
                          for t, u, k, n in ledger.ambil_kurs_voucher(conn.cursor(), lokasi[0], lokasi[1], dari, sampai)]
            finally:
                conn.close()
    except Exception as e:
        log.warning("Kurs voucher ERP tidak terbaca: %s", e)
        return {}
    if not baris:
        return {}
    d = pd.DataFrame(baris, columns=["comp", "tgl", "kode", "kurs", "n"])
    hasil = {}
    for kunci, g in [*d.groupby(["comp", "kode"]), *((( None, k), g) for k, g in d.groupby("kode"))]:
        g = g.groupby(["tgl", "kurs"], as_index=False)["n"].sum().sort_values(["tgl", "n"]).drop_duplicates("tgl", keep="last")
        hasil[kunci] = (g["tgl"].tolist(), g["kurs"].tolist())
    return hasil


def _kurs_erp(erp, comp, kode, tgl):
    """Kurs voucher terakhir pada tgl, paling lama KAS_KURS_ERP_HARI hari sebelumnya (perusahaan itu dulu, lalu perusahaan mana pun), atau None."""
    for kunci in ((comp, kode), (None, kode)):
        if kunci in erp:
            t, k = erp[kunci]
            i = bisect.bisect_right(t, tgl)
            if i and (tgl - t[i - 1]).days <= konfigurasi.KAS_KURS_ERP_HARI:
                return k[i - 1]
    return None


def _kurs_berlaku(masukan, comp, kode, tgl):
    """Kurs input yang berlaku pada tgl (perusahaan itu dulu, lalu semua perusahaan), atau None."""
    for kunci in ((comp, kode), (None, kode)):
        if kunci in masukan:
            t, k = masukan[kunci]
            i = bisect.bisect_right(t, tgl)
            if i:
                return k[i - 1]
    return None


def kurs_internet(kode, mulai, akhir, baca=None):
    """Series kurs harian 1 `kode` dalam rupiah, indeks tanggal mulai..akhir (hari tanpa kurs diisi kurs sebelumnya). Kosong kalau gagal."""
    mulai, akhir = pd.Timestamp(mulai), pd.Timestamp(akhir)
    url = konfigurasi.KAS_KURS_INTERNET.format(dari=(mulai - pd.Timedelta(days=10)).date(), sampai=akhir.date(), kode=kode)
    try:
        if baca is None:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dashboard-analytics"}), timeout=20) as f:
                isi = json.load(f)
        else:
            isi = baca(url)
        s = pd.Series({pd.Timestamp(t): float(v["IDR"]) for t, v in isi.get("rates", {}).items() if v.get("IDR")}).sort_index()
    except Exception as e:   # laporan tetap tampil; rekeningnya ditandai tanpa kurs
        log.warning("Kurs %s dari internet gagal diambil (%s): %s", kode, url, e)
        return pd.Series(dtype=float)
    hari = pd.date_range(mulai, akhir)
    return s.reindex(s.index.union(hari)).sort_index().ffill().reindex(hari)


def _teks(s):
    t = s.astype("string").str.strip()
    return t.where(t.notna() & (t != ""), KOSONG).astype(str)


def _mata_uang(rekening, bank):
    return ["USD" if "USD" in f"{r} {b}".upper() else "IDR" for r, b in zip(rekening, bank)]


def _rupiahkan(d, kurs, internet=None, masukan=None, erp=None):
    """nilai (dan saldo awal) ke rupiah. Kurs = 1 untuk IDR, lalu kurs voucher ERP, lalu kurs input CPOS (ambil_kurs_input), lalu kurs tahunan tabel,
    lalu kurs harian internet ({kode: Series})."""
    internet, masukan = internet or {}, masukan or {}
    k, sumber = [], []
    for c, u, t in zip(d["comp"], d["mata_uang"], d["tgl"]):
        v = _kurs_berlaku(masukan, c, u, t) if pd.notna(t) and u != "IDR" else None
        e = _kurs_erp(erp or {}, c, u, t) if pd.notna(t) and u != "IDR" else None
        if u == "IDR":
            k.append(1.0); sumber.append("")
        elif e is not None:
            k.append(e); sumber.append("ERP")
        elif v is not None:
            k.append(v); sumber.append("CPOS")
        elif pd.notna(t) and (c, u, t.year) in kurs:
            k.append(kurs[(c, u, t.year)]); sumber.append("EXC_RATE")
        else:
            v = internet.get(u, pd.Series(dtype=float)).get(t) if pd.notna(t) else None
            k.append(v if v is not None and pd.notna(v) else float("nan")); sumber.append("internet" if v is not None and pd.notna(v) else "")
    d["kurs"] = pd.Series(k, index=d.index, dtype=float)
    d["sumber_kurs"] = sumber
    d["nilai_asli"] = d["nilai"]
    d["tanpa_kurs"] = d["kurs"].isna()
    d["nilai"] = d["nilai"] * d["kurs"].fillna(0)
    return d


def bersihkan_mutasi(raw, kurs=None, internet=None, masukan=None, erp=None):
    if raw.empty:
        raise RuntimeError("Database ERP tidak mengembalikan mutasi bank untuk periode ini")
    angka = lambda k: pd.to_numeric(raw[k], errors="coerce").fillna(0.0)
    d = pd.DataFrame({
        "comp": _teks(raw["COMPANYID"]),
        "rekening": _teks(raw["BankAccountCode"]),
        "bank": _teks(raw["BankName"]),
        "tgl": pd.to_datetime(raw["DocumentDate"], errors="coerce").dt.normalize(),
        "waktu": pd.to_datetime(raw["DocumentDateTime"], errors="coerce"),
        "no": _teks(raw["DocumentNo"]),
        "jenis_dok": [JENIS_DOKUMEN.get(str(j).strip(), KOSONG) for j in raw["DocumentTypeID"].fillna("")],
        "tipe_mitra": [{"S": "Supplier", "C": "Customer"}.get(str(t).strip(), KOSONG) for t in raw["AssociateType"].fillna("")],
        "mitra": _teks(raw["AssociateName"]),
        "nilai": angka("Amount"),
        "keterangan": _teks(raw["Remarks"]),
        "pembuat": _teks(raw["VoucherCreateBy"]),
        "awal": raw["IsOB"].fillna(False).astype(bool),
        "periode": raw["__periode"],
        "urut": range(len(raw)),
    })
    d["mata_uang"] = _mata_uang(d["rekening"], d["bank"])
    d = _rupiahkan(d, kurs or {}, internet, masukan, erp)
    d["akun"] = d["comp"] + " · " + d["rekening"]   # kode rekening yang sama (mis. CIMB-NIAGA) dipakai beberapa perusahaan
    # Lawan transaksi berupa rekening perusahaan sendiri (mis. OCBC PINJAMAN, CIMB-NIAGA) = transfer antar rekening, bukan supplier/customer
    # (nama bisa tertulis dua kali di ERP, mis. "BANK CIMB NIAGA A/C 8001996683 BANK CIMB NIAGA A/C 8001996683", jadi cukup diawali namanya)
    sendiri = tuple(sorted({n.upper() for n in pd.concat([d["rekening"], d["bank"]]) if n != KOSONG}))
    d["transfer"] = d["mitra"].str.upper().str.startswith(sendiri)
    d.loc[d["transfer"], "jenis_dok"] = "Transfer Antar Rekening"
    # Jasa giro dikreditkan bank ke rekeningnya sendiri, jadi lawan transaksinya juga nama bank; dibedakan dari transfer lewat keterangannya
    giro = (d["nilai"] > 0) & d["keterangan"].str.upper().str.contains("JASA GIRO", regex=False) & d["transfer"]
    d.loc[giro, "transfer"] = False
    d.loc[giro, "jenis_dok"] = "Jasa Giro"
    d["masuk"] = d["nilai"].clip(lower=0)
    d["keluar"] = (-d["nilai"]).clip(lower=0)
    d["hari"] = d["tgl"].dt.strftime("%Y-%m-%d")
    # Saldo setelah tiap mutasi: saldo awal + mutasi berurutan tanggal. Dalam satu hari uang masuk dihitung lebih dulu, supaya saldo tidak terlihat
    # minus hanya karena voucher keluar diinput lebih awal; saldo akhir harinya tetap sama. Lalu waktu dokumen, dan urutan SP sebagai pemecah seri.
    d["__keluar"] = d["nilai_asli"] < 0
    d = d.sort_values(["comp", "rekening", "periode", "awal", "tgl", "__keluar", "waktu", "urut"],
                      ascending=[True, True, True, False, True, True, True, True], kind="stable").drop(columns="__keluar")
    grup = ["comp", "rekening", "periode"]
    d["saldo"] = d.groupby(grup)["nilai"].cumsum()
    # Valas: saldo mata uang aslinya dikali kurs hari itu. Menjumlahkan nilai rupiah meninggalkan selisih kurs, jadi rekening yang saldo dolarnya
    # sudah 0 masih terlihat punya saldo rupiah.
    valas = (d["mata_uang"] != "IDR") & d["kurs"].notna()
    d.loc[valas, "saldo"] = d["nilai_asli"].groupby([d[k] for k in grup]).cumsum().round(4)[valas] * d.loc[valas, "kurs"]
    return d.reset_index(drop=True)


def bersihkan_giro(raw, mutasi, kurs=None, internet=None, masukan=None, erp=None):
    if raw.empty:
        return pd.DataFrame(columns=["comp", "rekening", "bank", "tgl", "no", "nilai", "nilai_asli", "kurs", "sumber_kurs", "tanpa_kurs", "mata_uang", "akun",
                                     "hari", "periode"])
    d = pd.DataFrame({
        "comp": _teks(raw["COMPID"]),
        "rekening": _teks(raw["BANKACCOUNTCODE"]),
        "bank": _teks(raw["ASSOCIATENAME"]),
        "tgl": pd.to_datetime(raw["VOUCHERDATE"], errors="coerce").dt.normalize(),
        "no": _teks(raw["VOUCHERNO"]),
        "nilai": pd.to_numeric(raw["AMOUNT"], errors="coerce").fillna(0.0),
        "periode": raw["PERIODE"].astype(str).str.strip(),
    })
    # Mata uang mengikuti rekeningnya di mutasi (nama bank di data giro adalah nama lawan transaksi, mis. "CIMB USD")
    uang = mutasi.drop_duplicates(["comp", "rekening"]).set_index(["comp", "rekening"])["mata_uang"]
    d["mata_uang"] = [uang.get((c, r), m) for c, r, m in zip(d["comp"], d["rekening"], _mata_uang(d["rekening"], d["bank"]))]
    d = _rupiahkan(d, kurs or {}, internet, masukan, erp)
    d["akun"] = d["comp"] + " · " + d["rekening"]
    d["hari"] = d["tgl"].dt.strftime("%Y-%m-%d")
    return d


def muat(mulai, akhir, kendali=None):
    """Pemuat untuk Gudang. Bulan pertama sampai bulan terakhir dimuat utuh supaya saldo awal ikut; baris di luar periode tetap disimpan
    (saldo hari pertama bergantung pada mutasi sebelumnya di bulan itu) dan dipotong saat ditampilkan."""
    raw_mutasi, raw_giro = ambil(mulai, akhir, kendali)
    if kendali:
        kendali.periksa()
    kurs, masukan, erp = ambil_kurs(), ambil_kurs_input(), ambil_kurs_erp(mulai, akhir)
    # kurs internet hanya untuk mata uang asing yang ada di data (nama rekening/bank memuat kodenya)
    valas = sorted({u for u in _mata_uang(raw_mutasi.get("BankAccountCode", []), raw_mutasi.get("BankName", [])) if u != "IDR"})
    internet = {u: kurs_internet(u, mulai, akhir) for u in valas}
    mutasi = bersihkan_mutasi(raw_mutasi, kurs, internet, masukan, erp)
    # Data giro ikut dataset yang sama di Gudang, sebagai daftar biasa (attrs ikut tersalin di setiap operasi pandas, jadi dibuat ringan)
    mutasi.attrs["giro"] = bersihkan_giro(raw_giro, mutasi, kurs, internet, masukan, erp).to_dict("records")
    return mutasi, {"baris_sp": int(((mutasi["tgl"] >= pd.Timestamp(mulai)) & (mutasi["tgl"] <= pd.Timestamp(akhir)) & ~mutasi["awal"]).sum()),
               "bulan": len(bulan_di(mulai, akhir))}
