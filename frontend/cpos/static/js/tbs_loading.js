(() => {
    const path = window.location.pathname;
    const isTbsPage = /^\/rekapin\/tbs\/(daily|weekly|monthly)\/?$/.test(path);
    const startKey = 'cposTbsLoadingStartedAt';
    const tabBody = document.getElementById('tabBody');
    let overlay = null;
    let interval = null;
    let startedAt = null;

    function formatDuration(milliseconds) {
        return milliseconds < 1000
            ? `${Math.round(milliseconds)} ms`
            : `${(milliseconds / 1000).toFixed(2)} detik`;
    }

    function showDuration(milliseconds) {
        const toast = document.createElement('div');
        toast.className = 'fixed bottom-5 right-5 z-50 max-w-sm rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-lg';
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        toast.textContent = `Waktu pemuatan halaman TBS: ${formatDuration(milliseconds)}.`;
        document.body.append(toast);
        setTimeout(() => toast.remove(), 5000);
    }

    function showOverlay() {
        if (!tabBody) return;
        tabBody.classList.add('relative');
        tabBody.setAttribute('aria-busy', 'true');
        overlay = document.createElement('div');
        overlay.className = 'absolute inset-0 z-10 flex items-center justify-center bg-slate-900/40 p-4';
        overlay.setAttribute('role', 'status');
        overlay.setAttribute('aria-live', 'polite');
        overlay.innerHTML = `
            <div class="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 text-center shadow-xl">
                <div class="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" aria-hidden="true"></div>
                <h2 class="mt-4 font-semibold text-slate-800">Sedang memuat laporan TBS</h2>
                <p class="mt-1 text-sm text-slate-600">0 detik</p>
            </div>`;
        tabBody.append(overlay);
        const waktu = overlay.querySelector('p');
        interval = setInterval(() => {
            waktu.textContent = `${Math.floor((performance.now() - startedAt) / 1000)} detik`;
        }, 1000);
    }

    function start() {
        startedAt = performance.now();
        try {
            sessionStorage.setItem(startKey, String(Date.now()));
        } catch (error) {
            console.warn('Durasi loading TBS tidak dapat disimpan.', error);
        }
        clearInterval(interval);
        overlay?.remove();
        showOverlay();
    }

    function isTbsUrl(value) {
        try {
            const url = new URL(value, window.location.href);
            return url.origin === window.location.origin
                && /^\/rekapin\/tbs\/(daily|weekly|monthly)\/?$/.test(url.pathname);
        } catch {
            return false;
        }
    }

    document.addEventListener('click', event => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
        if (!link || (link.target && link.target !== '_self') || link.hasAttribute('download')) return;
        if (isTbsUrl(link.href)) start();
    });

    document.addEventListener('submit', event => {
        if (isTbsUrl(event.target.action || window.location.href)) start();
    });

    window.cposTbsLoading = { start };

    if (isTbsPage) {
        let waktuMulai;
        try {
            waktuMulai = Number(sessionStorage.getItem(startKey));
            sessionStorage.removeItem(startKey);
        } catch (error) {
            console.warn('Durasi loading TBS tidak dapat dibaca.', error);
        }

        if (Number.isFinite(waktuMulai) && waktuMulai > 0) {
            showDuration(Date.now() - waktuMulai);
        } else {
            window.addEventListener('load', () => {
                setTimeout(() => showDuration(performance.now()), 0);
            }, { once: true });
        }
    }
})();
