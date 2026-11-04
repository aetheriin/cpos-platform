"""Tabel detail semua laporan: pencarian, urutan, dan halaman."""
import pandas as pd

from .filter import FilterTidakValid, tgl


def nilai(v, tipe):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if tipe == "tanggal":
        return tgl(v)
    if tipe == "waktu":
        return pd.Timestamp(v).strftime("%Y-%m-%d %H:%M:%S")
    if tipe in ("angka", "campur"):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v).strip() or None
        return int(f) if f == int(f) else round(f, 2)
    t = str(v).strip()
    return t or None


def periksa(jenis, jenis_sah, urut, kolom, arah):
    """kolom: [(kunci, judul, tipe)]."""
    kunci = [k for k, _, _ in kolom]
    if jenis not in jenis_sah:
        raise FilterTidakValid(f"jenis harus salah satu dari: {', '.join(jenis_sah)}")
    if urut is not None and urut not in kunci:
        raise FilterTidakValid(f"urut harus salah satu dari: {', '.join(kunci)}")
    if arah not in (None, "asc", "desc"):
        raise FilterTidakValid("arah harus asc atau desc")


def susun(t, kolom, kolom_cari, cari, urut, arah, urut_awal, arah_awal, halaman, ukuran, pembanding=None):
    """pembanding: urutan kedua (naik) supaya baris dengan nilai urutan sama tetap stabil."""
    tipe = {k: tp for k, _, tp in kolom}
    total_semua = len(t)

    cari = (cari or "").strip()
    if cari and not t.empty:
        teks = t[kolom_cari[0]].astype(str)
        for k in kolom_cari[1:]:
            teks = teks + " " + t[k].astype(str)
        t = t[teks.str.lower().str.contains(cari.lower(), regex=False)]

    urut_pakai = urut or urut_awal
    arah_pakai = arah or (arah_awal if urut is None else "asc")
    if not t.empty:
        if urut is None and pembanding:
            t = t.sort_values(pembanding, kind="stable")
        kunci = t[urut_pakai]
        if urut_pakai == "aging":
            kunci = pd.to_numeric(kunci, errors="coerce")
        elif tipe.get(urut_pakai) == "teks":   # urut_awal boleh kolom yang tidak ditampilkan
            kunci = kunci.fillna("").astype(str).str.lower()
        t = (
            t.assign(_k=kunci)
            .sort_values("_k", ascending=(arah_pakai == "asc"), na_position="last", kind="stable")
            .drop(columns="_k")
        )

    total = len(t)
    jumlah_halaman = max(1, -(-total // ukuran))
    halaman = min(max(1, halaman), jumlah_halaman)
    potong = t.iloc[(halaman - 1) * ukuran: halaman * ukuran]
    baris = [{k: nilai(r[k], tp) for k, _, tp in kolom} for r in potong.to_dict("records")]
    return {
        "kolom": [{"kunci": k, "judul": j, "tipe": tp} for k, j, tp in kolom],
        "total_semua": int(total_semua),
        "total": int(total),
        "halaman": int(halaman),
        "ukuran": int(ukuran),
        "jumlah_halaman": int(jumlah_halaman),
        "urut": urut_pakai,
        "arah": arah_pakai,
        "cari": cari,
        "baris": baris,
    }
