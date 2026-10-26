"""Menjalankan semua uji tanpa pytest:   python tests/jalankan.py
Dengan pytest (pip install -r requirements-dev.txt):   pytest tests"""
import importlib
import sys
import time
import traceback
from pathlib import Path

import ahli

ahli_dir = Path(__file__).resolve().parent
lulus = gagal = lewat = 0
for berkas in sorted(ahli_dir.glob("test_*.py")):
    modul = importlib.import_module(berkas.stem)
    for nama in sorted(n for n in dir(modul) if n.startswith("test_")):
        t = time.time()
        try:
            getattr(modul, nama)()
            lulus += 1
            print(f"LULUS   {berkas.stem}.{nama}  ({time.time() - t:.1f} dtk)")
        except ahli.Lewati as e:
            lewat += 1
            print(f"LEWATI  {berkas.stem}.{nama}: {e}")
        except Exception:  # noqa: BLE001
            gagal += 1
            print(f"GAGAL   {berkas.stem}.{nama}")
            traceback.print_exc(limit=3)
print(f"\nLulus: {lulus} | Gagal: {gagal} | Dilewati: {lewat}")
sys.exit(1 if gagal else 0)
