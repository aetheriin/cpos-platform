import { useState } from 'react'

// Bukan atribut title: tooltip bawaan browser lambat, tidak muncul di layar sentuh, dan tidak muncul di atas SVG.
// Dekat tepi layar, kotaknya rata kiri atau kanan supaya tidak keluar layar.
const LEBAR = 224 // px, sama dengan w-56

export default function Info({ teks, label }) {
  const [posisi, setPosisi] = useState('left-1/2 -translate-x-1/2')
  const ukur = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const tengah = r.left + r.width / 2
    setPosisi(tengah + LEBAR / 2 > window.innerWidth - 8 ? 'right-0' : tengah - LEBAR / 2 < 8 ? 'left-0' : 'left-1/2 -translate-x-1/2')
  }
  return (
    <span className="group relative ml-1 inline-flex align-[-2px]" onMouseEnter={ukur} onFocus={ukur}>
      <button
        type="button"
        aria-label={label ? `Penjelasan ${label}` : 'Penjelasan'}
        className="cursor-help rounded-full text-slate-400 hover:text-slate-600 focus:outline-none focus-visible:text-slate-600 focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="8" cy="8" r="6.5" />
          <path d="M8 7.2v4M8 4.8v.01" strokeLinecap="round" />
        </svg>
      </button>
      <span
        role="tooltip"
        className={
          'pointer-events-none absolute top-full z-30 mt-1.5 hidden w-56 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs leading-snug font-normal text-slate-700 shadow-md group-focus-within:block group-hover:block ' +
          posisi
        }
      >
        {teks}
      </span>
    </span>
  )
}
