import buatDashboardPenilaian from './DashboardPenilaian'

// Pembuat yang dinilai di Excel Penilaian PVR dan Penilaian PV (sama dengan PVR_/PV_PENILAIAN_PEMBUAT di backend)
export const DashboardPvrKpi = buatDashboardPenilaian({
  laporanId: 'penilaian_pvr', judul: 'PVR KPI', voucher: 'PVR', tabelBobot: 'Bobot_PVR', dinilai: ['Dinda', 'Dwi', 'Ferdinan', 'Intan'],
})
export const DashboardPvKpi = buatDashboardPenilaian({
  laporanId: 'penilaian_pv', judul: 'PV KPI', voucher: 'PV', tabelBobot: 'Bobot_PV', dinilai: ['Agnes', 'Ana', 'Anisa', 'Mega', 'Nuri', 'Syely', 'Yusni'],
})
