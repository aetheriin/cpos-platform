"""Kategori aging satu-satunya: Tepat Waktu (0-8 hari), Perlu Perhatian (9-15), Telat (16-30), Perlu Tindakan (>30).
Dipakai dashboard PR & PO dan PO & PI (kategori_umur) serta laporan Reports (kelompok_umur): Outstanding, Purchase Request,
Purchase Orders, Purchase Invoice."""
import pandas as pd

KELOMPOK_UMUR = [("Tepat Waktu(0-8 Hari)", 8), ("Perlu Perhatian(9-15 Hari)", 15), ("Telat(16-30 Hari)", 30), ("Perlu Tindakan(>30 Hari)", None)]
URUTAN_KELOMPOK_UMUR = [label for label, _ in KELOMPOK_UMUR]


def kelompok_umur(hari):
    """Umur (hari) -> label kelompok; kosong bila umurnya tidak ada."""
    if hari is None or pd.isna(hari):
        return ""
    return next(label for label, atas in KELOMPOK_UMUR if atas is None or hari <= atas)


URUTAN_UMUR = URUTAN_KELOMPOK_UMUR + ["COMPLETED", "CLOSED", "VOID"]


def kategori_umur(aging):
    """Umur numerik dikelompokkan; yang bukan angka (COMPLETED, VOID, CLOSED) dipakai apa adanya."""
    try:
        u = float(aging)
    except (TypeError, ValueError):
        return str(aging)
    return kelompok_umur(u)
