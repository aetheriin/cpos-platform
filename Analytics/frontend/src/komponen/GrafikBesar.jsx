import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IkonTutup } from './Ikon'

const ZOOM_MIN = 1
const ZOOM_MAKS = 8
const LANGKAH = 1.25
const BATAS_GESER = 4 // px; gerakan lebih kecil dari ini tetap dihitung klik (cross filter tetap jalan)

// Grafik yang sama dengan di kartu, selebar layar. Zoom memperlebar grafik (sumbu x mendapat ruang untuk semua label), lalu
// digeser dengan menyeret atau scroll horizontal. Roda mouse: zoom di posisi kursor.
export default function GrafikBesar({ judul, onTutup, children }) {
  const [zoom, setZoom] = useState(1)
  const wadah = useRef(null)
  const seret = useRef(null)
  const zoomRef = useRef(1)

  const ubahZoom = (baru, x) => {
    const el = wadah.current
    const lama = zoomRef.current
    baru = Math.min(ZOOM_MAKS, Math.max(ZOOM_MIN, baru))
    if (!el || baru === lama) return
    const titik = x ?? el.clientWidth / 2
    const tujuan = ((el.scrollLeft + titik) * baru) / lama - titik
    zoomRef.current = baru
    setZoom(baru)
    requestAnimationFrame(() => {
      el.scrollLeft = tujuan
    })
  }

  useEffect(() => {
    const tekan = (e) => {
      if (e.key === 'Escape') onTutup()
      else if (e.key === '+' || e.key === '=') ubahZoom(zoomRef.current * LANGKAH)
      else if (e.key === '-') ubahZoom(zoomRef.current / LANGKAH)
      else if (e.key === '0') ubahZoom(1)
    }
    document.addEventListener('keydown', tekan)
    const lama = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', tekan)
      document.body.style.overflow = lama
    }
  }, [onTutup])

  // Listener wheel dipasang manual karena onWheel React bersifat pasif (tidak bisa preventDefault)
  useEffect(() => {
    const el = wadah.current
    if (!el) return undefined
    const roda = (e) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return // geser horizontal touchpad: biarkan scroll biasa
      e.preventDefault()
      const x = e.clientX - el.getBoundingClientRect().left
      ubahZoom(zoomRef.current * (e.deltaY < 0 ? LANGKAH : 1 / LANGKAH), x)
    }
    el.addEventListener('wheel', roda, { passive: false })
    return () => el.removeEventListener('wheel', roda)
  }, [])

  // Sumbu y ikut terlihat saat digeser: tiap bingkai sumbu kiri digeser sejauh scroll, sumbu kanan sejauh sisa scroll, dengan latar
  // supaya garis grafik tidak menimpa angkanya. Dipasang langsung ke SVG Recharts karena sumbu itu bagian dari gambar grafik.
  useEffect(() => {
    let jalan = true
    const tempel = () => {
      const el = wadah.current
      if (!jalan) return
      if (el) {
        const sisa = el.scrollWidth - el.clientWidth - el.scrollLeft
        // Recharts 3 menaruh angka sumbu di lapisan tersendiri (recharts-yAxis-tick-labels); sumbu kanan rata kiri (text-anchor start)
        el.querySelectorAll('.recharts-yAxis-tick-labels').forEach((g) => {
          const kanan = g.querySelector('.recharts-cartesian-axis-tick-value')?.getAttribute('text-anchor') === 'start'
          g.setAttribute('transform', `translate(${kanan ? -sisa : el.scrollLeft},0)`)
          if (!g.querySelector(':scope > rect.latar-sumbu')) {
            const kotak = g.getBBox()
            const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
            r.setAttribute('class', 'latar-sumbu')
            r.setAttribute('x', kotak.x - 4)
            r.setAttribute('y', kotak.y - 4)
            r.setAttribute('width', kotak.width + 8)
            r.setAttribute('height', kotak.height + 8)
            g.prepend(r)
          }
        })
      }
      requestAnimationFrame(tempel)
    }
    requestAnimationFrame(tempel)
    return () => {
      jalan = false
    }
  }, [])

  const mulaiSeret = (e) => {
    if (e.button !== 0) return
    seret.current = { x: e.clientX, kiri: wadah.current.scrollLeft, geser: false }
  }
  const gerak = (e) => {
    const s = seret.current
    if (!s) return
    const dx = e.clientX - s.x
    if (!s.geser && Math.abs(dx) < BATAS_GESER) return
    s.geser = true
    wadah.current.scrollLeft = s.kiri - dx
  }
  const selesaiSeret = () => {
    const s = seret.current
    seret.current = null
    if (s?.geser) {
      // klik yang menyusul seretan tidak boleh memfilter
      const tahan = (e) => e.stopPropagation()
      window.addEventListener('click', tahan, { capture: true, once: true })
      setTimeout(() => window.removeEventListener('click', tahan, { capture: true }), 0)
    }
  }

  const tombol = 'rounded-md border border-slate-200 px-2.5 py-1 text-sm tabular-nums hover:bg-slate-50 disabled:opacity-40'
  return createPortal(
    <div className="fixed inset-0 z-50 flex bg-slate-900/40 p-3 sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onTutup()}>
      <div role="dialog" aria-modal="true" aria-label={judul} className="flex min-w-0 flex-1 flex-col rounded-xl bg-white p-4 shadow-xl">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-medium">{judul}</h2>
          <button type="button" className={tombol} onClick={() => ubahZoom(zoom / LANGKAH)} disabled={zoom <= ZOOM_MIN} aria-label="Perkecil">
            −
          </button>
          <span className="w-12 text-center text-sm tabular-nums text-slate-600">{Math.round(zoom * 100)}%</span>
          <button type="button" className={tombol} onClick={() => ubahZoom(zoom * LANGKAH)} disabled={zoom >= ZOOM_MAKS} aria-label="Perbesar">
            +
          </button>
          <button type="button" className={tombol} onClick={() => ubahZoom(1)} disabled={zoom === 1}>
            Reset
          </button>
          <button type="button" onClick={onTutup} aria-label="Tutup" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100">
            <IkonTutup className="h-5 w-5" />
          </button>
        </div>
        <div
          ref={wadah}
          className={'min-h-0 flex-1 overflow-x-auto overflow-y-hidden ' + (zoom > 1 ? 'cursor-grab active:cursor-grabbing' : '')}
          onMouseDown={mulaiSeret}
          onMouseMove={gerak}
          onMouseUp={selesaiSeret}
          onMouseLeave={selesaiSeret}
        >
          <div className="grafik-besar h-full select-none" style={{ width: `${zoom * 100}%` }}>
            {children}
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">Scroll untuk zoom, seret untuk menggeser. Tombol + dan − juga bisa dipakai, 0 untuk reset.</p>
      </div>
    </div>,
    document.body,
  )
}
