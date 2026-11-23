// ===== ADMIN > AKSES ADMIN =====
// Superadmin memberi pengguna non-admin hak membuka halaman Admin (menu ADM_*): Lihat = buka halaman, Ubah = simpan perubahan.
// Penerima dipilih per Peran / Jabatan / Departemen / User. Gerbang grup Admin diisi server (routes/admin.py _sinkron_grup_admin).
(() => {
    if (!document.getElementById('aaDaftar')) return;     // template lama (tanpa tab Per orang) tetap jalan
    const el = id => document.getElementById(id);
    const JENIS = [['ROLE', 'Peran'], ['LEVEL', 'Jabatan'], ['DEPT', 'Departemen'], ['USER', 'User']];
    let DATA = { halaman: [], jabatan: [], departemen: [] };
    let aktif = null;          // halaman yang sedang diatur
    let aturan = [];           // salinan kerja aturan halaman aktif
    let asli = '[]';
    let barisUser = null;
    let pemicuUser = null;     // tombol yang membuka kotak pilih user, untuk mengembalikan fokus

    const bentuk = () => JSON.stringify(aturan.map(a => ({ jenis: a.jenis, id_target: String(a.id_target ?? ''), lihat: !!a.lihat, ubah: !!a.ubah })));
    const berubah = () => aktif && bentuk() !== asli;
    const opsi = (daftar, nilai) => daftar.map(([v, l]) => `<option value="${escapeHtml(v)}"${String(v) === String(nilai) ? ' selected' : ''}>${escapeHtml(l)}</option>`).join('');
    const jab = () => DATA.jabatan.map(j => [j.id, j.nama]);
    const dept = () => DATA.departemen.map(d => [d.id, d.nama]);
    const kosong = (teks, nilai) => `<option value=""${nilai ? '' : ' selected'}>${teks}</option>`;
    const belumLengkap = a => (a.jenis === 'ROLE' ? String(a.id_target || '|').split('|').some(x => !x) : !a.id_target);

    function targetAwal(jenis) {
        // Baris baru mulai kosong agar tidak ada departemen/jabatan yang ikut tersimpan tanpa sengaja
        return jenis === 'ROLE' ? '|' : '';
    }

    function perbaruiTanda() {
        const ya = berubah();
        el('aaBerubah').classList.toggle('hidden', !ya);
        el('aaSimpan').disabled = !ya;
    }

    const judulGrup = (h, i, daftar) => (h.grup && (i === 0 || daftar[i - 1].grup !== h.grup)
        ? `<p class="px-3 pt-3 pb-1 text-[11px] font-bold text-slate-500 uppercase tracking-wider">${escapeHtml(h.grup)}</p>` : '');

    function tampilDaftar() {
        el('aaDaftar').innerHTML = DATA.halaman.map((h, i, daftar) => {
            const pilih = aktif && aktif.kode === h.kode;
            const n = h.aturan.length;
            return `${judulGrup(h, i, daftar)}<button type="button" class="pohon-baris ${pilih ? 'pohon-baris-aktif' : ''} pl-3" data-kode="${escapeHtml(h.kode)}"${pilih ? ' aria-current="true"' : ''}>
                <span class="pohon-ikon pohon-ikon-2"><i class="fa-solid ${escapeHtml(h.ikon)}" aria-hidden="true"></i></span>
                <span class="flex-1 min-w-0 truncate font-semibold">${escapeHtml(h.nama)}</span>
                <span class="pohon-aturan ${n ? '' : 'pohon-aturan-kosong'}" title="${n ? `${n} penerima` : 'Belum diberikan'}">${n || '–'}</span>
            </button>`;
        }).join('');
    }

    function sasaran(a, i) {
        if (a.jenis === 'ROLE') {
            const [d, j] = String(a.id_target || '|').split('|');
            return `<div class="flex flex-wrap gap-1">
                <select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="role_dept" aria-label="Departemen">${kosong('Pilih departemen', d)}${opsi(dept(), d)}</select>
                <select class="input-field py-1 text-xs w-32" data-i="${i}" data-f="role_jab" aria-label="Jabatan">${kosong('Pilih jabatan', j)}${opsi(jab(), j)}</select></div>`;
        }
        if (a.jenis === 'LEVEL') return `<select class="input-field py-1 text-xs w-40" data-i="${i}" data-f="id_target" aria-label="Jabatan">${kosong('Pilih jabatan', a.id_target)}${opsi(jab(), a.id_target)}</select>`;
        if (a.jenis === 'DEPT') return `<select class="input-field py-1 text-xs w-40" data-i="${i}" data-f="id_target" aria-label="Departemen">${kosong('Pilih departemen', a.id_target)}${opsi(dept(), a.id_target)}</select>`;
        return `<button type="button" class="btn-secondary btn-sm max-w-full truncate" data-pilih-user="${i}">
            <i class="fa-solid fa-user mr-1" aria-hidden="true"></i>${escapeHtml(a.id_target ? a.nama_target : 'Pilih user')}</button>`;
    }

    // Nama penerima untuk pembaca layar, mis. "Lihat untuk Departemen Teknologi Informasi"
    function namaPenerima(a) {
        const cari = (daftar, id) => (daftar.find(x => String(x.id) === String(id)) || {}).nama || '';
        if (a.jenis === 'USER') return a.id_target ? `User ${a.nama_target}` : 'user yang belum dipilih';
        if (a.jenis === 'LEVEL') return a.id_target ? `Jabatan ${cari(DATA.jabatan, a.id_target)}` : 'jabatan yang belum dipilih';
        if (a.jenis === 'DEPT') return a.id_target ? `Departemen ${cari(DATA.departemen, a.id_target)}` : 'departemen yang belum dipilih';
        const [d, j] = String(a.id_target || '|').split('|');
        return `Peran ${cari(DATA.departemen, d)} ${cari(DATA.jabatan, j)}`;
    }

    function tampilAturan() {
        perbaruiTanda();
        if (!aktif) return;
        el('aaTabel').innerHTML = aturan.map((a, i) => `
            <tr class="hover:bg-slate-50">
                <td class="table-cell"><select class="input-field py-1 text-xs w-32" data-i="${i}" data-f="jenis" aria-label="Diberikan ke">${opsi(JENIS, a.jenis)}</select></td>
                <td class="table-cell">${sasaran(a, i)}</td>
                <td class="table-cell text-center"><input type="checkbox" class="w-4 h-4" data-i="${i}" data-f="lihat" aria-label="Lihat untuk ${escapeHtml(namaPenerima(a))}"${a.lihat ? ' checked' : ''}></td>
                <td class="table-cell text-center">${aktif.bisa_ubah
                    ? `<input type="checkbox" class="w-4 h-4" data-i="${i}" data-f="ubah" aria-label="Ubah untuk ${escapeHtml(namaPenerima(a))}"${a.ubah ? ' checked' : ''}>`
                    : '<span class="text-xs text-slate-500" title="Halaman ini hanya bisa dilihat">Tidak ada</span>'}</td>
                <td class="table-cell text-right"><button type="button" class="aturan-tombol hover:!text-red-600" data-hapus="${i}" title="Hapus penerima" aria-label="Hapus penerima"><i class="fa-solid fa-trash-can" aria-hidden="true"></i></button></td>
            </tr>`).join('') || `<tr><td colspan="5" class="table-cell text-center text-sm text-slate-500 py-10">
                Belum ada penerima. Halaman ini hanya terbuka untuk superadmin.</td></tr>`;
    }

    async function pilih(kode) {
        if (aktif && aktif.kode === kode) return;
        if (berubah() && !await Dialog.konfirmasi({ judul: 'Buang perubahan?', pesan: `Perubahan akses ${aktif.nama} belum disimpan.`, teksYa: 'Buang', bahaya: true })) return;
        aktif = DATA.halaman.find(h => h.kode === kode) || null;
        aturan = aktif ? aktif.aturan.map(a => ({ ...a, id_target: a.id_target ?? '' })) : [];
        asli = bentuk();
        el('aaJudul').textContent = aktif ? aktif.nama : 'Pilih halaman di kiri';
        el('aaKeterangan').textContent = aktif && !aktif.bisa_ubah ? 'Halaman ini hanya bisa dilihat, tidak ada yang bisa diubah.' : '';
        el('aaTambah').disabled = !aktif;
        tampilDaftar();
        tampilAturan();
    }

    async function muat(kodePilih) {
        const res = await ambilJson('/api/admin/akses-admin');
        if (res.error) { el('aaDaftar').innerHTML = `<p class="px-4 py-6 text-sm text-red-700">${escapeHtml(res.error)}</p>`; return; }
        DATA = res;
        if (!res.siap) {
            el('aaDaftar').innerHTML = '<p class="px-4 py-6 text-sm text-slate-600">Menu Admin belum ada di database. Hubungi IT untuk menjalankan perubahan 031_menu_admin.sql.</p>';
            return;
        }
        aktif = null;
        tampilDaftar();
        await pilih(kodePilih || res.halaman[0].kode);
    }

    const sempit = () => window.matchMedia('(max-width: 1023px)').matches;
    const gerak = () => (window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

    el('aaDaftar').addEventListener('click', async e => {
        const b = e.target.closest('[data-kode]');
        if (!b) return;
        await pilih(b.dataset.kode);
        if (sempit() && aktif && aktif.kode === b.dataset.kode) el('aaForm').scrollIntoView({ behavior: gerak(), block: 'start' });
    });

    // Tambah penerima: pilih dulu jenisnya (Departemen, Jabatan, Peran, atau User)
    function tambah(jenis) {
        if (jenis === 'USER') {
            aturan.push({ jenis: 'USER', id_target: '', nama_target: '', lihat: true, ubah: false, _baru: true });
            tampilAturan();
            return bukaUser(aturan.length - 1);
        }
        aturan.push({ jenis, id_target: targetAwal(jenis), nama_target: '', lihat: true, ubah: false });
        tampilAturan();
        const i = aturan.length - 1;
        const isian = el('aaTabel').querySelector(`[data-i="${i}"][data-f="id_target"], [data-i="${i}"][data-f="role_dept"]`);
        if (isian) isian.focus();
    }

    const menuTambah = document.createElement('div');
    menuTambah.id = 'aaMenuTambah';
    menuTambah.setAttribute('role', 'menu');
    menuTambah.setAttribute('aria-label', 'Jenis penerima');
    menuTambah.className = 'hidden absolute z-20 mt-1 w-56 rounded-lg border border-slate-200 bg-white shadow-lg py-1';
    menuTambah.innerHTML = [['DEPT', 'Departemen'], ['LEVEL', 'Jabatan'], ['ROLE', 'Peran (departemen + jabatan)'], ['USER', 'User tertentu']]
        .map(([v, l]) => `<button type="button" role="menuitem" tabindex="-1" class="block w-full text-left px-3 py-2 text-sm text-slate-700 focus:bg-slate-100 focus:text-slate-900" data-jenis="${v}">${l}</button>`).join('');
    const tombolTambah = el('aaTambah');
    tombolTambah.setAttribute('aria-haspopup', 'menu');
    tombolTambah.setAttribute('aria-expanded', 'false');
    tombolTambah.insertAdjacentElement('afterend', menuTambah);
    tombolTambah.parentElement.classList.add('relative');
    const itemTambah = () => [...menuTambah.querySelectorAll('[data-jenis]')];

    function tutupMenuTambah(kembali) {
        if (menuTambah.classList.contains('hidden')) return;
        menuTambah.classList.add('hidden');
        tombolTambah.setAttribute('aria-expanded', 'false');
        if (kembali) tombolTambah.focus();
    }
    function bukaMenuTambah() {
        menuTambah.style.top = `${tombolTambah.offsetTop + tombolTambah.offsetHeight}px`;
        menuTambah.style.left = `${Math.max(0, tombolTambah.offsetLeft + tombolTambah.offsetWidth - 224)}px`;
        menuTambah.classList.remove('hidden');
        tombolTambah.setAttribute('aria-expanded', 'true');
        itemTambah()[0].focus();
    }
    tombolTambah.addEventListener('click', () => (menuTambah.classList.contains('hidden') ? bukaMenuTambah() : tutupMenuTambah(true)));
    menuTambah.addEventListener('click', e => {
        const b = e.target.closest('[data-jenis]');
        if (!b) return;
        tutupMenuTambah(false);
        tambah(b.dataset.jenis);
    });
    // Sorotan ikut mouse, jadi hanya satu pilihan yang tampak aktif
    menuTambah.addEventListener('mouseover', e => { const b = e.target.closest('[data-jenis]'); if (b && b !== document.activeElement) b.focus(); });
    menuTambah.addEventListener('keydown', e => {
        const daftar = itemTambah(), i = daftar.indexOf(document.activeElement);
        const ke = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: daftar.length - 1 }[e.key];
        if (e.key === 'Escape' || e.key === 'Tab') { if (e.key === 'Escape') e.preventDefault(); return tutupMenuTambah(e.key === 'Escape'); }
        if (ke === undefined) return;
        e.preventDefault();
        daftar[(ke + daftar.length) % daftar.length].focus();
    });
    document.addEventListener('click', e => { if (!menuTambah.contains(e.target) && e.target !== tombolTambah && !tombolTambah.contains(e.target)) tutupMenuTambah(false); });

    el('aaTabel').addEventListener('click', e => {
        const hapus = e.target.closest('[data-hapus]');
        if (hapus) { aturan.splice(Number(hapus.dataset.hapus), 1); tampilAturan(); return; }
        const u = e.target.closest('[data-pilih-user]');
        if (u) bukaUser(Number(u.dataset.pilihUser));
    });

    el('aaTabel').addEventListener('change', e => {
        const t = e.target, a = aturan[Number(t.dataset.i)];
        if (!a) return;
        const f = t.dataset.f;
        if (f === 'jenis') { a.jenis = t.value; a.id_target = targetAwal(a.jenis); a.nama_target = ''; }
        else if (f === 'id_target') a.id_target = t.value;
        else if (f === 'role_dept' || f === 'role_jab') {
            const [d, j] = String(a.id_target || '|').split('|');
            a.id_target = f === 'role_dept' ? `${t.value}|${j}` : `${d}|${t.value}`;
        } else if (f === 'lihat') { a.lihat = t.checked; if (!t.checked) a.ubah = false; }
        else if (f === 'ubah') { a.ubah = t.checked; if (t.checked) a.lihat = true; }
        tampilAturan();
        if (f === 'jenis' && a.jenis === 'USER') bukaUser(Number(t.dataset.i));
    });

    // ===== Pilih user =====
    let jedaCari = null;
    function cariUser() {
        clearTimeout(jedaCari);
        jedaCari = setTimeout(async () => {
            const wadah = el('aaHasilUser');
            const data = await ambilJson(`/api/admin/akses/user?q=${encodeURIComponent(el('aaCariUser').value.trim())}`);
            if (data.error) { wadah.innerHTML = `<p class="p-3 text-sm text-red-700">${escapeHtml(data.error)}</p>`; return; }
            wadah.innerHTML = data.map(u => `
                <button type="button" class="w-full text-left px-3 py-2 hover:bg-slate-50" data-id="${u.id_user}" data-nama="${escapeHtml(u.nama)} · ${escapeHtml(u.username)}">
                    <span class="block text-sm font-semibold text-slate-800">${escapeHtml(u.nama)} <span class="font-normal text-slate-500">· ${escapeHtml(u.username)}</span></span>
                    <span class="block text-xs text-slate-500">${escapeHtml(u.nik || '-')} · ${escapeHtml(u.peran || '-')}</span>
                </button>`).join('') || '<p class="p-3 text-sm text-slate-500">Tidak ada user yang cocok</p>';
        }, 250);
    }

    function bukaUser(i) {
        barisUser = i;
        pemicuUser = document.activeElement;
        el('aaCariUser').value = '';
        el('aaHasilUser').innerHTML = '';
        openModal('modalAaUser');
        el('aaCariUser').focus();
        cariUser();
    }

    el('aaCariUser').addEventListener('input', cariUser);
    // Kotak ditutup (Tutup / Esc / klik luar) tanpa memilih: baris baru yang masih kosong dibuang
    new MutationObserver(() => {
        if (!el('modalAaUser').classList.contains('hidden')) return;
        const i = barisUser, a = aturan[i];
        let tujuan;
        if (a && a._baru && !a.id_target) { aturan.splice(i, 1); tampilAturan(); tujuan = el('aaTambah'); }
        else tujuan = el('aaTabel').querySelector(`[data-pilih-user="${i}"]`) || (pemicuUser && pemicuUser.isConnected ? pemicuUser : el('aaTambah'));
        barisUser = null;
        pemicuUser = null;
        if (tujuan && !tujuan.disabled) tujuan.focus();
    }).observe(el('modalAaUser'), { attributes: true, attributeFilter: ['class'] });
    el('aaHasilUser').addEventListener('click', e => {
        const b = e.target.closest('[data-id]');
        if (!b || !aturan[barisUser]) return;
        Object.assign(aturan[barisUser], { id_target: b.dataset.id, nama_target: b.dataset.nama });
        closeModal('modalAaUser');
        tampilAturan();
    });

    el('aaForm').addEventListener('submit', async e => {
        e.preventDefault();
        if (!aktif || !berubah()) return;
        const kurang = aturan.findIndex(belumLengkap);
        if (kurang >= 0) {
            const a = aturan[kurang];
            const apa = { USER: 'user', DEPT: 'departemen', LEVEL: 'jabatan', ROLE: 'departemen dan jabatan' }[a.jenis];
            tampilkanHasil({ error: `Pilih ${apa} di baris ${kurang + 1}, atau hapus barisnya.` });
            const isian = el('aaTabel').querySelector(`[data-i="${kurang}"]:not([data-f="jenis"]):not([type="checkbox"]), [data-pilih-user="${kurang}"]`);
            if (isian) isian.focus();
            return;
        }
        const kode = aktif.kode;
        const res = await denganTombol(el('aaSimpan'), () => kirimForm(`/api/admin/akses-admin/${encodeURIComponent(kode)}`,
            { aturan: JSON.stringify(aturan.map(a => ({ jenis: a.jenis, id_target: a.id_target, lihat: a.lihat, ubah: a.ubah }))) }));
        if (!tampilkanHasil(res)) return;
        asli = bentuk();
        await muat(kode);
    });

    // ===== Tab =====
    const daftarTab = [...document.querySelectorAll('[data-aa-tab]')];
    function aktifkanTab(t, dariPanah) {
        daftarTab.forEach(x => {
            const ya = x === t;
            x.classList.toggle('chip-active', ya);
            x.setAttribute('aria-selected', String(ya));
            x.tabIndex = ya ? 0 : -1;
        });
        el('aaPanelHalaman').classList.toggle('hidden', t.dataset.aaTab !== 'halaman');
        el('aaPanelOrang').classList.toggle('hidden', t.dataset.aaTab !== 'orang');
        if (dariPanah) t.focus();
        if (t.dataset.aaTab === 'orang') { if (!dariPanah) el('aaCariOrang').focus(); cariOrang(); }
    }
    daftarTab.forEach(t => {
        t.addEventListener('click', () => aktifkanTab(t, false));
        t.addEventListener('keydown', e => {
            const i = daftarTab.indexOf(t);
            const ke = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: daftarTab.length - 1 }[e.key];
            if (ke === undefined) return;
            e.preventDefault();
            aktifkanTab(daftarTab[(ke + daftarTab.length) % daftarTab.length], true);
        });
    });

    // ===== Per orang =====
    let jedaOrang = null;
    function cariOrang() {
        clearTimeout(jedaOrang);
        jedaOrang = setTimeout(async () => {
            const wadah = el('aaHasilOrang');
            const data = await ambilJson(`/api/admin/akses/user?q=${encodeURIComponent(el('aaCariOrang').value.trim())}`);
            const jumlah = el('aaJumlahOrang');
            if (data.error) {
                wadah.innerHTML = `<p class="p-3 text-sm text-red-700">${escapeHtml(data.error)}</p>`;
                if (jumlah) jumlah.textContent = data.error;
                return;
            }
            if (jumlah) jumlah.textContent = data.length ? `${data.length} user ditemukan` : 'Tidak ada user yang cocok';
            wadah.innerHTML = data.map(u => `
                <button type="button" class="w-full text-left px-4 py-2 hover:bg-slate-50" data-orang="${u.id_user}">
                    <span class="block text-sm font-semibold text-slate-800">${escapeHtml(u.nama)} <span class="font-normal text-slate-500">· ${escapeHtml(u.username)}</span></span>
                    <span class="block text-xs text-slate-500">${escapeHtml(u.peran || '-')}</span>
                </button>`).join('') || '<p class="p-4 text-sm text-slate-500">Tidak ada user yang cocok</p>';
        }, 250);
    }
    el('aaCariOrang')?.addEventListener('input', cariOrang);

    async function bukaOrang(id) {
        el('aaHasilOrang').querySelectorAll('[data-orang]').forEach(b => b.classList.toggle('bg-slate-100', b.dataset.orang === String(id)));
        el('aaOrangTabel').innerHTML = '<tr><td colspan="3" class="table-cell text-center text-slate-500 py-10">Memuat akses…</td></tr>';
        const res = await ambilJson(`/api/admin/akses-admin/user/${id}`);
        if (res.error) {
            el('aaOrangTabel').innerHTML = `<tr><td colspan="3" class="table-cell text-center text-red-700 py-10">${escapeHtml(res.error)}</td></tr>`;
            return;
        }
        const boleh = res.halaman.filter(h => h.lihat);
        el('aaOrangJudul').textContent = `${res.user.nama} · ${res.user.username}`;
        el('aaOrangInfo').textContent = boleh.length
            ? `${res.user.peran || '-'} · boleh membuka ${boleh.length} dari ${res.halaman.length} halaman Admin`
            : `${res.user.peran || '-'} · belum boleh membuka halaman Admin mana pun`;
        el('aaOrangTabel').innerHTML = res.halaman.map(h => `
            <tr class="${h.lihat ? '' : 'text-slate-500'}">
                <td class="table-cell"><span class="${h.lihat ? 'font-semibold text-slate-800' : ''}">${escapeHtml(h.nama)}</span>
                    <span class="block text-xs text-slate-500">${escapeHtml(h.grup)}</span></td>
                <td class="table-cell whitespace-nowrap">${h.ubah ? 'Lihat dan Ubah' : h.lihat ? 'Lihat' : 'Tidak bisa dibuka'}</td>
                <td class="table-cell text-xs">${h.asal.length ? h.asal.map(a => `<span class="block">${escapeHtml(a)}</span>`).join('') : ''}</td>
            </tr>`).join('');
        if (sempit()) el('aaOrangPanel').scrollIntoView({ behavior: gerak(), block: 'start' });
    }
    el('aaHasilOrang')?.addEventListener('click', e => {
        const b = e.target.closest('[data-orang]');
        if (b) bukaOrang(b.dataset.orang);
    });

    window.addEventListener('beforeunload', e => { if (berubah()) e.preventDefault(); });

    muat();
})();
