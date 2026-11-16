import { memo } from 'react'

// Satu bentuk untuk semua grafik peringkat satu seri di Analytics: satu baris per nama, batang dan nilainya di sebelah kanan. Tiap baris adalah tombol, jadi bisa dipilih dengan klik, Tab, dan Enter; Ctrl/Shift menambah pilihan.
// data: [{ nama, nilai, teks, kanan?, judul?, warna? }]. teks = nilai yang ditulis di ujung batang; kanan = keterangan kecil di kanan nama.
// kosong: elemen yang tampil kalau data kosong. catatan: satu baris di bawah daftar (mis. "+7 pengangkut lain, 199,9 ton").
function Peringkat({ data, terpilih = [], onPilih, warna = '#0369a1', kosong = null, catatan = null }) {
  if (data.length === 0) return kosong
  const maks = Math.max(...data.map((d) => Math.abs(d.nilai)), 1)
  const adaPilihan = terpilih.length > 0
  const adaKanan = data.some((d) => d.kanan)
  // Kolom nama selebar nama terpanjang (maks 40%), supaya batang tidak jauh dari nama yang pendek
  const panjang = Math.max(...data.map((d) => String(d.nama).length))
  const kolom = `minmax(0, min(40%, ${panjang + 1}ch)) minmax(0, 1fr)` + (adaKanan ? ' auto' : '')
  return (
    <div className="flex h-full flex-col">
      {/* Satu baris per nama (nama | batang + angka) supaya peringkat 10 nama tidak memakan banyak tempat; nama panjang dipotong, lengkapnya saat disorot */}
      <ul>
        {data.map((d) => {
          const aktif = terpilih.includes(d.nama)
          return (
            <li key={d.nama}>
              <button
                type="button"
                onClick={(e) => onPilih?.(d.nama, e)}
                aria-pressed={aktif}
                title={d.judul ?? d.nama}
                className={'grid w-full items-center gap-2 rounded-md px-1 py-0.5 text-left text-xs hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500'}
                style={{ gridTemplateColumns: kolom, opacity: adaPilihan && !aktif ? 0.45 : 1 }}
              >
                <span className={'truncate ' + (aktif ? 'font-semibold text-slate-900' : 'text-slate-700')}>{d.nama}</span>
                <span className="flex min-w-0 items-center gap-2">
                  <span className="h-2.5 min-w-1 shrink rounded-sm transition-[width] duration-400 motion-reduce:transition-none"
                    style={{ width: `${(Math.abs(d.nilai) / maks) * 65}%`, background: d.warna ?? warna }} />
                  <span className="shrink-0 tabular-nums text-slate-700">{d.teks}</span>
                </span>
                {/* Keterangan kedua (mis. harga per kg) di kolom sendiri, rata kanan, supaya sejajar antarbaris */}
                {adaKanan && <span className="text-right tabular-nums text-slate-500">{d.kanan}</span>}
              </button>
            </li>
          )
        })}
      </ul>
      {catatan && <p className="mt-auto pt-2 text-xs text-slate-500">{catatan}</p>}
    </div>
  )
}

export default memo(Peringkat)
