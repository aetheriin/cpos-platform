import { ambilRincian } from '../api'
import { useAmbil } from '../lib/ambil'
import { formatSel } from '../lib/data'
import Modal from './Modal'
import TabelBaris from './TabelBaris'
import { Memuat } from './Keadaan'

// Rincian satu baris tabel detail. buka: { jenis, kunci, judul } atau null.
export default function JendelaRincian({ laporanId, dataId, filter, buka, onTutup, onDataHilang }) {
  const { data, galat } = useAmbil(
    JSON.stringify([laporanId, dataId, filter, buka]),
    (sinyal) => ambilRincian(laporanId, dataId, filter, buka.jenis, buka.kunci, sinyal),
    onDataHilang,
  )
  return (
    <Modal judul={data?.judul ?? buka.judul} kecil={data?.kecil} onTutup={onTutup} lebar="max-w-6xl">
      {galat && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{galat.message}</div>}
      {!data && !galat && <Memuat teks="Memuat rincian..." />}
      {data && (
        <div className="space-y-5">
          {data.bagian.length > 0 && (
            <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              {data.bagian.map((b) => (
                <section key={b.judul} className="min-w-0">
                  <h3 className="mb-1.5 border-b border-slate-200 pb-1 text-xs font-medium text-slate-500">{b.judul}</h3>
                  <dl className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-3 gap-y-1 text-sm">
                    {b.isian.map((i) => (
                      <div key={i.label} className="contents">
                        <dt className="text-slate-600">{i.label}</dt>
                        <dd className="break-words tabular-nums text-slate-900">{formatSel(i.nilai, i.tipe)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          )}
          {(data.tabel ?? []).map((t) => (
            <section key={t.judul} className="min-w-0">
              <h3 className="mb-1.5 text-xs font-medium text-slate-500">{t.judul} ({t.baris.length})</h3>
              {t.baris.length > 0
                ? <TabelBaris kolom={t.kolom} baris={t.baris} />
                : <p className="text-sm text-slate-600">Belum ada.</p>}
            </section>
          ))}
          {data.catatan && <p className="text-xs text-amber-800">{data.catatan}</p>}
        </div>
      )}
    </Modal>
  )
}
