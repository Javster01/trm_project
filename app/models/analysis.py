from calendar import monthrange
from statistics import median, pstdev

from .data_loader import load_trm_data


def _percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    if p <= 0:
        return float(sorted_values[0])
    if p >= 100:
        return float(sorted_values[-1])

    k = (len(sorted_values) - 1) * (p / 100)
    low = int(k)
    high = min(low + 1, len(sorted_values) - 1)
    if low == high:
        return float(sorted_values[low])

    frac = k - low
    return float(sorted_values[low] * (1 - frac) + sorted_values[high] * frac)


def _linear_slope(values):
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2
    y_mean = sum(values) / n

    num = 0.0
    den = 0.0
    for i, y in enumerate(values):
        dx = i - x_mean
        num += dx * (y - y_mean)
        den += dx * dx

    return float(num / den) if den else 0.0


def _subtract_months(dt, months):
    if months <= 0:
        return dt

    total_months = (dt.year * 12 + (dt.month - 1)) - months
    year = total_months // 12
    month = (total_months % 12) + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _records_last_n_months(records, months):
    if not records:
        return []
    if months <= 0:
        return list(records)

    latest_date = records[-1]["date"]
    cutoff = _subtract_months(latest_date, months)
    return [item for item in records if item["date"] >= cutoff]


def _build_eda(records, monthly_periods_limit=12, yearly_periods_limit=10):
    if not records:
        return {
            "meta": {"count": 0},
            "descriptive": {},
            "outliers": {},
            "trend": {},
            "volatility": {},
            "latest": {},
            "monthly_summary": [],
            "yearly_summary": [],
        }

    values = [item["trm"] for item in records]
    dates = [item["date"] for item in records]
    sorted_values = sorted(values)

    count = len(values)
    min_v = float(min(values))
    max_v = float(max(values))
    mean_v = float(sum(values) / count)
    std_v = float(pstdev(values)) if count > 1 else 0.0
    median_v = float(median(values))

    q1 = _percentile(sorted_values, 25)
    q3 = _percentile(sorted_values, 75)
    p10 = _percentile(sorted_values, 10)
    p90 = _percentile(sorted_values, 90)
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outlier_values = [v for v in values if v < lower_bound or v > upper_bound]

    diffs = [values[i] - values[i - 1] for i in range(1, count)]
    avg_abs_daily_change = float(sum(abs(d) for d in diffs) / len(diffs)) if diffs else 0.0
    max_up_day = float(max(diffs)) if diffs else 0.0
    max_down_day = float(min(diffs)) if diffs else 0.0

    slope = _linear_slope(values)
    abs_change = float(values[-1] - values[0])
    pct_change = float((abs_change / values[0]) * 100) if values[0] else 0.0
    if abs_change > 0:
        direction = "up"
    elif abs_change < 0:
        direction = "down"
    else:
        direction = "flat"

    monthly_buckets = {}
    yearly_buckets = {}
    for item in records:
        d = item["date"]
        v = item["trm"]
        m_key = d.strftime("%Y-%m")
        y_key = d.year

        monthly_buckets.setdefault(m_key, []).append(v)
        yearly_buckets.setdefault(y_key, []).append(v)

    monthly_summary = []
    monthly_keys = sorted(monthly_buckets.keys())
    if monthly_periods_limit and monthly_periods_limit > 0:
        monthly_keys = monthly_keys[-monthly_periods_limit:]

    for m in monthly_keys:
        vals = monthly_buckets[m]
        monthly_summary.append(
            {
                "period": m,
                "count": len(vals),
                "avg": float(sum(vals) / len(vals)),
                "min": float(min(vals)),
                "max": float(max(vals)),
            }
        )

    yearly_summary = []
    yearly_keys = sorted(yearly_buckets.keys())
    if yearly_periods_limit and yearly_periods_limit > 0:
        yearly_keys = yearly_keys[-yearly_periods_limit:]

    for y in yearly_keys:
        vals = yearly_buckets[y]
        yearly_summary.append(
            {
                "year": int(y),
                "count": len(vals),
                "avg": float(sum(vals) / len(vals)),
                "min": float(min(vals)),
                "max": float(max(vals)),
            }
        )

    return {
        "meta": {
            "count": count,
            "start_date": dates[0].strftime("%Y-%m-%d"),
            "end_date": dates[-1].strftime("%Y-%m-%d"),
        },
        "descriptive": {
            "mean": mean_v,
            "median": median_v,
            "std": std_v,
            "cv": float((std_v / mean_v) * 100) if mean_v else 0.0,
            "min": min_v,
            "max": max_v,
            "p10": p10,
            "q1": q1,
            "q3": q3,
            "p90": p90,
            "iqr": iqr,
        },
        "outliers": {
            "count": len(outlier_values),
            "ratio_pct": float((len(outlier_values) / count) * 100),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
        },
        "trend": {
            "direction": direction,
            "absolute_change": abs_change,
            "percent_change": pct_change,
            "slope_per_step": float(slope),
        },
        "volatility": {
            "avg_abs_daily_change": avg_abs_daily_change,
            "max_up_day": max_up_day,
            "max_down_day": max_down_day,
        },
        "latest": {
            "date": dates[-1].strftime("%Y-%m-%d"),
            "value": float(values[-1]),
            "prev_date": dates[-2].strftime("%Y-%m-%d") if count > 1 else dates[-1].strftime("%Y-%m-%d"),
            "prev_value": float(values[-2]) if count > 1 else float(values[-1]),
            "delta": float(values[-1] - values[-2]) if count > 1 else 0.0,
        },
        "monthly_summary": monthly_summary,
        "yearly_summary": yearly_summary,
    }


def get_eda():
    return _build_eda(load_trm_data(), monthly_periods_limit=12, yearly_periods_limit=10)


def get_eda_last_36_months():
    records = load_trm_data()
    last_36_months = _records_last_n_months(records, 36)
    eda = _build_eda(last_36_months, monthly_periods_limit=36, yearly_periods_limit=3)
    eda["meta"]["window_months"] = 36
    eda["meta"]["scope"] = "last_36_months"
    return eda


def get_analysis():
    """Compatibilidad con endpoints existentes (/predict)."""
    eda = get_eda()
    desc = eda.get("descriptive", {})

    return {
        "mean": float(desc.get("mean", 0.0)),
        "std": float(desc.get("std", 0.0)),
        "max": float(desc.get("max", 0.0)),
        "min": float(desc.get("min", 0.0)),
    }