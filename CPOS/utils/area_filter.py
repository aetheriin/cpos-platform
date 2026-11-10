def sql_area(kolom, id_area):
    """(' AND kolom = ?', [id]) / (' AND kolom IN (?, ?)', [...]) / ('', []) untuk semua area."""
    if id_area is None:
        return "", []
    if isinstance(id_area, (tuple, list, set, frozenset)):
        ids = sorted(id_area) or [-1]          # daftar kosong = tidak ada site yang cocok
        return f" AND {kolom} IN ({', '.join('?' * len(ids))})", ids
    return f" AND {kolom} = ?", [id_area]

def area_cocok(id_area, nilai):
    """True bila site `nilai` termasuk area user."""
    if id_area is None:
        return True
    if isinstance(id_area, (tuple, list, set, frozenset)):
        return nilai in id_area
    return nilai == id_area
