const dasar = (isi) =>
  function Ikon({ className = 'h-4 w-4' }) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        {isi}
      </svg>
    )
  }

export const IkonPanah = dasar(<path d="m6 9 6 6 6-6" />)
export const IkonTutup = dasar(<path d="M18 6 6 18M6 6l12 12" />)
export const IkonPerbesar = dasar(<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />)
export const IkonSegarkan = dasar(
  <>
    <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    <path d="M3 21v-5h5" />
  </>,
)
export const IkonKalender = dasar(
  <>
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4M8 2v4M3 10h18" />
  </>,
)
export const IkonKunci = dasar(
  <>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </>,
)
export const IkonPeringatan = dasar(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4.5M12 16h.01" />
  </>,
)
export const IkonLaporan = dasar(
  <>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </>,
)
export const IkonTabel = dasar(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 10h18M9 10v10" />
  </>,
)
export const IkonMatahari = dasar(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </>,
)
export const IkonBulan = dasar(<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />)
export const IkonMenu = dasar(<path d="M4 6h16M4 12h16M4 18h16" />)
export const IkonPanahKanan = dasar(<path d="m9 18 6-6-6-6" />)
