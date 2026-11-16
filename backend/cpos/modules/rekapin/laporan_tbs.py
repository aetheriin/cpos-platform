"""Laporan Pembelian TBS (Daily / Weekly / Monthly): susunan tabel dari hasil prosedur ERP.

Fungsi format tabel disalin apa adanya dari RekapIn (app.py) supaya angka & susunan laporan tetap sama;
yang baru hanya LAPORAN (kode menu CPOS) dan susun_tabel()."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

LAPORAN = {
    "daily": {"judul": "Pembelian TBS - Daily", "menu": "RK_TBS_DAILY", "prosedur": "dbo.tbsdetailybs2", "periode": "daily"},
    "weekly": {"judul": "Pembelian TBS - Weekly", "menu": "RK_TBS_WEEKLY", "prosedur": "dbo.tbsdetailybsweekly", "periode": "range"},
    "monthly": {"judul": "Pembelian TBS - Monthly", "menu": "RK_TBS_MONTHLY", "prosedur": "dbo.tbsdetailmonthly", "periode": "range"},
}
TBS_WEEKLY_TARGET = 4000
TBS_WEEKLY_TARGET_BY_COMPANY = {"YBS": 7400}


def _report_row_value(row: dict[str, Any], *names: str) -> Any:
    normalized = {
        key.upper().replace(" ", "_"): value
        for key, value in row.items()
    }
    for name in names:
        value = normalized.get(name.upper().replace(" ", "_"))
        if value is not None:
            return value
    return None


def _report_number(value: Any) -> float:
    return float(value or 0)


def _table_row(**values: Any) -> dict[str, Any]:
    return values


def _raw_report_table(title: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": title,
        "headers": list(rows[0]) if rows else [],
        "rows": rows,
        "kind": "raw",
        "group_headers": [],
    }


def daily_report_table(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    first = rows[0]
    if _report_row_value(first, "CATEGORY") is None and "CATEGORY" not in {
        key.upper() for key in first
    }:
        return None

    headers = [
        "JENIS HARGA",
        "HARGA TBS + SPSI",
        "HARGA CPO",
        "PERSENTASE",
        "TONASE",
        "TONASE CPO",
    ]
    details = [
        _table_row(
            **{
                "JENIS HARGA": _report_row_value(row, "CATEGORY") or "—",
                "HARGA TBS + SPSI": _report_row_value(row, "HARGA_TBS_SPSI"),
                "HARGA CPO": _report_row_value(row, "HARGA_CPO"),
                "PERSENTASE": _report_number(_report_row_value(row, "PERSENTASE")) * 100,
                "TONASE": _report_row_value(row, "TONASE"),
                "TONASE CPO": _report_row_value(row, "TONASE_CPO"),
                "_row_type": "detail",
                "_percent_columns": ("PERSENTASE",),
            }
        )
        for row in rows
    ]
    details.sort(
        key=lambda row: (
            row["HARGA TBS + SPSI"] is not None,
            _report_number(row["HARGA TBS + SPSI"]),
        ),
        reverse=True,
    )

    summary_source = next(
        (row for row in rows if _report_row_value(row, "TOTAL_TONASE") is not None),
        first,
    )
    total_percent = _report_number(_report_row_value(summary_source, "PERSENTASE_TOTAL")) * 100
    kernel_percent = _report_number(_report_row_value(summary_source, "PERSENTASE_KERNEL")) * 100
    processing_cost = _report_number(_report_row_value(summary_source, "BIAYA_OLAH_TBS"))
    oer_cpo = _report_row_value(summary_source, "OER_CPO")
    selisih_parts = (
        _report_row_value(summary_source, "OER_CPO"),
        _report_row_value(summary_source, "PERSENTASE_KERNEL"),
        _report_row_value(summary_source, "PERSENTASE_TOTAL"),
        _report_row_value(summary_source, "BIAYA_OLAH_TBS"),
    )
    selisih = (
        _report_number(selisih_parts[0])
        + _report_number(selisih_parts[1]) * 100
        - _report_number(selisih_parts[2]) * 100
        - _report_number(selisih_parts[3])
        if all(value is not None for value in selisih_parts)
        else _report_row_value(summary_source, "SELISIH")
    )
    summary_values = [
        ("TOTAL", None, _report_row_value(summary_source, "TOTAL_TONASE"), _report_row_value(summary_source, "TOTAL_TONASE_CPO"), False),
        ("PERSENTASE (tonase cpo/tonase)", total_percent, None, None, True),
        ("KERNEL", kernel_percent, None, None, True),
        ("OER CPO", oer_cpo, None, None, True),
        ("BIAYA OLAH TBS", processing_cost, None, None, True),
        ("SELISIH( oer cpo + ker - persentase)", selisih, None, None, True),
    ]
    for label, value, tonase, tonase_cpo, is_percentage in summary_values:
        details.append(_table_row(
            **{
                "JENIS HARGA": label,
                "HARGA TBS + SPSI": None,
                "HARGA CPO": None,
                "PERSENTASE": None,
                "TONASE": tonase,
                "TONASE CPO": tonase_cpo if tonase_cpo is not None else value,
                "_row_type": "summary",
                "_percent_columns": ("TONASE CPO",) if is_percentage else (),
            }
        ))
    return {
        "title": "Rincian Pembelian TBS",
        "headers": headers,
        "rows": details,
        "kind": "daily",
        "group_headers": [],
    }


def _weekly_is_rsi_agen(row: dict[str, Any]) -> bool:
    return (
        str(_report_row_value(row, "KATEGORI") or "").strip().upper() == "AGEN"
        and str(_report_row_value(row, "JENIS_KEBUN") or "").strip().upper() == "AGEN BINA"
        and str(_report_row_value(row, "GROUP") or "").strip().upper() == "PT. RIAU SAWIT INDAH"
    )


def weekly_report_table(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows or _report_row_value(rows[0], "PERIODE") is None:
        return None

    periods = list(dict.fromkeys(
        str(_report_row_value(row, "PERIODE"))
        for row in rows
        if _report_row_value(row, "PERIODE") is not None
    ))
    if not periods:
        return None
    identities: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = {}
    identity_order: list[tuple[Any, Any, Any]] = []
    for row in rows:
        period = _report_row_value(row, "PERIODE")
        if period is None:
            continue
        identity = (
            "RSI" if _weekly_is_rsi_agen(row) else _report_row_value(row, "JENIS_KEBUN"),
            _report_row_value(row, "GROUP"),
            "Kebun" if _weekly_is_rsi_agen(row) else _report_row_value(row, "KATEGORI"),
        )
        if identity not in identities:
            identities[identity] = []
            identity_order.append(identity)
        identities[identity].append(row)

    identity_order.sort(key=lambda identity: (
        _weekly_category_order(identity[2]),
        str(identity[0] or "").casefold(),
        str(identity[1] or "").casefold(),
    ))
    identity_headers = ["NO", "KATEGORI", "JENIS KEBUN", "GRUP"]
    statistic_headers = ["STD DEV", "MEAN", "DIFFERENCE"]
    headers = identity_headers + periods + ["ATTENSI"]
    detail_rows: list[dict[str, Any]] = []
    for number, identity in enumerate(identity_order, start=1):
        source_rows = identities[identity]
        rows_by_period: dict[str, list[dict[str, Any]]] = {}
        for source in source_rows:
            rows_by_period.setdefault(str(_report_row_value(source, "PERIODE")), []).append(source)
        evaluated_rows = [
            source for source in source_rows
            if any(_report_row_value(source, field) is not None
                   for field in (*statistic_headers, "ATTENSI"))
        ]
        stats_source = max(
            evaluated_rows,
            key=lambda source: periods.index(str(_report_row_value(source, "PERIODE"))),
            default=source_rows[-1],
        )
        values: dict[str, Any] = {
            "NO": number,
            "KATEGORI": identity[2] or "—",
            "JENIS KEBUN": identity[0] or "—",
            "GRUP": identity[1] or "—",
        }
        gabungkan_rsi = (
            str(identity[0] or "").strip().upper() == "RSI"
            and str(identity[1] or "").strip().upper() == "PT. RIAU SAWIT INDAH"
            and str(identity[2] or "").strip().upper() == "KEBUN"
        )
        for period in periods:
            sumber_periode = rows_by_period.get(period, [])
            tonase = [_report_row_value(source, "TONASE_KG") for source in sumber_periode]
            if gabungkan_rsi and len(sumber_periode) > 1 and any(value is not None for value in tonase):
                values[period] = sum(_report_number(value) for value in tonase if value is not None)
            else:
                values[period] = _report_row_value(sumber_periode[-1], "TONASE_KG") if sumber_periode else None
        values["ATTENSI"] = _report_row_value(stats_source, "ATTENSI")
        values["_row_type"] = "detail"
        values["_percent_columns"] = ()
        detail_rows.append(values)

    group_headers = [
        {"label": "INFORMASI SUPPLIER", "colspan": len(identity_headers)},
        {"label": "PERIODE TONASE", "colspan": len(periods)},
        {"label": "ATTENSI", "colspan": 1},
    ]
    group_headers = [group for group in group_headers if group["colspan"]]
    return {
        "title": "Rincian Pembelian TBS",
        "headers": headers,
        "rows": detail_rows,
        "kind": "weekly",
        "group_headers": group_headers,
    }


def _weekly_category_order(category: Any) -> int:
    teks = str(category or "").strip().upper()
    if teks.startswith("KEBUN"):
        return 0
    if teks.startswith("AGEN"):
        return 1
    if teks.startswith("BRONDOLAN"):
        return 2
    return 3


def monthly_report_tables(
    rows: list[dict[str, Any]],
    extra_results: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    first = rows[0]
    periods = list(dict.fromkeys(
        str(_report_row_value(row, "PERIODE"))
        for row in rows
        if _report_row_value(row, "PERIODE") is not None
    ))
    if not periods:
        periods = [str(_report_row_value(first, "PERIODE") or "Periode")]

    period_headers = [f"{period} TONASE KG" for period in periods]
    detail_headers = ["NO", "JENIS KEBUN", "GRUP", "KATEGORI", *period_headers]
    detail_rows: list[dict[str, Any]] = []
    if _report_row_value(first, "PERIODE") is None:
        for number, row in enumerate(rows, start=1):
            detail_rows.append(_table_row(
                **{
                    "NO": number,
                    "JENIS KEBUN": _report_row_value(row, "JENIS_KEBUN") or _report_row_value(row, "JENIS KEBUN") or "—",
                    "GRUP": _report_row_value(row, "GROUP") or _report_row_value(row, "GRUP") or "—",
                    "KATEGORI": _report_row_value(row, "KATEGORI") or "—",
                    period_headers[0]: _report_row_value(row, "TONASE_KG", "TONASE KG"),
                    "_row_type": "detail",
                    "_percent_columns": (),
                }
            ))
    else:
        identities: dict[tuple[Any, Any, Any], dict[str, dict[str, Any]]] = {}
        identity_order: list[tuple[Any, Any, Any]] = []
        for row in rows:
            period = _report_row_value(row, "PERIODE")
            if period is None:
                continue
            identity = (
                _report_row_value(row, "JENIS_KEBUN", "JENIS KEBUN"),
                _report_row_value(row, "GROUP", "GRUP"),
                _report_row_value(row, "KATEGORI"),
            )
            if identity not in identities:
                identities[identity] = {}
                identity_order.append(identity)
            identities[identity][str(period)] = row

        for number, identity in enumerate(identity_order, start=1):
            values: dict[str, Any] = {
                "NO": number,
                "JENIS KEBUN": identity[0] or "—",
                "GRUP": identity[1] or "—",
                "KATEGORI": identity[2] or "—",
                "_row_type": "detail",
                "_percent_columns": (),
            }
            for period, header in zip(periods, period_headers):
                values[header] = _report_row_value(
                    identities[identity].get(period, {}),
                    "TONASE_KG",
                    "TONASE KG",
                )
            detail_rows.append(values)

    tables = [{
        "title": "Rincian Pembelian TBS",
        "headers": detail_headers,
        "rows": detail_rows,
        "kind": "monthly",
        "group_headers": [
            {"label": "INFORMASI SUPPLIER", "colspan": 4},
            *[
                {"label": period, "colspan": 1}
                for period in periods
            ],
        ],
    }]

    period_summaries: dict[str, dict[str, Any]] = {}
    for period in periods:
        period_rows = [
            row for row in rows
            if _report_row_value(row, "PERIODE") is None
            or str(_report_row_value(row, "PERIODE")) == period
        ]
        summary_source = next(
            (
                row for row in period_rows
                if _report_row_value(
                    row,
                    "TOTAL_TONASE_BULAN",
                    "GRAND_TOTAL",
                ) is not None
            ),
            None,
        )
        if summary_source is None:
            continue
        total = _report_row_value(summary_source, "TOTAL_TONASE_BULAN", "GRAND_TOTAL")
        agents = _report_row_value(summary_source, "AGEN_TOTAL_TON")
        kebun = _report_row_value(summary_source, "KEBUN_TOTAL_TON")
        brondolan = _report_row_value(summary_source, "BRONDOLAN_TOTAL_TON")
        total_number = _report_number(total)
        period_summaries[period] = {
            "GRAND TOTAL": total,
            "AGEN TOTAL": agents,
            "KEBUN TOTAL": kebun,
            "BRONDOLAN TOTAL": brondolan,
            "AGEN %": _report_number(agents) / total_number * 100 if total_number else 0,
            "KEBUN %": _report_number(kebun) / total_number * 100 if total_number else 0,
            "BRONDOLAN %": _report_number(brondolan) / total_number * 100 if total_number else 0,
        }
    if period_summaries:
        summary_labels = (
            "GRAND TOTAL",
            "AGEN TOTAL",
            "KEBUN TOTAL",
            "BRONDOLAN TOTAL",
            "AGEN %",
            "KEBUN %",
            "BRONDOLAN %",
        )
        summary_rows = [
            {
                "RINGKASAN": label,
                **{
                    period: period_summaries.get(period, {}).get(label)
                    for period in periods
                },
                "_row_type": "summary",
                "_percent_columns": tuple(
                    period for period in periods if label.endswith("%")
                ),
            }
            for label in summary_labels
        ]
        tables.append({
            "title": "Summary",
            "headers": ["RINGKASAN", *periods],
            "rows": summary_rows,
            "kind": "monthly_summary",
            "group_headers": [],
        })

    for result in extra_results:
        if result:
            tables.append(_raw_report_table("Summary", result))
    return tables


def tbs_report_value(value: Any, column: str, row: dict[str, Any], kind: str) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)) or hasattr(value, "as_tuple"):
        number = float(value)
        if column in row.get("_percent_columns", ()):
            return f"{number:,.2f}%".replace(",", "_").replace(".", ",").replace("_", ".")
        precision = 2 if (
            column in {"STD DEV", "MEAN", "DIFFERENCE"}
            or kind in {"weekly_summary", "monthly_summary"}
        ) else 0
        rendered = f"{number:,.{precision}f}"
        return rendered.replace(",", "_").replace(".", ",").replace("_", ".")
    return str(value)


def tbs_attensi_class(value: Any) -> str:
    status = str(value or "").strip().upper()
    if status == "NAIK":
        return "attensi-naik"
    if status == "TURUN":
        return "attensi-turun"
    return ""




def web_date_format(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return text
    return text




def weekly_report_summary(rows: list[dict[str, Any]], company: str | None = None) -> list[dict[str, Any]]:
    if not rows:
        return []
    first_row = rows[0]
    period_column = next((key for key in first_row if key.upper() == "PERIODE"), None)
    if period_column is None:
        return []
    fields = {
        key.upper(): key
        for key in first_row
    }
    required_fields = {
        "TOTAL_TONASE_MINGGU",
        "AGEN_TOTAL_TON",
        "KEBUN_TOTAL_TON",
        "BRONDOLAN_TOTAL_TON",
    }
    if not required_fields.issubset(fields):
        return []
    by_period: dict[str, dict[str, Any]] = {}
    for row in rows:
        period = row.get(period_column)
        if period is not None:
            by_period.setdefault(str(period), row)
    if not by_period:
        return []

    period_labels = list(by_period)
    totals = {
        period: float(by_period[period][fields["TOTAL_TONASE_MINGGU"]] or 0)
        for period in period_labels
    }
    agents = {
        period: float(by_period[period][fields["AGEN_TOTAL_TON"]] or 0)
        for period in period_labels
    }
    kebun = {
        period: float(by_period[period][fields["KEBUN_TOTAL_TON"]] or 0)
        for period in period_labels
    }
    brondolan = {
        period: float(by_period[period][fields["BRONDOLAN_TOTAL_TON"]] or 0)
        for period in period_labels
    }
    tonase_agen_rsi: dict[str, float] = {}
    for row in rows:
        if _weekly_is_rsi_agen(row):
            period = _report_row_value(row, "PERIODE")
            tonase = _report_row_value(row, "TONASE")
            if period is not None and tonase is not None:
                tonase_agen_rsi[str(period)] = tonase_agen_rsi.get(str(period), 0) + _report_number(tonase)
    for period, tonase in tonase_agen_rsi.items():
        if period in agents:
            agents[period] -= tonase
            kebun[period] += tonase
    company_key = (company or "").strip().upper()
    fallback_target = TBS_WEEKLY_TARGET_BY_COMPANY.get(company_key, TBS_WEEKLY_TARGET)
    targets = {}
    for period in period_labels:
        target = next(
            (
                _report_row_value(row, "TARGET", "TARGET_TON", "TARGET_TONASE", "TARGET_MINGGU")
                for row in rows
                if str(_report_row_value(row, "PERIODE")) == period
                and _report_row_value(row, "TARGET", "TARGET_TON", "TARGET_TONASE", "TARGET_MINGGU") is not None
            ),
            None,
        )
        targets[period] = _report_number(target) if target is not None else fallback_target
    values_by_metric: list[tuple[str, dict[str, float]]] = [
        ("TOTAL", totals),
        ("TARGET", targets),
        ("PENCAPAIAN %", {
            period: total / targets[period] * 100 if targets[period] else 0
            for period, total in totals.items()
        }),
        ("KEKURANGAN%", {
            period: total / targets[period] * 100 - 100 if targets[period] else 0
            for period, total in totals.items()
        }),
        ("AGEN TOTAL", agents),
        ("KEBUN TOTAL", kebun),
        ("BRONDOLAN TOTAL", brondolan),
        ("AGEN %", {
            period: agents[period] / totals[period] * 100 if totals[period] else 0
            for period in period_labels
        }),
        ("KEBUN %", {
            period: kebun[period] / totals[period] * 100 if totals[period] else 0
            for period in period_labels
        }),
        ("BRONDOLAN %", {
            period: brondolan[period] / totals[period] * 100 if totals[period] else 0
            for period in period_labels
        }),
    ]
    return [
        {"SUMMARY": metric, **metric_values}
        for metric, metric_values in values_by_metric
    ]



def _angka(v: Any) -> bool:
    return v is not None and not isinstance(v, bool) and (isinstance(v, (int, float)) or hasattr(v, "as_tuple"))


def _tandai_kolom_angka(tabel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """tabel["angka"] = kolom yang isinya angka: judul & sel kolom itu rata kanan supaya lurus."""
    for t in tabel:
        t["angka"] = {k for k in t["headers"] if any(_angka(r.get(k)) for r in t["rows"])}
    return tabel


def susun_tabel(jenis: str, hasil: list[list[dict[str, Any]]], company: str | None = None) -> list[dict[str, Any]]:
    """Result set prosedur -> daftar tabel yang ditampilkan (sama dengan render_tbs_report RekapIn)."""
    return _tandai_kolom_angka(_susun_tabel(jenis, hasil, company))


def _susun_tabel(jenis: str, hasil: list[list[dict[str, Any]]], company: str | None = None) -> list[dict[str, Any]]:
    terisi = [rows for rows in hasil if rows]
    if not terisi:
        return []
    utama = terisi[0]
    if jenis == "daily":
        harian = daily_report_table(utama)
        tabel = [harian] if harian else [_raw_report_table("Rincian Pembelian TBS", utama)]
        return tabel + [_raw_report_table("Summary", r) for r in terisi[1:]]
    if jenis == "weekly":
        tabel = []
        mingguan = weekly_report_table(utama)
        if mingguan:
            tabel.append(mingguan)
            ringkas = weekly_report_summary(utama, company)
            if ringkas:
                kolom = list(ringkas[0])
                tabel.append({
                    "title": "Summary", "headers": kolom, "kind": "weekly_summary", "group_headers": [],
                    "rows": [{**row, "_row_type": "summary",
                              "_percent_columns": tuple(c for c in kolom if "%" in str(row.get("SUMMARY", "")) and c != "SUMMARY")}
                             for row in ringkas],
                })
        else:
            tabel.append(_raw_report_table("Rincian Pembelian TBS", utama))
        return tabel + [_raw_report_table("Summary", r) for r in terisi[1:]]
    kunci = {k.upper().replace(" ", "_") for k in utama[0]}
    if {"JENIS_KEBUN", "TONASE_KG"}.issubset(kunci):
        return monthly_report_tables(utama, terisi[1:])
    return [_raw_report_table("Rincian Pembelian TBS" if i == 0 else "Summary", r) for i, r in enumerate(terisi)]
