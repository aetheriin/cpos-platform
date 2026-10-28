"""modules/item_request/mesin: bagian yang tidak butuh database / model (normalisasi teks, koneksi dari .env)."""
import os
import unittest
from unittest import mock

from modules.item_request import mesin


class TestMesin(unittest.TestCase):
    def test_normalize_sama_dengan_aplikasi_asli(self):
        self.assertEqual(mesin.normalize_text("  Survey JASA-Instalasi  (CCTV) "), "survey jasa instalasi cctv")
        self.assertEqual(mesin.normalize_text(None), "none")

    def test_koneksi_dari_env(self):
        with mock.patch.dict(os.environ, {"ITEM_REQUEST_SERVER": "172.20.111.4", "ITEM_REQUEST_DB": "Main",
                                          "ITEM_REQUEST_USER": "sa", "ITEM_REQUEST_PASSWORD": "a}b"}, clear=True):
            teks = mesin._connection_string()
        self.assertIn("SERVER=172.20.111.4;DATABASE=Main;UID=sa;PWD={a}}b};", teks)

    def test_tanpa_env_tidak_ada_koneksi(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(mesin._connection_string(), "")
            with self.assertRaises(RuntimeError):
                mesin.get_connection()

    def test_bobot_skor_tidak_berubah(self):
        # rumus aplikasi asli: 0.45 semantik + 0.30 TF-IDF + 0.15 fuzzy + 0.10 urutan kata
        import inspect
        sumber = inspect.getsource(mesin.ItemNLP.search)
        for bobot in ("0.45 * semantic_scores", "0.30 * tfidf_scores", "0.15 * fuzzy_scores", "0.10 * sort_scores"):
            self.assertIn(bobot, sumber)
