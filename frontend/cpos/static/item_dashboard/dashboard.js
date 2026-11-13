(() => {
    const root = document.getElementById('itemDashboard');
    if (!root) return;

    const pageSize = 50;
    const elements = {
        status: document.getElementById('statusItemDashboard'),
        error: document.getElementById('errorItemDashboard'),
        charts: document.getElementById('grafikSetItemDashboard'),
        dataset: document.getElementById('pilihHasilItemDashboard'),
        category: document.getElementById('filterKategoriItem'),
        search: document.getElementById('cariItemDashboard'),
        head: document.getElementById('headTabelItemDashboard'),
        body: document.getElementById('bodyTabelItemDashboard'),
        info: document.getElementById('infoTabelItemDashboard'),
        page: document.getElementById('halamanTabelItemDashboard'),
        previous: document.getElementById('sebelumItemDashboard'),
        next: document.getElementById('sesudahItemDashboard'),
        refresh: document.getElementById('refreshItemDashboard'),
        toast: document.getElementById('popupWaktuItemDashboard'),
        toastMessage: document.getElementById('pesanWaktuItemDashboard'),
        toastClose: document.getElementById('tutupPopupWaktuItemDashboard'),
    };

    let datasets = [];
    let activeDataset = 0;
    let columns = [];
    let rows = [];
    let page = 1;
    let categoryKey = null;
    let toastTimeout = null;

    const normalized = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
    const labelOf = value => String(value).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ');
    const numberOf = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
    const formatNumber = value => Number(value).toLocaleString('id-ID', { maximumFractionDigits: 2 });
    const categoryValue = row => categoryKey ? String(row[categoryKey] ?? '(Kosong)') : 'Semua item';

    function selectColumns() {
        const categoryNames = new Set(['category', 'kategori', 'categoryname', 'namakategori', 'itemcategory']);
        categoryKey = columns.find(column => categoryNames.has(normalized(column))) || null;
    }

    function chooseColumn(dataset, preferredNames, numeric = false) {
        const candidates = dataset.kolom.filter(column => {
            const isNumeric = dataset.baris.some(row => numberOf(row[column]) !== null);
            return numeric ? isNumeric : !isNumeric;
        });
        const byName = candidates.find(column => preferredNames.some(name => normalized(column).includes(name)));
        if (byName) return byName;
        if (!numeric) return candidates[0] || null;
        return candidates.find(column => !/(^id|id$|code|kode|nomor|no$)/.test(normalized(column)))
            || candidates[0]
            || null;
    }

    function renderCharts() {
        const labelNames = [
            ['itemname', 'namaitem', 'itemcode', 'kodeitem', 'description', 'deskripsi', 'item', 'nama', 'sku'],
            ['itemname', 'namaitem', 'itemcode', 'kodeitem', 'description', 'deskripsi', 'item', 'nama', 'sku'],
            ['itemname', 'namaitem', 'itemcode', 'kodeitem', 'description', 'deskripsi', 'item', 'nama', 'sku'],
            ['categoryname', 'namakategori', 'category', 'kategori', 'name', 'nama'],
            ['categoryname', 'namakategori', 'category', 'kategori', 'name', 'nama'],
            ['itemname', 'namaitem', 'itemcode', 'kodeitem', 'description', 'deskripsi', 'item', 'nama', 'sku'],
        ];
        const metricNames = [
            ['stock', 'stok', 'quantity', 'qty', 'onhand', 'saldo', 'jumlah'],
            ['pocount', 'jumlahpo', 'ordercount', 'purchaseorder', 'dokumen', 'count', 'jumlah', 'total'],
            ['usagecount', 'jumlahpemakaian', 'icusage', 'usage', 'pemakaian', 'dokumen', 'count', 'jumlah', 'total'],
            ['pocount', 'jumlahpo', 'ordercount', 'purchaseorder', 'dokumen', 'count', 'jumlah', 'total'],
            ['cost', 'nilai', 'amount', 'value', 'total', 'rp'],
            ['cost', 'nilai', 'amount', 'value', 'total', 'rp'],
        ];

        elements.charts.innerHTML = datasets.map((dataset, index) => {
            const labelKey = chooseColumn(dataset, labelNames[index] || ['name', 'nama', 'item', 'category', 'kategori']);
            const metricKey = chooseColumn(dataset, metricNames[index] || ['total', 'count', 'jumlah', 'value', 'cost'], true);
            const points = metricKey
                ? dataset.baris.map((row, rowIndex) => ({
                    label: String(labelKey ? row[labelKey] ?? '(Kosong)' : `Baris ${rowIndex + 1}`),
                    value: numberOf(row[metricKey]),
                })).filter(point => point.value !== null)
                    .sort((a, b) => b.value - a.value)
                    .slice(0, 10)
                : [];
            const title = dataset.judul || `Result set ${index + 1}`;
            let chartBody = '<p class="py-6 text-center text-sm text-slate-500">Tidak ada data angka untuk divisualisasikan.</p>';
            if (points.length) {
                const maximum = Math.max(...points.map(point => point.value), 1);
                chartBody = `<div class="space-y-3">${points.map(point => {
                    const width = Math.max(2, Math.min(100, point.value / maximum * 100));
                    return `<div>
                        <div class="mb-1 flex justify-between gap-3 text-xs">
                            <span class="truncate text-slate-600" title="${escapeHtml(point.label)}">${escapeHtml(point.label)}</span>
                            <span class="shrink-0 font-semibold text-slate-700">${formatNumber(point.value)}</span>
                        </div>
                        <div class="h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full bg-blue-600" style="width:${width}%"></div></div>
                    </div>`;
                }).join('')}</div>`;
            } else if (!dataset.baris.length) {
                chartBody = '<p class="py-6 text-center text-sm text-slate-500">Tidak ada data untuk ditampilkan.</p>';
            }
            return `<article class="section-box p-4">
                <h2 class="font-bold text-slate-800">${escapeHtml(title)}</h2>
                <p class="mb-4 mt-1 text-xs text-slate-500">${formatNumber(dataset.baris.length)} baris${metricKey ? ` · ${escapeHtml(labelOf(metricKey))}` : ''}</p>
                ${chartBody}
            </article>`;
        }).join('');
    }

    function filteredRows() {
        const category = elements.category.value;
        const search = elements.search.value.trim().toLocaleLowerCase('id-ID');
        return rows.filter(row => {
            if (category && categoryValue(row) !== category) return false;
            return !search || columns.some(column => String(row[column] ?? '').toLocaleLowerCase('id-ID').includes(search));
        });
    }

    function renderTable(data) {
        elements.head.innerHTML = `<tr>${columns.map(column => `<th class="table-cell whitespace-nowrap">${escapeHtml(labelOf(column))}</th>`).join('')}</tr>`;
        const pageCount = Math.max(1, Math.ceil(data.length / pageSize));
        page = Math.min(page, pageCount);
        const start = (page - 1) * pageSize;
        const visible = data.slice(start, start + pageSize);
        elements.info.textContent = `${formatNumber(data.length)} baris ditampilkan`;
        elements.page.textContent = data.length ? `${formatNumber(start + 1)}–${formatNumber(Math.min(start + pageSize, data.length))} dari ${formatNumber(data.length)}` : '0 baris';
        elements.previous.disabled = page <= 1;
        elements.next.disabled = page >= pageCount;
        elements.body.innerHTML = visible.length
            ? visible.map(row => `<tr class="hover:bg-slate-50">${columns.map(column => {
                const value = row[column];
                const display = typeof value === 'number' ? formatNumber(value) : value ?? '—';
                return `<td class="table-cell whitespace-nowrap">${escapeHtml(display)}</td>`;
            }).join('')}</tr>`).join('')
            : `<tr><td class="table-cell py-8 text-center text-slate-500" colspan="${Math.max(columns.length, 1)}">Tidak ada data yang cocok.</td></tr>`;
    }

    function render() {
        renderTable(filteredRows());
    }

    function populateCategoryFilter() {
        elements.category.innerHTML = '<option value="">Semua kategori</option>';
        if (!categoryKey) {
            elements.category.disabled = true;
            return;
        }
        elements.category.disabled = false;
        const categories = [...new Set(rows.map(categoryValue))].sort((a, b) => a.localeCompare(b, 'id'));
        elements.category.innerHTML += categories
            .map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    }

    function selectDataset() {
        activeDataset = Number(elements.dataset.value) || 0;
        const dataset = datasets[activeDataset];
        columns = dataset?.kolom || [];
        rows = dataset?.baris || [];
        selectColumns();
        populateCategoryFilter();
        elements.search.value = '';
        page = 1;
        render();
    }

    function formatDuration(milliseconds) {
        return milliseconds < 1000
            ? `${Math.round(milliseconds)} ms`
            : `${(milliseconds / 1000).toFixed(2)} detik`;
    }

    function showDuration(message) {
        elements.toastMessage.textContent = message;
        elements.toast.classList.remove('hidden');
        clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => elements.toast.classList.add('hidden'), 5000);
    }

    async function load() {
        const mulai = performance.now();
        let pesanSelesai = 'Data analisis item berhasil dimuat.';
        let statusSelesai = '';
        elements.refresh.disabled = true;
        elements.status.textContent = 'Memuat data analisis item…';
        elements.error.classList.add('hidden');
        try {
            const response = await fetch(root.dataset.api, { headers: { Accept: 'application/json' } });
            const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || `Permintaan gagal (${response.status}).`);
            datasets = data.hasil || (data.kolom ? [{ judul: 'Item dengan stok tertinggi', kolom: data.kolom, baris: data.baris || [] }] : []);
            if (!datasets.length) throw new Error('Stored procedure tidak menghasilkan data analisis.');
            elements.dataset.innerHTML = datasets.map((dataset, index) =>
                `<option value="${index}">${escapeHtml(dataset.judul || `Result set ${index + 1}`)}</option>`
            ).join('');
            activeDataset = 0;
            renderCharts();
            selectDataset();
            const totalBaris = datasets.reduce((total, dataset) => total + dataset.baris.length, 0);
            statusSelesai = `Sumber: dbo.top_item_category_analysis · ${formatNumber(datasets.length)} result set · ${formatNumber(totalBaris)} baris`;
        } catch (error) {
            pesanSelesai = 'Data analisis item gagal dimuat.';
            statusSelesai = 'Data analisis belum tersedia.';
            elements.error.textContent = error.message || 'Terjadi kesalahan saat memuat data.';
            elements.error.classList.remove('hidden');
        } finally {
            const durasi = formatDuration(performance.now() - mulai);
            elements.status.textContent = `${statusSelesai} · ${durasi}`;
            showDuration(`${pesanSelesai} Waktu loading: ${durasi}.`);
            elements.refresh.disabled = false;
        }
    }

    elements.dataset.addEventListener('change', selectDataset);
    elements.category.addEventListener('change', () => { page = 1; render(); });
    elements.search.addEventListener('input', () => { page = 1; render(); });
    elements.previous.addEventListener('click', () => { page -= 1; render(); });
    elements.next.addEventListener('click', () => { page += 1; render(); });
    elements.refresh.addEventListener('click', load);
    elements.toastClose.addEventListener('click', () => elements.toast.classList.add('hidden'));
    load();
})();
