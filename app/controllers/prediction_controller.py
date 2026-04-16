from flask import Blueprint, render_template, jsonify, request
from ..models.analysis import get_analysis, get_eda, get_eda_last_36_months
from ..models.data_loader import load_trm_data
from ..models.visualization import get_last_36_months_visualization
from ..models.prediction_service import build_prediction_dashboard
from ..models.llm_integration import (
    get_available_models,
    chat_with_llm,
    get_investment_recommendation,
)

prediction_bp = Blueprint('prediction', __name__)


def _format_trm_display(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"${formatted}"


def _eda_summary_for_view(eda: dict) -> dict:
    d = eda.get("descriptive", {})
    t = eda.get("trend", {})
    o = eda.get("outliers", {})
    v = eda.get("volatility", {})
    l = eda.get("latest", {})

    def money(x):
        if x is None:
            return "-"
        return _format_trm_display(float(x))

    return {
        "meta": eda.get("meta", {}),
        "latest": {
            "date": l.get("date"),
            "value": money(l.get("value")),
            "prev_date": l.get("prev_date"),
            "prev_value": money(l.get("prev_value")),
            "delta": money(l.get("delta")),
        },
        "descriptive": {
            "mean": money(d.get("mean")),
            "median": money(d.get("median")),
            "std": money(d.get("std")),
            "min": money(d.get("min")),
            "max": money(d.get("max")),
            "q1": money(d.get("q1")),
            "q3": money(d.get("q3")),
            "p10": money(d.get("p10")),
            "p90": money(d.get("p90")),
            "cv_pct": f"{float(d.get('cv', 0.0)):.2f}%",
        },
        "outliers": {
            "count": int(o.get("count", 0)),
            "ratio_pct": f"{float(o.get('ratio_pct', 0.0)):.2f}%",
            "lower_bound": money(o.get("lower_bound")),
            "upper_bound": money(o.get("upper_bound")),
        },
        "trend": {
            "direction": t.get("direction"),
            "absolute_change": money(t.get("absolute_change")),
            "percent_change": f"{float(t.get('percent_change', 0.0)):.2f}%",
            "slope_per_step": f"{float(t.get('slope_per_step', 0.0)):.6f}",
        },
        "volatility": {
            "avg_abs_daily_change": money(v.get("avg_abs_daily_change")),
            "max_up_day": money(v.get("max_up_day")),
            "max_down_day": money(v.get("max_down_day")),
        },
        "monthly_summary": (eda.get("monthly_summary") or [])[-6:],
        "yearly_summary": eda.get("yearly_summary") or [],
    }


@prediction_bp.route("/")
def home_page():
    records = load_trm_data()
    eda = get_eda()
    latest = records[-1] if records else None

    return render_template(
        "pages/home.html",
        current_page="home",
        total_count=len(records),
        latest_date=latest["date"].strftime("%Y-%m-%d") if latest else "-",
        latest_value=_format_trm_display(latest["trm"]) if latest else "-",
        trend_direction=(eda.get("trend") or {}).get("direction", "-"),
    )


@prediction_bp.route("/prediccion")
def prediction_page():
    analysis = get_analysis()

    return render_template(
        "pages/prediction.html",
        current_page="prediction",
        initial_analysis=analysis,
    )


@prediction_bp.route("/datos")
def data_page():
    records = load_trm_data()
    preview = list(reversed(records[-200:]))
    initial_rows = [
        {
            "date": item["date"].strftime("%Y-%m-%d"),
            "trm": round(item["trm"], 4),
            "trm_display": _format_trm_display(item["trm"]),
        }
        for item in preview
    ]

    return render_template(
        "pages/data.html",
        current_page="data",
        initial_rows=initial_rows,
        initial_count=len(records),
    )


@prediction_bp.route("/analisis-eda")
def eda_page():
    records = load_trm_data()
    eda = get_eda()
    eda_36m = get_eda_last_36_months()
    eda_summary = _eda_summary_for_view(eda)
    eda_36m_summary = _eda_summary_for_view(eda_36m)

    return render_template(
        "pages/eda.html",
        current_page="eda",
        initial_count=len(records),
        initial_eda=eda,
        initial_eda_summary=eda_summary,
        initial_eda_36m=eda_36m,
        initial_eda_36m_summary=eda_36m_summary,
    )


@prediction_bp.route("/visualizaciones")
def visualizations_page():
    visual = get_last_36_months_visualization()

    return render_template(
        "pages/visualizations.html",
        current_page="visualizations",
        visual=visual,
        latest_avg_display=_format_trm_display(visual["latest_avg"]) if visual.get("latest_avg") is not None else "-",
    )

@prediction_bp.route("/predict")
def predict():
    return jsonify(build_prediction_dashboard())


@prediction_bp.route("/data")
def data():
    records = load_trm_data()
    payload = [
        {
            "date": item["date"].strftime("%Y-%m-%d"),
            "trm": round(item["trm"], 4),
        }
        for item in records
    ]

    return jsonify({
        "count": len(payload),
        "data": payload,
    })


@prediction_bp.route("/eda")
def eda():
    return jsonify(get_eda())


# ============ Endpoints para LLM Chat ============

@prediction_bp.route("/api/llm/models", methods=["GET"])
def get_llm_models():
    """Retorna lista de modelos de LLM disponibles en OpenRouter."""
    models = get_available_models()
    return jsonify({
        "success": True,
        "models": models,
        "count": len(models),
    })


@prediction_bp.route("/api/llm/chat", methods=["POST"])
def llm_chat():
    """
    Endpoint para chat con LLM.
    
    Recibe:
    {
        "message": "string",
        "model": "model_id",
        "use_random_forest_prediction": true/false (opcional, default true)
    }
    """
    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        model_id = data.get("model", "arcee-ai/trinity-large-preview:free")
        use_rf = data.get("use_random_forest_prediction", True)

        if not message:
            return jsonify({
                "success": False,
                "error": "El mensaje no puede estar vacío",
            }), 400

        # Obtener datos para usar en la predicción
        records = load_trm_data()
        latest_record = records[-1] if records else None
        current_trm = float(latest_record["trm"]) if latest_record else 4000
        
        # Obtener las predicciones actuales con mejor manejo de errores
        predicted_trm_rf = current_trm
        predicted_trm_mc = current_trm
        rf_daily_forecast = []
        mc_daily_forecast = []
        
        try:
            dashboard = build_prediction_dashboard()
            if isinstance(dashboard, dict):
                # Usar comparación del scope principal
                comparison = dashboard.get("comparison", {})
                predicted_trm_rf = float(comparison.get("rf_forecast", current_trm))
                predicted_trm_mc = float(comparison.get("mc_projection", current_trm))
                
                # Obtener predicciones diarias
                scopes = dashboard.get("scopes", {})
                all_data_scope = scopes.get("all_data", {})
                
                # Random Forest - predicciones diarias
                rf_data = all_data_scope.get("random_forest", {})
                rf_forecast_data = rf_data.get("forecast", {})
                rf_daily_forecast = rf_forecast_data.get("future_series", [])
                
                # Monte Carlo - proyecciones diarias (scenarios)
                mc_data = all_data_scope.get("monte_carlo", {})
                mc_scenarios = mc_data.get("scenarios", [])
                # Para MC, usamos los escenarios como referencia de volatilidad
                if mc_scenarios:
                    days_in_month = len(mc_scenarios)
                    # Crear un pronóstico sintético usando percentiles
                    mc_percentiles = {
                        "p05": mc_data.get("percentiles", {}).get("p05", current_trm),
                        "p50": mc_data.get("percentiles", {}).get("p50", current_trm),
                        "p95": mc_data.get("percentiles", {}).get("p95", current_trm),
                    }
                    mc_daily_forecast = {
                        "type": "probabilistic",
                        "percentiles": mc_percentiles,
                        "day_count": days_in_month,
                    }
                
        except Exception as e:
            # Si falla la predicción, usar valores actuales
            print(f"Warning: No se pudieron obtener predicciones: {str(e)}")
            predicted_trm_rf = current_trm
            predicted_trm_mc = current_trm

        # Llamar al LLM con contexto de predicciones completo
        result = chat_with_llm(
            model_id=model_id,
            user_message=message,
            current_trm=current_trm,
            predicted_trm_rf=predicted_trm_rf,
            predicted_trm_mc=predicted_trm_mc,
            rf_daily_forecast=rf_daily_forecast,
            mc_daily_forecast=mc_daily_forecast,
        )

        return jsonify(result)

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": f"Error de configuración: {str(e)}",
        }), 500
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": f"Error en el servidor: {str(e)}",
            "trace": error_trace,
        }), 500