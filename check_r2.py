#!/usr/bin/env python
from app.models.data_loader import load_trm_data
from app.models.random_forest import build_random_forest_prediction

records = load_trm_data()
records_36m = [r for r in records if (records[-1]['date'] - r['date']).days <= 36*30]

print('=== RANDOM FOREST R² SCORES ===')
print()

rf_all = build_random_forest_prediction(records=records)
print('TODOS LOS DATOS:')
print(f'  Registros: {len(records)}')
print(f'  R²: {rf_all["metrics"]["r2"]:.6f}')
print(f'  MAE: ${rf_all["metrics"]["mae"]:.2f}')
print(f'  RMSE: ${rf_all["metrics"]["rmse"]:.2f}')
print()

rf_36m = build_random_forest_prediction(records=records_36m)
print('ÚLTIMOS 36 MESES:')
print(f'  Registros: {len(records_36m)}')
print(f'  R²: {rf_36m["metrics"]["r2"]:.6f}')
print(f'  MAE: ${rf_36m["metrics"]["mae"]:.2f}')
print(f'  RMSE: ${rf_36m["metrics"]["rmse"]:.2f}')
