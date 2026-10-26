import ahli

from inti.sesi import Sesi


class Jam:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_daftar_berisi_waktu_masuk_aktivitas_terakhir_dan_asal_tanpa_kode_cookie():
    jam = Jam(1000.0)
    s = Sesi(umur_detik=3600, jam=jam)
    a = s.buat("budi", asal="IP 10.0.0.5")
    jam.t = 1100.0
    s.buat("sari")
    jam.t = 1200.0
    assert s.ambil(a) == "budi"
    d = s.daftar()
    assert [x["username"] for x in d] == ["sari", "budi"]
    budi = d[1]
    assert (budi["masuk"], budi["terakhir"], budi["kedaluwarsa"], budi["asal"]) == (1000.0, 1200.0, 4600.0, "IP 10.0.0.5")
    assert budi["id"] == Sesi.id_sesi(a) and a not in str(d)


def test_cabut_id_mengakhiri_satu_sesi_dengan_alasan_dan_membersihkan_datanya():
    dibuang = []
    s = Sesi(umur_detik=3600, jam=Jam(1000.0), saat_berakhir=lambda k, u: dibuang.append(u))
    a, b = s.buat("budi"), s.buat("sari")
    assert s.cabut_id(Sesi.id_sesi(a), "Dikeluarkan admin") == "budi"
    assert s.ambil(a) is None and s.alasan(a) == "Dikeluarkan admin" and s.ambil(b) == "sari"
    assert dibuang == ["budi"] and [x["username"] for x in s.daftar()] == ["sari"]
    assert s.cabut_id(Sesi.id_sesi(a)) is None


def test_sesi_kedaluwarsa_tidak_tampil():
    jam = Jam(1000.0)
    s = Sesi(umur_detik=60, jam=jam)
    s.buat("budi")
    jam.t = 2000.0
    assert s.daftar() == []


def test_endpoint_admin_daftar_dan_paksa_keluar():
    import api

    asli = api.sesi_login
    api.sesi_login = Sesi(umur_detik=3600)
    try:
        admin_kode = api.sesi_login.buat("admin")
        budi_kode = api.sesi_login.buat("budi", asal="IP 10.0.0.9")
        admin = {"username": "admin", "_sid": admin_kode}
        api.penyimpan_pengguna.cari = lambda u: None
        d = api.daftar_sesi(user=admin)
        assert {x["username"]: x["sesi_ini"] for x in d} == {"admin": True, "budi": False}
        assert all(admin_kode not in str(x) and budi_kode not in str(x) for x in d)
        id_budi = next(x["id"] for x in d if x["username"] == "budi")
        id_admin = next(x["id"] for x in d if x["username"] == "admin")
        for id_, kode in ((id_admin, 400),):
            try:
                api.cabut_sesi(id_, user=admin)
                assert False
            except api.HTTPException as e:
                assert ahli.kode(e) == kode
        assert api.cabut_sesi(id_budi, user=admin)["username"] == "budi"
        assert api.sesi_login.ambil(budi_kode) is None and "administrator" in api.sesi_login.alasan(budi_kode)
        try:
            api.cabut_sesi(id_budi, user=admin)
            assert False
        except api.HTTPException as e:
            assert ahli.kode(e) == 404
    finally:
        api.sesi_login = asli
        api.penyimpan_pengguna.__dict__.pop("cari", None)
