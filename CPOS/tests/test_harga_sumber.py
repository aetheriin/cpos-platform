"""utils/harga_sumber: pilihan sumber harga (DailyPrice / tabel luar Main.dbo.HARGA) dari .env."""
import os
import unittest
from unittest import mock

import types

from flask import Flask

from utils import harga_sumber

ENV_HARGA = {"SQLSERVER_PRICE_SERVER": "172.20.111.4", "SQLSERVER_PRICE_DATABASE": "Main",
             "SQLSERVER_PRICE_UID": "rekap", "SQLSERVER_PRICE_PWD": "ra}hasia", "SQLSERVER_PRICE_TABLE": "Main.dbo.HARGA"}


class TestSumber(unittest.TestCase):
    def test_tanpa_env_pakai_dailyprice(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(harga_sumber.aktif())
            self.assertEqual(harga_sumber.nama_sumber(), "CPOS dbo.DailyPrice")

    def test_env_lengkap(self):
        with mock.patch.dict(os.environ, ENV_HARGA, clear=True):
            self.assertTrue(harga_sumber.aktif())
            teks = harga_sumber._connection_string()
            self.assertIn("SERVER=172.20.111.4;DATABASE=Main;UID=rekap;PWD={ra}}hasia};", teks)
            self.assertEqual(harga_sumber._tabel(), "[Main].[dbo].[HARGA]")
            self.assertEqual(harga_sumber.nama_sumber(), "Main.dbo.HARGA @ 172.20.111.4")

    def test_nama_tabel_tidak_valid(self):
        with mock.patch.dict(os.environ, {**ENV_HARGA, "SQLSERVER_PRICE_TABLE": "HARGA; DROP TABLE x"}, clear=True):
            with self.assertRaises(ValueError):
                harga_sumber._tabel()

    def test_galat_koneksi_jadi_503(self):
        class Galat(Exception):
            pass
        app = Flask(__name__)

        @harga_sumber.tangani_galat
        def gagal():
            raise Galat("08001", "Login timeout expired")

        # pyodbc tiruan (tes lain mengganti modul pyodbc dengan MagicMock)
        with app.app_context(), mock.patch.dict(os.environ, ENV_HARGA, clear=True), \
                mock.patch.object(harga_sumber, "pyodbc", types.SimpleNamespace(Error=Galat)):
            jawab, kode = gagal()
            self.assertEqual(kode, 503)
            self.assertIn("Main.dbo.HARGA", jawab.get_json()["error"])
