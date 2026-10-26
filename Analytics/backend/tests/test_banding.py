import ahli  # noqa: F401
import pandas as pd

from inti.banding import jendela_sebelumnya, lengkap


def test_jendela_sebelumnya_sama_panjang_dan_tepat_sebelum():
    assert jendela_sebelumnya("2026-10-01", "2026-10-19") == (pd.Timestamp("2026-09-12"), pd.Timestamp("2026-09-30"))
    assert jendela_sebelumnya("2026-10-13", "2026-10-19") == (pd.Timestamp("2026-10-06"), pd.Timestamp("2026-10-12"))


def test_hanya_dibandingkan_kalau_seluruh_jendela_ada_di_data():
    assert lengkap("2026-09-12", "2026-09-01") and lengkap("2026-09-12", "2026-09-12")
    assert not lengkap("2026-09-12", "2026-09-13") and not lengkap("2026-09-12", None)
