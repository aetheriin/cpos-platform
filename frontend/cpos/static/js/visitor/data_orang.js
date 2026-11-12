// Halaman Data Orang tanpa tab: tampilkan isi tab "orang" lalu pancing pemuatan data oleh personel.js.
const kontenOrang = document.querySelector('[data-tab-content="orang"]');
kontenOrang.classList.remove('hidden');
window.dispatchEvent(new CustomEvent('tabChange', { detail: 'orang' }));