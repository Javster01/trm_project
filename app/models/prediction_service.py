from __future__ import annotations

import mlflow

from .analysis import get_analysis
from .data_loader import load_trm_data
from .mlflow_integration import _tracking_uri, _experiment_name
from .monte_carlo import build_monte_carlo_simulation
from .random_forest import build_random_forest_prediction
from .visualization import get_last_36_months_visualization


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
        data_points = len(records)
        traces.append({
            "name": "load_data",
            "inputs": {"source": "TRM_20260413.csv"},
            "outputs": {"records_loaded": data_points}
        })
        mlflow.log_text(f"Cargados {data_points} registros del histórico TRM", "traces/01_load_data.txt")

        # Paso 2: Entrenar Random Forest
        rf = build_random_forest_prediction(records=records)
        traces.append({
            "name": "train_random_forest",
            "inputs": {"records_count": data_points, "features": ["day", "month", "year"], "test_ratio": 0.2},
            "outputs": {"mae": rf["metrics"]["mae"], "rmse": rf["metrics"]["rmse"], "r2": rf["metrics"]["r2"]}
        })
        mlflow.log_text(f"RF entrenado: MAE={rf['metrics']['mae']:.2f}, RMSE={rf['metrics']['rmse']:.2f}, R2={rf['metrics']['r2']:.4f}", "traces/02_train_random_forest.txt")

        # Paso 3: Simulación Monte Carlo
        mc = build_monte_carlo_simulation(records=records, scenarios=scenarios)
        traces.append({
            "name": "monte_carlo_simulation",
            "inputs": {"records_count": data_points, "scenarios": scenarios},
            "outputs": {"projection": mc["projection_next_month"], "p05": mc["percentiles"]["p05"], "p95": mc["percentiles"]["p95"]}
        })
        mlflow.log_text(f"MC simulado: {scenarios} escenarios | Proyección={mc['projection_next_month']:.2f} | P05={mc['percentiles']['p05']:.2f} | P95={mc['percentiles']['p95']:.2f}", "traces/03_monte_carlo_simulation.txt")

        # Paso 4: Análisis y Visualización
        analysis = get_analysis()
        history = get_last_36_months_visualization()
        traces.append({
            "name": "analysis_visualization",
            "inputs": {"analysis_type": "comprehensive"},
            "outputs": {"history_months": 36}
        })
        mlflow.log_text("Análisis e histórico de visualización completados", "traces/04_analysis_visualization.txt")

        # Paso 5: Comparación de modelos
        rf_forecast = float(rf["forecast"]["next_month_projection"])
        mc_projection = float(mc["projection_next_month"])
        gap = rf_forecast - mc_projection
        gap_pct = (gap / mc_projection * 100) if mc_projection else 0.0
        alignment = max(0.0, 100.0 - min(abs(gap_pct), 100.0))
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
        })
        mlflow.log_metrics({
            "rf_mae": rf["metrics"]["mae"],
            "rf_rmse": rf["metrics"]["rmse"],
            "rf_r2": rf["metrics"]["r2"],
            "mc_projection": mc_projection,
            "model_gap": gap,
            "model_gap_pct": gap_pct,
        })
        mlflow.log_dict({
            "analysis": analysis,
            "random_forest": {
                "metrics": rf["metrics"],
                "feature_importance": rf["feature_importance"],
                "forecast": rf["forecast"],
            },
            "monte_carlo": {
                "historical": mc["historical"],
                "projection_next_month": mc_projection,
                "percentiles": mc["percentiles"],
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

        recommendation = "Los modelos están alineados" if abs(gap_pct) < 3 else ("RF está por encima del escenario Monte Carlo" if gap > 0 else "Monte Carlo sugiere una TRM superior a RF")

        mlflow_run_info = {
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "run_id": run.info.run_id,
            "artifact_uri": run.info.artifact_uri,
        }

        return {
            "analysis": analysis,
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
            "mlflow": mlflow_run_info,
            "recommendation": recommendation,
        }