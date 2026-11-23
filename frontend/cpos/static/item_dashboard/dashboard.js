(() => {
    const root = document.getElementById('itemDashboard');
    if (!root) return;

    const pageSize = 50;
    const elements = {
        bar: document.getElementById('barItemDashboard'),
        periodLabel: document.getElementById('periodeItemDashboard'),
        progress: document.getElementById('progresItemDashboard'),
        progressText: document.getElementById('teksProgresItem'),
        progressSeconds: document.getElementById('detikProgresItem'),
        cancel: document.getElementById('batalItemDashboard'),
        changePeriod: document.getElementById('gantiPeriodeItem'),
        retryBar: document.getElementById('pesanUlangItem'),
        retryMessage: document.getElementById('isiPesanUlangItem'),
        retryButton: document.getElementById('cobaUlangItem'),
        closeMessage: document.getElementById('tutupPesanItem'),
        screen: document.getElementById('layarItemDashboard'),
        periodForm: document.getElementById('formPeriodeItem'),
        periodStart: document.getElementById('mulaiPeriodeItem'),
        periodEnd: document.getElementById('akhirPeriodeItem'),
        periodInfo: document.getElementById('infoPeriodeItem'),
        periodSubmit: document.getElementById('muatPeriodeItem'),
        charts: document.getElementById('grafikSetItemDashboard'),
        dataset: document.getElementById('pilihHasilItemDashboard'),
        company: document.getElementById('filterPerusahaanItem'),
        category: document.getElementById('filterKategoriItem'),
        search: document.getElementById('cariItemDashboard'),
        head: document.getElementById('headTabelItemDashboard'),
        body: document.getElementById('bodyTabelItemDashboard'),
        tableSection: document.getElementById('tabelRincianItem'),
        tableTitle: document.getElementById('judulTabelItemDashboard'),
        info: document.getElementById('infoTabelItemDashboard'),
        footer: document.getElementById('kakiTabelItemDashboard'),
        page: document.getElementById('halamanTabelItemDashboard'),
        previous: document.getElementById('sebelumItemDashboard'),
        next: document.getElementById('sesudahItemDashboard'),
        refresh: document.getElementById('refreshItemDashboard'),
    };
    elements.refreshLabel = elements.refresh.querySelector('span');

    let datasets = [];
    let activeDataset = 0;
    let columns = [];
    let rows = [];
    let page = 1;
    let categoryKey = null;
    let companyKey = null;
    let periodText = '';
    const chartCompanySelections = {};

    const normalized = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
    const labelOf = value => String(value).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ');
    const numberOf = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
    const formatNumber = value => Number(value).toLocaleString('id-ID', { maximumFractionDigits: 2 });
    const formatDate = iso => `${iso.slice(8, 10)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}`;
    const formatTime = date => date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    const categoryValue = row => categoryKey ? String(row[categoryKey] ?? '(Kosong)') : 'Semua item';
    const fewerMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Arti angka satu hasil, mis. "Jumlah PO · 1 Jan 2026 sampai 20 Nov 2026" (periode dikirim server, stok tidak ikut periode)
    function describe(dataset, metricKey) {
        const meaning = dataset.keterangan || (metricKey ? labelOf(metricKey) : '');
        const withPeriod = dataset.ikut_periode !== false && periodText;
        return [meaning, withPeriod ? periodText : ''].filter(Boolean).join(' · ');
    }

    function selectColumns() {
        const categoryNames = new Set(['category', 'kategori', 'categoryname', 'namakategori', 'itemcategory']);
        const companyNames = new Set(['company', 'companyname', 'comp', 'compid', 'companycode', 'kodeperusahaan', 'perusahaan']);
        categoryKey = columns.find(column => categoryNames.has(normalized(column))) || null;
        companyKey = columns.find(column => companyNames.has(normalized(column))) || null;
    }

    function chooseColumn(dataset, preferredNames, numeric = false) {
        const candidates = dataset.kolom.filter(column => {
            const isNumeric = dataset.baris.some(row => numberOf(row[column]) !== null);
            return numeric ? isNumeric : !isNumeric;
        });
        for (const name of preferredNames) {
            const byName = candidates.find(column => normalized(column).includes(name));
            if (byName) return byName;
        }
        if (!numeric) return candidates[0] || null;
        return candidates.find(column => !/(^id|id$|code|kode|nomor|no$|ranking)/.test(normalized(column)))
            || candidates[0]
            || null;
    }

    const chartTypes = ['bar', 'progress', 'lollipop', 'bar', 'progress', 'lollipop'];

    function tooltipText(point, nameType) {
        return [
            point.company ? `Perusahaan: ${point.company}` : null,
            `${nameType}: ${point.name || point.itemCode || point.label}`,
            `Jumlah: ${formatNumber(point.value)}`,
        ].filter(Boolean).join('\n');
    }

    function renderBarChart(points, nameType) {
        const maximum = Math.max(...points.map(point => point.value), 1);
        return `<div class="space-y-3">
            ${points.map(point => {
                const width = Math.max(2, Math.min(100, point.value / maximum * 100));
                return `<div class="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)_auto] items-center gap-2 text-xs" title="${escapeHtml(tooltipText(point, nameType))}">
                    <span class="truncate text-slate-600">${escapeHtml(point.label)}</span>
                    <div class="h-5">
                        <div class="h-full rounded-r bg-blue-600" style="width:${width}%"></div>
                    </div>
                    <span class="font-semibold tabular-nums text-slate-700">${formatNumber(point.value)}</span>
                </div>`;
            }).join('')}
        </div>`;
    }

    function renderProgressChart(points, nameType) {
        const maximum = Math.max(...points.map(point => point.value), 1);
        return `<div class="space-y-3">
            ${points.map(point => {
                const width = Math.max(2, Math.min(100, point.value / maximum * 100));
                return `<div title="${escapeHtml(tooltipText(point, nameType))}">
                    <div class="mb-1 flex justify-between gap-3 text-xs">
                        <span class="truncate text-slate-600">${escapeHtml(point.label)}</span>
                        <span class="shrink-0 font-semibold tabular-nums text-slate-700">${formatNumber(point.value)}</span>
                    </div>
                    <div class="h-2.5 overflow-hidden rounded-full bg-slate-100">
                        <div class="h-full rounded-full bg-teal-600" style="width:${width}%"></div>
                    </div>
                </div>`;
            }).join('')}
        </div>`;
    }

    function renderLollipopChart(points, nameType) {
        const maximum = Math.max(...points.map(point => point.value), 1);
        return `<div class="space-y-2">
            ${points.map(point => {
                const width = Math.max(0, Math.min(100, point.value / maximum * 100));
                return `<div class="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)_auto] items-center gap-2 text-xs" title="${escapeHtml(tooltipText(point, nameType))}">
                    <span class="truncate text-slate-600">${escapeHtml(point.label)}</span>
                    <div class="relative h-7">
                        <div class="absolute inset-x-0 top-1/2 h-px bg-slate-200"></div>
                        <div class="absolute left-0 top-1/2 h-0.5 bg-sky-300" style="width:${width}%"></div>
                        <span class="absolute top-1/2 h-3 w-3 rounded-full bg-sky-600 ring-2 ring-white" style="left:${width}%;transform:translate(-50%,-50%)"></span>
                    </div>
                    <span class="font-semibold tabular-nums text-slate-700">${formatNumber(point.value)}</span>
                </div>`;
            }).join('')}
        </div>`;
    }

    function renderCharts() {
        const companyNames = ['company', 'companyname', 'comp', 'compid', 'companycode', 'kodeperusahaan', 'perusahaan'];
        const itemCodeNames = ['itemcode', 'kodeitem', 'itemno', 'sku', 'code'];
        const itemNames = ['itemname', 'namaitem', 'itemcode', 'kodeitem', 'description', 'deskripsi', 'item', 'nama', 'sku'];
        const categoryNames = ['categoryname', 'namakategori', 'category', 'kategori', 'name', 'nama'];
        const labelNames = [itemNames, itemNames, itemNames, categoryNames, categoryNames, itemNames];
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
            const chartCompanyKey = chooseColumn(dataset, companyNames);
            const itemCodeKey = chooseColumn(dataset, itemCodeNames);
            const metricKey = chooseColumn(dataset, metricNames[index] || ['total', 'count', 'jumlah', 'value', 'cost'], true);
            const companies = chartCompanyKey
                ? [...new Set(dataset.baris.map(row => String(row[chartCompanyKey] ?? '')).filter(Boolean))]
                    .sort((a, b) => a.localeCompare(b, 'id'))
                : [];
            if (!companies.includes(chartCompanySelections[index])) chartCompanySelections[index] = '';
            const selectedCompany = chartCompanySelections[index];
            const companyRows = selectedCompany
                ? dataset.baris.filter(row => String(row[chartCompanyKey] ?? '') === selectedCompany)
                : dataset.baris;
            const nameType = [3, 4].includes(index) ? 'Kategori' : 'Item';
            const points = metricKey
                ? companyRows.map((row, rowIndex) => ({
                    company: chartCompanyKey ? String(row[chartCompanyKey] ?? '').trim() : '',
                    itemCode: itemCodeKey ? String(row[itemCodeKey] ?? '').trim() : '',
                    name: labelKey ? String(row[labelKey] ?? '').trim() : '',
                    label: [
                        chartCompanyKey ? row[chartCompanyKey] : null,
                        labelKey ? row[labelKey] : null,
                    ].filter(value => value != null && String(value).trim()).join(' · ') || `Baris ${rowIndex + 1}`,
                    value: numberOf(row[metricKey]),
                })).filter(point => point.value !== null)
                    .sort((a, b) => b.value - a.value)
                    .slice(0, 10)
                : [];
            const title = dataset.judul || `Hasil ${index + 1}`;
            const chartType = chartTypes[index] || 'bar';
            let chartBody = '<p class="py-6 text-center text-sm text-slate-500">Belum ada data</p>';
            if (points.length) {
                if (chartType === 'progress') chartBody = renderProgressChart(points, nameType);
                else if (chartType === 'lollipop') chartBody = renderLollipopChart(points, nameType);
                else chartBody = renderBarChart(points, nameType);
            } else if (selectedCompany) chartBody = `<p class="py-6 text-center text-sm text-slate-500">Tidak ada data ${escapeHtml(selectedCompany)} pada periode ini.</p>`;
            return `<article class="section-box p-4" aria-labelledby="judulGrafikItem${index}">
                <div class="flex flex-wrap items-start justify-between gap-2">
                    <div class="min-w-0">
                        <h2 id="judulGrafikItem${index}" class="font-bold text-slate-800">${escapeHtml(title)}</h2>
                        <p class="mt-1 text-xs text-slate-500">${escapeHtml(describe(dataset, metricKey))}</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                        ${companies.length ? `<select class="input-field py-1.5 text-xs" data-chart-company="${index}" aria-label="Filter perusahaan ${escapeHtml(title)}">
                            <option value="">Semua perusahaan</option>
                            ${companies.map(company => `<option value="${escapeHtml(company)}" ${company === selectedCompany ? 'selected' : ''}>${escapeHtml(company)}</option>`).join('')}
                        </select>` : ''}
                        <button type="button" class="btn-secondary btn-sm" data-rincian="${index}" aria-describedby="judulGrafikItem${index}">Lihat tabel</button>
                    </div>
                </div>
                <div class="mt-4">${chartBody}</div>
            </article>`;
        }).join('');
    }

    function filteredRows(sourceRows = rows) {
        const company = elements.company.value;
        const category = elements.category.value;
        const search = elements.search.value.trim().toLocaleLowerCase('id-ID');
        return sourceRows.filter(row => {
            if (company && companyKey && String(row[companyKey] ?? '') !== company) return false;
            if (category && categoryValue(row) !== category) return false;
            return !search || columns.some(column => String(row[column] ?? '').toLocaleLowerCase('id-ID').includes(search));
        });
    }

    function rankAllRows() {
        if (elements.company.value || !rows.length) return rows;
        const metricNames = [
            ['totalstok', 'stok', 'qty'],
            ['jumlahpo', 'doccount', 'count'],
            ['jumlahdokumenpemakaian', 'doccount', 'pemakaian'],
            ['jumlahpo', 'doccount', 'count'],
            ['totalcost', 'cost', 'nilai'],
            ['totalcost', 'cost', 'nilai'],
        ];
        const metricKey = chooseColumn(datasets[activeDataset], metricNames[activeDataset] || ['total', 'count', 'jumlah'], true);
        const countNames = activeDataset === 2 ? ['jumlahdokumenpemakaian', 'doccount'] : ['jumlahpo', 'doccount'];
        const countKey = [1, 2, 3].includes(activeDataset)
            ? columns.find(column => countNames.includes(normalized(column)))
            : null;
        const lineKey = [1, 2, 3].includes(activeDataset)
            ? columns.find(column => ['linecount', 'barispo', 'baris'].includes(normalized(column)))
            : null;
        const rankKey = columns.find(column => ['ranking', 'rank', 'peringkat'].includes(normalized(column)));
        const ranked = [...rows].sort((a, b) =>
            (numberOf(b[metricKey]) ?? 0) - (numberOf(a[metricKey]) ?? 0)
            || (countKey ? (numberOf(b[countKey]) ?? 0) - (numberOf(a[countKey]) ?? 0) : 0)
            || (lineKey ? (numberOf(b[lineKey]) ?? 0) - (numberOf(a[lineKey]) ?? 0) : 0)
        );
        const topTen = ranked.slice(0, 10);
        return rankKey ? topTen.map((row, index) => ({ ...row, [rankKey]: index + 1 })) : topTen;
    }

    function renderTable(data) {
        // Kolom angka rata kanan dengan digit sama lebar, supaya mudah dibandingkan
        const numeric = new Set(columns.filter(column => rows.some(row => typeof row[column] === 'number')));
        const align = column => numeric.has(column) ? ' text-right tabular-nums' : '';
        // Kolom yang punya pecahan selalu 2 desimal, supaya koma desimal sejajar dalam satu kolom
        const decimals = Object.fromEntries(columns.map(column =>
            [column, rows.some(row => typeof row[column] === 'number' && !Number.isInteger(row[column])) ? 2 : 0]));
        const cellNumber = (column, value) => value.toLocaleString('id-ID', { minimumFractionDigits: decimals[column], maximumFractionDigits: decimals[column] });
        elements.head.innerHTML = `<tr>${columns.map(column => `<th class="table-cell whitespace-nowrap${align(column)}">${escapeHtml(labelOf(column))}</th>`).join('')}</tr>`;
        const pageCount = Math.max(1, Math.ceil(data.length / pageSize));
        page = Math.min(page, pageCount);
        const start = (page - 1) * pageSize;
        const visible = data.slice(start, start + pageSize);
        const dataset = datasets[activeDataset];
        if (elements.tableTitle && dataset) elements.tableTitle.textContent = `Rincian: ${dataset.judul || `Hasil ${activeDataset + 1}`}`;
        elements.info.textContent = [`${formatNumber(data.length)} baris`, dataset ? describe(dataset) : ''].filter(Boolean).join(' · ');
        // Halaman tabel hanya tampil bila baris lebih dari satu halaman
        elements.footer?.classList.toggle('hidden', pageCount <= 1);
        elements.page.textContent = data.length ? `${formatNumber(start + 1)}–${formatNumber(Math.min(start + pageSize, data.length))} dari ${formatNumber(data.length)}` : '0 baris';
        elements.previous.disabled = page <= 1;
        elements.next.disabled = page >= pageCount;
        elements.body.innerHTML = visible.length
            ? visible.map(row => `<tr class="hover:bg-slate-50">${columns.map(column => {
                const value = row[column];
                const display = typeof value === 'number' ? cellNumber(column, value) : value ?? '-';
                return `<td class="table-cell whitespace-nowrap${align(column)}">${escapeHtml(display)}</td>`;
            }).join('')}</tr>`).join('')
            : `<tr><td class="table-cell py-8 text-center text-slate-500" colspan="${Math.max(columns.length, 1)}">Tidak ada data yang cocok. Ubah filter atau kosongkan pencarian.</td></tr>`;
    }

    function render() {
        renderTable(filteredRows(rankAllRows()));
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

    function populateCompanyFilter() {
        elements.company.innerHTML = '<option value="">Semua perusahaan</option>';
        if (!companyKey) {
            elements.company.disabled = true;
            return;
        }
        elements.company.disabled = false;
        const companies = [...new Set(rows.map(row => String(row[companyKey] ?? '')).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b, 'id'));
        elements.company.innerHTML += companies
            .map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    }

    function selectDataset() {
        activeDataset = Number(elements.dataset.value) || 0;
        const dataset = datasets[activeDataset];
        columns = dataset?.kolom || [];
        rows = dataset?.baris || [];
        selectColumns();
        populateCompanyFilter();
        populateCategoryFilter();
        elements.search.value = '';
        page = 1;
        render();
    }

    // Tombol "Lihat tabel" di kartu: tabel rincian pindah ke hasil itu, lalu layar & fokus ke judul tabel
    function showInTable(index) {
        elements.dataset.value = String(index);
        selectDataset();
        const target = elements.tableSection || elements.body;
        target.scrollIntoView({ behavior: fewerMotion() ? 'auto' : 'smooth', block: 'start' });
        elements.tableTitle?.focus({ preventScroll: true });
    }

    // ===== Periode & pemuatan (alurnya sama dengan Analytics) =====
    // SP berjalan di server tanpa menahan halaman. Halaman bertanya tiap detik sampai siap; Batalkan berhenti bertanya, dan server
    // menghentikan SP-nya bila tidak ada halaman lain yang menunggu periode itu.
    const MAX_DAYS = 1100; // sama dengan batas server dan Analytics
    const todayIso = () => {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };
    const defaultPeriod = () => ({ mulai: `${todayIso().slice(0, 4)}-01-01`, akhir: todayIso() });
    const daysBetween = (from, to) => Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000);
    const secondsText = seconds => `${formatNumber(seconds)} detik`;

    let shown = null;      // periode data yang sedang tampil
    let attempt = null;    // pemuatan terakhir yang diminta, untuk Coba lagi
    let loading = null;
    let pollTimer = null;
    let token = 0;

    function checkPeriod(from, to) {
        if (!from || !to) return 'Isi tanggal mulai dan tanggal akhir.';
        if (from > to) return 'Tanggal mulai tidak boleh setelah tanggal akhir.';
        if (daysBetween(from, to) > MAX_DAYS) return `Rentang terlalu panjang (maksimal ${MAX_DAYS} hari).`;
        return null;
    }

    // Hari ini cukup jamnya; data dari hari lain perlu tanggalnya supaya tidak dikira baru
    function fetchedAt(iso) {
        const when = iso ? new Date(iso) : new Date();
        const time = formatTime(when);
        return when.toDateString() === new Date().toDateString()
            ? `diambil hari ini ${time}`
            : `diambil ${when.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })} ${time}`;
    }

    function setBusy(busy) {
        const withData = datasets.length > 0;
        root.setAttribute('aria-busy', busy ? 'true' : 'false');
        elements.refresh.disabled = busy;
        elements.changePeriod.disabled = busy;
        const reloading = busy && loading?.reload;
        elements.refresh.querySelector('i')?.classList.toggle('fa-spin', reloading);
        elements.refreshLabel.textContent = reloading ? 'Memuat ulang…' : 'Muat ulang data';
        elements.progress.classList.toggle('hidden', !busy || !withData);
        elements.cancel.classList.toggle('hidden', !busy || !withData);
    }

    function showScreen(html) {
        elements.screen.innerHTML = html;
        elements.screen.classList.remove('hidden');
    }

    // Pemuatan pertama: kartu di tengah. Hitungan detik diperbarui sendiri supaya tombol Batalkan tidak kehilangan fokus.
    function screenLoading(from, to) {
        showScreen(`<div class="mx-auto h-8 w-8 animate-spin motion-reduce:animate-none rounded-full border-4 border-slate-200 border-t-utama-600" aria-hidden="true"></div>
            <h2 class="mt-4 text-lg font-semibold text-slate-800" role="status">Memuat data Item Category Analysis</h2>
            <p class="mt-1 text-sm text-slate-600"><span>Mengambil data ${formatDate(from)} sampai ${formatDate(to)}.</span> <span class="tabular-nums" data-detik aria-hidden="true">${secondsText(0)}</span></p>
            <button type="button" class="btn-secondary mt-4" data-batal>Batalkan</button>`);
    }

    function screenFailed(message) {
        showScreen(`<div role="alert">
            <span aria-hidden="true" class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600"><i class="fa-solid fa-triangle-exclamation text-xl"></i></span>
            <h2 class="mt-4 text-lg font-semibold text-slate-800">Data belum bisa ditampilkan</h2>
            <p class="mt-1 text-sm text-slate-600">${escapeHtml(message)}</p>
        </div>
        <button type="button" class="btn-primary mt-5" data-coba>Coba lagi</button>`);
    }

    function showSeconds(seconds) {
        const target = datasets.length ? elements.progressSeconds : elements.screen.querySelector('[data-detik]');
        if (target) target.textContent = secondsText(seconds);
    }

    function stopPolling() {
        clearTimeout(pollTimer);
        pollTimer = null;
    }

    async function ask(params) {
        let response;
        try {
            response = await fetch(`${root.dataset.api}?${new URLSearchParams(params)}`, { headers: { Accept: 'application/json' } });
        } catch {
            return { status: 'gagal', error: 'Server CPOS tidak bisa dihubungi.' };
        }
        const data = await response.json().catch(() => null);
        return data?.status ? data : { status: 'gagal', error: `Data analisis item gagal dimuat (kode ${response.status}).` };
    }

    function load(from, to, reload = false) {
        stopPolling();
        const mine = ++token;
        attempt = { from, to, reload };
        loading = { reload };
        elements.retryBar.classList.add('hidden');
        if (datasets.length) {
            elements.progressText.textContent = reload ? 'Memperbarui data...' : `Memuat ${formatDate(from)} sampai ${formatDate(to)}…`;
            elements.progressSeconds.textContent = secondsText(0);
        } else screenLoading(from, to);
        setBusy(true);

        const step = async first => {
            const params = { mulai: from, akhir: to };
            if (first && reload) params.ulang = '1';
            if (!first) params.cek = '1';
            const data = await ask(params);
            if (mine !== token) return; // sudah dibatalkan atau diganti pemuatan lain
            if (data.status === 'memuat') {
                showSeconds(data.detik ?? 0);
                pollTimer = setTimeout(() => step(false), 1000);
                return;
            }
            // Batalkan yang sedang difokus akan hilang: fokus pindah ke tombol berikutnya yang masuk akal, bukan ke awal halaman
            const hadFocus = document.activeElement === elements.cancel || elements.screen.contains(document.activeElement);
            loading = null;
            if (data.status === 'siap' && data.hasil?.length) applyData(data, reload);
            else showFailure(data.status === 'siap' ? 'Data analisis item belum tersedia.' : data.error || 'Data analisis item gagal dimuat.');
            setBusy(false);
            if (hadFocus) {
                const failedWithData = datasets.length && !elements.retryBar.classList.contains('hidden');
                (datasets.length ? (failedWithData ? elements.retryButton : elements.refresh) : elements.screen.querySelector('[data-coba]'))?.focus();
            }
        };
        step(true);
    }

    function cancel() {
        token += 1;
        stopPolling();
        loading = null;
        setBusy(false);
        if (datasets.length) elements.refresh.focus();
        else {
            screenFailed('Pemuatan dibatalkan.');
            elements.screen.querySelector('[data-coba]')?.focus();
        }
    }

    // Muat ulang periode yang sama: pilihan tabel, filter, dan halaman tetap. Periode baru: kembali ke awal, seperti di Analytics.
    function applyData(data, reload) {
        const keep = reload && datasets.length ? {
            dataset: elements.dataset.value, company: elements.company.value, category: elements.category.value,
            search: elements.search.value, page,
        } : null;
        datasets = data.hasil;
        shown = data.periode || null;
        periodText = shown ? `${formatDate(shown.mulai)} sampai ${formatDate(shown.akhir)}` : '';
        elements.dataset.innerHTML = datasets.map((dataset, index) =>
            `<option value="${index}">${escapeHtml(dataset.judul || `Hasil ${index + 1}`)}</option>`
        ).join('');
        if (!keep) Object.keys(chartCompanySelections).forEach(key => delete chartCompanySelections[key]);
        elements.dataset.value = keep && Number(keep.dataset) < datasets.length ? keep.dataset : '0';
        renderCharts();
        selectDataset();
        if (keep) {
            if ([...elements.company.options].some(option => option.value === keep.company)) elements.company.value = keep.company;
            if ([...elements.category.options].some(option => option.value === keep.category)) elements.category.value = keep.category;
            elements.search.value = keep.search;
            page = keep.page;
            render();
        }
        elements.periodLabel.textContent = [periodText ? `Periode ${periodText}` : '', fetchedAt(data.dimuat)].filter(Boolean).join(' · ');
        elements.screen.classList.add('hidden');
        elements.bar.classList.remove('hidden');
        elements.charts.classList.remove('hidden');
        elements.tableSection.classList.remove('hidden');
    }

    function showFailure(message) {
        if (!datasets.length) {
            screenFailed(message);
            return;
        }
        elements.retryMessage.textContent = message;
        elements.retryBar.classList.remove('hidden');
    }

    function retry() {
        load(attempt.from, attempt.to, attempt.reload);
    }

    function updatePeriodInfo() {
        const from = elements.periodStart.value;
        const to = elements.periodEnd.value;
        const error = checkPeriod(from, to);
        elements.periodInfo.textContent = error || `Rentang ${formatNumber(daysBetween(from, to) + 1)} hari.`;
        elements.periodInfo.classList.toggle('text-red-700', Boolean(error));
        elements.periodInfo.classList.toggle('text-slate-500', !error);
        elements.periodSubmit.disabled = Boolean(error);
        elements.periodStart.max = to;
        elements.periodEnd.min = from;
    }

    function openPeriod() {
        const base = shown || defaultPeriod();
        elements.periodStart.value = base.mulai;
        elements.periodEnd.value = base.akhir;
        updatePeriodInfo();
        openModal('modalPeriodeItem');
        setTimeout(() => elements.periodStart.focus());
    }

    elements.periodStart.addEventListener('input', updatePeriodInfo);
    elements.periodEnd.addEventListener('input', updatePeriodInfo);
    elements.periodForm.addEventListener('submit', event => {
        event.preventDefault();
        const from = elements.periodStart.value;
        const to = elements.periodEnd.value;
        if (checkPeriod(from, to)) return;
        closeModal('modalPeriodeItem');
        load(from, to);
        // Setelah popup tertutup: tombol Ganti periode nonaktif selama memuat, jadi fokus ke Batalkan
        setTimeout(() => (loading ? elements.cancel : elements.changePeriod).focus());
    });
    elements.changePeriod.addEventListener('click', openPeriod);
    elements.cancel.addEventListener('click', cancel);
    elements.retryButton.addEventListener('click', retry);
    elements.closeMessage.addEventListener('click', () => {
        elements.retryBar.classList.add('hidden');
        elements.refresh.focus();
    });
    elements.screen.addEventListener('click', event => {
        if (event.target.closest('[data-batal]')) cancel();
        else if (event.target.closest('[data-coba]')) retry();
    });

    elements.dataset.addEventListener('change', selectDataset);
    elements.company.addEventListener('change', () => { page = 1; render(); });
    elements.charts.addEventListener('change', event => {
        const select = event.target.closest('[data-chart-company]');
        if (!select) return;
        chartCompanySelections[Number(select.dataset.chartCompany)] = select.value;
        renderCharts();
        // Kartu digambar ulang: fokus kembali ke filter kartu itu, setelah pilih_cari.js memasang tombolnya
        setTimeout(() => document.querySelector(`[data-chart-company="${select.dataset.chartCompany}"]`)?.focus());
    });
    elements.charts.addEventListener('click', event => {
        const button = event.target.closest('[data-rincian]');
        if (button) showInTable(Number(button.dataset.rincian));
    });
    elements.category.addEventListener('change', () => { page = 1; render(); });
    elements.search.addEventListener('input', () => { page = 1; render(); });
    elements.previous.addEventListener('click', () => { page -= 1; render(); });
    elements.next.addEventListener('click', () => { page += 1; render(); });
    elements.refresh.addEventListener('click', () => {
        const period = shown || defaultPeriod();
        load(period.mulai, period.akhir, true);
    });
    const first = defaultPeriod();
    load(first.mulai, first.akhir);
})();
