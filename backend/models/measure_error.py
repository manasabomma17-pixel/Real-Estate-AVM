import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error

model = joblib.load("backend/models/trained_model.pkl")
data = pd.read_csv("data/processed/bangalore_final_dataset.csv")

data["bath"] = data["bath"].fillna(0)
for col in ["dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]:
    data[col] = data[col].fillna(data[col].median())

data["price_per_sqft"] = data["price"] / data["total_sqft_clean"]
low = data["price_per_sqft"].quantile(0.01)
high = data["price_per_sqft"].quantile(0.99)
sl = data["total_sqft_clean"].quantile(0.01)
sh = data["total_sqft_clean"].quantile(0.99)
data = data[(data["price_per_sqft"] >= low) & (data["price_per_sqft"] <= high)]
data = data[(data["total_sqft_clean"] >= sl) & (data["total_sqft_clean"] <= sh)]

train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)

loc_avg = train_data.groupby("location")["price_per_sqft"].median()
overall = train_data["price_per_sqft"].median()
test_data["location_price"] = test_data["location"].map(loc_avg).fillna(overall)

features = ["bhk", "bath", "total_sqft_clean", "lat", "lon",
            "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km", "location_price"]

predictions = model.predict(test_data[features])
actual = test_data["price"]

mape = mean_absolute_percentage_error(actual, predictions) * 100
mae = mean_absolute_error(actual, predictions)

print("Average percentage error (MAPE):", round(mape, 1), "%")
print("Average error (MAE):", round(mae, 2), "Lakhs")

# save so the app can use the real number instead of a guess
pd.DataFrame([{"mape_percent": round(mape, 1), "mae_lakhs": round(mae, 2)}]).to_csv(
    "reports/model_error.csv", index=False
)
print("Saved to reports/model_error.csv")
