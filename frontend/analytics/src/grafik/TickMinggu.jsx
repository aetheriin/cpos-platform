// Dua baris: rentang tanggal dan tahun. Kalau minggunya banyak (padat), diputar miring.
// ringkas: hanya tanggal awal minggu, untuk grafik yang sempit.
export default function TickMinggu({ x, y, payload, data, terpilih, onPilih, padat, ringkas }) {
  const w = data.find((d) => d.singkat === payload.value)
  const indeks = w?.indeks
  const aktif = terpilih === indeks
  const gaya = { fontSize: 11, fill: '#475569', opacity: terpilih != null && !aktif ? 0.4 : 1, fontWeight: aktif ? 700 : 400 }
  return (
    <g transform={`translate(${x},${y})`} style={{ cursor: 'pointer' }} onClick={() => onPilih(indeks)}>
      {padat ? (
        <text transform="rotate(-35)" textAnchor="end" x={0} y={0} dy={10} {...gaya}>
          {payload.value} {w?.tahun}
        </text>
      ) : (
        <>
          <text textAnchor="middle" x={0} y={0} dy={14} {...gaya}>
            {ringkas ? String(payload.value).split(' sd ')[0] : payload.value}
          </text>
          <text textAnchor="middle" x={0} y={0} dy={27} {...gaya}>
            {w?.tahun}
          </text>
        </>
      )}
    </g>
  )
}
