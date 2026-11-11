"""
Explains the saved model with SHAP: which features move the price most,
and how the effect splits between the property itself and its location.

Run from the project folder:  python -m backend.models.explain_model
"""

import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_processing.prepare_model_data import ALL_FEATURES, PROPERTY_FEATURES, LOCATION_FEATURES, prepare_train_test

# load the trained model and the same cleaned rows it was trained and tested on.
# location_price comes from the training medians, exactly what the model saw
model = joblib.load("backend/models/trained_model.pkl")
data, train_data, test_data, location_price, overall_price = prepare_train_test()
data = pd.concat([train_data, test_data])

features = ALL_FEATURES

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
property_features = PROPERTY_FEATURES
location_features = LOCATION_FEATURES

property_effect = importance[importance["feature"].isin(property_features)]["average_effect_lakhs"].sum()
location_effect = importance[importance["feature"].isin(location_features)]["average_effect_lakhs"].sum()
total = property_effect + location_effect

print("\n--- Property vs Location ---")
print("Property features:", round(property_effect, 2), "Lakhs  (", round(property_effect / total * 100, 1), "% )")
print("Location features:", round(location_effect, 2), "Lakhs  (", round(location_effect / total * 100, 1), "% )")

pd.DataFrame([
    {"group": "property", "effect_lakhs": round(property_effect, 2), "share_percent": round(property_effect / total * 100, 1)},
    {"group": "location", "effect_lakhs": round(location_effect, 2), "share_percent": round(location_effect / total * 100, 1)},
]).to_csv("reports/shap_group_share.csv", index=False)

# bar chart for the report
plt.figure(figsize=(8, 5))
plt.barh(importance["feature"][::-1], importance["average_effect_lakhs"][::-1])
plt.xlabel("Average effect on price (Lakhs)")
plt.title("What drives property prices in Bangalore")
plt.tight_layout()
plt.savefig("reports/shap_feature_importance.png", dpi=150)
print("\nSaved chart to reports/shap_feature_importance.png")

# the summary plot shows every property as a dot: how far each feature pushed
# its price (left = down, right = up), coloured by whether the feature value
# was high (red) or low (blue)
plt.figure()
shap.summary_plot(shap_values, x, show=False)
plt.tight_layout()
plt.savefig("reports/shap_summary.png", dpi=150)
print("Saved chart to reports/shap_summary.png")
