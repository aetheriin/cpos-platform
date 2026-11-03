// Daftar dashboard untuk tiap laporan. Kuncinya harus sama dengan id laporan di backend (backend/laporan/__init__.py).
// Untuk laporan baru: buat folder laporan/<nama>/Dashboard<Nama>.jsx lalu tambahkan satu baris impor dan satu baris di bawah.
import DashboardPalm from './palm/DashboardPalm'
import DashboardKasBank from './kas_bank/DashboardKasBank'
import { DashboardPvKpi, DashboardPvrKpi } from './penilaian'
import DashboardPiGt from './pi_gt/DashboardPiGt'
import LaporanPiPvr from './pi_pvr/LaporanPiPvr'
import DashboardPoPi from './po_pi/DashboardPoPi'
import DashboardPrPo from './pr_po/DashboardPrPo'
import DashboardTbs from './tbs/DashboardTbs'
import DashboardTbsMingguan from './tbs_mingguan/DashboardTbsMingguan'

export const DASHBOARD = {
  pr_po: DashboardPrPo,
  po_pi: DashboardPoPi,
  pi_gt: DashboardPiGt,
  penilaian_pvr: DashboardPvrKpi,
  penilaian_pv: DashboardPvKpi,
  palm_weighbridge: DashboardPalm,
  penerimaan_tbs: DashboardTbs,
  tbs_mingguan: DashboardTbsMingguan,
  cash_flow: DashboardKasBank,
  pi_pvr: LaporanPiPvr,
}
