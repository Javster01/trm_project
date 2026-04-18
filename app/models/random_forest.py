from __future__ import annotations

import calendar
from datetime import timedelta

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .data_loader import load_trm_data


def _build_lagged_features(values, lags=[1, 7, 30]):
    """
    Construye features basadas en valores anteriores (lags).
    
    Ejemplo: Si values = [100, 101, 102, 105, 103]
    Y lags = [1, 2]
    Retorna: [[NaN, NaN], [NaN, 100], [101, 100], [102, 101], [105, 102]]
    
    Estos features capturan "cuál era el valor hace N días"
    """
    n = len(values)
    max_lag = max(lags) if lags else 1
    
    features = []
    for i in range(n):
        row = []
        for lag in lags:
            if i >= lag:
                row.append(float(values[i - lag]))
            else:
                row.append(np.nan)
        features.append(row)
    
    return np.array(features, dtype=float)


def _build_volatility_features(values, window=30):
    """
    Calcula volatilidad (desviación estándar) en una ventana móvil.
    
    Ejemplo: Calcula cuánto varía el TRM en los últimos 30 días.
    """
    n = len(values)
    volatility = []
    
    for i in range(n):
        start = max(0, i - window + 1)
        window_values = values[start:i+1]
        vol = float(np.std(window_values)) if len(window_values) > 1 else 0.0
        volatility.append(vol)
    
    return np.array(volatility, dtype=float).reshape(-1, 1)


def _build_trend_features(values, window=30):
    """
    Calcula la tendencia: cambio promedio en una ventana móvil.
    """
    n = len(values)
    trend = []
    
    for i in range(n):
        if i >= window:
            change = (values[i] - values[i - window]) / window
        else:
            change = 0.0
        trend.append(float(change))
    
    return np.array(trend, dtype=float).reshape(-1, 1)


def _build_moving_average(values, window=7):
    """
    Promedio móvil: promedio del TRM en los últimos N días.
    """
    n = len(values)
    ma = []
    
    for i in range(n):
        start = max(0, i - window + 1)
        avg = float(np.mean(values[start:i+1]))
        ma.append(avg)
    
    return np.array(ma, dtype=float).reshape(-1, 1)


def _as_features_enhanced(values_array, index):
    """
    Combina todos los features en un solo vector.
    Retorna los features para la posición 'index'.
    """
    return values_array[index]


def _build_all_features(values):
    """
    Construye todos los features mejorados a partir de los valores históricos.
    """
    # Features de lags (valores anteriores)
    lag_features = _build_lagged_features(values, lags=[1, 7, 30])
    
    # Features de volatilidad
    vol_features = _build_volatility_features(values, window=30)
    
    # Features de tendencia
    trend_features = _build_trend_features(values, window=30)
    
    # Features de promedio móvil
    ma_features = _build_moving_average(values, window=7)
    
    # Combina todos
    all_features = np.hstack([
        lag_features,
        vol_features,
        trend_features,
        ma_features,
    ])
    
    return all_features


def _next_month_dates(latest_date):
    first_next = (latest_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = calendar.monthrange(first_next.year, first_next.month)[1]
    return [first_next.replace(day=day) for day in range(1, last_day + 1)]


def build_random_forest_prediction(records=None, test_ratio=0.2, random_state=42):
    if records is None:
        records = load_trm_data()

    ordered = sorted(records, key=lambda item: item["date"])
    if len(ordered) < 50:
        raise ValueError("Se necesitan al menos 50 registros para entrenar Random Forest con features lag")

    dates = [item["date"].date() for item in ordered]
    values = np.array([float(item["trm"]) for item in ordered], dtype=float)
    
    # Construir features mejorados
    features = _build_all_features(values)

    
    # Filtrar filas con valores NaN (primeras filas no tienen lags completos)
    valid_mask = ~np.isnan(features).any(axis=1)
    features_clean = features[valid_mask]
    values_clean = values[valid_mask]
    dates_clean = [d for i, d in enumerate(dates) if valid_mask[i]]

    # Split entrenamiento/prueba
    split_index = max(1, int(len(features_clean) * (1 - test_ratio)))
    if split_index >= len(features_clean):
        split_index = len(features_clean) - 1

    x_train = features_clean[:split_index]
    y_train = values_clean[:split_index]
    x_test = features_clean[split_index:]
    y_test = values_clean[split_index:]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=random_state,
        n_jobs=-1,
        min_samples_leaf=1,
        max_depth=15,
    )
    model.fit(x_train, y_train)

    test_predictions = model.predict(x_test) if len(x_test) else np.array([])
    if len(test_predictions):
        mae = float(mean_absolute_error(y_test, test_predictions))
        rmse = float(mean_squared_error(y_test, test_predictions) ** 0.5)
        r2 = float(r2_score(y_test, test_predictions)) if len(y_test) > 1 else 0.0
    else:
        mae = rmse = r2 = 0.0

    # Para futuras predicciones, usar bootstrap con los últimos valores
    last_values = values_clean[-50:].tolist() if len(values_clean) >= 50 else values_clean.tolist()
    
    future_dates = _next_month_dates(dates_clean[-1])
    future_predictions = []
    
    # Usar simulación similar a Monte Carlo para las predicciones futuras
    simulated_paths = []
    for _ in range(100):  # 100 simulaciones
        current_path = last_values.copy()
        
        # Calcular cambios históricos
        if len(current_path) > 1:
            changes = np.diff(current_path)
            mean_change = np.mean(changes)
            std_change = np.std(changes) if np.std(changes) > 0 else 0.1
        else:
            mean_change = 0
            std_change = 1
        
        # Generar predicciones para el próximo mes
        path_predictions = []
        for _ in range(len(future_dates)):
            # Generar cambio aleatorio siguiendo el patrón histórico
            random_change = np.random.normal(mean_change, std_change)
            next_val = current_path[-1] + random_change
            path_predictions.append(next_val)
            current_path.append(next_val)
        
        simulated_paths.append(path_predictions)
    
    # Promediar las 100 simulaciones
    simulated_paths = np.array(simulated_paths)
    future_predictions = np.mean(simulated_paths, axis=0)
    future_predictions = np.array(future_predictions)
    next_month_projection = float(np.mean(future_predictions))

    next_day_date = dates_clean[-1] + timedelta(days=1)
    next_day_projection = float(future_predictions[0]) if len(future_predictions) > 0 else values_clean[-1]

    # Feature importance (solo con los features que realmente usa)
    feature_names = ["lag_1", "lag_7", "lag_30", "volatility_30", "trend_30", "ma_7"]
    feature_importance = {}
    for i, name in enumerate(feature_names):
        if i < len(model.feature_importances_):
            feature_importance[name] = float(model.feature_importances_[i])

    importance_total = sum(feature_importance.values()) or 1.0
    feature_importance = {
        key: float(value / importance_total)
        for key, value in feature_importance.items()
    }

    test_series = [
        {
            "date": dates_clean[split_index + idx].strftime("%Y-%m-%d"),
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
        "model_name": "Random Forest Regressor (Enhanced Features)",
        "feature_names": feature_names,
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