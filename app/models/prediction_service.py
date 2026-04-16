from __future__ import annotations

from calendar import monthrange
from collections import defaultdict

import mlflow

from .analysis import get_analysis
from .data_loader import load_trm_data
from .mlflow_integration import _tracking_uri, _experiment_name
from .monte_carlo import build_monte_carlo_simulation
from .random_forest import build_random_forest_prediction


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


def _aggregate_monthly_avg(records):
    buckets = defaultdict(list)
    for item in records:
        period = item["date"].strftime("%Y-%m")
        buckets[period].append(float(item["trm"]))

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


def _build_history_from_records(records, limit_months=36):
    monthly = _aggregate_monthly_avg(records)
    if limit_months and limit_months > 0:
        monthly = monthly[-limit_months:]

    if not monthly:
        return {
            "count_months": 0,
            "start_period": None,
            "end_period": None,
            "latest_avg": None,
            "series": [],
        }

    series = []
    prev_avg = None
    for row in monthly:
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

    return {
        "count_months": len(series),
        "start_period": series[0]["period"],
        "end_period": series[-1]["period"],
        "latest_avg": series[-1]["avg"],
        "series": series,
    }


def _build_scope_prediction(records, scenarios, scope_key, scope_label):
    rf = build_random_forest_prediction(records=records)
    mc = build_monte_carlo_simulation(records=records, scenarios=scenarios)
    history = _build_history_from_records(records, limit_months=36)

    rf_forecast = float(rf["forecast"]["next_month_projection"])
    mc_projection = float(mc["projection_next_month"])
    gap = rf_forecast - mc_projection
    gap_pct = (gap / mc_projection * 100) if mc_projection else 0.0
    alignment = max(0.0, 100.0 - min(abs(gap_pct), 100.0))
    recommendation = "Los modelos están alineados" if abs(gap_pct) < 3 else ("RF está por encima del escenario Monte Carlo" if gap > 0 else "Monte Carlo sugiere una TRM superior a RF")

    return {
        "scope": {
            "key": scope_key,
            "label": scope_label,
            "records_count": len(records),
            "start_date": records[0]["date"].strftime("%Y-%m-%d") if records else None,
            "end_date": records[-1]["date"].strftime("%Y-%m-%d") if records else None,
        },
        "history": history,
        "random_forest": rf,
        "monte_carlo": mc,
        "comparison": {
            "gap": gap,
            "gap_pct": gap_pct,
            "alignment_score": alignment,
            "rf_forecast": rf_forecast,
            "mc_projection": mc_projection,
            "message": recommendation,
        },
        "recommendation": recommendation,
    }


def build_prediction_dashboard(scenarios=1000):
    """Construye el dashboard con trazabilidad automática de pasos."""
    tracking_uri = _tracking_uri()
    experiment_name = _experiment_name()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    
    traces = []  # Colectar todos los pasos para registrar como trazabilidad

    with mlflow.start_run(run_name="random_forest_vs_monte_carlo") as run:
        # Paso 1: Cargar datos
        records = load_trm_data()
        records_36m = _records_last_n_months(records, 36)
        if len(records_36m) < 3:
            records_36m = list(records)

        data_points = len(records)
        traces.append({
            "name": "load_data",
            "inputs": {"source": "TRM_20260413.csv"},
            "outputs": {"records_loaded": data_points, "records_loaded_36m": len(records_36m)}
        })
        mlflow.log_text(f"Cargados {data_points} registros del histórico TRM | ventana 36M: {len(records_36m)}", "traces/01_load_data.txt")

        # Paso 2: Calcular predicción con histórico completo
        full_scope = _build_scope_prediction(records=records, scenarios=scenarios, scope_key="all_data", scope_label="Todos los datos")
        rf = full_scope["random_forest"]
        mc = full_scope["monte_carlo"]

        traces.append({
            "name": "train_random_forest",
            "inputs": {"records_count": data_points, "features": ["day", "month", "year"], "test_ratio": 0.2},
            "outputs": {"mae": rf["metrics"]["mae"], "rmse": rf["metrics"]["rmse"], "r2": rf["metrics"]["r2"]}
        })
        mlflow.log_text(f"RF entrenado: MAE={rf['metrics']['mae']:.2f}, RMSE={rf['metrics']['rmse']:.2f}, R2={rf['metrics']['r2']:.4f}", "traces/02_train_random_forest.txt")

        # Paso 3: Simulación Monte Carlo (histórico completo)
        traces.append({
            "name": "monte_carlo_simulation",
            "inputs": {"records_count": data_points, "scenarios": scenarios},
            "outputs": {"projection": mc["projection_next_month"], "p05": mc["percentiles"]["p05"], "p95": mc["percentiles"]["p95"]}
        })
        mlflow.log_text(f"MC simulado: {scenarios} escenarios | Proyección={mc['projection_next_month']:.2f} | P05={mc['percentiles']['p05']:.2f} | P95={mc['percentiles']['p95']:.2f}", "traces/03_monte_carlo_simulation.txt")

        # Paso 4: Calcular predicción para últimos 36 meses
        scope_36m = _build_scope_prediction(records=records_36m, scenarios=scenarios, scope_key="last_36_months", scope_label="Últimos 36 meses")

        traces.append({
            "name": "analysis_visualization",
            "inputs": {"analysis_type": "dual_scope"},
            "outputs": {"history_months_full": full_scope["history"]["count_months"], "history_months_36m": scope_36m["history"]["count_months"]}
        })
        mlflow.log_text("Predicciones por alcance completadas: histórico completo y últimos 36 meses", "traces/04_analysis_visualization.txt")

        # Paso 5: Comparación de modelos (alcance completo para métricas principales)
        analysis = get_analysis()
        full_comparison = full_scope["comparison"]
        rf_forecast = float(full_comparison["rf_forecast"])
        mc_projection = float(full_comparison["mc_projection"])
        gap = float(full_comparison["gap"])
        gap_pct = float(full_comparison["gap_pct"])
        alignment = float(full_comparison["alignment_score"])
        traces.append({
            "name": "model_comparison",
            "inputs": {"rf_forecast": rf_forecast, "mc_projection": mc_projection},
            "outputs": {"gap": gap, "gap_pct": gap_pct, "alignment_score": alignment}
        })
        mlflow.log_text(f"Comparación: Gap={gap:.2f} ({gap_pct:.2f}%) | Alineación={alignment:.2f}%", "traces/05_model_comparison.txt")

        # Paso 6: Persistir métricas y artefactos
        mlflow.log_params({
            "model": rf["model_name"],
            "features": ",".join(rf["feature_names"]),
            "n_estimators": 300,
            "scenarios": scenarios,
            "records_full": len(records),
            "records_last_36m": len(records_36m),
        })
        mlflow.log_metrics({
            "rf_mae": rf["metrics"]["mae"],
            "rf_rmse": rf["metrics"]["rmse"],
            "rf_r2": rf["metrics"]["r2"],
            "mc_projection": mc_projection,
            "model_gap": gap,
            "model_gap_pct": gap_pct,
            "36m_rf_mae": scope_36m["random_forest"]["metrics"]["mae"],
            "36m_rf_rmse": scope_36m["random_forest"]["metrics"]["rmse"],
            "36m_rf_r2": scope_36m["random_forest"]["metrics"]["r2"],
            "36m_mc_projection": scope_36m["monte_carlo"]["projection_next_month"],
            "36m_model_gap": scope_36m["comparison"]["gap"],
            "36m_model_gap_pct": scope_36m["comparison"]["gap_pct"],
        })
        mlflow.log_dict({
            "analysis": analysis,
            "scopes": {
                "all_data": {
                    "scope": full_scope["scope"],
                    "comparison": full_scope["comparison"],
                    "random_forest": {
                        "metrics": full_scope["random_forest"]["metrics"],
                        "feature_importance": full_scope["random_forest"]["feature_importance"],
                        "forecast": full_scope["random_forest"]["forecast"],
                    },
                    "monte_carlo": {
                        "historical": full_scope["monte_carlo"]["historical"],
                        "projection_next_month": full_scope["monte_carlo"]["projection_next_month"],
                        "percentiles": full_scope["monte_carlo"]["percentiles"],
                    },
                },
                "last_36_months": {
                    "scope": scope_36m["scope"],
                    "comparison": scope_36m["comparison"],
                    "random_forest": {
                        "metrics": scope_36m["random_forest"]["metrics"],
                        "feature_importance": scope_36m["random_forest"]["feature_importance"],
                        "forecast": scope_36m["random_forest"]["forecast"],
                    },
                    "monte_carlo": {
                        "historical": scope_36m["monte_carlo"]["historical"],
                        "projection_next_month": scope_36m["monte_carlo"]["projection_next_month"],
                        "percentiles": scope_36m["monte_carlo"]["percentiles"],
                    },
                },
            },
        }, "prediction_summary.json")
        
        # Registrar trazas como artefactos individuales (visible en MLflow UI)
        for trace in traces:
            mlflow.log_dict(trace, f"traces/{trace['name']}.json")
        
        traces.append({
            "name": "log_mlflow_artifacts",
            "inputs": {"artifact_count": len(traces)},
            "outputs": {"run_id": run.info.run_id}
        })
        mlflow.log_text(f"Trazabilidad: {len(traces)} pasos registrados en este run", "traces/06_log_mlflow_artifacts.txt")

        recommendation = full_scope["recommendation"]

        mlflow_run_info = {
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "run_id": run.info.run_id,
            "artifact_uri": run.info.artifact_uri,
        }

        return {
            "analysis": analysis,
            "history": full_scope["history"],
            "random_forest": full_scope["random_forest"],
            "monte_carlo": full_scope["monte_carlo"],
            "comparison": full_scope["comparison"],
            "scopes": {
                "all_data": full_scope,
                "last_36_months": scope_36m,
            },
            "default_scope": "all_data",
            "mlflow": mlflow_run_info,
            "recommendation": recommendation,
        }