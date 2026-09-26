"""Trains the final XGBoost model served by the API and saves everything it needs at inference time.

Saves two artifacts:
- backend/models/trained_model.pkl: a dict bundle with the fitted model, the
  feature order it expects, a residual-based margin for confidence intervals,
  the model version, and the training date - so the API never has to guess
  feature order or hardcode the version string.
- data/processed/location_lookup.csv: per-location lat/lon/amenity
  distances/location_price, so the API can look up everything it needs from
  just a location name.
"""

from datetime import datetime, timezone

import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

from backend.config import config
from data_processing.prepare_model_data import (
    ALL_FEATURES,
    RANDOM_SEED,
    TARGET,
    add_location_price_feature,
    build_location_lookup,
    load_clean_data,
    trim_outliers,
)

MODEL_VERSION = "xgboost_v1"
CONFIDENCE_Z = 1.96  # ~95% interval, assuming roughly normal residuals


def main() -> None:
    data = load_clean_data()
    data = trim_outliers(data)

    train_data, test_data = train_test_split(data, test_size=0.2, random_state=RANDOM_SEED)
    train_data, test_data, location_price, overall_price = add_location_price_feature(train_data, test_data)

    x_train, y_train = train_data[ALL_FEATURES], train_data[TARGET]
    x_test, y_test = test_data[ALL_FEATURES], test_data[TARGET]

    model = XGBRegressor(n_estimators=100, random_state=RANDOM_SEED)
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    residuals = y_test.values - predictions
    residual_std = float(np.std(residuals))

    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)
    print("Final model RMSE:", round(rmse, 2))
    print("Final model R2:", round(r2, 4))
    print("Residual std (used for confidence interval width):", round(residual_std, 2))

    bundle = {
        "model": model,
        "features": ALL_FEATURES,
        "residual_std": residual_std,
        "confidence_z": CONFIDENCE_Z,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).date().isoformat(),
    }
    joblib.dump(bundle, config.MODEL_PATH)
    print("Saved model bundle to", config.MODEL_PATH)

    location_lookup = build_location_lookup(data, location_price, overall_price)
    location_lookup.to_csv(config.LOCATION_LOOKUP_PATH, index=False)
    print("Saved location lookup to", config.LOCATION_LOOKUP_PATH)


if __name__ == "__main__":
    main()
