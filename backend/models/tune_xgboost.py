"""
Tunes XGBoost and saves the model the API serves.

RandomizedSearchCV tries 25 random combinations of settings, scoring each one
with 3-fold cross-validation on the training rows only. The test rows are kept
aside until the end, so the final score is honest.

Saves:
- backend/models/trained_model.pkl      (only if tuning beat the default model)
- data/processed/location_lookup.csv    (what the API needs for each area)
- reports/best_params.csv               (the settings that won)

Run from the project folder:  python -m backend.models.tune_xgboost
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV
from xgboost import XGBRegressor

from data_processing.prepare_model_data import (
    ALL_FEATURES,
    RANDOM_SEED,
    TARGET,
    build_location_lookup,
    prepare_train_test,
)

data, train_data, test_data, location_price, overall_price = prepare_train_test()
print("Rows after removing outliers:", len(data))

x_train = train_data[ALL_FEATURES]
y_train = train_data[TARGET]
x_test = test_data[ALL_FEATURES]
y_test = test_data[TARGET]

baseline_predictions = test_data["location_price"] * test_data["total_sqft_clean"]
baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline_predictions))
print("\nBaseline RMSE:", round(baseline_rmse, 2))


def show_results(model, name):
    predictions = model.predict(x_test)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)
    improvement = (1 - (rmse / baseline_rmse)) * 100
    print(name, "-> RMSE:", round(rmse, 2),
          " MAE:", round(mae, 2),
          " R2:", round(r2, 4),
          " Improvement vs baseline:", round(improvement, 1), "%")
    return rmse


print("\n--- Before tuning ---")
default_model = XGBRegressor(n_estimators=100, random_state=RANDOM_SEED)
default_model.fit(x_train, y_train)
default_rmse = show_results(default_model, "XGBoost (default)")

settings_to_try = {
    "n_estimators": [100, 200, 300, 500, 800],
    "max_depth": [3, 4, 5, 6, 8, 10],
    "learning_rate": [0.01, 0.05, 0.1, 0.2],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.7, 0.8, 0.9, 1.0],
}

print("\n--- Tuning (this takes a few minutes) ---")

search = RandomizedSearchCV(
    XGBRegressor(random_state=RANDOM_SEED),
    param_distributions=settings_to_try,
    n_iter=25,
    cv=3,
    scoring="neg_root_mean_squared_error",
    random_state=RANDOM_SEED,
    n_jobs=-1,
    verbose=1,
)

search.fit(x_train, y_train)

print("\nBest settings found:")
for name, value in search.best_params_.items():
    print(" ", name, "=", value)

print("\n--- After tuning ---")
tuned_model = search.best_estimator_
tuned_rmse = show_results(tuned_model, "XGBoost (tuned)")

change = (1 - (tuned_rmse / default_rmse)) * 100
print("\nTuning improved RMSE by", round(change, 1), "% compared to the default model")

if tuned_rmse < default_rmse:
    joblib.dump(tuned_model, "backend/models/trained_model.pkl")
    pd.DataFrame([search.best_params_]).to_csv("reports/best_params.csv", index=False)
    print("Tuned model is better - saved to backend/models/trained_model.pkl")
else:
    print("Tuned model is NOT better - keeping the existing model")

# the API looks up each area's position, distances and price level here,
# built from the same rows and the same training medians as the model
lookup = build_location_lookup(data, location_price, overall_price)
lookup.to_csv("data/processed/location_lookup.csv", index=False)
print("Saved location lookup for", len(lookup), "areas")
