from flask import g, has_request_context
from utils.db_organisasi import area_menu_banyak, area_menu_user, area_per_company, cakupan_user, company_area, daftar_area, daftar_company

def _kode_aktif():
    return getattr(g, "kode_menu", None) if has_request_context() else None

def _area_menu(user_id, kode_menu, area=None, c=None):
    """None = semua area · int = area sendiri saja · tuple = beberapa area. Tanpa aturan Lihat di menu itu -> bawaan."""
    area = area_menu_user(user_id, kode_menu) if area is None else area
    if not area:
        return None
    if area >= set(company_area()):
        return None
    c = cakupan_user(user_id) if c is None else c
    if c and area == {c["OwnAreaID"]}:
        return c["OwnAreaID"]
    return tuple(sorted(area))

def area_data(user_id, kode_menu=None):
    """None = semua area · int = area sendiri · tuple = area-area dalam cakupan menu."""
    kode = kode_menu or _kode_aktif()
    if kode and area_menu_user(user_id, kode):
        return _area_menu(user_id, kode)
    c = cakupan_user(user_id)
    if c is None or c["AllAreas"]:
        return None
    return c["OwnAreaID"]

def company_user(user_id, kode_menu=None):
    """PT dalam cakupan: None = semua PT, atau frozenset kode PT."""
    area = area_data(user_id, kode_menu)
    if area is None:
        return None
    peta = company_area()
    return frozenset(peta.get(a) for a in (area if isinstance(area, tuple) else (area,)) if peta.get(a))

def company_site(user_id, harus_ada_site=False):
    """PT aktif dalam cakupan user, selain PT yang areanya hanya kantor pusat: [{id_company, nama}].
    Untuk harga dan laporan Pembelian TBS (kodenya = CompName di Main.dbo.Company ERP). harus_ada_site=True: hanya PT yang
    punya site aktif (form Isi Harga di Dashboard); tanpa itu PT yang belum punya area juga ikut (mis. ORI, RCM di ERP)."""
    pt = company_user(user_id)
    area, site = set(), set()
    for a in daftar_area():
        if a["is_active"]:
            area.add(a["id_company"])
            if not a["is_pusat"]:
                site.add(a["id_company"])
    return [{"id_company": c["id_company"], "nama": c["nama"]} for c in daftar_company()
            if c["is_active"] and (pt is None or c["id_company"] in pt)
            and (c["id_company"] in site or (not harus_ada_site and c["id_company"] not in area))]

def _ke_company(area):
    if area is None:
        return None
    peta = company_area()
    return frozenset(peta.get(a) for a in (area if isinstance(area, tuple) else (area,)) if peta.get(a))

def company_menu_banyak(user_id, kode_menu):
    """Sama dengan company_menu untuk banyak menu sekaligus: {kode: frozenset PT / None}. Cakupan user dan aturan semua menu dibaca
    sekali (dua query), bukan dua query per menu."""
    c = cakupan_user(user_id)
    bawaan = None if c is None or c["AllAreas"] else c["OwnAreaID"]
    aturan = area_menu_banyak(user_id, kode_menu)
    semua = set(area_per_company())
    hasil = {}
    for kode in kode_menu:
        area = _area_menu(user_id, kode, aturan[kode], c) if aturan.get(kode) else bawaan
        pt = _ke_company(area)
        hasil[kode] = None if pt is not None and set(pt) >= semua else pt
    return hasil

def company_menu(user_id, kode_menu):
    """Untuk aplikasi lain (Analytics): PT dalam cakupan menu itu, None = semua PT."""
    pt = company_user(user_id, kode_menu)
    return None if pt is not None and set(pt) >= set(area_per_company()) else pt
