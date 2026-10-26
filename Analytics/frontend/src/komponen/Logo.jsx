import { useId } from 'react'

// Sama dengan favicon public/logo.svg: kalau salah satu diubah, ubah juga yang lain. Warnanya tidak ikut mode gelap.
export default function Logo({ className = 'h-8 w-8' }) {
  const id = useId()
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0284c7" />
          <stop offset="1" stopColor="#075985" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${id})`} />
      <rect x="7.5" y="17" width="4.5" height="8" rx="1.5" fill="#fff" fillOpacity=".5" />
      <rect x="13.75" y="12" width="4.5" height="13" rx="1.5" fill="#fff" fillOpacity=".75" />
      <rect x="20" y="7" width="4.5" height="18" rx="1.5" fill="#fff" />
    </svg>
  )
}
