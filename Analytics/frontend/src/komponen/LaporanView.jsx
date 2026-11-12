import { memo, useEffect, useState } from 'react'
import { batalkanPekerjaan, mulaiMuat, statusPekerjaan } from '../api'
import { rentangTgl, tglLengkap, waktuDari } from '../lib/data'
import { LaporanAktif } from '../lib/tampilan'
import { IkonKalender, IkonPeringatan, IkonSegarkan } from './Ikon'
import { PopupPeriode } from './PanelPeriode'

export function LayarMemuat({ nama, mulai, akhir, detik, onBatalkan }) {
  return (
    <section className="mx-auto mt-10 max-w-lg rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
      <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-sky-600" aria-hidden="true" />
      <h1 className="mt-4 text-lg font-semibold">Memuat data {nama}</h1>
      <p className="mt-1 text-sm text-slate-600">
        Mengambil data {tglLengkap(mulai)} sampai {tglLengkap(akhir)}. {detik} detik.
      </p>
      <button type="button" onClick={onBatalkan} className="mt-4 rounded-md border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50">
        Batalkan
      </button>
    </section>
  )
}

// Pemuatan pertama gagal atau dibatalkan. Bentuknya sama dengan kartu "Sesi CPOS berakhir" (App.jsx); pesannya dari server, sudah dalam
// bahasa pengguna (gudang.pesan_galat). Tanggal hanya bisa diganti lewat popup setelah data tampil.
export function LayarGagal({ pesan, onCoba }) {
  return (
    <section role="alert" className="mx-auto mt-10 max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
      <span aria-hidden="true" className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600">
        <IkonPeringatan className="h-6 w-6" />
      </span>
      <h1 className="mt-4 text-lg font-semibold">Data belum bisa ditampilkan</h1>
      <p className="mt-1 text-sm text-slate-600">{pesan}</p>
      <button type="button" onClick={onCoba} className="mt-5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700">
        Coba lagi
      </button>
    </section>
  )
}

const tombolBar = 'inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 disabled:opacity-40'

// segar: { detik } selama muat ulang berjalan. pesanSegar: galat muat ulang; data lama tetap dipakai.
export function BarAtas({ dataset, onGanti, onSegarkan, segar = null, onBatalSegar, pesanSegar = '', onCobaLagi, onTutupPesan }) {
  return (
    <div className="mb-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
        <span className="text-slate-600">
          Data tersedia {rentangTgl(dataset.mulai, dataset.akhir)}
          {dataset.dimuat ? ` · diambil ${waktuDari(dataset.dimuat)}` : ' · memakai data yang sudah dimuat'}
        </span>
        <span className="inline-flex flex-wrap items-center gap-2">
          {segar && (
            <span role="status" className="text-xs text-slate-500">
              Memperbarui data... {segar.detik} detik
            </span>
          )}
          {segar && (
            <button type="button" onClick={onBatalSegar} className={tombolBar}>
              Batalkan
            </button>
          )}
          {onSegarkan && (
            <button type="button" onClick={onSegarkan} disabled={Boolean(segar)} title="Ambil ulang data periode ini" className={tombolBar}>
              <IkonSegarkan className={'h-3.5 w-3.5 ' + (segar ? 'animate-spin' : '')} />
              {segar ? 'Memuat ulang...' : 'Muat ulang data'}
            </button>
          )}
          <button type="button" onClick={onGanti} disabled={Boolean(segar)} className={tombolBar}>
            <IkonKalender className="h-3.5 w-3.5" />
            Ganti periode
          </button>
        </span>
      </div>
      {pesanSegar && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>
            <strong>Data belum diperbarui:</strong> {pesanSegar} Data lama tetap ditampilkan.
          </span>
          <span className="inline-flex gap-2">
            <button type="button" onClick={onCobaLagi} className="rounded-md border border-red-200 bg-white px-3 py-1 text-xs hover:bg-red-100">
              Coba lagi
            </button>
            <button type="button" onClick={onTutupPesan} className="rounded-md border border-red-200 bg-white px-3 py-1 text-xs hover:bg-red-100">
              Tutup
            </button>
          </span>
        </div>
      )}
      {(dataset.peringatan ?? []).map((teks) => (
        <div key={teks} role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <strong>Peringatan data:</strong> {teks}
        </div>
      ))}
    </div>
  )
}

// Satu laporan. Tetap terpasang (disembunyikan) saat pindah laporan, jadi data dan filternya tidak hilang.
// Dibuka -> langsung dimuat dengan tanggal bawaan -> dashboard. Setelah tampil, dashboard tidak pernah disembunyikan lagi:
// Ganti periode dan Muat ulang data berjalan di atasnya, dan data lama tetap dipakai kalau gagal.
function LaporanView({ laporan, Dashboard, onStatus }) {
  const [mulai, setMulai] = useState(laporan.mulai_bawaan)
  const [akhir, setAkhir] = useState(laporan.akhir_bawaan)
  const [fase, setFase] = useState('memuat')
  const [panel, setPanel] = useState(false)
  const [pekerjaan, setPekerjaan] = useState(null)
  const [dataset, setDataset] = useState(null)
  const [catatan, setCatatan] = useState('')
  const [detik, setDetik] = useState(0)
  const [sumber, setSumber] = useState('periode') // 'periode' (popup tanggal) atau 'segar' (Muat ulang data)

  // Dibatalkan: tanpa data, layar Coba lagi; dengan data, kembali ke dashboard (popup terbuka lagi kalau asalnya dari popup).
  const kembali = () => {
    if (!dataset) {
      setCatatan('Pemuatan dibatalkan.')
      setFase('gagal')
      return
    }
    setFase('siap')
    setPanel(sumber === 'periode')
  }

  const selesai = (p, baru) => {
    setDataset({
      dataId: p.data_id,
      mulai: p.mulai,
      akhir: p.akhir,
      dimuat: p.dimuat_pada ?? (baru ? new Date().toISOString() : null),
      peringatan: p.catatan?.peringatan ?? [],
    })
    setFase('siap')
    setPanel(false)
    setCatatan('')
  }

  // Dengan data lama, pesannya muncul di tempat pemuatan dimulai (popup, atau bar atas untuk muat ulang).
  const gagalMuat = (pesan, dari) => {
    setCatatan(pesan)
    if (!dataset) {
      setFase('gagal')
      return
    }
    setFase('siap')
    setPanel(dari === 'periode')
  }

  const muat = (dari = 'periode') => {
    setCatatan('')
    setDetik(0)
    setSumber(dari)
    setFase('memuat')
    jalankan(dari)
  }

  const jalankan = async (dari) => {
    const segar = dari === 'segar'
    try {
      const p = await mulaiMuat(laporan.id, segar ? dataset.mulai : mulai, segar ? dataset.akhir : akhir, segar)
      setPekerjaan(p)
      if (p.status === 'selesai') selesai(p, segar)
      else if (p.status !== 'berjalan') gagalMuat(p.pesan || 'Pemuatan tidak berjalan.', dari)
    } catch (e) {
      gagalMuat(e.message, dari)
    }
  }

  useEffect(() => {
    if (fase !== 'memuat' || !pekerjaan) return undefined
    let berhenti = false
    const timer = setInterval(async () => {
      try {
        const s = await statusPekerjaan(pekerjaan.id)
        if (berhenti) return
        setDetik(Math.floor(s.detik))
        if (s.status === 'selesai') selesai(s, true)
        else if (s.status === 'gagal') gagalMuat(s.pesan, sumber)
        else if (s.status === 'dibatalkan') kembali()
      } catch (e) {
        if (!berhenti) gagalMuat(e.message, sumber)
      }
    }, 1000)
    return () => {
      berhenti = true
      clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fase, pekerjaan?.id])

  useEffect(() => {
    onStatus(laporan.id, fase === 'memuat' ? 'memuat' : dataset ? 'siap' : null)
  }, [fase, dataset]) // eslint-disable-line react-hooks/exhaustive-deps

  // fase awal sudah 'memuat', jadi cukup kirim permintaannya
  useEffect(() => {
    jalankan('periode')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const batalkan = async () => {
    try {
      if (pekerjaan) await batalkanPekerjaan(pekerjaan.id)
    } catch {
      // tetap kembali; hasilnya dibuang server
    }
    kembali()
  }

  // Data sudah tidak ada di server (mis. server dimulai ulang): muat lagi periode yang sama
  const dataHilang = () => {
    const d = dataset
    setDataset(null)
    setPanel(false)
    if (d) {
      setMulai(d.mulai)
      setAkhir(d.akhir)
    }
    setCatatan('')
    setDetik(0)
    setSumber('periode')
    setFase('memuat')
    mulaiMuat(laporan.id, d?.mulai ?? mulai, d?.akhir ?? akhir, false)
      .then((p) => {
        setPekerjaan(p)
        if (p.status === 'selesai') selesai(p, false)
        else if (p.status !== 'berjalan') gagalMuat(p.pesan || 'Pemuatan tidak berjalan.', 'periode')
      })
      .catch((e) => gagalMuat(e.message, 'periode'))
  }

  const bukaPanel = () => {
    setMulai(dataset.mulai)
    setAkhir(dataset.akhir)
    setCatatan('')
    setFase('siap')
    setPanel(true)
  }

  const tutupPopup = () => {
    setPanel(false)
    setCatatan('')
  }

  let layar = null
  if (!dataset) {
    if (fase === 'memuat') {
      layar = <LayarMemuat nama={laporan.nama} mulai={mulai} akhir={akhir} detik={detik} onBatalkan={batalkan} />
    } else {
      layar = <LayarGagal pesan={catatan} onCoba={() => muat('periode')} />
    }
  }

  const memuatPeriode = fase === 'memuat' && sumber === 'periode'
  const memuatUlang = fase === 'memuat' && sumber === 'segar'

  return (
    <div>
      {layar}
      {dataset && (
        <div>
          <BarAtas
            dataset={dataset}
            onGanti={bukaPanel}
            onSegarkan={() => muat('segar')}
            segar={memuatUlang ? { detik } : null}
            onBatalSegar={batalkan}
            pesanSegar={sumber === 'segar' && fase === 'siap' ? catatan : ''}
            onCobaLagi={() => muat('segar')}
            onTutupPesan={() => setCatatan('')}
          />
          {/* key tidak memuat id data: muat ulang tidak membuat dashboard baru, jadi filter dan halaman tabel tetap */}
          <LaporanAktif.Provider value={laporan.id}>
            <Dashboard key={`${dataset.mulai}|${dataset.akhir}`} dataId={dataset.dataId} onDataHilang={dataHilang} />
          </LaporanAktif.Provider>
        </div>
      )}
      {dataset && panel && (
        <PopupPeriode
          nama={laporan.nama}
          mulai={mulai}
          akhir={akhir}
          onMulai={setMulai}
          onAkhir={setAkhir}
          onMuat={() => muat('periode')}
          onTutup={tutupPopup}
          catatan={catatan}
          memuat={memuatPeriode}
          detik={detik}
          onBatalkan={batalkan}
          maksHari={laporan.maks_hari}
        />
      )}
    </div>
  )
}

export default memo(LaporanView)
