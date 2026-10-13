import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# load the trained model and the data it was trained on
model = joblib.load("backend/models/trained_model.pkl")
data = pd.read_csv("data/processed/bangalore_final_dataset.csv")

data["bath"] = data["bath"].fillna(0)
data["dist_to_school_km"] = data["dist_to_school_km"].fillna(data["dist_to_school_km"].median())
data["dist_to_hospital_km"] = data["dist_to_hospital_km"].fillna(data["dist_to_hospital_km"].median())
data["dist_to_transit_km"] = data["dist_to_transit_km"].fillna(data["dist_to_transit_km"].median())

data["price_per_sqft"] = data["price"] / data["total_sqft_clean"]
low = data["price_per_sqft"].quantile(0.01)
high = data["price_per_sqft"].quantile(0.99)
sqft_low = data["total_sqft_clean"].quantile(0.01)
sqft_high = data["total_sqft_clean"].quantile(0.99)
data = data[(data["price_per_sqft"] >= low) & (data["price_per_sqft"] <= high)]
data = data[(data["total_sqft_clean"] >= sqft_low) & (data["total_sqft_clean"] <= sqft_high)]

location_avg_price = data.groupby("location")["price_per_sqft"].median()
overall_avg_price = data["price_per_sqft"].median()
data["location_price"] = data["location"].map(location_avg_price).fillna(overall_avg_price)

features = [
    "bhk", "bath", "total_sqft_clean",
    "lat", "lon",
    "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km",
    "location_price"
]

x = data[features]

print("Calculating SHAP values for", len(x), "properties...")

# TreeExplainer is the fast version of SHAP made for tree models like XGBoost
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(x)

# average effect of each feature, in Lakhs
# abs() because we want size of effect, not direction
importance = pd.DataFrame({
    "feature": features,
    "average_effect_lakhs": np.abs(shap_values).mean(axis=0)
}).sort_values("average_effect_lakhs", ascending=False)

print("\n--- Which features drive the price the most? ---")
for i, row in importance.iterrows():
    print(row["feature"], "->", round(row["average_effect_lakhs"], 2), "Lakhs average effect")

importance.to_csv("reports/shap_feature_importance.csv", index=False)
print("\nSaved to reports/shap_feature_importance.csv")

# group features into property vs location, which is our research question
property_features = ["bhk", "bath", "total_sqft_clean"]
location_features = ["lat", "lon", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km", "location_price"]

property_effect = importance[importance["feature"].isin(property_features)]["average_effect_lakhs"].sum()
location_effect = importance[importance["feature"].isin(location_features)]["average_effect_lakhs"].sum()
total = property_effect + location_effect

print("\n--- Property vs Location ---")
print("Property features:", round(property_effect, 2), "Lakhs  (", round(property_effect / total * 100, 1), "% )")
print("Location features:", round(location_effect, 2), "Lakhs  (", round(location_effect / total * 100, 1), "% )")

# bar chart for the report
plt.figure(figsize=(8, 5))
plt.barh(importance["feature"][::-1], importance["average_effect_lakhs"][::-1])
plt.xlabel("Average effect on price (Lakhs)")
plt.title("What drives property prices in Bangalore")
plt.tight_layout()
plt.savefig("reports/shap_feature_importance.png", dpi=150)
print("\nSaved chart to reports/shap_feature_importance.png")
