"""Galat validasi yang menyebut isian form-nya.

raise GalatIsian("NIK harus 16 digit angka.", "nik") -> respons {"error": ..., "kolom": "nik"}; layar menampilkan
pesannya di bawah isian bernama "nik" (static/js/form_rapi.js) selain notifikasi. GalatIsian turunan ValueError,
jadi penangkap ValueError yang lama tetap berlaku."""


class GalatIsian(ValueError):
    def __init__(self, pesan, kolom):
        super().__init__(pesan)
        self.kolom = kolom


def isi_galat(e):
    """Isi JSON respons galat: pesan + nama isian bila ada."""
    isi = {"error": str(e)}
    if getattr(e, "kolom", None):
        isi["kolom"] = e.kolom
    return isi
