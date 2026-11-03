import { potong } from '../lib/data'

// Label sumbu kategori yang bisa diklik untuk memfilter nilainya. Teks panjang dipotong; isi lengkap tampil saat disorot.
export default function TickKlik({ x, y, payload, onPilih, terpilih = [], maks = 34, miring = false }) {
  const nilai = String(payload.value)
  const aktif = terpilih.includes(nilai)
  const redup = terpilih.length > 0 && !aktif
  return (
    <g transform={`translate(${x},${y})`} style={{ cursor: 'pointer' }} onClick={(e) => onPilih(nilai, e)}>
      <title>{nilai}</title>
      <text
        transform={miring ? 'rotate(-35)' : undefined}
        x={miring ? 0 : -6}
        y={0}
        dy={miring ? 10 : 4}
        textAnchor="end"
        fontSize={miring ? 10 : 11}
        fill={aktif ? '#0f172a' : '#475569'}
        fontWeight={aktif ? 600 : 400}
        opacity={redup ? 0.45 : 1}
      >
        {potong(nilai, maks)}
      </text>
    </g>
  )
}
