(() => {
    const root = document.getElementById('itemDashboard');
    if (!root) return;

    const pageSize = 50;
    const elements = {
        status: document.getElementById('statusItemDashboard'),
        error: document.getElementById('errorItemDashboard'),
        kpi: document.getElementById('kpiItemDashboard'),
        chart: document.getElementById('grafikItemDashboard'),
        chartLabel: document.getElementById('labelGrafikItem'),
        category: document.getElementById('filterKategoriItem'),
        search: document.getElementById('cariItemDashboard'),
        head: document.getElementById('headTabelItemDashboard'),
        body: document.getElementById('bodyTabelItemDashboard'),
        info: document.getElementById('infoTabelItemDashboard'),
        page: document.getElementById('halamanTabelItemDashboard'),
        previous: document.getElementById('sebelumItemDashboard'),
        next: document.getElementById('sesudahItemDashboard'),
        refresh: document.getElementById('refreshItemDashboard'),
    };

    let columns = [];
    let rows = [];
    let page = 1;
    let categoryKey = null;
    let metricKey = null;

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
        const numericColumns = columns.filter(column => rows.some(row => numberOf(row[column]) !== null));
        const metricNames = ['itemcount', 'totalitems', 'jumlahitem', 'itemqty', 'quantity', 'qty', 'count', 'total'];
        metricKey = numericColumns.find(column => metricNames.includes(normalized(column)))
            || numericColumns[0]
            || null;
    }

    function filteredRows() {
        const category = elements.category.value;
        const search = elements.search.value.trim().toLocaleLowerCase('id-ID');
        return rows.filter(row => {
            if (category && categoryValue(row) !== category) return false;
            return !search || columns.some(column => String(row[column] ?? '').toLocaleLowerCase('id-ID').includes(search));
        });
    }

    function categorySummary(data) {
        const totals = new Map();
        data.forEach(row => {
            const name = categoryValue(row);
            const value = metricKey ? numberOf(row[metricKey]) : 1;
            totals.set(name, (totals.get(name) || 0) + (value ?? 0));
        });
        return [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
    }

    function renderKpis(data, categories) {
        const values = metricKey
            ? data.reduce((sum, row) => sum + (numberOf(row[metricKey]) ?? 0), 0)
            : data.length;
        const cards = [
            ['Baris Analisis', formatNumber(data.length), 'fa-list'],
            ['Kategori', formatNumber(new Set(data.map(categoryValue)).size), 'fa-layer-group'],
            [metricKey ? `Total ${labelOf(metricKey)}` : 'Total Item', formatNumber(values), 'fa-boxes-stacked'],
            ['Kategori Teratas', categories[0]?.[0] || '-', 'fa-ranking-star'],
        ];
        elements.kpi.innerHTML = cards.map(([title, value, icon]) => `
            <article class="section-box p-4 flex items-center gap-3">
                <div class="judul-ikon judul-ikon-biru shrink-0"><i class="fa-solid ${icon}"></i></div>
                <div class="min-w-0"><p class="text-xs text-slate-500">${escapeHtml(title)}</p>
                    <p class="font-bold text-lg text-slate-800 truncate" title="${escapeHtml(value)}">${escapeHtml(value)}</p></div>
            </article>`).join('');
    }

    function renderChart(categories) {
        elements.chartLabel.textContent = metricKey
            ? `Berdasarkan ${labelOf(metricKey)} · 10 kategori teratas`
            : 'Jumlah baris per kategori · 10 kategori teratas';
        if (!categories.length) {
            elements.chart.innerHTML = '<p class="text-sm text-slate-500 py-6 text-center">Tidak ada data untuk ditampilkan.</p>';
            return;
        }
        const maximum = Math.max(...categories.map(([, value]) => value), 1);
        elements.chart.innerHTML = categories.map(([name, value]) => {
            const width = Math.max(2, Math.min(100, value / maximum * 100));
            return `<div>
                <div class="mb-1 flex justify-between gap-3 text-xs"><span class="truncate text-slate-600" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
                    <span class="shrink-0 font-semibold text-slate-700">${formatNumber(value)}</span></div>
                <div class="h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full bg-blue-600" style="width:${width}%"></div></div>
            </div>`;
        }).join('');
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
        const data = filteredRows();
        const categories = categorySummary(data);
        renderKpis(data, categories);
        renderChart(categories);
        renderTable(data);
    }

    function populateCategoryFilter() {
        if (!categoryKey) {
            elements.category.disabled = true;
            return;
        }
        const categories = [...new Set(rows.map(categoryValue))].sort((a, b) => a.localeCompare(b, 'id'));
        elements.category.innerHTML = '<option value="">Semua kategori</option>'
            + categories.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    }

    async function load() {
        elements.refresh.disabled = true;
        elements.status.textContent = 'Memuat data analisis item…';
        elements.error.classList.add('hidden');
        try {
            const response = await fetch(root.dataset.api, { headers: { Accept: 'application/json' } });
            const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || `Permintaan gagal (${response.status}).`);
            columns = data.kolom || [];
            rows = data.baris || [];
            selectColumns();
            populateCategoryFilter();
            page = 1;
            render();
            elements.status.textContent = `Sumber: dbo.top_item_category_analysis · ${formatNumber(rows.length)} baris`;
        } catch (error) {
            elements.status.textContent = 'Data analisis belum tersedia.';
            elements.error.textContent = error.message || 'Terjadi kesalahan saat memuat data.';
            elements.error.classList.remove('hidden');
        } finally {
            elements.refresh.disabled = false;
        }
    }

    elements.category.addEventListener('change', () => { page = 1; render(); });
    elements.search.addEventListener('input', () => { page = 1; render(); });
    elements.previous.addEventListener('click', () => { page -= 1; render(); });
    elements.next.addEventListener('click', () => { page += 1; render(); });
    elements.refresh.addEventListener('click', load);
    load();
})();
