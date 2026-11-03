// Huruf awal nama: "Admin Satu" -> "AS", "Admin" -> "A", kosong -> "?".
const inisial = (nama) => {
  const kata = String(nama ?? '').trim().split(/\s+/).filter(Boolean)
  if (kata.length === 0) return '?'
  return (kata[0][0] + (kata.length > 1 ? kata[kata.length - 1][0] : '')).toUpperCase()
}

export default function Avatar({ nama, ukuran = 'h-8 w-8 text-xs' }) {
  return (
    <span aria-hidden="true" className={'flex shrink-0 items-center justify-center rounded-full bg-sky-100 font-semibold text-sky-800 ' + ukuran}>
      {inisial(nama)}
    </span>
  )
}
