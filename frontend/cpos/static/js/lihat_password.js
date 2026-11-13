// Tombol mata di kotak password: klik -> password terlihat / tersembunyi lagi
document.querySelectorAll('[data-lihat-password]').forEach(tombol => {
    const input = tombol.parentElement.querySelector('input');
    const atur = (lihat) => {
        input.type = lihat ? 'text' : 'password';
        tombol.innerHTML = `<i class="fa-regular ${lihat ? 'fa-eye-slash' : 'fa-eye'}"></i>`;
        tombol.title = lihat ? 'Sembunyikan password' : 'Tampilkan password';
        tombol.setAttribute('aria-label', tombol.title);
    };
    tombol.addEventListener('click', () => {
        atur(input.type === 'password');
        input.focus();
    });
    input.form?.addEventListener('reset', () => atur(false));   // form dibuka lagi: password tersembunyi

    // Peringatan Caps Lock: username otomatis huruf besar, jadi Caps Lock mudah terbawa menyala saat mengetik password
    const peringatan = tombol.closest('div')?.parentElement?.querySelector('[data-capslock]');
    if (!peringatan) return;
    const periksa = e => { if (e.getModifierState) peringatan.classList.toggle('hidden', !e.getModifierState('CapsLock')); };
    input.addEventListener('keydown', periksa);
    input.addEventListener('keyup', periksa);
    input.addEventListener('mousedown', periksa);
    input.addEventListener('blur', () => peringatan.classList.add('hidden'));
});
