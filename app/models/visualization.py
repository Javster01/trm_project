from collections import defaultdict
from html import escape

from .data_loader import load_trm_data


def _month_period(dt):
    return f"{dt.year:04d}-{dt.month:02d}"


def _aggregate_monthly_avg(records):
    buckets = defaultdict(list)
    for item in records:
        buckets[_month_period(item["date"])].append(item["trm"])

    monthly = []
    for period in sorted(buckets.keys()):
        vals = buckets[period]
        monthly.append(
            {
                "period": period,
                "avg": float(sum(vals) / len(vals)),
                "count": len(vals),
            }
        )

    return monthly


def _sparkline_svg(values, labels, width=980, height=300):
    if not values:
        return '<svg viewBox="0 0 980 180"><text x="20" y="40">Sin datos para graficar.</text></svg>'

    pad_left = 50
    pad_right = 20
    pad_top = 20
    pad_bottom = 40

    min_v = min(values)
    max_v = max(values)
    v_range = (max_v - min_v) or 1.0

    usable_w = width - pad_left - pad_right
    usable_h = height - pad_top - pad_bottom

    points = []
    for i, v in enumerate(values):
        x = pad_left + (i * usable_w / (len(values) - 1 if len(values) > 1 else 1))
        y = pad_top + ((max_v - v) / v_range) * usable_h
        points.append((x, y))

    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)

    # grid lines + Y axis labels
    grid = []
    for k in range(5):
        y = pad_top + (k * usable_h / 4)
        value = max_v - (k * v_range / 4)
        grid.append(
            f'<line x1="{pad_left}" y1="{y:.2f}" x2="{width - pad_right}" y2="{y:.2f}" stroke="#e2e8f0" stroke-width="1" />'
        )
        grid.append(
            f'<text x="8" y="{y + 4:.2f}" fill="#64748b" font-size="11">{value:,.0f}</text>'
        )

    # X axis guide ticks (every 6 months and last point)
    x_ticks = []
    for i, lbl in enumerate(labels):
        if i % 6 == 0 or i == len(labels) - 1:
            x = pad_left + (i * usable_w / (len(values) - 1 if len(values) > 1 else 1))
            x_ticks.append(
                f'<line x1="{x:.2f}" y1="{height - pad_bottom}" x2="{x:.2f}" y2="{height - pad_bottom + 5}" stroke="#94a3b8" stroke-width="1" />'
            )
            x_ticks.append(
                f'<text x="{x - 18:.2f}" y="{height - 8}" fill="#64748b" font-size="10">{escape(lbl)}</text>'
            )

    points_with_tooltips = []
    for i, (x, y) in enumerate(points):
        radius = 3.5 if i != len(points) - 1 else 4.5
        fill = "#1d4ed8" if i != len(points) - 1 else "#0f172a"
        label = escape(labels[i]) if i < len(labels) else f"idx-{i}"
        points_with_tooltips.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" class="chart-point">'
            f'<title>{label}: {values[i]:,.2f}</title>'
            f'</circle>'
        )

    start_label = escape(labels[0]) if labels else ""
    end_label = escape(labels[-1]) if labels else ""

    return f'''
<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Tendencia TRM últimos 36 meses">
    {''.join(grid)}
    <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#64748b" stroke-width="1.2" />
    {''.join(x_ticks)}
    <polyline points="{polyline}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    {''.join(points_with_tooltips)}
    <text x="{pad_left}" y="{height - 10}" fill="#64748b" font-size="11">{start_label}</text>
    <text x="{width - pad_right - 60}" y="{height - 10}" fill="#64748b" font-size="11">{end_label}</text>
</svg>
'''.strip()


def _bars_svg(changes, labels, width=980, height=300):
    if not changes:
        return '<svg viewBox="0 0 980 180"><text x="20" y="40">Sin datos para variación mensual.</text></svg>'

    pad_left = 50
    pad_right = 20
    pad_top = 20
    pad_bottom = 40

    max_abs = max(abs(v) for v in changes) or 1.0
    usable_w = width - pad_left - pad_right
    usable_h = height - pad_top - pad_bottom

    zero_y = pad_top + usable_h / 2
    bar_w = max(4, usable_w / max(len(changes), 1) * 0.75)

    bars = []
    for i, v in enumerate(changes):
        x_center = pad_left + ((i + 0.5) * usable_w / len(changes))
        h = (abs(v) / max_abs) * (usable_h / 2)
        y = zero_y - h if v >= 0 else zero_y
        color = "#16a34a" if v >= 0 else "#dc2626"
        lbl = escape(labels[i]) if i < len(labels) else f"idx-{i}"
        bars.append(
            f'<rect x="{x_center - bar_w/2:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}" rx="2" class="chart-bar">'
            f'<title>{lbl}: {v:+,.2f}</title>'
            f'</rect>'
        )

    x_ticks = []
    for i, lbl in enumerate(labels):
        if i % 6 == 0 or i == len(labels) - 1:
            x = pad_left + ((i + 0.5) * usable_w / len(changes))
            x_ticks.append(
                f'<line x1="{x:.2f}" y1="{height - pad_bottom}" x2="{x:.2f}" y2="{height - pad_bottom + 5}" stroke="#94a3b8" stroke-width="1" />'
            )
            x_ticks.append(
                f'<text x="{x - 18:.2f}" y="{height - 8}" fill="#64748b" font-size="10">{escape(lbl)}</text>'
            )

    return f'''
<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Variación mensual TRM últimos 36 meses">
    <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#64748b" stroke-width="1.2" />
    <line x1="{pad_left}" y1="{zero_y:.2f}" x2="{width - pad_right}" y2="{zero_y:.2f}" stroke="#475569" stroke-width="1.4" />
    {''.join(x_ticks)}
    {''.join(bars)}
    <text x="{pad_left}" y="{height - 10}" fill="#64748b" font-size="11">{escape(labels[0]) if labels else ''}</text>
    <text x="{width - pad_right - 60}" y="{height - 10}" fill="#64748b" font-size="11">{escape(labels[-1]) if labels else ''}</text>
</svg>
'''.strip()


def _moving_average(values, window=3):
    if not values:
        return []
    out = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _index_base_100(values):
    if not values:
        return []
    base = values[0] if values[0] else 1.0
    return [(v / base) * 100 for v in values]


def _two_line_svg(values_a, values_b, labels, line_a_label, line_b_label, width=980, height=300):
    if not values_a or not values_b:
        return '<svg viewBox="0 0 980 180"><text x="20" y="40">Sin datos para gráfica comparativa.</text></svg>'

    pad_left = 50
    pad_right = 20
    pad_top = 20
    pad_bottom = 40

    merged = values_a + values_b
    min_v = min(merged)
    max_v = max(merged)
    v_range = (max_v - min_v) or 1.0

    usable_w = width - pad_left - pad_right
    usable_h = height - pad_top - pad_bottom

    def to_points(vals):
        pts = []
        for i, v in enumerate(vals):
            x = pad_left + (i * usable_w / (len(vals) - 1 if len(vals) > 1 else 1))
            y = pad_top + ((max_v - v) / v_range) * usable_h
            pts.append((x, y))
        return pts

    pts_a = to_points(values_a)
    pts_b = to_points(values_b)
    poly_a = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts_a)
    poly_b = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts_b)

    grid = []
    for k in range(5):
        y = pad_top + (k * usable_h / 4)
        value = max_v - (k * v_range / 4)
        grid.append(f'<line x1="{pad_left}" y1="{y:.2f}" x2="{width - pad_right}" y2="{y:.2f}" stroke="#e2e8f0" stroke-width="1" />')
        grid.append(f'<text x="8" y="{y + 4:.2f}" fill="#64748b" font-size="11">{value:,.2f}</text>')

    x_ticks = []
    for i, lbl in enumerate(labels):
        if i % 6 == 0 or i == len(labels) - 1:
            x = pad_left + (i * usable_w / (len(labels) - 1 if len(labels) > 1 else 1))
            x_ticks.append(f'<line x1="{x:.2f}" y1="{height - pad_bottom}" x2="{x:.2f}" y2="{height - pad_bottom + 5}" stroke="#94a3b8" stroke-width="1" />')
            x_ticks.append(f'<text x="{x - 18:.2f}" y="{height - 8}" fill="#64748b" font-size="10">{escape(lbl)}</text>')

    return f'''
<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Gráfica comparativa">
    {''.join(grid)}
    <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#64748b" stroke-width="1.2" />
    {''.join(x_ticks)}
    <polyline points="{poly_a}" fill="none" stroke="#2563eb" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />
    <polyline points="{poly_b}" fill="none" stroke="#f59e0b" stroke-width="2.4" stroke-dasharray="5 4" stroke-linecap="round" stroke-linejoin="round" />
    <text x="{pad_left}" y="{pad_top - 6}" fill="#2563eb" font-size="11">● {escape(line_a_label)}</text>
    <text x="{pad_left + 170}" y="{pad_top - 6}" fill="#f59e0b" font-size="11">● {escape(line_b_label)}</text>
    <title>{escape(line_a_label)} vs {escape(line_b_label)}</title>
</svg>
'''.strip()


def _seasonality_svg(series, width=980, height=300):
    if not series:
        return '<svg viewBox="0 0 980 180"><text x="20" y="40">Sin datos para estacionalidad.</text></svg>'

    month_names = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
    }

    by_month = defaultdict(list)
    for row in series:
        month = int(row["period"].split("-")[1])
        by_month[month].append(row["avg"])

    months = list(range(1, 13))
    vals = [sum(by_month[m]) / len(by_month[m]) if by_month[m] else 0.0 for m in months]

    pad_left = 50
    pad_right = 20
    pad_top = 20
    pad_bottom = 40
    usable_w = width - pad_left - pad_right
    usable_h = height - pad_top - pad_bottom
    min_v = min(vals)
    max_v = max(vals)
    v_range = (max_v - min_v) or 1.0
    bar_w = usable_w / 12 * 0.7

    bars = []
    labels = []
    for i, m in enumerate(months):
        v = vals[i]
        x = pad_left + (i + 0.15) * (usable_w / 12)
        h = ((v - min_v) / v_range) * usable_h
        y = pad_top + usable_h - h
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="#0ea5e9" rx="2" class="chart-bar"><title>{month_names[m]}: {v:,.2f}</title></rect>'
        )
        labels.append(f'<text x="{x + bar_w/2 - 10:.2f}" y="{height - 10}" fill="#64748b" font-size="10">{month_names[m]}</text>')

    return f'''
<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Estacionalidad mensual TRM">
    <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#64748b" stroke-width="1.2" />
    {''.join(bars)}
    {''.join(labels)}
</svg>
'''.strip()


def _histogram_svg(values, bins=10, width=980, height=300):
    if not values:
        return '<svg viewBox="0 0 980 180"><text x="20" y="40">Sin datos para distribución.</text></svg>'

    min_v = min(values)
    max_v = max(values)
    v_range = (max_v - min_v) or 1.0
    step = v_range / bins

    counts = [0] * bins
    for v in values:
        idx = int((v - min_v) / step) if step else 0
        idx = min(idx, bins - 1)
        counts[idx] += 1

    pad_left = 50
    pad_right = 20
    pad_top = 20
    pad_bottom = 40
    usable_w = width - pad_left - pad_right
    usable_h = height - pad_top - pad_bottom
    max_c = max(counts) or 1
    bar_w = usable_w / bins * 0.8

    bars = []
    for i, c in enumerate(counts):
        x = pad_left + (i + 0.1) * (usable_w / bins)
        h = (c / max_c) * usable_h
        y = pad_top + usable_h - h
        b_start = min_v + i * step
        b_end = b_start + step
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="#8b5cf6" rx="2" class="chart-bar"><title>{b_start:,.2f} - {b_end:,.2f}: {c} meses</title></rect>'
        )

    return f'''
<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Distribución de promedios mensuales TRM">
    <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#64748b" stroke-width="1.2" />
    {''.join(bars)}
    <text x="{pad_left}" y="{height - 10}" fill="#64748b" font-size="10">{min_v:,.0f}</text>
    <text x="{width - pad_right - 50}" y="{height - 10}" fill="#64748b" font-size="10">{max_v:,.0f}</text>
</svg>
'''.strip()


def get_last_36_months_visualization():
    records = load_trm_data()
    monthly = _aggregate_monthly_avg(records)
    # Se entrega toda la serie para permitir filtros rápidos (12/24/36/Todo) en frontend.
    # La vista sigue iniciando en 36 meses por la configuración de `visualQuickWindow`.
    last_36 = monthly

    if not last_36:
        return {
            "count_months": 0,
            "start_period": None,
            "end_period": None,
            "latest_avg": None,
            "series": [],
            "line_svg": _sparkline_svg([], []),
            "change_svg": _bars_svg([], []),
            "moving_avg_svg": _two_line_svg([], [], [], "", ""),
            "index_base_svg": _two_line_svg([], [], [], "", ""),
            "seasonality_svg": _seasonality_svg([]),
            "distribution_svg": _histogram_svg([]),
        }

    series = []
    prev_avg = None
    for row in last_36:
        avg = row["avg"]
        change_abs = None if prev_avg is None else avg - prev_avg
        change_pct = None if prev_avg in (None, 0) else (change_abs / prev_avg) * 100

        series.append(
            {
                "period": row["period"],
                "avg": avg,
                "change_abs": change_abs,
                "change_pct": change_pct,
            }
        )
        prev_avg = avg

    values = [s["avg"] for s in series]
    labels = [s["period"] for s in series]
    changes = [s["change_abs"] or 0.0 for s in series[1:]]
    change_labels = [s["period"] for s in series[1:]]
    moving_avg_3 = _moving_average(values, window=3)
    index_base = _index_base_100(values)
    index_base_ma = _moving_average(index_base, window=3)

    return {
        "count_months": len(series),
        "start_period": series[0]["period"],
        "end_period": series[-1]["period"],
        "latest_avg": series[-1]["avg"],
        "series": series,
        "line_svg": _sparkline_svg(values, labels),
        "change_svg": _bars_svg(changes, change_labels),
        "moving_avg_svg": _two_line_svg(values, moving_avg_3, labels, "Promedio mensual", "Media móvil 3M"),
        "index_base_svg": _two_line_svg(index_base, index_base_ma, labels, "Índice base 100", "Media móvil índice 3M"),
        "seasonality_svg": _seasonality_svg(series),
        "distribution_svg": _histogram_svg(values),
    }
