/* IT Helpdesk - JS mandiri (tanpa dependensi pada dispatcher data-on-*) */
(function () {
  'use strict';

  var MAX_MB = 10;
  var ALLOWED = ['png', 'jpg', 'jpeg', 'pdf', 'xls', 'xlsx', 'csv'];

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  /* 1. Filter: submit otomatis saat status / site diganti */
  $$('form[data-hd-filter] select').forEach(function (el) {
    el.addEventListener('change', function () { el.form.submit(); });
  });

  /* 2. Tabel: urutkan kolom + paging di browser */
  var table = $('table[data-hd-sort]');
  if (table) initTable(table);

  function initTable(tbl) {
    var tbody = $('tbody', tbl);
    var perPage = parseInt(tbody.getAttribute('data-per-halaman'), 10) || 10;
    var rows = $$('tr:not([data-empty])', tbody);
    var pager = $('#hdPager');
    var page = 1;
    var sortIdx = -1;
    var sortDir = 1;

    function cellValue(row, idx, type) {
      var t = (row.cells[idx].textContent || '').trim();
      if (type === 'date') {
        var m = t.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/);
        return m ? new Date(m[3], m[2] - 1, m[1], m[4], m[5]).getTime() : 0;
      }
      return t;
    }

    function render() {
      var total = rows.length;
      var pages = Math.max(1, Math.ceil(total / perPage));
      if (page > pages) page = pages;
      var from = (page - 1) * perPage;
      var to = from + perPage;

      rows.forEach(function (r, i) {
        tbody.appendChild(r);
        r.style.display = (i >= from && i < to) ? '' : 'none';
      });

      if (!pager) return;
      pager.innerHTML = '';
      if (!total) { pager.style.display = 'none'; return; }
      pager.style.display = '';

      var info = document.createElement('span');
      info.textContent = 'Menampilkan ' + (from + 1) + '-' + Math.min(to, total) + ' dari ' + total;

      var nav = document.createElement('div');
      nav.className = 'flex items-center gap-2';
      var prev = document.createElement('button');
      prev.type = 'button'; prev.className = 'btn-secondary disabled:opacity-50 disabled:cursor-not-allowed'; prev.textContent = 'Sebelumnya';
      prev.disabled = page <= 1;
      prev.addEventListener('click', function () { page--; render(); });
      var label = document.createElement('span');
      label.textContent = 'Halaman ' + page + ' / ' + pages;
      var next = document.createElement('button');
      next.type = 'button'; next.className = 'btn-secondary disabled:opacity-50 disabled:cursor-not-allowed'; next.textContent = 'Berikutnya';
      next.disabled = page >= pages;
      next.addEventListener('click', function () { page++; render(); });

      nav.appendChild(prev); nav.appendChild(label); nav.appendChild(next);
      pager.appendChild(info); pager.appendChild(nav);
    }

    $$('th[data-sort]', tbl).forEach(function (th) {
      var icon = document.createElement('i');
      icon.className = 'fa-solid fa-sort ml-1.5 text-xs opacity-50';
      th.appendChild(icon);

      th.addEventListener('click', function () {
        var idx = th.cellIndex;
        var type = th.getAttribute('data-sort');
        sortDir = (sortIdx === idx) ? -sortDir : 1;
        sortIdx = idx;

        rows.sort(function (a, b) {
          var x = cellValue(a, idx, type);
          var y = cellValue(b, idx, type);
          if (typeof x === 'number') return (x - y) * sortDir;
          return x.localeCompare(y, 'id', { numeric: true, sensitivity: 'base' }) * sortDir;
        });

        $$('th[data-sort]', tbl).forEach(function (h) {
          h.lastChild.className = 'fa-solid fa-sort ml-1.5 text-xs opacity-50';
        });
        icon.className = sortDir === 1
          ? 'fa-solid fa-sort-up ml-1.5 text-xs opacity-100'
          : 'fa-solid fa-sort-down ml-1.5 text-xs opacity-100';

        page = 1;
        render();
      });
    });

    render();
  }

  /* 3. Validasi lampiran (ekstensi + ukuran) sebelum dikirim */
  $$('input[type=file][data-hd-file]').forEach(function (inp) {
    var msg = document.createElement('p');
    msg.className = 'text-xs mt-1 text-rose-600';
    msg.style.display = 'none';
    inp.parentNode.insertBefore(msg, inp.nextSibling);

    inp.addEventListener('change', function () {
      var bad = [];
      Array.prototype.forEach.call(inp.files, function (f) {
        var ext = (f.name.split('.').pop() || '').toLowerCase();
        if (ALLOWED.indexOf(ext) < 0) bad.push(f.name + ' (ekstensi tidak diizinkan)');
        else if (f.size > MAX_MB * 1024 * 1024) bad.push(f.name + ' (lebih dari ' + MAX_MB + ' MB)');
      });
      if (bad.length) {
        inp.value = '';
        msg.textContent = 'File ditolak: ' + bad.join(', ');
        msg.style.display = '';
      } else {
        msg.style.display = 'none';
      }
    });
  });

  /* 4. Form tindakan IT: catatan penyelesaian wajib saat status Done */
  var sf = $('form[data-hd-status]');
  if (sf) {
    var sel = $('select[name=status]', sf);
    var res = $('textarea[name=resolution_note]', sf);
    var sync = function () {
      var done = sel.value === 'Done';
      res.required = done;
      res.placeholder = done ? 'Wajib diisi saat status Done' : 'Isi saat status Done';
    };
    sel.addEventListener('change', sync);
    sync();
  }

  /* 5. Cegah klik ganda saat submit */
  $$('form[data-hd-once]').forEach(function (f) {
    f.addEventListener('submit', function () {
      var b = $('button[type=submit]', f);
      if (b) setTimeout(function () { b.disabled = true; }, 0);
    });
  });
  window.addEventListener('pageshow', function () {
    $$('form[data-hd-once] button[type=submit]').forEach(function (b) { b.disabled = false; });
  });
})();
