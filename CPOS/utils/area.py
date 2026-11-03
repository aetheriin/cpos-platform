"""Data per area: akun di area biasa hanya melihat areanya; akun di area bertipe Mill kantor pusat (Admin › Organisasi ›
Mill, centang "Kantor pusat") melihat semua PT. Per menu, cakupan bisa diatur lain di Admin › Hak Akses › Cakupan data
(area sendiri / PT sendiri / semua PT / PT tertentu). Tanpa kode menu, dipakai menu halaman / API yang sedang dibuka
(diisi dekorator halaman() & izin() di utils/hak_akses.py). Aturannya ada di database (dbo.fn_UserScope /
fn_UserMenuScope / sp_UserScope) supaya sama untuk semua aplikasi."""
from flask import g, has_request_context

from utils.db_organisasi import area_menu_user, area_per_company, cakupan_user, company_area


def _kode_aktif():
    return getattr(g, "kode_menu", None) if has_request_context() else None


def _area_menu(user_id, kode_menu):
    """None = semua area · int = area sendiri saja · tuple = beberapa area. Tanpa aturan Lihat di menu itu -> bawaan."""
    area = area_menu_user(user_id, kode_menu)
    if not area:
        return None
    if area >= set(company_area()):
        return None
    c = cakupan_user(user_id)
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


def company_menu(user_id, kode_menu):
    """Untuk aplikasi lain (Analytics): PT dalam cakupan menu itu, None = semua PT."""
    pt = company_user(user_id, kode_menu)
    return None if pt is not None and set(pt) >= set(area_per_company()) else pt
