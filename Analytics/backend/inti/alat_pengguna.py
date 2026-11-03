"""Alat bantu tabel pengguna. Dijalankan dari folder backend dengan venv aktif:

    python -m inti.alat_pengguna cek          periksa koneksi, kolom, role, jenis hash, dan izin tabel pengguna
    python -m inti.alat_pengguna buat-admin   buat akun System Administrator pertama (kalau belum ada)

Keduanya tidak pernah menampilkan hash maupun kata sandi.
"""
import argparse
import getpass
import os
from collections import Counter

from . import konfigurasi, sandi as kata_sandi
from .pengguna import (
    KOLOM, KOLOM_COMPANY, KOLOM_IZIN, KOLOM_ROLE, ROLE_ADMIN, DataTidakValid, PenyimpanPengguna, PenyimpanTidakTersedia, adalah_admin, daftar_company_akun,
    kanonik_role, periksa_pengguna_baru,
)


def _cek_role(p, akun, keluar):
    """Tabel role, format penyimpanan role, dan role yang dipakai akun. Mengembalikan jumlah masalah."""
    masalah = 0
    try:
        p.periksa_role()
        role = p.daftar_role()
    except PenyimpanTidakTersedia as e:
        keluar(f"Tabel role '{p.tabel_role}': GAGAL dibaca (kolom yang dibutuhkan: {', '.join(KOLOM_ROLE)}). Akun baru belum bisa dibuat dari aplikasi.\nDetail: {e}")
        return 1
    keluar(f"Tabel role '{p.tabel_role}': {len(role)} role")
    for r in role:
        catatan = []
        if not r["aktif"]:
            catatan.append("nonaktif, tidak ditawarkan untuk akun baru")
        keluar(f"  {r['id']}: {r['nama']}" + (f"   <- {'; '.join(catatan)}" if catatan else ""))
    nama_sah = [r["nama"] for r in role]
    per_role = Counter(a.role for a in akun)
    keluar("Akun per role:")
    for nama, n in sorted(per_role.items(), key=lambda x: str(x[0])):
        if kanonik_role(nama, nama_sah) is None:
            keluar(f"  '{nama}': {n} akun   <- tidak cocok dengan nama maupun RoleId di tabel role; akun ini tidak melihat laporan apa pun")
            masalah += 1
        else:
            keluar(f"  {nama}: {n} akun")
    try:
        keluar(f"Kolom users.role menyimpan: {'RoleId (angka)' if p.role_disimpan() == 'id' else 'nama role'}   (akun baru disimpan dengan cara yang sama)")
    except PenyimpanTidakTersedia:
        pass
    return masalah


def _cek_company(p, akun, keluar):
    """Tabel company dan company yang dipakai akun. Mengembalikan jumlah masalah."""
    try:
        p.periksa_company()
        comp = p.daftar_company()
    except PenyimpanTidakTersedia as e:
        keluar(f"Tabel company '{p.tabel_company}': GAGAL dibaca (kolom yang dibutuhkan: {', '.join(KOLOM_COMPANY)}). Akun baru belum bisa dibuat dari aplikasi.\nDetail: {e}")
        return 1
    aktif = [c["nama"] for c in comp if c["aktif"]]
    mati = [c["nama"] for c in comp if not c["aktif"]]
    keluar(f"Tabel company '{p.tabel_company}': {len(aktif)} company aktif ({', '.join(aktif) or '-'})" + (f"; tidak aktif: {', '.join(mati)}" if mati else ""))
    masalah = 0
    for judul, sumber in (("laporan PR/PO dan PO/PI", konfigurasi.SUMBER_LAPORAN), ("laporan Deteksi Kecurangan Timbangan", konfigurasi.SUMBER_PALM)):
        dipanggil = p.company_menurut_jenis(sumber)
        keluar(f"  Perusahaan yang dipanggil {judul} (jenis '{sumber}'): {', '.join(dipanggil) or 'TIDAK ADA   <- laporannya tidak bisa dimuat; periksa CompType dan Status di tabel company, atau pengaturan .env'}")
        masalah += 0 if dipanggil else 1
    dikenal = {c["nama"].casefold() for c in comp}
    asing = sorted({c for a in akun for c in daftar_company_akun(a.company) if c.casefold() not in dikenal})
    if asing:
        keluar(f"  Company di akun yang tidak ada di tabel company: {', '.join(asing)}   <- tidak bisa dipilih lagi untuk akun baru")
        masalah += 1
    return masalah


def _cek_izin(p, akun, keluar):
    """Tabel izin (dipakai bersama aplikasi lain) dan hak tiap role pada laporan program ini. Mengembalikan jumlah masalah."""
    from laporan import SEMUA as LAPORAN   # diimpor di sini: paket laporan memakai paket inti ini, jadi tidak boleh diimpor di atas
    ids = list(LAPORAN)
    try:
        p.periksa_izin()
        role = p.izin_semua_role(ids)
        ini, lain = p.hitung_baris_izin(ids)
        asing = p.role_izin_asing()
    except PenyimpanTidakTersedia as e:
        keluar(f"Tabel izin '{p.tabel_izin}': GAGAL dibaca (kolom yang dibutuhkan: {', '.join(KOLOM_IZIN)}). Akun selain {ROLE_ADMIN} belum bisa melihat laporan.\n"
               f"Periksa DB_APP_TABEL_IZIN (mis. Main.dbo.PERMISSIONS kalau di database lain), kolomnya, dan izin akun database.\nDetail: {e}")
        return 1
    keluar(f"Tabel izin '{p.tabel_izin}': OK ({ini} baris untuk laporan program ini, {lain} baris halaman lain milik aplikasi lain, tidak disentuh)")
    masalah = 0
    jumlah_akun = Counter(kanonik_role(a.role, [r["nama"] for r in role]) for a in akun)
    for r in sorted(role, key=lambda r: r["nama"].casefold()):
        if not r["aktif"]:
            continue
        if adalah_admin(r["nama"]):
            keluar(f"  {r['nama']}: akses penuh (selalu, tidak bisa dibatasi)")
            continue
        boleh = [i for i in ids if r["izin"][i]]
        n = jumlah_akun.get(r["nama"], 0)
        catatan = ""
        if not boleh and n:
            catatan = f"   <- punya {n} akun tetapi belum punya akses ke laporan apa pun (atur di menu Permission Control)"
            masalah += 1
        keluar(f"  {r['nama']}: akses {len(boleh)} dari {len(ids)} laporan{catatan}")
    for nilai, n in sorted(asing.items()):
        keluar(f"  Role '{nilai}' di tabel izin ({n} baris) tidak cocok dengan nama role mana pun di tabel role   <- barisnya tidak berlaku untuk akun mana pun")
        masalah += 1
    izin_tulis = p.izin_tulis(tabel=p.tabel_izin, aksi=("INSERT", "UPDATE"))
    if izin_tulis is None:
        keluar("Izin tulis tabel izin: tidak bisa diperiksa (hanya didukung di SQL Server)")
    else:
        for aksi, ok in izin_tulis.items():
            keluar(f"Izin {aksi} pada tabel izin: {'ada' if ok else 'TIDAK ADA   <- tanpa ini menu Permission Control tidak bisa menyimpan (lihat database/permission.sql)'}")
            masalah += 0 if ok else 1
    return masalah


def _cek(p, keluar):
    keluar(f"Tabel pengguna: {p.tabel}")
    try:
        p.periksa()
        keluar(f"Koneksi dan kolom: OK ({', '.join(KOLOM)})")
        akun = p.daftar()
    except PenyimpanTidakTersedia as e:
        keluar(f"GAGAL membaca tabel. Periksa DB_APP_* dan DB_APP_TABEL di .env serta nama kolomnya.\nDetail: {e}")
        return 2
    keluar(f"Jumlah akun: {len(akun)}")
    masalah = _cek_role(p, akun, keluar)
    masalah += _cek_company(p, akun, keluar)
    masalah += _cek_izin(p, akun, keluar)
    for judul, nilai in (("Divisi", [a.divisi for a in akun]), ("Company", [c for a in akun for c in daftar_company_akun(a.company) or [None]])):
        isi = Counter(v or "(kosong)" for v in nilai).most_common(10)
        keluar(f"{judul} di tabel (contoh): " + (", ".join(f"{v} ({n})" for v, n in isi) if isi else "-"))
    jenis = Counter(kata_sandi.jenis_hash(a.sandi) for a in akun)
    keluar("Format hash kata sandi:")
    for j, n in jenis.items():
        if j is None:
            keluar(f"  tidak dikenal: {n} akun   <- tidak bisa masuk. Beri tahu jenis hash yang dipakai agar bisa ditambahkan")
            masalah += 1
        elif not kata_sandi.pustaka_tersedia(j):
            keluar(f"  {j}: {n} akun   <- pustaka {kata_sandi.PUSTAKA[j]} BELUM terpasang (pip install {kata_sandi.PUSTAKA[j]})")
            masalah += 1
        else:
            keluar(f"  {j}: {n} akun")
    try:
        keluar(f"Akun baru akan memakai hash: {kata_sandi.pilih_algoritma(jenis, os.environ.get('PASSWORD_HASH', 'auto'))}")
    except ValueError as e:
        keluar(f"PASSWORD_HASH salah isi: {e}")
        masalah += 1
    admin = sum(1 for a in akun if adalah_admin(a.role))
    keluar(f"System Administrator: {admin}" + ("   <- belum ada; buat dengan: python -m inti.alat_pengguna buat-admin" if admin == 0 else ""))
    izin = p.izin_tulis()
    if izin is None:
        keluar("Izin tulis: tidak bisa diperiksa (hanya didukung di SQL Server)")
    else:
        for aksi, ok in izin.items():
            keluar(f"Izin {aksi}: {'ada' if ok else 'TIDAK ADA   <- tanpa ini membuat, mengubah, atau menghapus akun dari aplikasi gagal (lihat database/users.sql)'}")
            masalah += 0 if ok else 1
    if p.id_otomatis() is False:
        keluar("Kolom id: bukan IDENTITY. Tidak masalah kalau id punya nilai bawaan (mis. NEWID()); kalau tidak, membuat akun baru akan gagal.")
    return 1 if masalah else 0


def _buat_admin(p, args, baca_sandi, baca_teks, keluar):
    try:
        ada = p.jumlah_admin()
        nama_admin = next((r["nama"] for r in p.daftar_role() if adalah_admin(r["nama"])), None)
        company_sah = p.company_aktif()
    except PenyimpanTidakTersedia as e:
        keluar(f"Tidak bisa membaca tabel pengguna, role, atau company: {e}")
        return 2
    if nama_admin is None:
        keluar(f"Gagal: tabel role '{p.tabel_role}' tidak punya role '{ROLE_ADMIN}'. Tambahkan dulu role itu di tabel role.")
        return 1
    if ada and not args.paksa:
        keluar(f"Sudah ada {ada} System Administrator. Buat akun lain lewat halaman Pengguna di aplikasi (atau pakai --paksa).")
        return 1
    username = baca_teks("Username: ")
    nama = baca_teks("Nama lengkap: ")
    divisi = baca_teks("Divisi: ")
    company = baca_teks(f"Company ({'/'.join(company_sah)}): ")
    sandi = baca_sandi("Password (minimal 8 karakter): ")
    if sandi != baca_sandi("Ulangi password: "):
        keluar("Gagal: kedua password berbeda.")
        return 1
    try:
        data = periksa_pengguna_baru(username, sandi, nama, nama_admin, divisi, company, [nama_admin], company_sah)
        algoritma = kata_sandi.pilih_algoritma(p.jenis_hash(), os.environ.get("PASSWORD_HASH", "auto"))
        baru = p.tambah(data, kata_sandi.hash_sandi(sandi, algoritma))
    except (DataTidakValid, ValueError) as e:
        keluar(f"Gagal: {e}")
        return 1
    except kata_sandi.PustakaHilang as e:
        keluar(f"Gagal: {e}")
        return 1
    except PenyimpanTidakTersedia as e:
        keluar(f"Gagal menyimpan ke tabel pengguna: {e}")
        return 2
    keluar(f"Akun System Administrator '{baru.username}' dibuat (hash {algoritma}).")
    return 0


def main(argv=None, penyimpan=None, baca_sandi=getpass.getpass, baca_teks=input, keluar=print):
    """Mengembalikan 0 kalau berhasil, 1 kalau ada masalah atau masukan salah, 2 kalau tabel tidak bisa dibaca."""
    ap = argparse.ArgumentParser(prog="python -m inti.alat_pengguna", description="Alat bantu tabel pengguna login dashboard.")
    sub = ap.add_subparsers(dest="perintah", required=True)
    sub.add_parser("cek", help="periksa tabel pengguna dan tabel role")
    sub.add_parser("buat-admin", help="buat System Administrator pertama").add_argument("--paksa", action="store_true", help="buat walau sudah ada administrator")
    args = ap.parse_args(argv)
    if penyimpan is None:
        from .db import get_connection_app
        penyimpan = PenyimpanPengguna(
            get_connection_app, tabel=konfigurasi.TABEL_PENGGUNA, tabel_role=konfigurasi.TABEL_ROLE,
            tabel_company=konfigurasi.TABEL_COMPANY, tabel_izin=konfigurasi.TABEL_IZIN, cache_detik=0, role_disimpan=os.environ.get("ROLE_DISIMPAN", "auto").strip().lower(),
        )
    if args.perintah == "cek":
        return _cek(penyimpan, keluar)
    return _buat_admin(penyimpan, args, baca_sandi, baca_teks, keluar)


if __name__ == "__main__":
    raise SystemExit(main())
