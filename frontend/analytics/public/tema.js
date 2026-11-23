// Bawaan sama dengan CPOS (terang), bukan tema browser, supaya isi laporan tidak berbeda dari sidebar CPOS
try {
  document.documentElement.dataset.tema = localStorage.getItem('tema') === 'gelap' ? 'gelap' : 'terang'
} catch (e) {
  document.documentElement.dataset.tema = 'terang'
}
