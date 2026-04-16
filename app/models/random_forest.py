from __future__ import annotations

import calendar
from datetime import timedelta

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .data_loader import load_trm_data


def _as_features(dt):
    return [dt.day, dt.month, dt.year]


def _next_month_dates(latest_date):
    first_next = (latest_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = calendar.monthrange(first_next.year, first_next.month)[1]
    return [first_next.replace(day=day) for day in range(1, last_day + 1)]


def build_random_forest_prediction(records=None, test_ratio=0.2, random_state=42):
    if records is None:
        records = load_trm_data()

    ordered = sorted(records, key=lambda item: item["date"])
    if len(ordered) < 3:
        raise ValueError("Se necesitan al menos 3 registros para entrenar Random Forest")

    dates = [item["date"].date() for item in ordered]
    values = np.array([float(item["trm"]) for item in ordered], dtype=float)
    features = np.array([_as_features(dt) for dt in dates], dtype=float)

    split_index = max(1, int(len(features) * (1 - test_ratio)))
    if split_index >= len(features):
        split_index = len(features) - 1

    x_train = features[:split_index]
    y_train = values[:split_index]
    x_test = features[split_index:]
    y_test = values[split_index:]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=random_state,
        n_jobs=-1,
        min_samples_leaf=1,
    )
    model.fit(x_train, y_train)

    test_predictions = model.predict(x_test) if len(x_test) else np.array([])
    if len(test_predictions):
        mae = float(mean_absolute_error(y_test, test_predictions))
        rmse = float(mean_squared_error(y_test, test_predictions) ** 0.5)
        r2 = float(r2_score(y_test, test_predictions)) if len(y_test) > 1 else 0.0
    else:
        mae = rmse = r2 = 0.0

    future_dates = _next_month_dates(dates[-1])
    future_features = np.array([_as_features(dt) for dt in future_dates], dtype=float)
    future_predictions = model.predict(future_features)
    next_month_projection = float(np.mean(future_predictions))

    next_day_date = dates[-1] + timedelta(days=1)
    next_day_feature = np.array([_as_features(next_day_date)], dtype=float)
    next_day_projection = float(model.predict(next_day_feature)[0])

    feature_importance = {
        "day": float(model.feature_importances_[0]),
        "month": float(model.feature_importances_[1]),
        "year": float(model.feature_importances_[2]),
    }

    importance_total = sum(feature_importance.values()) or 1.0
    feature_importance = {
        key: float(value / importance_total)
        for key, value in feature_importance.items()
    }

    test_series = [
        {
            "date": ordered[split_index + idx]["date"].strftime("%Y-%m-%d"),
            "actual": float(actual),
            "predicted": float(predicted),
            "error": float(actual - predicted),
        }
        for idx, (actual, predicted) in enumerate(zip(y_test, test_predictions))
    ]

    future_series = [
        {
            "date": dt.strftime("%Y-%m-%d"),
            "prediction": float(prediction),
        }
        for dt, prediction in zip(future_dates, future_predictions)
    ]

    return {
        "model_name": "Random Forest Regressor",
        "feature_names": ["day", "month", "year"],
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "train_size": int(len(x_train)),
            "test_size": int(len(x_test)),
        },
        "feature_importance": feature_importance,
        "test_series": test_series,
        "future_series": future_series,
        "forecast": {
            "next_day_projection": next_day_projection,
            "next_day_date": next_day_date.strftime("%Y-%m-%d"),
            "next_month_projection": next_month_projection,
            "next_month_start": future_series[0]["date"] if future_series else None,
            "next_month_end": future_series[-1]["date"] if future_series else None,
            "daily_mean": float(np.mean(future_predictions)) if len(future_predictions) else next_month_projection,
            "daily_min": float(np.min(future_predictions)) if len(future_predictions) else next_month_projection,
            "daily_max": float(np.max(future_predictions)) if len(future_predictions) else next_month_projection,
        },
    }


def predict_trm():
    return build_random_forest_prediction()["forecast"]["next_month_projection"]