"""
Measures how far off the saved model is on the test rows it never saw.

The app uses these numbers for the price range it shows, so the range is
based on measured error instead of a guess.

Run from the project folder:  python -m backend.models.measure_error
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score

from data_processing.prepare_model_data import ALL_FEATURES, TARGET, prepare_train_test

model = joblib.load("backend/models/trained_model.pkl")
data, train_data, test_data, location_price, overall_price = prepare_train_test()

predictions = model.predict(test_data[ALL_FEATURES])
actual = test_data[TARGET]

mape = mean_absolute_percentage_error(actual, predictions) * 100
mae = mean_absolute_error(actual, predictions)
rmse = np.sqrt(mean_squared_error(actual, predictions))
r2 = r2_score(actual, predictions)

# a common way to judge valuation models: how often is the estimate
# within 10% or 20% of the real price?
percent_off = np.abs(predictions - actual) / actual * 100
within_10 = (percent_off <= 10).mean() * 100
within_20 = (percent_off <= 20).mean() * 100

print("Average percentage error (MAPE):", round(mape, 1), "%")
print("Average error (MAE):", round(mae, 2), "Lakhs")
print("RMSE:", round(rmse, 2), "Lakhs")
print("R2:", round(r2, 4))
print("Estimates within 10% of the real price:", round(within_10, 1), "%")
print("Estimates within 20% of the real price:", round(within_20, 1), "%")

pd.DataFrame([{
    "mape_percent": round(mape, 1),
    "mae_lakhs": round(mae, 2),
    "rmse_lakhs": round(rmse, 2),
    "r2": round(r2, 4),
    "within_10_percent": round(within_10, 1),
    "within_20_percent": round(within_20, 1),
    "test_rows": len(test_data),
}]).to_csv("reports/model_error.csv", index=False)
print("Saved to reports/model_error.csv")
