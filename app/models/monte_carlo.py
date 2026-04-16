from __future__ import annotations

import calendar
from datetime import timedelta

import numpy as np

from .data_loader import load_trm_data


def _next_month_length(latest_date):
    first_next = (latest_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    return calendar.monthrange(first_next.year, first_next.month)[1]


def build_monte_carlo_simulation(records=None, scenarios=1000, random_state=42):
    if records is None:
        records = load_trm_data()

    ordered = sorted(records, key=lambda item: item["date"])
    if len(ordered) < 3:
        raise ValueError("Se necesitan al menos 3 registros para simular Monte Carlo")

    values = np.array([float(item["trm"]) for item in ordered], dtype=float)
    changes = np.diff(values)
    mean_change = float(np.mean(changes)) if len(changes) else 0.0
    std_change = float(np.std(changes, ddof=0)) if len(changes) else 0.0
    if std_change == 0:
        std_change = max(abs(mean_change) * 0.1, 1.0)

    latest_value = float(values[-1])
    latest_date = ordered[-1]["date"].date()
    days_next_month = _next_month_length(latest_date)
    rng = np.random.default_rng(random_state)

    scenario_end_values = []
    for _ in range(scenarios):
        daily_shocks = rng.normal(loc=mean_change, scale=std_change, size=days_next_month)
        path = latest_value + np.cumsum(daily_shocks)
        scenario_end_values.append(float(path[-1]))

    projection = float(np.mean(scenario_end_values))
    scenario_std = float(np.std(scenario_end_values, ddof=0)) if len(scenario_end_values) else 0.0
    p05, p50, p95 = [float(x) for x in np.percentile(scenario_end_values, [5, 50, 95])]

    return {
        "scenario_count": int(scenarios),
        "historical": {
            "mean_change": mean_change,
            "std_change": std_change,
            "latest_value": latest_value,
            "days_next_month": int(days_next_month),
        },
        "projection_next_month": projection,
        "scenario_std": scenario_std,
        "percentiles": {
            "p05": p05,
            "p50": p50,
            "p95": p95,
        },
        "scenarios": [float(value) for value in scenario_end_values],
    }


def simulate_trm(n=10):
    simulation = build_monte_carlo_simulation(scenarios=max(int(n), 1))
    return [round(value, 2) for value in simulation["scenarios"][:n]]