import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

data = pd.read_csv("data/processed/bangalore_final_dataset.csv")
print("Total rows:", len(data))

data["bath"] = data["bath"].fillna(0)
data["dist_to_school_km"] = data["dist_to_school_km"].fillna(data["dist_to_school_km"].median())
data["dist_to_hospital_km"] = data["dist_to_hospital_km"].fillna(data["dist_to_hospital_km"].median())
data["dist_to_transit_km"] = data["dist_to_transit_km"].fillna(data["dist_to_transit_km"].median())

data["price_per_sqft"] = data["price"] / data["total_sqft_clean"]
low_limit = data["price_per_sqft"].quantile(0.01)
high_limit = data["price_per_sqft"].quantile(0.99)
sqft_low = data["total_sqft_clean"].quantile(0.01)
sqft_high = data["total_sqft_clean"].quantile(0.99)
data = data[(data["price_per_sqft"] >= low_limit) & (data["price_per_sqft"] <= high_limit)]
data = data[(data["total_sqft_clean"] >= sqft_low) & (data["total_sqft_clean"] <= sqft_high)]
print("Rows after removing outliers:", len(data))

train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)

location_avg_price = train_data.groupby("location")["price_per_sqft"].median()
overall_avg_price = train_data["price_per_sqft"].median()

train_data["location_price"] = train_data["location"].map(location_avg_price).fillna(overall_avg_price)
test_data["location_price"] = test_data["location"].map(location_avg_price).fillna(overall_avg_price)

features = [
    "bhk", "bath", "total_sqft_clean",
    "lat", "lon",
    "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km",
    "location_price"
]

x_train = train_data[features]
y_train = train_data["price"]
x_test = test_data[features]
y_test = test_data["price"]

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
default_model = XGBRegressor(n_estimators=100, random_state=42)
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
    XGBRegressor(random_state=42),
    param_distributions=settings_to_try,
    n_iter=25,
    cv=3,
    scoring="neg_root_mean_squared_error",
    random_state=42,
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
    print("Tuned model is better - saved to backend/models/trained_model.pkl")
else:
    print("Tuned model is NOT better - keeping the existing model")
