"""Compares Random Forest and XGBoost, with and without location features, against the neighborhood $/sqft baseline."""

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from data_processing.prepare_model_data import (
    LOCATION_FEATURES,
    PROPERTY_FEATURES,
    RANDOM_SEED,
    TARGET,
    add_location_price_feature,
    load_clean_data,
    trim_outliers,
)

data = load_clean_data()
print("Total rows:", len(data))

data["balcony"] = data["balcony"].fillna(0)

data = trim_outliers(data)
print("Rows after removing outliers:", len(data))

train_data, test_data = train_test_split(data, test_size=0.2, random_state=RANDOM_SEED)
print("Train rows:", len(train_data))
print("Test rows:", len(test_data))

train_data, test_data, location_price, overall_price = add_location_price_feature(train_data, test_data)

baseline_predictions = test_data["location_price"] * test_data["total_sqft_clean"]
baseline_rmse = np.sqrt(mean_squared_error(test_data[TARGET], baseline_predictions))
print("\nBaseline RMSE:", round(baseline_rmse, 2))

y_train = train_data[TARGET]
y_test = test_data[TARGET]

property_only_features = PROPERTY_FEATURES + ["balcony"]
property_and_location_features = property_only_features + LOCATION_FEATURES


def train_and_test_model(model, features, model_name):
    x_train = train_data[features]
    x_test = test_data[features]

    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    improvement = (1 - (rmse / baseline_rmse)) * 100

    print(model_name, "-> RMSE:", round(rmse, 2),
          " MAE:", round(mae, 2),
          " R2:", round(r2, 4),
          " Improvement vs baseline:", round(improvement, 1), "%")


print("\n--- Property Features Only ---")
train_and_test_model(RandomForestRegressor(n_estimators=100, random_state=RANDOM_SEED), property_only_features, "Random Forest")
train_and_test_model(XGBRegressor(n_estimators=100, random_state=RANDOM_SEED), property_only_features, "XGBoost")

print("\n--- Property + Location Features ---")
train_and_test_model(RandomForestRegressor(n_estimators=100, random_state=RANDOM_SEED), property_and_location_features, "Random Forest")
train_and_test_model(XGBRegressor(n_estimators=100, random_state=RANDOM_SEED), property_and_location_features, "XGBoost")
