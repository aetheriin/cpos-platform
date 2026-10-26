"""Mode gabungan CPOS (CPOS_URL diisi): login, sesi, dan hak laporan mengikuti CPOS (inti/cpos.py)."""
import ahli  # noqa: F401
from types import SimpleNamespace

import pytest

import api
from inti import cpos, konfigurasi

try:
    from fastapi import HTTPException
except ImportError:
    HTTPException = Exception

DARI_CPOS = {"id": 7, "username": "ho", "nama": "Andi Wijaya", "role": "Head Office", "company": ["SUN", "YBS"],
             "laporan": ["pr_po", "pi_gt", "tidak_ada"], "sid": "abc"}


@pytest.fixture
def mode_cpos(monkeypatch):
    monkeypatch.setattr(konfigurasi, "CPOS_URL", "http://cpos.test")
    jawaban = {"isi": DARI_CPOS}
    monkeypatch.setattr(cpos, "pengguna", lambda cookie, ua=None, ip=None: jawaban["isi"] if cookie == "kue" else None)
    return jawaban


def permintaan(cookie="kue"):
    return SimpleNamespace(cookies={"wb_sesi": cookie} if cookie else {}, headers={}, client=SimpleNamespace(host="10.0.0.5"))


def test_pengguna_dan_laporan_dari_cpos(mode_cpos):
    u = api.pengguna_saat_ini(sesi_id=None, request=permintaan())
    assert (u["username"], u["admin"], u["company"]) == ("ho", False, "SUN, YBS")
    assert u["laporan"] == [i for i in api.LAPORAN if i in ("pr_po", "pi_gt")]      # id yang tidak dikenal Analytics dibuang
    assert u["_sid"] == "cpos:abc"


def test_sesi_cpos_tidak_berlaku_401(mode_cpos):
    with pytest.raises(HTTPException) as e:
        api.pengguna_saat_ini(sesi_id=None, request=permintaan(cookie=None))
    assert e.value.status_code == 401


def test_cpos_mati_503(mode_cpos, monkeypatch):
    def mati(*a, **k):
        raise cpos.CposTidakTersedia("connection refused")
    monkeypatch.setattr(cpos, "pengguna", mati)
    with pytest.raises(HTTPException) as e:
        api.pengguna_saat_ini(sesi_id=None, request=permintaan())
    assert e.value.status_code == 503


def test_login_sendiri_dan_admin_ditutup(mode_cpos):
    with pytest.raises(HTTPException) as e:
        api.masuk(api.PermintaanLogin(username="ho", sandi="x"), SimpleNamespace(), None)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        api.wajib_admin(api.pengguna_saat_ini(sesi_id=None, request=permintaan()))
    assert e.value.status_code == 403
    assert api.status()["cpos"] is True
