def _tahap(id_alur):
    """Urutan tahap tiket dari alurnya (kosong bila tiket lama tanpa alur)."""
    if not id_alur:
        return []
    from utils.alur import tahap_alur
    return tahap_alur(id_alur)


def _tahap_tiket(row):
    from utils.alur import tahap_banyak, tahap_menunggu
    tahap = tahap_banyak([row.no_tiket]).get(row.no_tiket)
    if tahap:
        return {"alur_tahap": [t["kode_tahap"] for t in tahap], "tahap_menunggu": tahap_menunggu(tahap)}
    return {"alur_tahap": _tahap(getattr(row, "id_alur", None)), "tahap_menunggu": None}


def _angkut(cara, id_pengangkutan):
    if cara == "PIHAK_KETIGA":
        return f"PIHAK_KETIGA:{id_pengangkutan}"
    return cara or ""


def serialisasi_tiket(row):
    return {
        "status": "ADA_TIKET",
        "no_tiket": row.no_tiket, "jenis_transaksi": row.jenis_transaksi, "no_do": row.no_do,
        "status_alur": row.status_alur,
        "id_supplier": row.id_supplier, "supplier": row.nama_supplier,
        "id_produk": row.id_produk, "produk": row.nama_produk, "kategori_produk": row.kategori,
        **_tahap_tiket(row),
        "angkut": _angkut(getattr(row, "cara_angkut", None), getattr(row, "id_pengangkutan", None)),
        "no_plat": row.no_plat, "no_stnk": row.no_stnk,
        "driver": {
            "id_driver": row.id_driver, "nik": row.nik, "nama": row.nama_driver,
            "no_sim": row.no_sim, "is_updated": bool(row.is_updated), "foto_path": row.foto_path,
            "is_blacklisted": bool(row.is_blacklisted)
        }
    }

def serialisasi_driver(row):
    if row is None:
        return None

    masa_berlaku = getattr(row, "sim_berlaku_sampai", None)
    if masa_berlaku is not None:
        masa_berlaku = (
            masa_berlaku.isoformat()
            if hasattr(masa_berlaku, "isoformat")
            else str(masa_berlaku)
        )

    return {
        "id_driver": row.id_driver,
        "nik": row.nik,
        "nama": row.nama_driver,
        "no_sim": row.no_sim,
        "id_jenis_sim": getattr(row, "id_jenis_sim", None),
        "kode_jenis_sim": getattr(row, "kode_jenis_sim", None),
        "sim_berlaku_sampai": masa_berlaku,
        "kategori": row.kategori,
        "is_blacklisted": bool(row.is_blacklisted),
        "is_updated": bool(row.is_updated),
        "foto_path": row.foto_path,
    }