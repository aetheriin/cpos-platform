"""Daftar laporan yang tampil di menu samping.

Untuk menambah laporan baru:
1. Buat folder laporan/<nama>/ berisi sumber.py (SP dan pembersihan), ukuran.py (rumus), dashboard.py (grafik dan
   tabel), dan __init__.py yang membuat satu objek LAPORAN (lihat pr_po/__init__.py sebagai contoh).
2. Tambahkan satu baris impor dan satu elemen di SEMUA di bawah.
"""
from .kas_bank import LAPORAN as _kas_bank
from .palm import LAPORAN as _palm
from .penilaian_pv import LAPORAN as _penilaian_pv
from .penilaian_pvr import LAPORAN as _penilaian_pvr
from .pi_gt import LAPORAN as _pi_gt
from .pi_pvr import LAPORAN as _pi_pvr
from .po_pi import LAPORAN as _po_pi
from .pr_po import LAPORAN as _pr_po
from .tbs import LAPORAN as _tbs
from .tbs_mingguan import LAPORAN as _tbs_mingguan

SEMUA = {l.id: l for l in (_pr_po, _po_pi, _pi_gt, _penilaian_pvr, _penilaian_pv, _palm, _tbs_mingguan, _tbs, _pi_pvr, _kas_bank)}
