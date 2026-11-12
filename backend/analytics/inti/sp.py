"""Menjalankan stored procedure laporan satu kali per perusahaan, paralel, lalu menggabungkan hasilnya.

Satu panggilan per perusahaan, bukan 'ybs, sun, sjn' sekaligus: SP PR/PO bisa menautkan PO milik perusahaan lain kalau dipanggil bersamaan.
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd


def per_perusahaan(perusahaan, buka, perintah, parameter, kendali=None, boleh_kosong=False, tandai=False):
    """perintah: "EXEC nama ?, ?", atau fungsi comp -> teks SQL; parameter(comp) -> tuple. buka: fungsi koneksi (diberikan pemanggil supaya bisa diganti di tes).
    boleh_kosong: SP tanpa tabel hasil dianggap tidak ada baris. tandai: kolom __comp berisi perusahaan yang dipanggil."""

    def satu(comp):
        if kendali:
            kendali.periksa()
        conn = buka()
        try:
            cur = conn.cursor()
            if kendali:
                kendali.daftarkan(cur)
            cur.execute(perintah(comp) if callable(perintah) else perintah, *parameter(comp))
            while cur.description is None:
                if not cur.nextset():
                    if boleh_kosong:
                        return pd.DataFrame()
                    raise RuntimeError(f"SP tidak mengembalikan tabel hasil untuk {comp}")
            d = pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description])
            if tandai:
                d["__comp"] = comp
            return d
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=len(perusahaan)) as pool:
        bagian = [b for b in pool.map(satu, perusahaan) if len(b)]
    if not bagian:
        raise RuntimeError("Tidak ada data dari SP untuk rentang tanggal ini")
    return pd.concat(bagian, ignore_index=True)
