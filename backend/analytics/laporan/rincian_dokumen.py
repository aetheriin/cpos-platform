"""Jendela rincian satu PR, PO, atau PI untuk laporan Purchase Request, Purchase Order, dan Purchase Invoice.

Isi diambil dari SP rincian (RINCIAN_SP) yang juga dipakai laporan Outstanding, jadi bentuk dan aturannya sama."""
from inti.filter import FilterTidakValid

_KET = ["Ket", "PerluPR", "KetPR", "KetPO"]
_KOLOM_ITEM = {
    "pr": [("kode", "Kode Barang", "teks"), ("nama", "Nama Barang", "teks"), ("qty", "Qty PR", "angka"), ("no_po", "No. PO", "teks"),
           ("no_pi", "No. PI", "teks"), ("ket", "Keterangan", "teks")],
    "po": [("kode", "Kode Barang", "teks"), ("nama", "Nama Barang", "teks"), ("qty", "Qty", "angka"), ("harga", "Harga Satuan", "angka"),
           ("nilai", "Jumlah", "angka"), ("no_pr", "No. PR", "teks"), ("tgl_pr", "Tanggal PR", "tanggal"), ("pembuat_pr", "PR Dibuat Oleh", "teks"),
           ("no_pi", "No. PI", "teks"), ("ket", "Keterangan", "teks")],
}
_NAMA = {"pr": "PR", "po": "PO", "pi": "PI"}


def rincian(jenis, kunci):
    """jenis: 'pr', 'po', atau 'pi'. kunci: {comp, no_dok} dari baris tabel detail."""
    # Diimpor di sini: laporan Outstanding (sumber modul ini) sendiri mengimpor pi_pvr, jadi impor di atas berputar
    from .hutang_piutang.dashboard import _bermakna, _dari_erp, _gabung_ket, _tabel_rinci
    from .hutang_piutang.sumber import ambil_rincian
    comp, no = str(kunci.get("comp") or "").strip(), str(kunci.get("no_dok") or "").strip()
    if not comp or not no:
        raise FilterTidakValid("Baris ini tidak punya perusahaan atau nomor dokumen.")
    kecil = f"{_NAMA[jenis]} · {comp}"
    if jenis == "pi":
        bagian, tabel, catatan = _dari_erp({"comp": comp, "kode": "PI", "no_dok": no}, "hutang")
        return {"kecil": kecil, "judul": no, "bagian": bagian, "tabel": tabel, "catatan": catatan}
    try:
        e = ambil_rincian(comp, "#PR" if jenis == "pr" else "#PO", no)
    except Exception as ex:   # jendela tetap terbuka dengan pesan, bukan galat
        return {"kecil": kecil, "judul": no, "bagian": [], "tabel": [], "catatan": f"Rincian dari ERP belum bisa dibaca: {ex}"}
    if e is None:
        return {"kecil": kecil, "judul": no, "bagian": [], "tabel": [], "catatan": "Rincian belum tersedia: SP rincian belum dibuat di database."}
    lama = "NoPI" not in e   # SP versi lama: belum punya mode PR, data kepala PO, dan kolom PI
    if lama and jenis == "pr":
        return {"kecil": kecil, "judul": no, "bagian": [], "tabel": [], "catatan": "Rincian PR belum tersedia: SP rincian di database perlu diperbarui."}
    if lama:
        e = e.assign(NoPI=None)
    e = e.sort_values(["Bagian", "Urut"])
    info = e[e["Bagian"] == "info"]
    isian = [{"label": x.Nama, "nilai": _bermakna(x.Ket), "tipe": "teks"} for x in info.itertuples() if _bermakna(x.Ket)]
    item = e[e["Bagian"] == "item"].rename(columns={"No": "kode", "Nama": "nama", "Qty": "qty", "Harga": "harga", "Nilai": "nilai",
                                                     "NoPO": "no_po", "NoPR": "no_pr", "TglPR": "tgl_pr", "PembuatPR": "pembuat_pr", "NoPI": "no_pi"})
    item = item.assign(ket=[_gabung_ket(r, _KET) for r in item.to_dict("records")])
    return {"kecil": kecil, "judul": no, "bagian": [{"judul": "Dokumen", "isian": isian}] if isian else [],
            "tabel": [_tabel_rinci(item, _KOLOM_ITEM[jenis], "Barang")],
            "catatan": None if len(e) else f"{_NAMA[jenis]} ini tidak ditemukan di ERP."}
