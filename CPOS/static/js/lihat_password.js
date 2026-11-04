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
});
