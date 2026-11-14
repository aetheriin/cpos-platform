import { angka, rentangTgl } from '../../lib/data'

const satu = new Intl.NumberFormat('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// Naik atau turun dalam persen, ditulis sebagai kalimat. Penjualan yang naik ditandai hijau, turun merah.
function Perubahan({ kini, lalu, periode }) {
  if (lalu == null || kini == null || lalu === 0) return <p className="mt-1 text-sm text-slate-600">Belum ada pembanding</p>
  const beda = ((kini - lalu) / Math.abs(lalu)) * 100
  if (Math.abs(beda) < 0.05) return <p className="mt-1 text-sm text-slate-600">Sama dengan {periode}</p>
  const naik = beda > 0
  return (
    <p className="mt-1 text-sm text-slate-600">
      <span className={'font-semibold tabular-nums ' + (naik ? 'text-emerald-700' : 'text-red-700')}>
        {naik ? '▲ naik' : '▼ turun'} {satu.format(Math.abs(beda))}%
      </span>{' '}
      dibanding {periode}
    </p>
  )
}

// Selisih jumlah (bukan persen): untuk hitungan kecil seperti jumlah pengangkut.
function selisih(kini, lalu) {
  if (lalu == null) return ''
  const d = kini - lalu
  return d === 0 ? ', sama seperti sebelumnya' : `, ${d > 0 ? 'bertambah' : 'berkurang'} ${angka.format(Math.abs(d))}`
}

function AngkaUtama({ judul, nilai, satuan, keterangan, children }) {
  return (
    <div className="min-w-0">
      <h2 className="text-sm text-slate-600">{judul}</h2>
      <p className="mt-0.5 leading-none">
        <span className="text-3xl font-semibold tabular-nums text-slate-900">{nilai}</span>
        <span className="ml-1.5 text-base text-slate-600">{satuan}</span>
      </p>
      {children}
      {keterangan && <p className="mt-0.5 text-xs text-slate-600">{keterangan}</p>}
    </div>
  )
}

// Ringkasan periode: dua angka utama (berat dan jumlah pengiriman) dengan perubahannya, lalu tiga angka pendukung dalam kalimat.
export default function Ringkasan({ kpi, banding }) {
  const lalu = banding?.kpi
  const periode = banding ? rentangTgl(banding.mulai, banding.akhir) : ''
  return (
    <section aria-label="Ringkasan" className="rounded-xl border border-slate-200 bg-white px-5 py-4">
      <div className="grid gap-x-10 gap-y-4 sm:grid-cols-2">
        <AngkaUtama judul="Total berat bersih" nilai={satu.format(kpi.netto / 1000)} satuan="ton">
          <Perubahan kini={kpi.netto} lalu={lalu?.netto} periode={periode} />
        </AngkaUtama>
        <AngkaUtama judul="Jumlah pengiriman" nilai={angka.format(kpi.rit)} satuan="truk">
          <Perubahan kini={kpi.rit} lalu={lalu?.rit} periode={periode} />
        </AngkaUtama>
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 border-t border-slate-100 pt-3 text-sm text-slate-700">
        <li>
          Rata-rata muatan <strong className="font-semibold tabular-nums text-slate-900">{kpi.per_rit == null ? '–' : `${satu.format(kpi.per_rit / 1000)} ton`}</strong> per truk
        </li>
        <li>
          <strong className="font-semibold tabular-nums text-slate-900">{angka.format(kpi.pengangkut)}</strong> pengangkut{selisih(kpi.pengangkut, lalu?.pengangkut)}
        </li>
        <li>
          <strong className="font-semibold tabular-nums text-slate-900">{angka.format(kpi.pembeli)}</strong> pembeli{selisih(kpi.pembeli, lalu?.pembeli)}
        </li>
      </ul>
    </section>
  )
}
