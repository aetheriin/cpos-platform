// Company sebuah akun, boleh lebih dari satu. Di server disimpan di satu kolom, dipisah koma ("ORI, RCM").
export const pisahCompany = (teks) =>
  String(teks ?? '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean)

// Kotak centang company untuk formulir akun. opsi: nama company dari tabel company; terpilih: daftar nama; onUbah(daftarBaru).
// Company akun yang sudah tidak aktif tetap ditampilkan (dan tetap tercentang) supaya tidak hilang diam-diam saat akun disunting.
export default function PilihCompany({ opsi, terpilih, onUbah, kelas = '' }) {
  const sama = (a, b) => a.toLowerCase() === b.toLowerCase()
  const daftar = [...opsi, ...terpilih.filter((t) => !opsi.some((o) => sama(o, t)))]
  const dipilih = (c) => terpilih.some((t) => sama(t, c))
  const ganti = (c) => onUbah(dipilih(c) ? terpilih.filter((t) => !sama(t, c)) : [...terpilih, c])
  return (
    <fieldset className={'rounded-md border border-slate-300 px-3 pt-1 pb-3 ' + kelas}>
      <legend className="px-1 text-xs font-medium text-slate-600">Company (pilih satu atau lebih)</legend>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 pt-1 sm:grid-cols-3">
        {daftar.map((c) => (
          <label key={c} className="flex min-w-0 cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={dipilih(c)} onChange={() => ganti(c)} className="h-4 w-4 shrink-0 rounded border-slate-300 accent-sky-700" />
            <span className="truncate">{c}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
