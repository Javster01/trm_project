from flask import Blueprint, render_template, jsonify
from models.analysis import get_analysis, get_eda
from models.random_forest import predict_trm
from models.monte_carlo import simulate_trm
from models.llm_integration import get_recommendation
from models.data_loader import load_trm_data
from models.visualization import get_last_36_months_visualization

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
    eda_summary = _eda_summary_for_view(eda)

    return render_template(
        "pages/eda.html",
        current_page="eda",
        initial_count=len(records),
        initial_eda=eda,
        initial_eda_summary=eda_summary,
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
    analysis = get_analysis()
    prediction = predict_trm()
    simulation = simulate_trm()
    recommendation = get_recommendation(prediction)

    return jsonify({
        "analysis": analysis,
        "prediction": prediction,
        "simulation": simulation,
        "recommendation": recommendation
    })


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