import { periksaPeriode, selisihHari, tglLengkap } from '../lib/data'
import Modal from './Modal'

function IsianPeriode({ mulai, akhir, onMulai, onAkhir, galat, maksHari }) {
  const hari = !galat ? selisihHari(mulai, akhir) + 1 : null
  return (
    <>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <label className="text-sm text-slate-600">
          Dari tanggal
          <input
            type="date"
            value={mulai}
            max={akhir || undefined}
            onChange={(e) => onMulai(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-sm text-slate-600">
          Sampai tanggal
          <input
            type="date"
            value={akhir}
            min={mulai || undefined}
            onChange={(e) => onAkhir(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      <p className={'mt-2 min-h-5 text-xs ' + (galat ? 'text-red-600' : 'text-slate-500')}>
        {galat ?? `Rentang ${hari} hari${maksHari ? ` (maksimal ${maksHari} hari)` : ''}.`}
      </p>
    </>
  )
}

// Dashboard lama tetap terlihat di belakang popup sampai data baru selesai. Selama memuat, popup hanya bisa ditutup dengan Batalkan.
export function PopupPeriode({ nama, mulai, akhir, onMulai, onAkhir, onMuat, onTutup, catatan, memuat, detik, onBatalkan, maksHari }) {
  const galat = periksaPeriode(mulai, akhir, maksHari)

  return (
    <Modal kecil="Periode data" judul="Ganti periode" onTutup={memuat ? () => {} : onTutup}>
      {memuat ? (
        <div className="py-2 text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-sky-600" aria-hidden="true" />
          <p role="status" className="mt-4 font-medium">
            Memuat data {nama}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            Mengambil data {tglLengkap(mulai)} sampai {tglLengkap(akhir)}. {detik} detik.
          </p>
          <p className="mt-1 text-xs text-slate-500">Dashboard yang sekarang tetap ada sampai data baru selesai dimuat.</p>
          <button type="button" onClick={onBatalkan} className="mt-4 rounded-md border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50">
            Batalkan
          </button>
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-600">
            Pilih rentang tanggal data yang ingin ditarik.
            Filter kembali ke awal untuk data yang baru.
          </p>
          {catatan && (
            <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {catatan}
            </p>
          )}
          <IsianPeriode mulai={mulai} akhir={akhir} onMulai={onMulai} onAkhir={onAkhir} galat={galat} maksHari={maksHari} />
          <p className="text-xs text-slate-500">Muat ulang data.</p>
          <div className="mt-4 flex justify-end gap-2 border-t border-slate-200 pt-4">
            <button type="button" onClick={onTutup} className="rounded-md border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50">
              Batal
            </button>
            <button
              type="button"
              disabled={Boolean(galat)}
              onClick={onMuat}
              className="rounded-md bg-sky-600 px-4 py-1.5 text-sm text-white hover:bg-sky-700 disabled:opacity-40"
            >
              Muat data
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
