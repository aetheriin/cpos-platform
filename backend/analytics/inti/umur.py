"""Kategori aging laporan PR/PO dan PO/PI."""

URUTAN_UMUR = [
    "Tepat Waktu(0-8 Hari)", "Perlu Perhatian(9-15 Hari)", "Telat(16-30 Hari)", "Perlu Tindakan(>30 Hari)",
    "COMPLETED", "CLOSED", "VOID",
]


def kategori_umur(aging):
    """Umur numerik dikelompokkan; yang bukan angka (COMPLETED, VOID, CLOSED) dipakai apa adanya."""
    try:
        u = float(aging)
    except (TypeError, ValueError):
        return str(aging)
    if u <= 8:
        return "Tepat Waktu(0-8 Hari)"
    if u <= 15:
        return "Perlu Perhatian(9-15 Hari)"
    if u <= 30:
        return "Telat(16-30 Hari)"
    return "Perlu Tindakan(>30 Hari)"
