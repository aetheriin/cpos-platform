// Grafik Recharts bisa difokus keyboard (panah kiri/kanan menggeser tooltip), tapi tanpa nama pembaca layar hanya menyebut "application".
// Namanya diambil dari judul kartu tempat grafik itu berada, untuk semua grafik sekaligus.
function beriNama(svg) {
  if (svg.hasAttribute('aria-label')) return
  const kepala = svg.closest('section, article, [role="dialog"]')?.querySelector('h2, h3')?.cloneNode(true)
  kepala?.querySelectorAll('button, [role="tooltip"], .sr-only').forEach((e) => e.remove())   // tanpa teks penjelasan (i)
  const judul = kepala?.textContent.trim()
  svg.setAttribute('aria-label', judul ? `Grafik ${judul}` : 'Grafik')
}

export function pasangNamaGrafik() {
  const periksa = () => document.querySelectorAll('svg.recharts-surface[tabindex]:not([aria-label])').forEach(beriNama)
  new MutationObserver(periksa).observe(document.body, { childList: true, subtree: true })
  periksa()
}
