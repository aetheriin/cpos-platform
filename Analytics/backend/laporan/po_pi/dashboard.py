"""Grafik dan tabel detail laporan PO/PI. Cross filter sama dengan PR/PO."""
import pandas as pd

from inti import kecepatan
from inti.banding import bagi, jendela_sebelumnya, kpi_sebelumnya
from inti.filter import FilterTidakValid, kanonik as _kanonik, saring, tgl as _tgl
from inti.laporan import MINGGU_BAWAAN, minggu_rentang
from inti.tabel import periksa, susun

from . import ukuran as P

KOLOM_CARI = ["po_number", "itemcode", "itemname", "supplier_name", "pi_number", "creator", "category", "comp"]


def _saring(df, filt, lewati=None):
    return saring(df, filt, DIM, lewati)


DIM = {"perusahaan": "comp", "kategori": "category", "pembuat": "creator", "umur": "umur"}


def _pilihan(df):
    perusahaan = sorted(df["comp"].unique().tolist())
    kategori = sorted(df["category"].unique().tolist(), key=lambda k: (k == "(kosong)", k.lower()))
    # pembuat diurutkan dari PO terbanyak
    pembuat = df.groupby("creator")["line"].nunique().sort_values(ascending=False).index.tolist()
    umur = [u for u in P.URUTAN_UMUR if u in set(df["umur"])]
    return perusahaan, kategori, pembuat, umur


def _periode(dari, sampai, minggu):
    """Minggu Jumat-Kamis di dalam rentang tampilan (dipotong ke rentang itu), dan jendela hitung (minggu terpilih, atau seluruh rentang)."""
    daftar = minggu_rentang(dari, sampai)
    if minggu is not None and not (0 <= minggu < len(daftar)):
        raise FilterTidakValid(f"minggu harus antara 0 dan {len(daftar) - 1} (0 = minggu paling lama)")
    ws, we = daftar[minggu] if minggu is not None else (daftar[0][0], daftar[-1][1])
    return daftar, ws, we


def _rapikan(df, perusahaan, kategori, pembuat, umur):
    p, k, b, u = _pilihan(df)
    return {
        "perusahaan": _kanonik(perusahaan, p, "perusahaan"),
        "kategori": _kanonik(kategori, k, "kategori"),
        "pembuat": _kanonik(pembuat, b, "pembuat"),
        "umur": _kanonik(umur, u, "umur"),
    }, (p, k, b, u)


def _kpi_jendela(semua, ws, we):
    """Kartu yang bergantung pada jendela waktu (bisa dibandingkan dengan jendela sebelumnya)."""
    y, total_pi, pct = P.pi_partial(semua, ws, we)
    return {
        "outstanding_awal": int(P.outstanding_awal(semua, ws)),
        "new_po": int(P.new_po(semua, ws, we)),
        "new_pi": int(P.new_pi(semua, ws, we)),
        "outstanding_akhir": int(P.outstanding_akhir(semua, we)),
        "completion_rate": float(P.completion_rate(semua, ws, we)),
        "pi_partial": {"jumlah": int(y), "dari": int(total_pi), "persen": float(pct)},
    }


def bangun(data, dari, sampai, minggu=None, perusahaan=None, kategori=None, pembuat=None, umur=None, mulai_data=None):
    """Semua angka untuk semua grafik dan kartu laporan PO PI. data: seluruh baris yang dimuat (termasuk baris `lalu` untuk perbandingan);
    dari..sampai: rentang tampilan."""
    df, lalu = bagi(data)
    daftar, ws, we = _periode(dari, sampai, minggu)
    filt, (p_list, k_list, b_list, u_list) = _rapikan(df, perusahaan, kategori, pembuat, umur)
    semua = _saring(df, filt)

    kpi = {**_kpi_jendela(semua, ws, we), "aging_rata_rata": round(P.aging_rata_rata(semua), 1), "aging_maks": float(P.aging_maks(semua))}
    ps, pe = jendela_sebelumnya(ws, we)
    kpi_lalu = kpi_sebelumnya(_kpi_jendela, semua, _saring(data, filt) if lalu is not None else semua, lalu is not None, ps, pe, mulai_data,
                              stok=("outstanding_awal", "outstanding_akhir"))
    banding = {"mulai": _tgl(ps), "akhir": _tgl(pe), "kpi": kpi_lalu} if kpi_lalu else None

    selesai = P.penyelesaian(semua)   # PO yang sudah selesai, untuk kartu dan grafik kecepatan

    mingguan = [
        {
            "indeks": i, "mulai": _tgl(s), "akhir": _tgl(e), "label": f"{s:%d/%m} - {e:%d/%m}",
            "outstanding_awal": int(P.outstanding_awal(semua, s)),
            "new_po": int(P.new_po(semua, s, e)),
            "new_pi": int(P.new_pi(semua, s, e)),
            "outstanding_akhir": int(P.outstanding_akhir(semua, e)),
        }
        for i, (s, e) in enumerate(daftar)
    ]

    # Per kategori (filter kategori dilewati)
    dasar = _saring(df, filt, "kategori")
    kat_out, kat_po, kat_pi = [], [], []
    for nama, g in dasar.groupby("category"):
        awal, akhir = int(P.outstanding_awal(g, ws)), int(P.outstanding_akhir(g, we))
        if awal or akhir:
            kat_out.append({"kategori": nama, "outstanding_awal": awal, "outstanding_akhir": akhir})
        n_po, n_pi = int(P.new_po(g, ws, we)), int(P.new_pi(g, ws, we))
        if n_po:
            kat_po.append({"kategori": nama, "jumlah": n_po})
        if n_pi:
            kat_pi.append({"kategori": nama, "jumlah": n_pi})
    kat_out.sort(key=lambda d: (-d["outstanding_akhir"], -d["outstanding_awal"]))
    kat_po.sort(key=lambda d: -d["jumlah"])
    kat_pi.sort(key=lambda d: -d["jumlah"])

    # Per perusahaan (filter perusahaan dilewati)
    dasar = _saring(df, filt, "perusahaan")
    po_comp, pi_comp = [], []
    for c in p_list:
        g = dasar[dasar["comp"] == c]
        po_comp.append({"nama": c, "nilai": [int(P.new_po(g, s, e)) for s, e in daftar]})
        pi_comp.append({"nama": c, "nilai": [int(P.new_pi(g, s, e)) for s, e in daftar]})

    # Per pembuat (filter pembuat dilewati). Garis PO Creator dan menu filter hanya memuat pembuat yang membuat PO baru
    # pada periode yang tampil; grafik Outstanding by Creator memuat pembuat yang punya outstanding. Pembuat yang sedang
    # dipilih selalu tampil supaya bisa dilepas.
    dasar = _saring(df, filt, "pembuat")
    kandidat = list(b_list)   # semua pembuat, urut dari PO terbanyak (yang dipilih pasti ada di sini)
    tampil = [b for b in kandidat if b in filt["pembuat"] or P.new_po(dasar[dasar["creator"] == b], ws, we) > 0]
    po_pembuat = [
        {"nama": b, "nilai": [int(P.new_po(dasar[dasar["creator"] == b], s, e)) for s, e in daftar]} for b in tampil
    ]
    masuk = P.mask_outstanding_akhir(dasar, we)
    out_pembuat = []
    for b in kandidat:
        jumlah = int(dasar.loc[masuk & (dasar["creator"] == b), "line"].nunique())
        if jumlah > 0 or b in filt["pembuat"]:
            out_pembuat.append({"pembuat": b, "jumlah": jumlah})

    return {
        "filter": {"minggu": minggu, **filt},
        "periode": {"mulai": _tgl(ws), "akhir": _tgl(we), "jumlah_minggu": len(daftar)},
        "rentang": {"dari": _tgl(dari), "sampai": _tgl(sampai), "satuan": "minggu", "bawaan": MINGGU_BAWAAN},
        # pembuat: yang tampil di menu. pembuat_semua: seluruh nama, urutan tetap (dipakai untuk warna yang stabil)
        "pilihan": {"perusahaan": p_list, "kategori": k_list, "pembuat": tampil, "pembuat_semua": b_list, "umur": u_list},
        "kpi": kpi,
        "banding": banding,
        "mingguan": mingguan,
        "kecepatan": kecepatan.ringkas(selesai, ws, we),                    # tanggal dokumen PO sampai PI terakhir
        "kategori_outstanding": kat_out,
        "kategori_new_po": kat_po,
        "kategori_new_pi": kat_pi,
        "new_po_per_perusahaan": po_comp,
        "new_pi_per_perusahaan": pi_comp,
        "new_po_per_pembuat": po_pembuat,
        "outstanding_per_pembuat": out_pembuat,
    }


# Tabel detail
KOLOM_DETAIL = [
    ("po_number", "No PO", "teks"),
    ("comp", "Perusahaan", "teks"),
    ("cd", "Tgl PO Dibuat", "tanggal"),
    ("creator", "Dibuat Oleh", "teks"),
    ("aging", "Aging (hari)", "campur"),
    ("lama", "Lama selesai (hari)", "angka"),    # hanya terisi untuk PO yang sudah selesai
    ("itemcode", "Kode Item", "teks"),
    ("itemname", "Nama Item", "teks"),
    ("category", "Kategori", "teks"),
    ("qtyordered", "Qty Order", "angka"),
    ("qtydelivered", "Qty Terima", "angka"),
    ("qtyout", "Qty Out", "angka"),
    ("uom", "Satuan", "teks"),
    ("itemtype", "Tipe Item", "teks"),
    ("supplier_code", "Kode Supplier", "teks"),
    ("supplier_name", "Supplier", "teks"),
    ("pi_number", "No PI", "teks"),
    ("pi_date", "Tgl PI", "tanggal"),
    ("status", "Status", "teks"),
    ("partial", "Partial", "teks"), 
]


JENIS_DETAIL = {"outstanding": "Outstanding akhir", "pi": "Sudah PI"}


def _gabung(seri):
    return ", ".join(dict.fromkeys(v for v in seri if v))


def _satu_baris_per_po(sub):
    """Satu baris per baris PO. Kalau punya beberapa PI, nomor PI digabung dan tanggal terakhir diambil."""
    sub = sub.sort_values(["line", "pi_date"], kind="stable")
    dasar = sub.drop_duplicates("line", keep="first").set_index("line")
    g = sub.groupby("line")
    pi = pd.DataFrame({"pi_number": g["pi_number"].agg(_gabung), "pi_date": g["pi_date"].max()})
    return dasar.drop(columns=["pi_number", "pi_date"]).join(pi).reset_index()


def detail(data, jenis, dari, sampai, minggu=None, perusahaan=None, kategori=None, pembuat=None,
           umur=None, cari=None, urut=None, arah=None, halaman=1, ukuran=50):
    """Baris detail. 'outstanding': baris PO di kartu Outstanding akhir (satu per baris PO).
    'pi': penerimaan di kartu New PI (satu baris per PI)."""
    periksa(jenis, JENIS_DETAIL, urut, KOLOM_DETAIL, arah)
    df, _ = bagi(data)
    daftar, ws, we = _periode(dari, sampai, minggu)
    filt, _ = _rapikan(df, perusahaan, kategori, pembuat, umur)
    semua = _saring(df, filt)
    kosong = pd.DataFrame(columns=[k for k, _, _ in KOLOM_DETAIL])

    if jenis == "outstanding":
        pilih = semua[P.mask_outstanding_akhir(semua, we)]
        urut_awal, arah_awal = "aging", "desc"
        t = _satu_baris_per_po(pilih) if len(pilih) else kosong
    else:
        pilih = semua[P.mask_pi(semua, ws, we)]
        urut_awal, arah_awal = "pi_date", "desc"
        t = pilih.reset_index(drop=True) if len(pilih) else kosong

    if not t.empty:
        t["lama"] = t["line"].map(P.penyelesaian(df)["lama"])   # dari seluruh baris PO itu, bukan hanya yang lolos filter
    hasil = susun(t, KOLOM_DETAIL, KOLOM_CARI, cari, urut, arah, urut_awal, arah_awal, halaman, ukuran,
                  pembanding="cd" if jenis == "outstanding" else None)
    return {"jenis": jenis, "judul": JENIS_DETAIL[jenis], "periode": {"mulai": _tgl(ws), "akhir": _tgl(we)}, **hasil}
