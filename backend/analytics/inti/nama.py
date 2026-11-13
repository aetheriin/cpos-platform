"""Merapikan teks nama untuk pilihan filter: spasi berlebih dibuang, ejaan yang hanya beda huruf besar-kecil disatukan."""
import re

PEMISAH = ", "   # pemisah nama yang digabung dalam satu sel (status_dokumen.gabung)


def _spasi(v):
    return re.sub(r"\s+", " ", str(v)).strip()


def orang(seri):
    """Nama orang: 'kevin  muliawan' / 'KEVIN MULIAWAN' -> 'Kevin Muliawan'. Sel berisi beberapa nama tetap dipisah koma."""
    return seri.fillna("").map(lambda s: PEMISAH.join(dict.fromkeys(_spasi(n).title() for n in str(s).split(",") if _spasi(n))))


def seragam(seri):
    """Kategori, supplier: ejaan yang beda huruf besar-kecil saja diganti ejaan yang paling sering muncul."""
    s = seri.fillna("").map(_spasi)
    kunci = s.str.casefold()
    terbanyak = s.groupby(kunci).agg(lambda x: x.value_counts().index[0])
    return kunci.map(terbanyak).where(s != "", s)


def pisah(teks):
    """Sel berisi beberapa nama -> daftar nama."""
    return [n for n in str(teks).split(PEMISAH) if n]


