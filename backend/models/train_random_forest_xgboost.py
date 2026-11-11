"""
The main experiment of the project: does location help predict price?

Random Forest and XGBoost are each trained three times on the same rows:
  1. property_only     - size, bedrooms, bathrooms
  2. plus_amenities    - + map position and distance to school, hospital, transit
  3. plus_area_price   - + the area's median price per sqft (the full model)

Every result is compared with a simple baseline: the area's median price per
sqft multiplied by the property's size. Results are saved to
reports/model_comparison.csv so the app and the report can show them.

Run from the project folder:  python -m backend.models.train_random_forest_xgboost
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from data_processing.prepare_model_data import (
    ALL_FEATURES,
    PROPERTY_FEATURES,
    RANDOM_SEED,
    TARGET,
    prepare_train_test,
)

data, train_data, test_data, location_price, overall_price = prepare_train_test()
print("Rows after cleaning:", len(data))
print("Train rows:", len(train_data), " Test rows:", len(test_data))

y_train = train_data[TARGET]
y_test = test_data[TARGET]


def score(predictions, model_name, condition, baseline_rmse=None):
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    mae = float(mean_absolute_error(y_test, predictions))
    mape = float(mean_absolute_percentage_error(y_test, predictions) * 100)
    r2 = float(r2_score(y_test, predictions))

    if baseline_rmse is None:
        improvement = 0.0
    else:
        improvement = (1 - rmse / baseline_rmse) * 100

    print(f"  {model_name:14s} {condition:16s} RMSE={rmse:6.2f}  MAE={mae:6.2f}  "
          f"MAPE={mape:5.1f}%  R2={r2:.3f}  vs baseline {improvement:+.1f}%")

    return {
        "model": model_name,
        "condition": condition,
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "mape_percent": round(mape, 1),
        "r2": round(r2, 4),
        "rmse_improvement_vs_baseline": round(improvement, 1),
    }


# the baseline needs no training: area rate x size
print("\n--- Baseline ---")
baseline_predictions = test_data["location_price"] * test_data["total_sqft_clean"]
baseline = score(baseline_predictions, "Baseline", "area_rate_x_size")
baseline_rmse = baseline["rmse"]

conditions = {
    "property_only": PROPERTY_FEATURES,
    "plus_amenities": PROPERTY_FEATURES + ["lat", "lon", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"],
    "plus_area_price": ALL_FEATURES,
}

results = [baseline]

for condition, features in conditions.items():
    print("\n---", condition, "(" + str(len(features)) + " features) ---")

    models = {
        "Random Forest": RandomForestRegressor(n_estimators=100, random_state=RANDOM_SEED, n_jobs=-1),
        "XGBoost": XGBRegressor(n_estimators=100, random_state=RANDOM_SEED),
    }

    for model_name, model in models.items():
        model.fit(train_data[features], y_train)
        predictions = model.predict(test_data[features])
        results.append(score(predictions, model_name, condition, baseline_rmse))

results_df = pd.DataFrame(results)
results_df.to_csv("reports/model_comparison.csv", index=False)
print("\nSaved to reports/model_comparison.csv")

# the headline answer to the research question
xgb = results_df[results_df["model"] == "XGBoost"].set_index("condition")
before = xgb.loc["property_only", "rmse"]
after = xgb.loc["plus_area_price", "rmse"]
print("\nAdding location cuts XGBoost RMSE from", before, "to", after,
      "Lakhs, a", round((1 - after / before) * 100, 1), "% improvement")
