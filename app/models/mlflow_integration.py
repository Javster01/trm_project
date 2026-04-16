from __future__ import annotations

import json
import os
from datetime import datetime

import mlflow
import mlflow.sklearn


def _tracking_uri():
    host = os.environ.get("MLFLOW_TRACKING_HOST", "127.0.0.1")
    port = os.environ.get("MLFLOW_TRACKING_PORT", "5001")
    return f"http://{host}:{port}"


def _experiment_name():
    return os.environ.get("MLFLOW_EXPERIMENT_NAME", "trm_prediction_dashboard")


def log_trace(step_name: str, inputs: dict = None, outputs: dict = None):
    """Registra un paso (trace) como texto en MLflow."""
    trace_data = {
        "step": step_name,
        "timestamp": datetime.now().isoformat(),
        "inputs": inputs or {},
        "outputs": outputs or {},
    }
    mlflow.log_text(json.dumps(trace_data, indent=2), f"traces/{step_name}.json")


def log_prediction_run(model=None, params: dict = None, metrics: dict = None, summary: dict = None, traces: list = None) -> dict:
    tracking_uri = _tracking_uri()
    experiment_name = _experiment_name()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name="random_forest_vs_monte_carlo") as run:
        if params:
            mlflow.log_params(params)
        if metrics:
            mlflow.log_metrics(metrics)
        if summary:
            mlflow.log_dict(summary, "prediction_summary.json")
        if traces:
            for trace in traces:
                log_trace(trace.get("name", "unknown"), trace.get("inputs"), trace.get("outputs"))
        if model is not None:
            mlflow.sklearn.log_model(model, "random_forest_model")

        return {
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "run_id": run.info.run_id,
            "artifact_uri": run.info.artifact_uri,
        }